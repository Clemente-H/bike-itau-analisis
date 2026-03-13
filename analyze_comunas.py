"""
Análisis por comuna de Bike Itaú — Santiago
Genera:
  - output/resumen_comunas.csv
  - output/saturacion_por_comuna.png
  - output/horario_por_comuna.png
  - output/barrio_italia.png
"""

import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches

DATA_FILE = "data/station_status.csv"
OUTPUT_DIR = "output"
MIN_SNAPSHOTS = 10
LAT_CHILE_MIN, LAT_CHILE_MAX = -56.0, -17.0  # fuera = GPS basura

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 1. Cargar y limpiar ────────────────────────────────────────────────────────

df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
df["hora"] = df["timestamp"].dt.hour

# Filtrar GPS inválidos (e.g. "Galpon - 459" está en Madrid)
df = df[(df["lat"] >= LAT_CHILE_MIN) & (df["lat"] <= LAT_CHILE_MAX)]

# Filtrar estaciones fantasma
snaps = df.groupby("station_id")["timestamp"].count()
validas = snaps[snaps >= MIN_SNAPSHOTS].index
df = df[df["station_id"].isin(validas) & (df["capacity"] > 0)]

print(f"Estaciones válidas: {df['station_id'].nunique()}")

# ── 2. Asignar comuna por prefijo del nombre ────────────────────────────────────

COMUNAS = {
    r"^N\d":   "Ñuñoa",
    r"^P\d":   "Providencia",
    r"^LC\d":  "Las Condes",
    r"^I\d":   "Independencia",
    r"^V\d":   "Vitacura",
}

def asignar_comuna(nombre):
    for patron, comuna in COMUNAS.items():
        if re.match(patron, nombre.strip()):
            return comuna
    return "Otra"

df["comuna"] = df["station_name"].apply(asignar_comuna)

dist = df.groupby("comuna")["station_id"].nunique().sort_values(ascending=False)
print("\nEstaciones por comuna:")
print(dist.to_string())

# ── 3. Métricas por estación ────────────────────────────────────────────────────

metricas = df.groupby(["station_id", "station_name", "comuna"]).agg(
    pct_llena=("docks_available", lambda x: (x == 0).mean()),
    pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
    bikes_avg=("bikes_available", "mean"),
    docks_avg=("docks_available", "mean"),
    capacity=("capacity", "first"),
).reset_index()

# ── 4. Resumen por comuna ───────────────────────────────────────────────────────

resumen = metricas.groupby("comuna").agg(
    n_estaciones=("station_id", "count"),
    pct_llena_avg=("pct_llena", "mean"),
    pct_vacia_avg=("pct_vacia", "mean"),
    pct_llena_max=("pct_llena", "max"),
    bikes_avg=("bikes_avg", "mean"),
    docks_avg=("docks_avg", "mean"),
    pct_criticas=("pct_llena", lambda x: (x >= 0.6).mean()),
).reset_index()

resumen = resumen.sort_values("pct_llena_avg", ascending=False)
resumen.to_csv(f"{OUTPUT_DIR}/resumen_comunas.csv", index=False)
print(f"\nResumen comunas:")
print(resumen[["comuna","n_estaciones","pct_llena_avg","pct_vacia_avg","pct_criticas"]].to_string(index=False))

# ── 5. Gráfico: Saturación y vaciado por comuna ─────────────────────────────────

COLORES_COMUNAS = {
    "Ñuñoa":        "#e74c3c",
    "Providencia":  "#3498db",
    "Las Condes":   "#2ecc71",
    "Vitacura":     "#9b59b6",
    "Independencia":"#f39c12",
    "Otra":         "#95a5a6",
}

comunas_ord = resumen["comuna"].tolist()
colores = [COLORES_COMUNAS.get(c, "#aaa") for c in comunas_ord]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Disponibilidad de Bike Itaú por comuna\n(promedio de toda la semana)", fontsize=13, fontweight="bold")

# Saturación
ax = axes[0]
bars = ax.barh(resumen["comuna"], resumen["pct_llena_avg"] * 100, color=colores)
ax.axvline(40, color="red", linestyle="--", linewidth=1, alpha=0.6, label="Umbral crítico 40%")
ax.set_xlabel("% del tiempo sin anclajes libres (promedio de estaciones)")
ax.set_title("¿Dónde no puedo devolver mi bici?")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.invert_yaxis()
ax.legend(fontsize=8)
ax.set_xlim(0, 100)
for i, (bar, val) in enumerate(zip(bars, resumen["pct_llena_avg"])):
    ax.text(val * 100 + 1, bar.get_y() + bar.get_height() / 2,
            f"{val*100:.1f}%", va="center", fontsize=9)

# Vaciado
ax = axes[1]
bars = ax.barh(resumen["comuna"], resumen["pct_vacia_avg"] * 100, color=colores)
ax.axvline(40, color="orange", linestyle="--", linewidth=1, alpha=0.6, label="Umbral 40%")
ax.set_xlabel("% del tiempo sin bicis disponibles (promedio de estaciones)")
ax.set_title("¿Dónde no puedo retirar una bici?")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.invert_yaxis()
ax.legend(fontsize=8)
ax.set_xlim(0, 100)
for i, (bar, val) in enumerate(zip(bars, resumen["pct_vacia_avg"])):
    ax.text(val * 100 + 1, bar.get_y() + bar.get_height() / 2,
            f"{val*100:.1f}%", va="center", fontsize=9)

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/saturacion_por_comuna.png", dpi=150)
plt.close()
print(f"\nGráfico guardado: {OUTPUT_DIR}/saturacion_por_comuna.png")

# ── 6. Patrón horario por comuna ────────────────────────────────────────────────

comunas_principales = ["Ñuñoa", "Providencia", "Las Condes", "Vitacura"]
patron = df[df["comuna"].isin(comunas_principales)].groupby(["comuna", "hora"]).agg(
    pct_llena=("docks_available", lambda x: (x == 0).mean()),
).reset_index()

fig, ax = plt.subplots(figsize=(13, 5))
for comuna in comunas_principales:
    sub = patron[patron["comuna"] == comuna].sort_values("hora")
    ax.plot(sub["hora"], sub["pct_llena"] * 100,
            marker="o", markersize=5, linewidth=2,
            label=comuna, color=COLORES_COMUNAS[comuna])

ax.axhline(40, color="gray", linestyle="--", linewidth=1, alpha=0.5, label="Umbral crítico 40%")
ax.set_xlabel("Hora del día")
ax.set_ylabel("% del tiempo sin anclajes")
ax.set_title("Saturación por hora según comuna\n(% de snapshots sin anclajes libres)", fontweight="bold")
ax.set_xticks(range(0, 24))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.legend()
ax.grid(axis="y", alpha=0.3)
ax.set_ylim(0, 100)
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/horario_por_comuna.png", dpi=150)
plt.close()
print(f"Gráfico guardado: {OUTPUT_DIR}/horario_por_comuna.png")

# ── 7. Cercanías Barrio Italia — estaciones críticas ───────────────────────────
# Zona entre Av. Italia, Bustamante, Seminario y Marín (Providencia)
# Aproximado: lat [-33.449, -33.440], lon [-70.635, -70.618]

barrio_italia_mask = (
    (df["lat"].between(-33.449, -33.440)) &
    (df["lon"].between(-70.635, -70.618))
)
bi_ids = df[barrio_italia_mask]["station_id"].unique()

print(f"\nEstaciones detectadas en cercanías Barrio Italia ({len(bi_ids)}):")
bi_names = df[df["station_id"].isin(bi_ids)][["station_name","lat","lon"]].drop_duplicates()
print(bi_names.to_string(index=False))

if len(bi_ids) > 0:
    bi_metricas = metricas[metricas["station_id"].isin(bi_ids)].copy()

    # Patrón horario Barrio Italia
    bi_patron = df[df["station_id"].isin(bi_ids)].groupby(["station_name", "hora"]).agg(
        pct_llena=("docks_available", lambda x: (x == 0).mean()),
        pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
    ).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Cercanías Barrio Italia — Disponibilidad por hora y estación", fontsize=13, fontweight="bold")

    palette = plt.cm.tab10.colors
    estaciones_bi = bi_patron["station_name"].unique()

    for i, ax in enumerate(axes):
        metric = "pct_llena" if i == 0 else "pct_vacia"
        ylabel = "Sin anclajes (% del tiempo)" if i == 0 else "Sin bicis (% del tiempo)"
        title = "¿Dónde no puedo dejar la bici?" if i == 0 else "¿Dónde no hay bicis?"
        for j, est in enumerate(sorted(estaciones_bi)):
            sub = bi_patron[bi_patron["station_name"] == est].sort_values("hora")
            ax.plot(sub["hora"], sub[metric] * 100,
                    marker="o", markersize=4, linewidth=2,
                    label=est.replace("P", "").strip(), color=palette[j % 10])
        ax.axhline(40, color="gray", linestyle="--", linewidth=1, alpha=0.5)
        ax.set_xlabel("Hora del día")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(range(0, 24))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax.legend(fontsize=7, loc="upper left")
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/barrio_italia.png", dpi=150)
    plt.close()
    print(f"Gráfico guardado: {OUTPUT_DIR}/barrio_italia.png")

print("\nAnálisis por comunas completo.")
