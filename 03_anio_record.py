"""Paso 3. ¿Es 2026 un año récord? Focos de la misma semana, 2012-2026, por departamento.

Decisiones de método:
- Ventana: los días completos del archivo de 7 días (se excluye el último día, que suele estar incompleto),
  comparados con esas mismas fechas (mes-día) en cada año 2012-2025.
- Solo S-NPP, para que la serie sea comparable desde 2012. Se excluye la confianza baja.
- 2012-2025: archivo anual por país de NASA FIRMS; se usan solo focos de tipo 0 (vegetación).
- 2026 (tiempo casi real) no trae el tipo; se quitan los focos a <= 1 km de fuentes fijas o volcanes
  identificados en el archivo histórico (tipos 1, 2 y 3).
- Departamento asignado por intersección con los límites INEI.
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from scipy.spatial import cKDTree

from comun import CRS_METRICO, DEPARTAMENTO, OUT, PROC, RAW, URL_FIRMS_ANUAL, descargar, limites

ANIOS = range(2012, 2026)


def a_gdf(df):
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")


def main():
    deps = limites("departamental")[["NOMBDEP", "geometry"]]
    reciente = pd.read_csv(RAW / "firms_snpp_south_america_7d.csv")
    fechas = sorted(reciente["acq_date"].unique())[:-1]          # días completos
    md = {f[5:] for f in fechas}                                  # "MM-DD"
    reciente = reciente[reciente["acq_date"].isin(fechas)]
    reciente = reciente[reciente["confidence"].astype(str).str.lower() != "l"]

    historicos, fijos = [], []
    for anio in ANIOS:
        ruta = descargar(URL_FIRMS_ANUAL.format(anio=anio), RAW / f"viirs-snpp_{anio}_Peru.csv")
        h = pd.read_csv(ruta, usecols=lambda c: c in {"latitude", "longitude", "acq_date",
                                                       "confidence", "type"})
        fijos.append(h.loc[h["type"].isin([1, 2, 3]), ["latitude", "longitude"]])
        h = h[(h["type"] == 0) & (h["acq_date"].str[5:].isin(md))
              & (h["confidence"].astype(str).str.lower() != "l")]
        historicos.append(h.assign(anio=anio))
    hist = pd.concat(historicos)

    # Quitar fuentes fijas y volcanes de 2026
    fijos = a_gdf(pd.concat(fijos).drop_duplicates()).to_crs(CRS_METRICO)
    rec = a_gdf(reciente).to_crs(CRS_METRICO)
    d, _ = cKDTree(list(zip(fijos.geometry.x, fijos.geometry.y))).query(
        list(zip(rec.geometry.x, rec.geometry.y)))
    n_quitados = int((d <= 1000).sum())
    rec = rec[d > 1000].to_crs("EPSG:4326").assign(anio=2026)

    todo = pd.concat([a_gdf(hist), rec[["latitude", "longitude", "acq_date", "anio", "geometry"]]])
    todo = gpd.sjoin(todo, deps, predicate="intersects", how="inner")   # solo Perú
    tabla = todo.groupby(["NOMBDEP", "anio"]).size().unstack(fill_value=0)
    tabla = tabla.reindex(columns=list(ANIOS) + [2026], fill_value=0)
    tabla.loc["PERÚ"] = tabla.sum()

    prev = tabla[list(ANIOS)]
    res = pd.DataFrame({
        "focos_2026": tabla[2026],
        "promedio_2012_2025": prev.mean(axis=1).round(1),
        "max_previo": prev.max(axis=1),
        "anio_max_previo": prev.idxmax(axis=1),
    })
    res["variacion_pct"] = ((res["focos_2026"] / res["promedio_2012_2025"] - 1) * 100).round(0)
    res["puesto_2026"] = tabla.rank(axis=1, ascending=False, method="min")[2026].astype(int)
    res["record"] = res["focos_2026"] > res["max_previo"]
    res = res.sort_values("focos_2026", ascending=False)
    tabla.to_csv(OUT / "focos_semana_por_anio_departamento.csv")
    res.to_csv(OUT / "anio_record_por_departamento.csv")

    obj = res.loc[DEPARTAMENTO]
    resumen = {
        "ventana": [fechas[0], fechas[-1]],
        "focos_2026_quitados_por_fuente_fija": n_quitados,
        "departamento": DEPARTAMENTO,
        "focos_2026": int(obj["focos_2026"]),
        "promedio_2012_2025": float(obj["promedio_2012_2025"]),
        "variacion_pct": float(obj["variacion_pct"]),
        "puesto_2026_de_15": int(obj["puesto_2026"]),
        "max_previo": int(obj["max_previo"]), "anio_max_previo": int(obj["anio_max_previo"]),
        "peru_focos_2026": int(res.loc["PERÚ", "focos_2026"]),
        "peru_variacion_pct": float(res.loc["PERÚ", "variacion_pct"]),
        "peru_puesto_2026_de_15": int(res.loc["PERÚ", "puesto_2026"]),
        "departamentos_en_record": [d for d in res.index[res["record"]] if d != "PERÚ"],
    }
    (PROC / "resumen_record.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))

    # Gráfico
    serie = tabla.loc[DEPARTAMENTO]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colores = ["#b0b0b0"] * len(ANIOS) + ["#c2410c"]
    ax.bar([str(a) for a in serie.index], serie.values, color=colores)
    ax.axhline(obj["promedio_2012_2025"], color="#333", ls="--", lw=1)
    ax.text(0, obj["promedio_2012_2025"], " promedio 2012-2025", va="bottom", fontsize=8)
    ax.set_title(f"{DEPARTAMENTO.title()}: focos VIIRS S-NPP entre el {fechas[0][5:]} y el "
                 f"{fechas[-1][5:]} de cada año", fontsize=11)
    ax.set_ylabel("Focos de calor"); ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=45); fig.tight_layout(); fig.savefig(OUT / "serie_record.png", dpi=160)

    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(res.to_string())


if __name__ == "__main__":
    main()
