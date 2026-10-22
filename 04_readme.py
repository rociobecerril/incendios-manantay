"""Paso 4. Escribe README.md con los números de los pasos 1-3."""
import json

import pandas as pd

from comun import OUT, PROC, RAIZ

f = json.loads((PROC / "resumen_focos.json").read_text())
d = json.loads((PROC / "resumen_dnbr.json").read_text())
r = json.loads((PROC / "resumen_record.json").read_text())
sev = pd.read_csv(OUT / "ha_por_severidad.csv")
dist = pd.read_csv(OUT / "ha_por_distrito.csv")

alta = sev.loc[sev["clase"].isin(["Moderada-alta", "Alta"]), "ha"].sum()
pct_alta = 100 * alta / d["ha_quemadas"] if d["ha_quemadas"] else 0
top = dist.iloc[0]
pct_top = 100 * top["ha_quemadas"] / d["ha_quemadas"] if d["ha_quemadas"] else 0
signo = "+" if r["variacion_pct"] >= 0 else ""
signo_pe = "+" if r["peru_variacion_pct"] >= 0 else ""
record_txt = ("**es el valor más alto de la serie**" if r["puesto_2026_de_15"] == 1 else
              f"ocupa el puesto {r['puesto_2026_de_15']} de 15 (el máximo fue {r['max_previo']} "
              f"focos en {r['anio_max_previo']})")
deps_record = ", ".join(x.title() for x in r["departamentos_en_record"]) or "ninguno"

tabla_sev = "\n".join(f"| {c} | {h:,.1f} |" for c, h in zip(sev["clase"], sev["ha"]))
tabla_dist = "\n".join(f"| {u} | {n.title()} | {h:,.1f} |"
                       for u, n, h in zip(dist["ubigeo"], dist["distrito"], dist["ha_quemadas"]))

md = f"""# Incendio de {f['distrito'].title()} (Ucayali), octubre de 2026: ¿cuánto se quemó y es un año récord?

Tarea del curso *Ciencia de datos con Python* (Universidad del Pacífico) · Retos A + E.

## La pregunta

¿Cuántas hectáreas quemó el incendio de {f['distrito'].title()} detectado entre el {f['primer_foco'][:10]} y el {f['ultimo_foco'][:10]}, y los focos de calor de esta semana en Ucayali son récord frente a las mismas fechas de 2012-2025?

## Tres hallazgos

1. **{d['ha_quemadas']:,.0f} ha quemadas** (dNBR ≥ {d['umbral']}) dentro de una zona de estudio de {d['aoi_ha']:,.0f} ha. Con un umbral más estricto (0,44) o más laxo (0,10) la cifra va de {d['ha_quemadas_umbral_0_44']:,.0f} a {d['ha_quemadas_umbral_0_10']:,.0f} ha: el número depende del umbral.
2. **{pct_alta:.0f} % del área quemada tiene severidad moderada-alta o alta**, y el {pct_top:.0f} % está en el distrito de {top['distrito'].title()} (UBIGEO {top['ubigeo']}).
3. **Ucayali registra {r['focos_2026']:,} focos entre el {r['ventana'][0]} y el {r['ventana'][1]}**, {signo}{r['variacion_pct']:.0f} % frente al promedio de esas fechas en 2012-2025 ({r['promedio_2012_2025']:,.0f}); 2026 {record_txt}. A nivel nacional la variación es {signo_pe}{r['peru_variacion_pct']:.0f} % (puesto {r['peru_puesto_2026_de_15']} de 15). Departamentos en récord esa semana: {deps_record}.

## Dashboard

https://rociobecerril.github.io/incendios-manantay/

## Mapa

![Severidad dNBR](outputs/mapa_dnbr.png)

![Serie de focos](outputs/serie_record.png)

## Datos y fechas

| Dato | Fuente | Fecha usada |
|---|---|---|
| Focos de calor 2026 | NASA FIRMS, VIIRS S-NPP «South America 7d» (tiempo casi real) | {f['ventana_7d'][0]} a {f['ventana_7d'][1]} |
| Focos 2012-2025 | NASA FIRMS, archivo anual por país «viirs-snpp Peru» | mismas fechas de cada año |
| Imagen antes | Sentinel-2 L2A, Microsoft Planetary Computer | {d['fecha_antes']} ({d['nubes_antes_pct']} % nubes en la zona) |
| Imagen después | Sentinel-2 L2A, Microsoft Planetary Computer | {d['fecha_despues']} ({d['nubes_despues_pct']} % nubes en la zona) |
| Límites con UBIGEO | INEI vía GitHub juaneladio/peru-geojson | — |

## Método

1. **Focos** (`01_focos.py`): focos S-NPP de confianza nominal o alta; un incendio es un grupo de focos a ≤ 1 km y ≤ 48 h entre sí. Se tomó el grupo más grande que toca {f['distrito'].title()}: {f['focos_incendio']} focos. Zona de estudio = envolvente del grupo + 2 km.
2. **dNBR** (`02_dnbr.py`): NBR = (B08 − B12)/(B08 + B12) a 20 m; dNBR = NBR antes − NBR después. La imagen «después» es la de menos nubes tras el primer foco. La imagen «antes» se eligió manualmente: se usó la del 21-sep en vez de la del 14-ago (que tenía igual o menos nubes) porque está más cerca del incendio y reduce los cambios por estación y por chacras. Nubes, sombras, agua y sin dato se enmascararon con la capa SCL; quedó medible el {d['aoi_medible_pct']} % de la zona. Clases de severidad USGS.
3. **Año récord** (`03_anio_record.py`): conteo de focos por departamento en las mismas fechas de 2012 a 2026, solo S-NPP. En la serie histórica se usan focos de vegetación (tipo 0); en 2026 se quitaron {r['focos_2026_quitados_por_fuente_fija']} focos a ≤ 1 km de fuentes fijas o volcanes conocidos.

### Hectáreas por severidad

| Clase | ha |
|---|---|
{tabla_sev}

### Hectáreas quemadas por distrito

| UBIGEO | Distrito | ha |
|---|---|---|
{tabla_dist}

## Limitaciones

- Un foco de calor no es un incendio: es un píxel de ~375 m más caliente que su entorno en el momento del paso del satélite. Incendios pequeños, de sotobosque o bajo nubes no se detectan.
- Las nubes y el humo esconden el fuego: solo el {d['aoi_medible_pct']} % de la zona fue medible; el área quemada es un mínimo.
- La imagen del 16-oct se tomó con el fuego aún activo, así que el área quemada es un mínimo.
- En el noroeste de la zona hay parches rectangulares con dNBR alto que parecen quemas o limpieza de chacras ajenas a este incendio; están incluidos en las hectáreas, por lo que la cifra puede estar sobreestimada en esa parte, mientras que las nubes y el humo sobre el sur la subestiman.
- El umbral de dNBR cambia el resultado (ver hallazgo 1). En la Amazonía, la quema agrícola y la deforestación previa también bajan el NBR.
- Los focos de 2026 son de tiempo casi real y los históricos de archivo procesado; la diferencia mensual entre ambos es pequeña, pero no nula.
- Es una herramienta independiente: no reemplaza las cifras de COEN, INDECI, SERFOR ni SERNANP.

## Cómo reproducir

```bash
pip install -r requirements.txt
python 01_focos.py
python 02_dnbr.py            # o forzar fechas: --pre AAAA-MM-DD --post AAAA-MM-DD
python 03_anio_record.py
python 04_readme.py
```
"""
(RAIZ / "README.md").write_text(md, encoding="utf-8")
print("README.md actualizado")
