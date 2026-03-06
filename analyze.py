"""
Análisis de saturación Bike Itaú - Santiago
Ejecutar después de recolectar ~7 días de datos.

Genera:
  - output/resumen_estaciones.csv
  - output/saturacion_top20.png
  - output/vaciado_top20.png
  - output/patron_horario.png
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

DATA_FILE = "data/station_status.csv"
OUTPUT_DIR = "output"
SATURACION_UMBRAL = 0.40  # >40% del tiempo sin anclajes → saturada
VACIADO_UMBRAL = 0.40     # >40% del tiempo sin bicis → vacía

# ──────────────────────────────────────────────
# 1. Cargar datos
# ──────────────────────────────────────────────

df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
df["hora"] = df["timestamp"].dt.hour

print(f"Snapshots: {df['timestamp'].nunique()}")
print(f"Estaciones: {df['station_id'].nunique()}")
print(f"Período: {df['timestamp'].min()} → {df['timestamp'].max()}")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# 2. Métricas por estación
# ──────────────────────────────────────────────

total_snapshots = df.groupby("station_id")["timestamp"].count().rename("n_snapshots")

metricas = df.groupby(["station_id", "station_name"]).agg(
    pct_llena=("docks_available", lambda x: (x == 0).mean()),
    pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
    bikes_avg=("bikes_available", "mean"),
    docks_avg=("docks_available", "mean"),
    capacity=("capacity", "first"),
).reset_index()

metricas["saturacion_avg"] = metricas["bikes_avg"] / metricas["capacity"]

metricas = metricas.merge(total_snapshots, on="station_id")
metricas = metricas.sort_values("pct_llena", ascending=False)

metricas.to_csv(f"{OUTPUT_DIR}/resumen_estaciones.csv", index=False)
print(f"\nEstaciones guardadas en {OUTPUT_DIR}/resumen_estaciones.csv")

# Imprimir estaciones críticas
criticas = metricas[metricas["pct_llena"] >= SATURACION_UMBRAL]
print(f"\n--- Estaciones saturadas (>{SATURACION_UMBRAL*100:.0f}% del tiempo llenas): {len(criticas)} ---")
print(criticas[["station_name", "pct_llena", "pct_vacia", "capacity"]].to_string(index=False))

vacias = metricas[metricas["pct_vacia"] >= VACIADO_UMBRAL]
print(f"\n--- Estaciones vacías (>{VACIADO_UMBRAL*100:.0f}% del tiempo sin bicis): {len(vacias)} ---")
print(vacias[["station_name", "pct_vacia", "pct_llena", "capacity"]].to_string(index=False))

# ──────────────────────────────────────────────
# 3. Gráfico: Top 20 estaciones más saturadas
# ──────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 8))
top20_sat = metricas.nlargest(20, "pct_llena")
colors = ["#d62728" if v >= SATURACION_UMBRAL else "#1f77b4" for v in top20_sat["pct_llena"]]
ax.barh(top20_sat["station_name"], top20_sat["pct_llena"] * 100, color=colors)
ax.axvline(SATURACION_UMBRAL * 100, color="red", linestyle="--", linewidth=1, label=f"Umbral crítico {SATURACION_UMBRAL*100:.0f}%")
ax.set_xlabel("% del tiempo sin anclajes libres")
ax.set_title("Top 20 estaciones con mayor saturación\n(sin espacio para devolver bici)")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.legend()
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/saturacion_top20.png", dpi=150)
plt.close()
print(f"\nGráfico guardado: {OUTPUT_DIR}/saturacion_top20.png")

# ──────────────────────────────────────────────
# 4. Gráfico: Top 20 estaciones más vacías
# ──────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 8))
top20_vac = metricas.nlargest(20, "pct_vacia")
colors = ["#d62728" if v >= VACIADO_UMBRAL else "#ff7f0e" for v in top20_vac["pct_vacia"]]
ax.barh(top20_vac["station_name"], top20_vac["pct_vacia"] * 100, color=colors)
ax.axvline(VACIADO_UMBRAL * 100, color="red", linestyle="--", linewidth=1, label=f"Umbral crítico {VACIADO_UMBRAL*100:.0f}%")
ax.set_xlabel("% del tiempo sin bicis disponibles")
ax.set_title("Top 20 estaciones con mayor vaciado\n(sin bicis para retirar)")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.legend()
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/vaciado_top20.png", dpi=150)
plt.close()
print(f"Gráfico guardado: {OUTPUT_DIR}/vaciado_top20.png")

# ──────────────────────────────────────────────
# 5. Gráfico: Patrón horario de saturación
# ──────────────────────────────────────────────

patron = df.groupby("hora").agg(
    pct_llena=("docks_available", lambda x: (x == 0).mean()),
    pct_vacia=("bikes_available", lambda x: (x == 0).mean()),
).reset_index()

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(patron["hora"], patron["pct_llena"] * 100, marker="o", label="% estaciones llenas (sin anclajes)", color="#d62728")
ax.plot(patron["hora"], patron["pct_vacia"] * 100, marker="o", label="% estaciones vacías (sin bicis)", color="#ff7f0e")
ax.set_xlabel("Hora del día")
ax.set_ylabel("% de estaciones")
ax.set_title("Patrón horario de saturación y vaciado\n(promedio de toda la red)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.set_xticks(range(0, 24))
ax.legend()
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/patron_horario.png", dpi=150)
plt.close()
print(f"Gráfico guardado: {OUTPUT_DIR}/patron_horario.png")

print("\nAnalisis completo.")
