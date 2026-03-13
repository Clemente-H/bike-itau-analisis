"""
Genera output/mapa_disponibilidad.html
Mapa interactivo con slider de hora para ver disponibilidad de Bike Itaú por estación.

Color de círculos:
  Rojo      → saturada (sin anclajes para devolver)
  Naranja   → vacía (sin bicis para retirar)
  Verde     → OK
  Gris      → sin datos para esa hora

Tamaño del círculo proporcional a la capacidad de la estación.
"""

import json
import os
import pandas as pd

DATA_FILE = "data/station_status.csv"
OUTPUT_DIR = "output"
MIN_SNAPSHOTS = 10  # filtrar estaciones con muy pocos registros

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 1. Cargar y limpiar ────────────────────────────────────────────────────────

df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
df["hora"] = df["timestamp"].dt.hour

# Filtrar estaciones fantasma (capacity=0 o muy pocos snapshots)
snaps = df.groupby("station_id")["timestamp"].count()
estaciones_validas = snaps[snaps >= MIN_SNAPSHOTS].index
df = df[df["station_id"].isin(estaciones_validas) & (df["capacity"] > 0)]

print(f"Estaciones válidas: {df['station_id'].nunique()}")
print(f"Estaciones filtradas (fantasmas): {len(snaps) - df['station_id'].nunique()}")

# ── 2. Coordenadas y capacidad por estación ────────────────────────────────────

estaciones = (
    df.groupby("station_id")
    .agg(
        name=("station_name", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
        capacity=("capacity", "first"),
    )
    .reset_index()
)

# ── 3. Métricas por estación × hora ────────────────────────────────────────────

por_hora = (
    df.groupby(["station_id", "hora"])
    .agg(
        pct_llena=("docks_available", lambda x: (x == 0).mean()),
        pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
        bikes_avg=("bikes_available", "mean"),
        docks_avg=("docks_available", "mean"),
        n=("timestamp", "count"),
    )
    .reset_index()
)

por_hora = por_hora.merge(estaciones, on="station_id")

# ── 4. Construir datos para el JS (dict hora → lista de estaciones) ─────────────

def color_estado(pct_llena, pct_vacia):
    """Devuelve color hex según estado predominante."""
    if pct_llena >= 0.6:
        return "#e74c3c"   # rojo: saturada
    elif pct_vacia >= 0.6:
        return "#e67e22"   # naranja: vacía
    elif pct_llena >= 0.3:
        return "#f39c12"   # amarillo: tendencia a saturarse
    else:
        return "#27ae60"   # verde: ok

datos_por_hora = {}
for hora in range(24):
    sub = por_hora[por_hora["hora"] == hora]
    lista = []
    for _, row in sub.iterrows():
        lista.append({
            "id": int(row["station_id"]),
            "name": row["name"],
            "lat": round(row["lat"], 6),
            "lon": round(row["lon"], 6),
            "capacity": int(row["capacity"]),
            "pct_llena": round(row["pct_llena"] * 100, 1),
            "pct_vacia": round(row["pct_vacia"] * 100, 1),
            "bikes_avg": round(row["bikes_avg"], 1),
            "docks_avg": round(row["docks_avg"], 1),
            "n": int(row["n"]),
            "color": color_estado(row["pct_llena"], row["pct_vacia"]),
        })
    # También incluir estaciones sin datos en esa hora (gris)
    ids_con_datos = {e["id"] for e in lista}
    for _, est in estaciones.iterrows():
        if int(est["station_id"]) not in ids_con_datos:
            lista.append({
                "id": int(est["station_id"]),
                "name": est["name"],
                "lat": round(est["lat"], 6),
                "lon": round(est["lon"], 6),
                "capacity": int(est["capacity"]),
                "pct_llena": None,
                "pct_vacia": None,
                "bikes_avg": None,
                "docks_avg": None,
                "n": 0,
                "color": "#95a5a6",  # gris: sin datos
            })
    datos_por_hora[hora] = lista

# ── 5. Métricas globales para el resumen ────────────────────────────────────────

resumen = (
    df.groupby("station_id")
    .agg(
        name=("station_name", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
        capacity=("capacity", "first"),
        pct_llena=("docks_available", lambda x: (x == 0).mean()),
        pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
        bikes_avg=("bikes_available", "mean"),
        docks_avg=("docks_available", "mean"),
    )
    .reset_index()
)

# Top 10 más saturadas (peor para devolver)
top_saturadas = resumen.nlargest(10, "pct_llena")[["name", "pct_llena"]].values.tolist()
top_saturadas = [[n, round(p * 100, 1)] for n, p in top_saturadas]

# Top 10 más vacías (peor para retirar)
top_vacias = resumen.nlargest(10, "pct_vacia")[["name", "pct_vacia"]].values.tolist()
top_vacias = [[n, round(p * 100, 1)] for n, p in top_vacias]

# ── 6. Generar HTML ─────────────────────────────────────────────────────────────

datos_json = json.dumps(datos_por_hora)
top_sat_json = json.dumps(top_saturadas)
top_vac_json = json.dumps(top_vacias)

# Centro del mapa: centroide de las estaciones
lat_center = estaciones["lat"].mean()
lon_center = estaciones["lon"].mean()

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bike Itaú — Disponibilidad por hora</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f4f8; color: #222; }}
  #header {{ padding: 14px 20px; background: #fff; border-bottom: 2px solid #e74c3c; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  #header h1 {{ font-size: 1.1rem; font-weight: 700; color: #222; }}
  #header .sub {{ font-size: 0.75rem; color: #888; }}
  #container {{ display: flex; height: calc(100vh - 58px); }}
  #map {{ flex: 1; }}
  #sidebar {{ width: 320px; background: #f4f4f8; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; }}

  /* Slider */
  #slider-wrap {{ background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  #slider-wrap h2 {{ font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
  #hora-display {{ font-size: 2.5rem; font-weight: 800; color: #e74c3c; text-align: center; margin-bottom: 6px; }}
  input[type=range] {{ width: 100%; accent-color: #e74c3c; cursor: pointer; }}
  #hora-labels {{ display: flex; justify-content: space-between; font-size: 0.65rem; color: #aaa; margin-top: 2px; }}

  /* Leyenda */
  #leyenda {{ background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  #leyenda h2 {{ font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
  .leyenda-item {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 0.82rem; color: #333; }}
  .dot {{ width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; }}

  /* Rankings */
  .ranking {{ background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .ranking h2 {{ font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
  .rank-item {{ display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #eee; font-size: 0.78rem; }}
  .rank-item:last-child {{ border-bottom: none; }}
  .rank-name {{ flex: 1; padding-right: 8px; color: #444; }}
  .rank-pct {{ font-weight: 700; font-size: 0.85rem; }}
  .rank-pct.rojo {{ color: #e74c3c; }}
  .rank-pct.naranja {{ color: #e67e22; }}

  /* Stats counter */
  #stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }}
  .stat-box {{ background: #fff; border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .stat-val {{ font-size: 1.4rem; font-weight: 800; }}
  .stat-lab {{ font-size: 0.65rem; color: #888; margin-top: 2px; }}
  .val-rojo {{ color: #e74c3c; }}
  .val-naranja {{ color: #e67e22; }}
  .val-verde {{ color: #27ae60; }}

  /* Popup */
  .leaflet-popup-content-wrapper {{ background: #fff; color: #222; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
  .leaflet-popup-tip {{ background: #fff; }}
  .popup-title {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 6px; color: #111; }}
  .popup-row {{ display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 3px; }}
  .popup-row .label {{ color: #888; }}
  .popup-row .val {{ font-weight: 600; color: #222; }}
  .bar-wrap {{ margin-top: 6px; }}
  .bar-label {{ font-size: 0.72rem; color: #888; margin-bottom: 2px; }}
  .bar-bg {{ background: #eee; border-radius: 4px; height: 8px; }}
  .bar-fill {{ height: 8px; border-radius: 4px; }}
</style>
</head>
<body>
<div id="header">
  <div>
    <h1>🚲 Bike Itaú — Disponibilidad por hora</h1>
    <div class="sub">Santiago · datos recolectados 6–13 Mar 2026 (~162 snapshots)</div>
  </div>
</div>
<div id="container">
  <div id="map"></div>
  <div id="sidebar">

    <div id="slider-wrap">
      <h2>Hora del día</h2>
      <div id="hora-display">12:00</div>
      <input type="range" id="slider" min="0" max="23" value="12" step="1">
      <div id="hora-labels">
        <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
      </div>
    </div>

    <div id="stats">
      <div class="stat-box">
        <div class="stat-val val-rojo" id="cnt-sat">—</div>
        <div class="stat-lab">saturadas</div>
      </div>
      <div class="stat-box">
        <div class="stat-val val-naranja" id="cnt-vac">—</div>
        <div class="stat-lab">vacías</div>
      </div>
      <div class="stat-box">
        <div class="stat-val val-verde" id="cnt-ok">—</div>
        <div class="stat-lab">ok</div>
      </div>
    </div>

    <div id="leyenda">
      <h2>Leyenda (% del tiempo en esa hora)</h2>
      <div class="leyenda-item"><div class="dot" style="background:#e74c3c"></div>Saturada ≥60% sin anclajes</div>
      <div class="leyenda-item"><div class="dot" style="background:#f39c12"></div>Tendencia a saturarse 30–60%</div>
      <div class="leyenda-item"><div class="dot" style="background:#e67e22"></div>Vacía ≥60% sin bicis</div>
      <div class="leyenda-item"><div class="dot" style="background:#27ae60"></div>OK &lt;30% problemas</div>
      <div class="leyenda-item"><div class="dot" style="background:#95a5a6"></div>Sin datos para esa hora</div>
      <div style="font-size:0.72rem; color:#777; margin-top:8px;">Tamaño del círculo = capacidad de la estación</div>
    </div>

    <div class="ranking">
      <h2>🔴 Top 10 más saturadas (global)</h2>
      <div id="list-sat"></div>
    </div>

    <div class="ranking">
      <h2>🟠 Top 10 más vacías (global)</h2>
      <div id="list-vac"></div>
    </div>

  </div>
</div>

<script>
const DATOS = {datos_json};
const TOP_SAT = {top_sat_json};
const TOP_VAC = {top_vac_json};

// ── Mapa ──────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([-33.4546, -70.5874], 14);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  subdomains: 'abcd', maxZoom: 19
}}).addTo(map);

// ── Markers ───────────────────────────────────────────────────────────────────
let markers = [];

function barHtml(pct, color) {{
  const w = Math.min(100, Math.max(0, pct));
  return `<div class="bar-bg"><div class="bar-fill" style="width:${{w}}%;background:${{color}}"></div></div>`;
}}

function popupHtml(e) {{
  if (e.pct_llena === null) {{
    return `<div class="popup-title">${{e.name}}</div>
      <div style="color:#aaa;font-size:0.82rem">Sin datos para esta hora</div>
      <div class="popup-row"><span class="label">Capacidad</span><span class="val">${{e.capacity}} anclajes</span></div>`;
  }}
  const satColor = e.pct_llena >= 60 ? '#e74c3c' : e.pct_llena >= 30 ? '#f39c12' : '#27ae60';
  const vacColor = e.pct_vacia >= 60 ? '#e67e22' : '#27ae60';
  return `<div class="popup-title">${{e.name}}</div>
    <div class="popup-row"><span class="label">Capacidad</span><span class="val">${{e.capacity}} anclajes</span></div>
    <div class="popup-row"><span class="label">Bicis prom.</span><span class="val">${{e.bikes_avg}}</span></div>
    <div class="popup-row"><span class="label">Anclajes prom.</span><span class="val">${{e.docks_avg}}</span></div>
    <div class="bar-wrap">
      <div class="bar-label">Saturada (sin dónde devolver): ${{e.pct_llena}}%</div>
      ${{barHtml(e.pct_llena, satColor)}}
    </div>
    <div class="bar-wrap" style="margin-top:6px">
      <div class="bar-label">Vacía (sin bicis para retirar): ${{e.pct_vacia}}%</div>
      ${{barHtml(e.pct_vacia, vacColor)}}
    </div>
    <div style="font-size:0.68rem;color:#666;margin-top:6px">${{e.n}} mediciones en esta hora</div>`;
}}

function renderHora(hora) {{
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  const estaciones = DATOS[hora] || [];
  let nSat = 0, nVac = 0, nOk = 0;

  estaciones.forEach(e => {{
    const radio = Math.max(5, Math.min(20, e.capacity * 0.9));
    const m = L.circleMarker([e.lat, e.lon], {{
      radius: radio,
      fillColor: e.color,
      color: '#fff',
      weight: 1,
      opacity: 0.8,
      fillOpacity: 0.75,
    }});
    m.bindPopup(popupHtml(e), {{maxWidth: 240}});
    m.addTo(map);
    markers.push(m);

    if (e.color === '#e74c3c' || e.color === '#f39c12') nSat++;
    else if (e.color === '#e67e22') nVac++;
    else if (e.color === '#27ae60') nOk++;
  }});

  document.getElementById('cnt-sat').textContent = nSat;
  document.getElementById('cnt-vac').textContent = nVac;
  document.getElementById('cnt-ok').textContent = nOk;
}}

// ── Slider ────────────────────────────────────────────────────────────────────
const slider = document.getElementById('slider');
const horaDisplay = document.getElementById('hora-display');

slider.addEventListener('input', function() {{
  const h = parseInt(this.value);
  horaDisplay.textContent = String(h).padStart(2,'0') + ':00';
  renderHora(h);
}});

// ── Rankings ──────────────────────────────────────────────────────────────────
function renderRanking(data, elId, colorClass) {{
  const el = document.getElementById(elId);
  el.innerHTML = data.map((d, i) =>
    `<div class="rank-item">
      <span class="rank-name">${{i+1}}. ${{d[0]}}</span>
      <span class="rank-pct ${{colorClass}}">${{d[1]}}%</span>
    </div>`
  ).join('');
}}
renderRanking(TOP_SAT, 'list-sat', 'rojo');
renderRanking(TOP_VAC, 'list-vac', 'naranja');

// ── Init ──────────────────────────────────────────────────────────────────────
renderHora(12);
</script>
</body>
</html>
"""

output_path = f"{OUTPUT_DIR}/mapa_disponibilidad.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Mapa generado: {output_path}")
print(f"Abre con: open {output_path}")
