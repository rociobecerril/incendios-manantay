"""Paso 5. Dashboard HTML que cuenta el hallazgo (docs/index.html, listo para GitHub Pages).

Usa solo lo que ya generaron los pasos 1-3: no descarga nada nuevo.
El archivo resultante es autocontenido (datos y capa dNBR incrustados); Leaflet y Chart.js
se cargan desde cdnjs.
"""
import base64
import io
import json

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

from comun import DEPARTAMENTO, OUT, PROC, RAIZ

DOCS = RAIZ / "docs"
DOCS.mkdir(exist_ok=True)

TILDES = {"JUNIN": "Junín", "APURIMAC": "Apurímac", "ANCASH": "Áncash", "HUANUCO": "Huánuco",
          "SAN MARTIN": "San Martín", "PERÚ": "Perú", "MADRE DE DIOS": "Madre de Dios",
          "LA LIBERTAD": "La Libertad", "LIMA": "Lima", "CALLAO": "Callao"}


def nombre(dep):
    return TILDES.get(dep, dep.title())


def capa_dnbr():
    """Reproyecta dnbr.tif a lat/lon y lo pinta por clase de severidad (PNG con transparencia)."""
    with rasterio.open(OUT / "dnbr.tif") as src:
        tr, w, h = calculate_default_transform(src.crs, "EPSG:4326", src.width, src.height, *src.bounds)
        dst = np.full((h, w), np.nan, dtype="float32")
        reproject(rasterio.band(src, 1), dst, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tr, dst_crs="EPSG:4326", resampling=Resampling.nearest,
                  src_nodata=np.nan, dst_nodata=np.nan)
    rgba = np.zeros((h, w, 4), dtype="float32")
    colores = [(0.10, 0.27, (254, 227, 145, 150)), (0.27, 0.44, (254, 153, 41, 220)),
               (0.44, 0.66, (215, 48, 31, 235)), (0.66, 9.00, (103, 0, 13, 245))]
    for lo, hi, c in colores:
        m = (dst >= lo) & (dst < hi)
        rgba[m] = np.array(c) / 255
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    oeste, norte = tr.c, tr.f
    este, sur = oeste + w * tr.a, norte + h * tr.e
    return base64.b64encode(buf.getvalue()).decode(), [[sur, oeste], [norte, este]]


def main():
    f = json.loads((PROC / "resumen_focos.json").read_text())
    d = json.loads((PROC / "resumen_dnbr.json").read_text())
    r = json.loads((PROC / "resumen_record.json").read_text())
    sev = pd.read_csv(OUT / "ha_por_severidad.csv")
    cand = pd.read_csv(OUT / "imagenes_candidatas.csv")
    serie = pd.read_csv(OUT / "focos_semana_por_anio_departamento.csv", index_col=0)
    rec = pd.read_csv(OUT / "anio_record_por_departamento.csv", index_col=0)

    png, limites_capa = capa_dnbr()
    s_dep = serie.loc[DEPARTAMENTO]
    deps = rec.drop(index="PERÚ")
    deps = deps[deps["focos_2026"] >= 10].sort_values("variacion_pct", ascending=False)

    datos = {
        "f": f, "d": d, "r": r,
        "sev": sev[sev["clase"] != "No quemado"][["clase", "ha"]].to_dict("records"),
        "cand": cand.to_dict("records"),
        "serie": {"anios": [str(a) for a in s_dep.index], "focos": [int(v) for v in s_dep.values]},
        "deps": [{"dep": nombre(i), "f26": int(x.focos_2026), "prom": float(x.promedio_2012_2025),
                  "max": int(x.max_previo), "anio_max": int(x.anio_max_previo),
                  "var": float(x.variacion_pct), "record": bool(x.record)}
                 for i, x in deps.iterrows()],
        "focos": json.loads((PROC / "focos_incendio.geojson").read_text()),
        "aoi": json.loads((PROC / "aoi.geojson").read_text()),
        "png": png, "limites": limites_capa,
        "dep_nombre": nombre(DEPARTAMENTO), "distrito": f["distrito"].title(),
        "n_record": len(r["departamentos_en_record"]),
    }
    html = PLANTILLA.replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"docs/index.html creado ({len(html) / 1024:.0f} KB)")


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Incendio de Manantay</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600&family=Public+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root { --fondo:#f5f2eb; --tarjeta:#fff; --tinta:#1c1b19; --suave:#6b665e; --linea:#e4ded2;
          --oxido:#a8472a; --azul:#33597a; --gris:#b9b3a8; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--fondo); color:var(--tinta); font:16px/1.5 "Public Sans",system-ui,sans-serif; }
  .portada { background:#1c1b19; color:#f5f2eb; padding:48px 16px 40px; }
  .ancho { max-width:1120px; margin:0 auto; padding:0 16px; }
  .eti { font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:#e08a55; font-weight:600; }
  h1,h2 { font-family:Oswald,sans-serif; font-weight:600; line-height:1.1; margin:.3em 0; }
  h1 { font-size:clamp(34px,6vw,60px); }
  h2 { font-size:clamp(24px,3.4vw,34px); }
  .portada p { color:#d9d3c7; max-width:760px; font-size:18px; }
  section { padding:40px 0 8px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-top:-28px; }
  .kpi { background:var(--tarjeta); border:1px solid var(--linea); border-radius:12px; padding:20px; }
  .kpi b { display:block; font-family:Oswald,sans-serif; font-size:44px; line-height:1; color:var(--oxido); }
  .kpi span { color:var(--suave); font-size:14px; }
  .dos { display:grid; grid-template-columns:1.6fr 1fr; gap:20px; align-items:start; }
  @media (max-width:820px){ .dos { grid-template-columns:1fr; } }
  .tarjeta { background:var(--tarjeta); border:1px solid var(--linea); border-radius:12px; padding:20px; }
  #mapa { height:520px; border-radius:12px; border:1px solid var(--linea); }
  .leyenda { display:flex; flex-wrap:wrap; gap:10px 16px; font-size:13px; color:var(--suave); margin-top:10px; }
  .leyenda i { display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:6px; vertical-align:-1px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th,td { padding:7px 8px; border-bottom:1px solid var(--linea); text-align:right; }
  th:first-child,td:first-child { text-align:left; }
  th { color:var(--suave); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
  tr.rec td { background:#fbeee7; }
  tr.rec td:first-child { font-weight:600; color:var(--oxido); }
  .nota { color:var(--suave); font-size:14px; }
  .lim li { margin-bottom:6px; }
  .grafico { position:relative; height:300px; }
  footer { padding:32px 0 48px; color:var(--suave); font-size:13px; }
  a { color:var(--azul); }
</style>
</head>
<body>
<header class="portada"><div class="ancho">
  <div class="eti">Ciencia de datos con Python · Octubre de 2026</div>
  <h1 id="titulo"></h1>
  <p id="bajada"></p>
</div></header>

<div class="ancho">
  <div class="kpis" id="kpis"></div>

  <section>
    <div class="eti" style="color:var(--oxido)">1 · Cuánto se quemó</div>
    <h2 id="h-mapa"></h2>
    <div class="dos">
      <div>
        <div id="mapa"></div>
        <div class="leyenda">
          <span><i style="background:#fee391"></i>Baja</span><span><i style="background:#fe9929"></i>Moderada-baja</span>
          <span><i style="background:#d7301f"></i>Moderada-alta</span><span><i style="background:#67000d"></i>Alta</span>
          <span><i style="background:#2b6cb0;border-radius:50%"></i>Focos VIIRS</span>
          <span><i style="border:2px dashed #fff;background:#555"></i>Zona de estudio</span>
        </div>
      </div>
      <div class="tarjeta">
        <h3 style="margin-top:0">Hectáreas por severidad</h3>
        <table id="t-sev"></table>
        <p class="nota" id="nota-umbral"></p>
      </div>
    </div>
  </section>

  <section>
    <div class="eti" style="color:var(--oxido)">2 · La decisión que cambia el número</div>
    <h2>Elegí la imagen «antes» por cercanía, no solo por nubes</h2>
    <div class="dos">
      <div class="tarjeta"><div class="grafico"><canvas id="g-nubes"></canvas></div></div>
      <div class="tarjeta" id="decision"></div>
    </div>
  </section>

  <section>
    <div class="eti" style="color:var(--azul)">3 · ¿Año récord?</div>
    <h2 id="h-record"></h2>
    <div class="dos">
      <div class="tarjeta"><div class="grafico"><canvas id="g-serie"></canvas></div><p class="nota" id="nota-serie"></p></div>
      <div class="tarjeta" style="max-height:420px;overflow:auto"><table id="t-deps"></table></div>
    </div>
  </section>

  <section>
    <div class="eti" style="color:var(--suave)">Limitaciones</div>
    <h2>Lo que este número no dice</h2>
    <ul class="lim">
      <li>Un foco de calor no es un incendio: es un píxel de ~375 m más caliente que su entorno cuando pasa el satélite.</li>
      <li id="lim-nubes"></li>
      <li>La imagen «después» se tomó con el fuego aún activo: el área quemada es un mínimo.</li>
      <li>En el noroeste de la zona hay parches rectangulares que parecen chacras quemadas ajenas a este incendio: ahí la cifra puede estar sobreestimada.</li>
      <li>En Arequipa, Moquegua y Tacna pueden quedar focos de volcanes o minas que el filtro no quitó.</li>
      <li>Herramienta independiente: no reemplaza las cifras de COEN, INDECI, SERFOR ni SERNANP.</li>
    </ul>
  </section>

  <footer>Fuentes: NASA FIRMS (VIIRS S-NPP), Sentinel-2 L2A vía Microsoft Planetary Computer, límites INEI (juaneladio/peru-geojson). Código y método: <a href="https://github.com/rociobecerril/incendios-manantay">github.com/rociobecerril/incendios-manantay</a>.</footer>
</div>

<script>
const D = __DATOS__;
const fmt = (x, n=0) => Number(x).toLocaleString("es-PE", {maximumFractionDigits:n, minimumFractionDigits:n});
const fecha = s => { const [a,m,d] = s.slice(0,10).split("-"); return `${+d} ${["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"][m-1]}`; };
const pct = v => (v >= 0 ? "+" : "") + fmt(v) + " %";

document.getElementById("titulo").textContent = `El incendio de ${D.distrito} quemó al menos ${fmt(D.d.ha_quemadas)} ha en una semana de fuego en todo el Perú`;
document.getElementById("bajada").textContent =
  `Medí el área quemada con imágenes Sentinel-2 y comparé los focos de calor del ${fecha(D.r.ventana[0])} al ${fecha(D.r.ventana[1])} con las mismas fechas de 2012 a 2025. ${D.dep_nombre} está ${pct(D.r.variacion_pct)} sobre su promedio, pero los récords están en los Andes y el sur.`;

const kpis = [
  [fmt(D.d.ha_quemadas), `hectáreas quemadas (dNBR ≥ ${String(D.d.umbral).replace(".", ",")}) · rango ${fmt(D.d.ha_quemadas_umbral_0_44)}–${fmt(D.d.ha_quemadas_umbral_0_10)} según el umbral`],
  [D.f.focos_incendio, `focos VIIRS en el incendio, del ${fecha(D.f.primer_foco)} al ${fecha(D.f.ultimo_foco)}`],
  [pct(D.r.variacion_pct), `focos en ${D.dep_nombre} frente al promedio 2012–2025 · puesto ${D.r.puesto_2026_de_15} de 15`],
  [D.n_record, `departamentos con récord histórico esa semana`],
];
document.getElementById("kpis").innerHTML = kpis.map(([b,s]) => `<div class="kpi"><b>${b}</b><span>${s}</span></div>`).join("");

// Mapa
document.getElementById("h-mapa").textContent = `${fmt(D.d.ha_quemadas)} ha con severidad moderada o alta, todas en ${D.distrito}`;
const mapa = L.map("mapa", {scrollWheelZoom:false});
const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {attribution:"Imágenes © Esri", maxZoom:18}).addTo(mapa);
const calles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {attribution:"© OpenStreetMap", maxZoom:18});
const capa = L.imageOverlay("data:image/png;base64," + D.png, D.limites, {opacity:0.9}).addTo(mapa);
const aoi = L.geoJSON(D.aoi, {style:{color:"#fff", weight:2, dashArray:"6 5", fill:false}}).addTo(mapa);
const focos = L.geoJSON(D.focos, {pointToLayer:(ft, ll) => L.circleMarker(ll, {radius:4, color:"#fff", weight:1, fillColor:"#2b6cb0", fillOpacity:1})
  .bindTooltip(`${ft.properties.acq_date} · FRP ${ft.properties.frp} MW`)}).addTo(mapa);
L.control.layers({"Satélite":sat, "Calles":calles}, {"Severidad dNBR":capa, "Focos VIIRS":focos, "Zona de estudio":aoi}).addTo(mapa);
mapa.fitBounds(aoi.getBounds(), {padding:[10,10]});

document.getElementById("t-sev").innerHTML = "<tr><th>Clase</th><th>ha</th><th>%</th></tr>" +
  D.sev.map(s => `<tr><td>${s.clase}</td><td>${fmt(s.ha)}</td><td>${fmt(100*s.ha/D.sev.reduce((a,b)=>a+b.ha,0))}</td></tr>`).join("");
document.getElementById("nota-umbral").innerHTML =
  `Cuento como quemado desde «moderada-baja» (dNBR ≥ ${String(D.d.umbral).replace(".", ",")}): <b>${fmt(D.d.ha_quemadas)} ha</b>. Si incluyo «baja» serían ${fmt(D.d.ha_quemadas_umbral_0_10)} ha; solo moderada-alta o más, ${fmt(D.d.ha_quemadas_umbral_0_44)} ha. Fue medible el ${fmt(D.d.aoi_medible_pct,1)} % de la zona de ${fmt(D.d.aoi_ha)} ha.`;

// Decisión de imágenes
const c = D.cand;
new Chart(document.getElementById("g-nubes"), {
  type:"bar",
  data:{labels:c.map(x => fecha(x.fecha)),
    datasets:[{label:"% de nubes en la zona", data:c.map(x => x.nubes_pct),
      backgroundColor:c.map(x => x.fecha===D.d.fecha_antes || x.fecha===D.d.fecha_despues ? "#a8472a" : (x.fecha==="2026-08-14" ? "#33597a" : "#d6d0c4"))}]},
  options:{maintainAspectRatio:false, plugins:{legend:{display:false},
    tooltip:{callbacks:{label:t => `${t.raw} % nubes · ${c[t.dataIndex].tipo}`}}},
    scales:{y:{max:100, title:{display:true, text:"% de nubes en la zona"}}, x:{ticks:{maxRotation:90, minRotation:60}}}}
});
document.getElementById("decision").innerHTML = `
  <p>La regla automática elegía la imagen con menos nubes: el <b style="color:#33597a">14 de agosto</b> (0 %), a dos meses del incendio. Con tanta distancia, el dNBR mezcla el fuego con el secado de la estación y la quema de chacras.</p>
  <p>Elegí el <b style="color:#a8472a">${fecha(D.d.fecha_antes)}</b> (${fmt(D.d.nubes_antes_pct,1)} % de nubes), a 24 días del primer foco. <b>El área bajó 11 %.</b></p>
  <p>Para el «después» solo había dos opciones: el <b style="color:#a8472a">${fecha(D.d.fecha_despues)}</b> (${fmt(D.d.nubes_despues_pct,1)} %) o el 21 oct (56 %).</p>
  <p class="nota">La computadora siempre da un número; la credibilidad depende de fechas, nubes, umbral y zona.</p>`;

// Récord
const recUcayali = D.r.puesto_2026_de_15 === 1;
document.getElementById("h-record").textContent = recUcayali
  ? `${D.dep_nombre} vive su peor semana desde 2012`
  : `${D.dep_nombre} no bate su récord (${D.r.anio_max_previo} fue peor), pero ${D.n_record} departamentos de los Andes y el sur sí`;
const s = D.serie;
new Chart(document.getElementById("g-serie"), {
  type:"bar",
  data:{labels:s.anios, datasets:[
    {label:"Focos", data:s.focos, backgroundColor:s.anios.map(a => a==="2026" ? "#a8472a" : "#cfc8bb")},
    {type:"line", label:"Promedio 2012–2025", data:s.anios.map(() => D.r.promedio_2012_2025), borderColor:"#1c1b19", borderDash:[5,4], pointRadius:0, borderWidth:1.5}]},
  options:{maintainAspectRatio:false, plugins:{legend:{position:"bottom"}},
    scales:{y:{title:{display:true, text:"Focos de calor"}}}}
});
document.getElementById("nota-serie").textContent =
  `Focos VIIRS S-NPP en ${D.dep_nombre} entre el ${fecha(D.r.ventana[0])} y el ${fecha(D.r.ventana[1])} de cada año. 2026: ${fmt(D.r.focos_2026)} focos; promedio: ${fmt(D.r.promedio_2012_2025)}.`;
document.getElementById("t-deps").innerHTML =
  "<tr><th>Departamento</th><th>2026</th><th>Prom.</th><th>Máx. previo</th><th>Var.</th></tr>" +
  D.deps.map(x => `<tr class="${x.record ? "rec" : ""}"><td>${x.dep}${x.record ? " ★" : ""}</td><td>${fmt(x.f26)}</td><td>${fmt(x.prom)}</td><td>${fmt(x.max)} (${x.anio_max})</td><td>${pct(x.var)}</td></tr>`).join("") +
  `<tr><td colspan="5" class="nota" style="text-align:left">★ récord: 2026 supera el máximo de 2012–2025. Solo departamentos con 10 o más focos en 2026.</td></tr>`;
document.getElementById("lim-nubes").textContent =
  `Las nubes y el humo esconden el fuego: solo el ${fmt(D.d.aoi_medible_pct,1)} % de la zona fue medible.`;
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
