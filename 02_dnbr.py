"""Paso 2. Área quemada con dNBR de Sentinel-2 L2A (Microsoft Planetary Computer).

Decisiones de método:
- Solo se lee la zona del incendio (AOI del paso 1), a 20 m (resolución de B12).
- Imagen "antes": la de menos nubes en la AOI en los 75 días previos al primer foco.
- Imagen "después": la de menos nubes en la AOI desde el primer foco hasta hoy.
  Se pueden forzar las fechas:  python 02_dnbr.py --pre 2026-09-20 --post 2026-10-18
- NBR = (B08 - B12) / (B08 + B12); dNBR = NBR antes - NBR después.
- Se corrige el desplazamiento de -1000 de las imágenes con baseline >= 04.00.
- Se enmascaran con la capa SCL: sin dato, saturado, sombra de nube, nubes, cirros y agua.
- Quemado = dNBR >= 0,27 (clases USGS de severidad); se reporta también la sensibilidad a 0,10 y 0,44.
"""
import argparse
import json
from datetime import date, timedelta

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import odc.stac
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from rasterio.features import geometry_mask

from comun import CRS_METRICO, OUT, PROC, STAC_PC, UMBRAL_QUEMADO, limites

RES = 20
HA_PIXEL = RES * RES / 10_000
SCL_INVALIDO = [0, 1, 3, 6, 8, 9, 10]   # sin dato, saturado, sombra, agua, nubes, cirros
SCL_NUBE = [0, 1, 3, 8, 9, 10]
CLASES = [(-np.inf, 0.10, "No quemado"), (0.10, 0.27, "Baja"), (0.27, 0.44, "Moderada-baja"),
          (0.44, 0.66, "Moderada-alta"), (0.66, np.inf, "Alta")]


def buscar(bbox, inicio, fin):
    cat = pystac_client.Client.open(STAC_PC, modifier=planetary_computer.sign_inplace)
    items = cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                       datetime=f"{inicio}/{fin}").item_collection()
    return list(items)


def nubes_por_fecha(items, bbox, mascara_aoi_fn):
    """% de la AOI cubierto por nubes/sin dato en cada fecha, según SCL."""
    if not items:
        return pd.DataFrame(columns=["fecha", "nubes_pct"])
    ds = odc.stac.load(items, bands=["SCL"], bbox=bbox, crs=CRS_METRICO,
                       resolution=RES, groupby="solar_day")
    dentro = mascara_aoi_fn(ds)
    filas = []
    for t in ds.time.values:
        scl = ds.SCL.sel(time=t).values
        filas.append({"fecha": pd.Timestamp(t).date().isoformat(),
                      "nubes_pct": round(100 * np.isin(scl[dentro], SCL_NUBE).mean(), 1)})
    return pd.DataFrame(filas)


def elegir(tabla, forzada, mas_reciente=True):
    if forzada:
        return forzada
    if tabla.empty:
        raise SystemExit("No hay imágenes Sentinel-2 en esa ventana.")
    orden = tabla.sort_values(["nubes_pct", "fecha"], ascending=[True, not mas_reciente])
    return orden.iloc[0]["fecha"]


def cargar_nbr(items, fecha, bbox):
    del_dia = [it for it in items if it.datetime.date().isoformat() == fecha]
    ds = odc.stac.load(del_dia, bands=["B08", "B12", "SCL"], bbox=bbox, crs=CRS_METRICO,
                       resolution=RES, groupby="solar_day").isel(time=0)
    baseline = float(del_dia[0].properties.get("s2:processing_baseline", "0"))
    offset = -1000 if baseline >= 4 else 0
    nir = (ds.B08.values.astype("float32") + offset) / 10_000
    swir = (ds.B12.values.astype("float32") + offset) / 10_000
    with np.errstate(invalid="ignore", divide="ignore"):
        nbr = (nir - swir) / (nir + swir)
    valido = ~np.isin(ds.SCL.values, SCL_INVALIDO) & np.isfinite(nbr)
    return nbr, valido, ds.odc.geobox


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre", help="Fecha imagen antes (YYYY-MM-DD)")
    ap.add_argument("--post", help="Fecha imagen después (YYYY-MM-DD)")
    args = ap.parse_args()

    aoi = gpd.read_file(PROC / "aoi.geojson")
    focos = gpd.read_file(PROC / "focos_incendio.geojson")
    resumen_focos = json.loads((PROC / "resumen_focos.json").read_text())
    bbox = list(aoi.total_bounds)
    aoi_m = aoi.to_crs(CRS_METRICO)

    def mascara_aoi(ds):
        gb = ds.odc.geobox
        return ~geometry_mask(aoi_m.geometry, out_shape=gb.shape, transform=gb.transform)

    primer = pd.Timestamp(resumen_focos["primer_foco"]).date()
    items_pre = buscar(bbox, primer - timedelta(days=75), primer - timedelta(days=1))
    items_post = buscar(bbox, primer, date.today())

    t_pre = nubes_por_fecha(items_pre, bbox, mascara_aoi)
    t_post = nubes_por_fecha(items_post, bbox, mascara_aoi)
    print("\nCandidatas ANTES (% nubes en la zona del incendio):\n", t_pre.to_string(index=False))
    print("\nCandidatas DESPUÉS:\n", t_post.to_string(index=False))

    f_pre = elegir(t_pre, args.pre)
    f_post = elegir(t_post, args.post)
    nubes_pre = float(t_pre.set_index("fecha")["nubes_pct"].get(f_pre, np.nan))
    nubes_post = float(t_post.set_index("fecha")["nubes_pct"].get(f_post, np.nan))
    if np.isnan(nubes_pre) or np.isnan(nubes_post):
        raise SystemExit("La fecha forzada no tiene imagen sobre la zona; elige una de las candidatas.")
    print(f"\nElegidas -> antes: {f_pre} ({nubes_pre} % nubes) | después: {f_post} ({nubes_post} % nubes)")
    if max(nubes_pre, nubes_post) > 30:
        print("AVISO: más de 30 % de nubes en la zona; el área quemada estará subestimada.")

    nbr_pre, ok_pre, gb = cargar_nbr(items_pre, f_pre, bbox)
    nbr_post, ok_post, _ = cargar_nbr(items_post, f_post, bbox)
    dnbr = nbr_pre - nbr_post
    dentro = ~geometry_mask(aoi_m.geometry, out_shape=gb.shape, transform=gb.transform)
    medible = dentro & ok_pre & ok_post
    dnbr_m = np.where(medible, dnbr, np.nan)

    # Hectáreas por clase de severidad
    por_clase = []
    for lo, hi, nombre in CLASES:
        n = int(((dnbr_m >= lo) & (dnbr_m < hi)).sum())
        por_clase.append({"clase": nombre, "dnbr_desde": lo, "ha": round(n * HA_PIXEL, 1)})
    por_clase = pd.DataFrame(por_clase)
    quemado = dnbr_m >= UMBRAL_QUEMADO
    ha_quemadas = round(float(quemado.sum()) * HA_PIXEL, 1)

    # Hectáreas quemadas por distrito
    distritos = limites("distrital").to_crs(CRS_METRICO)
    distritos = distritos[distritos.intersects(aoi_m.union_all())]
    por_distrito = []
    for _, d in distritos.iterrows():
        m = ~geometry_mask([d.geometry], out_shape=gb.shape, transform=gb.transform)
        por_distrito.append({"ubigeo": d["IDDIST"], "distrito": d["NOMBDIST"],
                             "provincia": d["NOMBPROV"],
                             "ha_quemadas": round(float((quemado & m).sum()) * HA_PIXEL, 1)})
    por_distrito = pd.DataFrame(por_distrito).sort_values("ha_quemadas", ascending=False)

    resumen = {
        "fecha_antes": f_pre, "nubes_antes_pct": nubes_pre,
        "fecha_despues": f_post, "nubes_despues_pct": nubes_post,
        "aoi_ha": round(float(dentro.sum()) * HA_PIXEL, 1),
        "aoi_medible_pct": round(100 * float(medible.sum()) / max(int(dentro.sum()), 1), 1),
        "umbral": UMBRAL_QUEMADO,
        "ha_quemadas": ha_quemadas,
        "ha_quemadas_umbral_0_10": round(float((dnbr_m >= 0.10).sum()) * HA_PIXEL, 1),
        "ha_quemadas_umbral_0_44": round(float((dnbr_m >= 0.44).sum()) * HA_PIXEL, 1),
        "dnbr_mediana_quemado": round(float(np.nanmedian(dnbr_m[quemado])), 3) if quemado.any() else None,
    }
    por_clase.to_csv(OUT / "ha_por_severidad.csv", index=False)
    por_distrito.to_csv(OUT / "ha_por_distrito.csv", index=False)
    pd.concat([t_pre.assign(tipo="antes"), t_post.assign(tipo="despues")]).to_csv(
        OUT / "imagenes_candidatas.csv", index=False)
    (PROC / "resumen_dnbr.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))

    with rasterio.open(OUT / "dnbr.tif", "w", driver="GTiff", height=gb.shape[0], width=gb.shape[1],
                       count=1, dtype="float32", crs=CRS_METRICO, transform=gb.transform,
                       nodata=np.nan) as dst:
        dst.write(dnbr_m.astype("float32"), 1)

    # Mapa
    cmap = ListedColormap(["#d9d9d9", "#fee391", "#fe9929", "#d7301f", "#67000d"])
    norm = BoundaryNorm([-1, 0.10, 0.27, 0.44, 0.66, 2], cmap.N)
    x0, y0 = gb.transform.c, gb.transform.f
    ext = [x0, x0 + gb.shape[1] * RES, y0 - gb.shape[0] * RES, y0]
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(dnbr_m, cmap=cmap, norm=norm, extent=ext)
    distritos.boundary.plot(ax=ax, color="#555", lw=0.8)
    aoi_m.boundary.plot(ax=ax, color="black", lw=1, ls="--")
    focos.to_crs(CRS_METRICO).plot(ax=ax, color="#08519c", markersize=6, label="Focos VIIRS")
    for _, d in distritos.iterrows():
        p = d.geometry.representative_point()
        if ext[0] < p.x < ext[1] and ext[2] < p.y < ext[3]:
            ax.annotate(d["NOMBDIST"].title(), (p.x, p.y), fontsize=8, color="#333")
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    cb = fig.colorbar(im, ax=ax, ticks=[-0.45, 0.185, 0.355, 0.55, 1.33], shrink=0.7)
    cb.ax.set_yticklabels([c[2] for c in CLASES])
    ax.set_title(f"Severidad (dNBR) — incendio de {resumen_focos['distrito'].title()}\n"
                 f"Sentinel-2: {f_pre} ({nubes_pre} % nubes) vs {f_post} ({nubes_post} % nubes) · "
                 f"{ha_quemadas:,.0f} ha con dNBR ≥ {UMBRAL_QUEMADO}", fontsize=10)
    ax.legend(loc="lower left"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel("En blanco: nubes, sombra, agua o sin dato (no medible)", fontsize=8); ax.set_ylabel("")
    fig.tight_layout(); fig.savefig(OUT / "mapa_dnbr.png", dpi=160)

    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(por_clase.to_string(index=False)); print(por_distrito.to_string(index=False))


if __name__ == "__main__":
    main()
