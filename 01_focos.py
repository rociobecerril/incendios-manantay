"""Paso 1. Descarga los focos VIIRS de los últimos 7 días y ubica el incendio de Manantay.

Decisiones de método:
- Satélite: solo Suomi-NPP (S-NPP), el mismo de la serie 2012-2025 del paso 3.
- Se descartan focos de confianza baja ("l").
- Un incendio = grupo de focos a <= 1 km y <= 48 h entre sí (enlace simple).
- Se elige el grupo con más focos que toque el distrito de Manantay.
- La zona de estudio (AOI) es la envolvente del grupo más 2 km de margen.
"""
import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from comun import (BUFFER_AOI_M, CRS_METRICO, DIST_MAX_M, DISTRITO, HORAS_MAX,
                   PROC, RAW, URL_FIRMS_7D, descargar, limites)


def leer_focos_7d() -> gpd.GeoDataFrame:
    ruta = descargar(URL_FIRMS_7D, RAW / "firms_snpp_south_america_7d.csv", forzar=True)
    df = pd.read_csv(ruta)
    df = df[df["confidence"].astype(str).str.lower() != "l"].copy()
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    df["fecha_hora"] = pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")


def agrupar_incendios(focos: gpd.GeoDataFrame) -> np.ndarray:
    """Etiqueta cada foco con un id de incendio (componentes conexas por distancia y tiempo)."""
    xy = np.c_[focos.geometry.x, focos.geometry.y]
    t = focos["fecha_hora"].astype("int64").to_numpy() / 3.6e12  # horas
    padre = np.arange(len(focos))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i, j in cKDTree(xy).query_pairs(DIST_MAX_M):
        if abs(t[i] - t[j]) <= HORAS_MAX:
            padre[raiz(i)] = raiz(j)
    return np.array([raiz(i) for i in range(len(focos))])


def main():
    distritos = limites("distrital")
    distrito = distritos[distritos["NOMBDIST"] == DISTRITO]
    focos = leer_focos_7d()

    # Recorte previo a 20 km del distrito para no agrupar toda Sudamérica
    zona = distrito.to_crs(CRS_METRICO).buffer(20_000).to_crs("EPSG:4326").union_all()
    cerca = focos[focos.within(zona)].to_crs(CRS_METRICO).reset_index(drop=True)
    if cerca.empty:
        sys.exit(f"No hay focos S-NPP en {DISTRITO} (+20 km) en los últimos 7 días. "
                 "Elige otro incendio (Río Tambo, Chichas) cambiando DISTRITO en comun.py.")

    cerca["incendio"] = agrupar_incendios(cerca)
    dist_m = distrito.to_crs(CRS_METRICO).union_all()
    ids_en_distrito = cerca.loc[cerca.intersects(dist_m), "incendio"].unique()
    if len(ids_en_distrito) == 0:
        sys.exit(f"Hay focos cerca, pero ninguno dentro de {DISTRITO}. Revisa el mapa o amplía la zona.")
    tam = cerca[cerca["incendio"].isin(ids_en_distrito)].groupby("incendio").size()
    elegido = tam.idxmax()
    inc = cerca[cerca["incendio"] == elegido].copy()

    aoi = gpd.GeoDataFrame(geometry=[inc.union_all().convex_hull.buffer(BUFFER_AOI_M)], crs=CRS_METRICO)
    inc.to_crs("EPSG:4326").drop(columns=["fecha_hora"]).assign(
        fecha_hora=inc["fecha_hora"].astype(str)).to_file(PROC / "focos_incendio.geojson")
    aoi.to_crs("EPSG:4326").to_file(PROC / "aoi.geojson")

    resumen = {
        "distrito": DISTRITO,
        "focos_7d_cerca": int(len(cerca)),
        "incendios_detectados_cerca": int(cerca["incendio"].nunique()),
        "focos_incendio": int(len(inc)),
        "primer_foco": str(inc["fecha_hora"].min()),
        "ultimo_foco": str(inc["fecha_hora"].max()),
        "frp_total_mw": round(float(inc["frp"].sum()), 1),
        "aoi_ha": round(float(aoi.area.iloc[0]) / 10_000, 1),
        "ventana_7d": [str(focos["acq_date"].min()), str(focos["acq_date"].max())],
    }
    (PROC / "resumen_focos.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
