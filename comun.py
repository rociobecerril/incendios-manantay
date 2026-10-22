"""Rutas, fuentes y funciones compartidas por los scripts del proyecto."""
from pathlib import Path

import geopandas as gpd
import requests

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
OUT = RAIZ / "outputs"
for carpeta in (RAW, PROC, OUT):
    carpeta.mkdir(parents=True, exist_ok=True)

# --- Fuentes (todas abiertas, sin clave) ---
URL_FIRMS_7D = ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
                "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_7d.csv")
URL_FIRMS_ANUAL = ("https://firms.modaps.eosdis.nasa.gov/data/country/"
                   "viirs-snpp/{anio}/viirs-snpp_{anio}_Peru.csv")
URL_GEOJSON = "https://raw.githubusercontent.com/juaneladio/peru-geojson/master/{archivo}"
STAC_PC = "https://planetarycomputer.microsoft.com/api/stac/v1"

# --- Parámetros del caso ---
DISTRITO = "MANANTAY"          # Coronel Portillo, Ucayali (UBIGEO 250107)
DEPARTAMENTO = "UCAYALI"
CRS_METRICO = "EPSG:32718"     # UTM 18S, cubre Ucayali; permite medir en metros
DIST_MAX_M = 1000              # focos a <= 1 km ...
HORAS_MAX = 48                 # ... y <= 48 h se consideran un mismo incendio
BUFFER_AOI_M = 2000            # margen alrededor del incendio para medir dNBR
UMBRAL_QUEMADO = 0.27          # dNBR >= 0,27 = quemado (moderado-bajo o más, USGS)


def descargar(url: str, destino: Path, forzar: bool = False) -> Path:
    """Descarga un archivo una sola vez (caché en data/raw)."""
    if destino.exists() and not forzar:
        return destino
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def limites(nivel: str = "distrital") -> gpd.GeoDataFrame:
    """Límites INEI con UBIGEO del repositorio juaneladio/peru-geojson."""
    archivo = f"peru_{nivel}_simple.geojson"
    ruta = descargar(URL_GEOJSON.format(archivo=archivo), RAW / archivo)
    return gpd.read_file(ruta).to_crs("EPSG:4326")
