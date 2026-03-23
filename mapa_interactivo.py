"""
Genera output/mapa_disponibilidad.html y docs/index.html
Mapa interactivo por franja horaria para ver disponibilidad de Bike Itaú por estación.

Franjas:
  Madrugada  0–6
  Mañana     7–11
  Mediodía   12–14
  Tarde      15–19
  Noche      20–23

Color de círculos (basado en % de veces que llegamos y estaba sin anclajes/bicis):
  Rojo      → sin dónde dejar la bici ≥35% de las veces
  Amarillo  → riesgo de no encontrar lugar 15–35%
  Azul      → sin bicis disponibles ≥35% de las veces
  Verde     → sin problemas (<15%)
  Gris      → sin datos para esa franja

Tamaño del círculo proporcional a la capacidad de la estación.
"""

import json
import os
import pandas as pd

DATA_FILE = "data/station_status.csv"
OUTPUT_DIR = "output"
MIN_SNAPSHOTS = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 1. Cargar y limpiar ────────────────────────────────────────────────────────

df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
df["hora"] = df["timestamp"].dt.hour

# Filtrar estaciones fantasma (capacity=0 o GPS inválido o muy pocos snapshots)
df = df[(df["lat"] >= -56) & (df["lat"] <= -17)]
snaps = df.groupby("station_id")["timestamp"].count()
estaciones_validas = snaps[snaps >= MIN_SNAPSHOTS].index
df = df[df["station_id"].isin(estaciones_validas) & (df["capacity"] > 0)]

print(f"Estaciones válidas: {df['station_id'].nunique()}")
print(f"Estaciones filtradas (fantasmas): {len(snaps) - df['station_id'].nunique()}")

# ── 2. Franjas horarias ────────────────────────────────────────────────────────

FRANJAS = {
    "Madrugada": (0, 6),
    "Mañana":    (7, 11),
    "Mediodía":  (12, 14),
    "Tarde":     (15, 19),
    "Noche":     (20, 23),
}
FRANJA_DEFAULT = "Tarde"
FRANJA_ORDEN = list(FRANJAS.keys())

def asignar_franja(hora):
    for nombre, (h_ini, h_fin) in FRANJAS.items():
        if h_ini <= hora <= h_fin:
            return nombre
    return None

df["franja"] = df["hora"].apply(asignar_franja)
df = df[df["franja"].notna()]

# ── 3. Coordenadas y capacidad por estación ────────────────────────────────────

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

# ── 4. Métricas por estación × franja ─────────────────────────────────────────

por_franja = (
    df.groupby(["station_id", "franja"])
    .agg(
        pct_llena=("docks_available", lambda x: (x == 0).mean()),
        pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
        bikes_avg=("bikes_available", "mean"),
        docks_avg=("docks_available", "mean"),
        n=("timestamp", "count"),
    )
    .reset_index()
)
por_franja = por_franja.merge(estaciones, on="station_id")

# ── 5. Color según umbrales ────────────────────────────────────────────────────

def color_estado(pct_llena, pct_vacia):
    if pct_llena >= 0.35:
        return "#e74c3c"   # rojo: sin dónde dejar
    elif pct_vacia >= 0.35:
        return "#3498db"   # azul: sin bicis
    elif pct_llena >= 0.15:
        return "#f1c40f"   # amarillo: riesgo
    else:
        return "#27ae60"   # verde: ok

# ── 6. Construir datos para el JS (dict franja → lista estaciones) ─────────────

datos_por_franja = {}
for franja in FRANJA_ORDEN:
    sub = por_franja[por_franja["franja"] == franja]
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
    # Estaciones sin datos en esta franja → gris
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
                "color": "#bdc3c7",
            })
    datos_por_franja[franja] = lista

# ── 7. Top 10 globales ─────────────────────────────────────────────────────────

resumen = (
    df.groupby("station_id")
    .agg(
        name=("station_name", "first"),
        pct_llena=("docks_available", lambda x: (x == 0).mean()),
        pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
    )
    .reset_index()
)
top_saturadas = resumen.nlargest(10, "pct_llena")[["name", "pct_llena"]].values.tolist()
top_saturadas = [[n, round(p * 100, 1)] for n, p in top_saturadas]
top_vacias = resumen.nlargest(10, "pct_vacia")[["name", "pct_vacia"]].values.tolist()
top_vacias = [[n, round(p * 100, 1)] for n, p in top_vacias]

# ── 8. Generar HTML ─────────────────────────────────────────────────────────────

datos_json      = json.dumps(datos_por_franja, ensure_ascii=False)
franjas_json    = json.dumps(FRANJA_ORDEN, ensure_ascii=False)
top_sat_json    = json.dumps(top_saturadas, ensure_ascii=False)
top_vac_json    = json.dumps(top_vacias, ensure_ascii=False)
default_franja  = json.dumps(FRANJA_DEFAULT, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bike Itaú — Disponibilidad por franja horaria</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f4f8; color: #222; }}

  #header {{ padding: 12px 20px; background: #fff; border-bottom: 2px solid #e74c3c; display: flex; align-items: center; gap: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  #header h1 {{ font-size: 1.05rem; font-weight: 700; }}
  #header .sub {{ font-size: 0.72rem; color: #999; }}

  #container {{ display: flex; height: calc(100vh - 54px); }}
  #map {{ flex: 1; }}
  #sidebar {{ width: 310px; background: #f4f4f8; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; }}

  .card {{ background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card-title {{ font-size: 0.72rem; color: #999; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}

  /* Selector franjas */
  #franja-btns {{ display: flex; flex-direction: column; gap: 6px; }}
  .franja-btn {{
    padding: 9px 12px; border: 2px solid #e8e8e8; border-radius: 8px;
    background: #fff; cursor: pointer; font-size: 0.85rem; color: #444;
    display: flex; justify-content: space-between; align-items: center;
    transition: all 0.15s;
  }}
  .franja-btn:hover {{ border-color: #e74c3c; color: #e74c3c; }}
  .franja-btn.active {{ border-color: #e74c3c; background: #fff5f5; color: #e74c3c; font-weight: 700; }}
  .franja-horas {{ font-size: 0.7rem; color: #bbb; }}
  .franja-btn.active .franja-horas {{ color: #e74c3c; opacity: 0.7; }}

  /* Stats */
  #stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }}
  .stat-box {{ background: #fff; border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .stat-val {{ font-size: 1.5rem; font-weight: 800; }}
  .stat-lab {{ font-size: 0.62rem; color: #999; margin-top: 2px; line-height: 1.3; }}

  /* Leyenda */
  .leyenda-item {{ display: flex; align-items: flex-start; gap: 9px; margin-bottom: 9px; font-size: 0.81rem; color: #333; line-height: 1.35; }}
  .dot {{ width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; margin-top: 2px; }}
  .leyenda-nota {{ font-size: 0.7rem; color: #aaa; margin-top: 6px; line-height: 1.4; }}

  /* Rankings */
  .rank-item {{ display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.78rem; }}
  .rank-item:last-child {{ border-bottom: none; }}
  .rank-name {{ flex: 1; padding-right: 8px; color: #444; }}
  .rank-pct {{ font-weight: 700; font-size: 0.85rem; }}
  .rojo {{ color: #e74c3c; }}
  .azul {{ color: #3498db; }}

  /* Popup */
  .leaflet-popup-content-wrapper {{ border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.15); }}
  .popup-title {{ font-weight: 700; font-size: 0.92rem; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #eee; }}
  .popup-row {{ display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 3px; color: #555; }}
  .popup-row b {{ color: #222; }}
  .bar-wrap {{ margin-top: 8px; }}
  .bar-label {{ font-size: 0.7rem; color: #888; margin-bottom: 3px; }}
  .bar-bg {{ background: #eee; border-radius: 4px; height: 7px; }}
  .bar-fill {{ height: 7px; border-radius: 4px; }}
  .popup-note {{ font-size: 0.67rem; color: #bbb; margin-top: 8px; }}
</style>
</head>
<body>

<div id="header">
  <div>
    <h1>🚲 Bike Itaú Santiago — Disponibilidad por franja horaria</h1>
    <div class="sub">Datos recolectados 6–23 Mar 2026 · 359 snapshots · 17 días · 199 estaciones</div>
  </div>
</div>

<div id="container">
  <div id="map"></div>
  <div id="sidebar">

    <div class="card">
      <div class="card-title">Franja horaria</div>
      <div id="franja-btns"></div>
    </div>

    <div id="stats">
      <div class="stat-box">
        <div class="stat-val rojo" id="cnt-sat">—</div>
        <div class="stat-lab">sin dónde dejar</div>
      </div>
      <div class="stat-box">
        <div class="stat-val azul" id="cnt-vac">—</div>
        <div class="stat-lab">sin bicis</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" style="color:#27ae60" id="cnt-ok">—</div>
        <div class="stat-lab">sin problemas</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">¿Qué significa cada color?</div>
      <div class="leyenda-item">
        <div class="dot" style="background:#e74c3c"></div>
        <div><b>Sin dónde dejar la bici</b> — más de 1 de cada 3 veces que llegamos a esta estación en esta franja, estaba llena (0 anclajes libres)</div>
      </div>
      <div class="leyenda-item">
        <div class="dot" style="background:#f1c40f"></div>
        <div><b>Riesgo de no encontrar lugar</b> — entre 15% y 35% de las veces estaba llena. Hay que tener cuidado.</div>
      </div>
      <div class="leyenda-item">
        <div class="dot" style="background:#3498db"></div>
        <div><b>Sin bicis disponibles</b> — más de 1 de cada 3 veces no había bicis para retirar</div>
      </div>
      <div class="leyenda-item">
        <div class="dot" style="background:#27ae60"></div>
        <div><b>Sin problemas</b> — casi siempre hay bicis y anclajes disponibles</div>
      </div>
      <div class="leyenda-item">
        <div class="dot" style="background:#bdc3c7"></div>
        <div><b>Sin datos</b> — no se registraron mediciones en esta franja</div>
      </div>
      <div class="leyenda-nota">El tamaño del círculo indica la capacidad de la estación (cantidad de anclajes totales).</div>
    </div>

    <div class="card">
      <div class="card-title">🔴 Top 10 más saturadas (promedio global)</div>
      <div id="list-sat"></div>
    </div>

    <div class="card">
      <div class="card-title">🔵 Top 10 más vacías (promedio global)</div>
      <div id="list-vac"></div>
    </div>

  </div>
</div>

<script>
const DATOS   = {datos_json};
const FRANJAS = {franjas_json};
const TOP_SAT = {top_sat_json};
const TOP_VAC = {top_vac_json};
const FRANJA_DEFAULT = {default_franja};

const FRANJA_HORAS = {{
  "Madrugada": "0:00 – 6:59",
  "Mañana":    "7:00 – 11:59",
  "Mediodía":  "12:00 – 14:59",
  "Tarde":     "15:00 – 19:59",
  "Noche":     "20:00 – 23:59",
}};

// ── Mapa ──────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([-33.4546, -70.5874], 13);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: 'abcd', maxZoom: 19
}}).addTo(map);

// ── Botones de franja ─────────────────────────────────────────────────────────
const btnContainer = document.getElementById('franja-btns');
FRANJAS.forEach(f => {{
  const btn = document.createElement('button');
  btn.className = 'franja-btn' + (f === FRANJA_DEFAULT ? ' active' : '');
  btn.dataset.franja = f;
  btn.innerHTML = `<span>${{f}}</span><span class="franja-horas">${{FRANJA_HORAS[f]}}</span>`;
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.franja-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderFranja(f);
  }});
  btnContainer.appendChild(btn);
}});

// ── Markers ───────────────────────────────────────────────────────────────────
let markers = [];

function barHtml(pct, color) {{
  const w = Math.min(100, Math.max(0, pct || 0));
  return `<div class="bar-bg"><div class="bar-fill" style="width:${{w}}%;background:${{color}}"></div></div>`;
}}

function popupHtml(e, franja) {{
  if (e.pct_llena === null) {{
    return `<div class="popup-title">${{e.name}}</div>
      <div style="color:#aaa;font-size:0.8rem;margin-bottom:6px">Sin datos para esta franja</div>
      <div class="popup-row"><span>Capacidad</span><b>${{e.capacity}} anclajes</b></div>`;
  }}
  const satColor = e.pct_llena >= 35 ? '#e74c3c' : e.pct_llena >= 15 ? '#f1c40f' : '#27ae60';
  const vacColor = e.pct_vacia >= 35 ? '#3498db' : '#27ae60';
  return `
    <div class="popup-title">${{e.name}}</div>
    <div class="popup-row"><span>Capacidad total</span><b>${{e.capacity}} anclajes</b></div>
    <div class="popup-row"><span>Bicis disponibles (prom.)</span><b>${{e.bikes_avg}}</b></div>
    <div class="popup-row"><span>Anclajes libres (prom.)</span><b>${{e.docks_avg}}</b></div>
    <div class="bar-wrap">
      <div class="bar-label">Estaba llena (sin anclajes) en el ${{e.pct_llena}}% de las mediciones</div>
      ${{barHtml(e.pct_llena, satColor)}}
    </div>
    <div class="bar-wrap" style="margin-top:6px">
      <div class="bar-label">Estaba vacía (sin bicis) en el ${{e.pct_vacia}}% de las mediciones</div>
      ${{barHtml(e.pct_vacia, vacColor)}}
    </div>
    <div class="popup-note">Basado en ${{e.n}} mediciones en la franja "${{franja}}"</div>`;
}}

function renderFranja(franja) {{
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  const estaciones = DATOS[franja] || [];
  let nSat = 0, nVac = 0, nOk = 0;

  estaciones.forEach(e => {{
    const radio = Math.max(5, Math.min(22, e.capacity * 0.85));
    const m = L.circleMarker([e.lat, e.lon], {{
      radius: radio,
      fillColor: e.color,
      color: '#fff',
      weight: 1.5,
      opacity: 0.9,
      fillOpacity: 0.82,
    }});
    m.bindPopup(popupHtml(e, franja), {{maxWidth: 250}});
    m.addTo(map);
    markers.push(m);

    if (e.color === '#e74c3c' || e.color === '#f1c40f') nSat++;
    else if (e.color === '#3498db') nVac++;
    else if (e.color === '#27ae60') nOk++;
  }});

  document.getElementById('cnt-sat').textContent = nSat;
  document.getElementById('cnt-vac').textContent = nVac;
  document.getElementById('cnt-ok').textContent = nOk;
}}

// ── Rankings ──────────────────────────────────────────────────────────────────
function renderRanking(data, elId, cls) {{
  document.getElementById(elId).innerHTML = data.map((d, i) =>
    `<div class="rank-item">
      <span class="rank-name">${{i+1}}. ${{d[0]}}</span>
      <span class="rank-pct ${{cls}}">${{d[1]}}%</span>
    </div>`
  ).join('');
}}
renderRanking(TOP_SAT, 'list-sat', 'rojo');
renderRanking(TOP_VAC, 'list-vac', 'azul');

// ── Init ──────────────────────────────────────────────────────────────────────
renderFranja(FRANJA_DEFAULT);
</script>
</body>
</html>
"""

output_path = f"{OUTPUT_DIR}/mapa_disponibilidad.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Mapa generado: {output_path}")
print(f"GitHub Pages:  docs/index.html")
print(f"Abre con: open {output_path}")
