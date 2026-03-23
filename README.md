# Bike Itaú — Análisis de disponibilidad en Santiago

Recolección y análisis automatizado de datos públicos de disponibilidad de [Bike Itaú (Tembici)](https://www.bikeitau.cl/) en Santiago, usando la API estándar [GBFS](https://gbfs.org/).

**Objetivo:** identificar patrones de saturación y vaciado por estación, hora y comuna, para evidenciar dónde el sistema falla a los usuarios.

---

## Estructura

```
collect.py            # Recolector: llama a la API GBFS y guarda en data/
analyze.py            # Análisis general: saturación, vaciado, patrón horario
analyze_comunas.py    # Análisis por comuna y Barrio Italia
mapa_interactivo.py   # Genera output/mapa_disponibilidad.html
requirements.txt
data/
  station_status.csv  # Datos acumulados (CSV append, commiteado por el bot)
output/               # Gráficos y mapa generados
.github/workflows/
  collect.yml         # GitHub Actions: corre collect.py cada ~30 min
```

---

## Cómo usar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Recolección automática

El workflow `.github/workflows/collect.yml` corre `collect.py` cada 30 minutos vía GitHub Actions y hace commit del CSV automáticamente. No requiere configuración adicional — basta con tener el repositorio en GitHub con Actions habilitado.

> **Nota:** GitHub puede throttlear el cron schedule; en la práctica los runs ocurren cada ~1 hora.

### 3. Análisis (local, después de acumular datos)

```bash
python analyze.py            # gráficos generales → output/
python analyze_comunas.py    # análisis por comuna → output/
python mapa_interactivo.py   # mapa HTML interactivo → output/mapa_disponibilidad.html
```

---

## Datos

- **Fuente:** API pública GBFS de Tembici — `santiago.publicbikesystem.net`
- **Frecuencia:** ~1 snapshot/hora por estación
- **Variables:** bicis disponibles, anclajes libres, capacidad, coordenadas
- **Sin datos personales:** solo disponibilidad agregada por estación

---

## Análisis y conclusiones

> Datos recolectados del 6 al 23 de marzo de 2026 (17 días, ~359 snapshots, 198 estaciones válidas).

### Ñuñoa es la comuna más saturada de la red

En Ñuñoa, las estaciones no tienen anclajes libres el **35% del tiempo en promedio** — más de cinco veces que Las Condes (6.5%) y casi sin comparación con Vitacura (0.4%). Esto significa que un usuario que llega pedaleando a Ñuñoa tiene una probabilidad significativa de no encontrar dónde dejar su bici.

| Comuna | Sin anclajes (prom.) | Sin bicis (prom.) | Estaciones |
|---|---|---|---|
| Ñuñoa | **35.2%** | 0.1% | 20 |
| Providencia | 26.9% | 0.6% | 67 |
| Independencia | 12.1% | 0.0% | 3 |
| Las Condes | 6.5% | 7.4% | 95 |
| Vitacura | 0.4% | 14.7% | 12 |

### Vitacura tiene el problema inverso

Las estaciones de Vitacura están vacías el 13% del tiempo — pocas bicis disponibles para retirar — pero casi nunca saturadas. Hay demanda de salida pero no de llegada, lo que sugiere un flujo neto desde Vitacura hacia las comunas del sur.

### Cercanías Barrio Italia: 7 estaciones, todas bajo presión

Las 7 estaciones del área entre Av. Italia, Bustamante, Seminario y Marín (P02, P11, P34, P35, P41, P56, P70) muestran picos de saturación en horario vespertino. El patrón es consistente: llenas en la tarde, cuando la gente vuelve al barrio.

### El problema de fondo: redistribución insuficiente

La asimetría entre comunas no es un problema de cantidad de estaciones — Las Condes tiene 95 estaciones y Ñuñoa solo 20, pero Ñuñoa tiene mayor saturación. El problema es que los camiones de redistribución no están operando con suficiente frecuencia (o en los horarios correctos) para vaciar las estaciones saturadas de Ñuñoa/Providencia.

### Recomendaciones al operador

1. **Aumentar frecuencia de redistribución en Ñuñoa**, especialmente en horario vespertino (17:00–20:00).
2. **Agregar estaciones en Ñuñoa**: la demanda de llegada supera la capacidad instalada (20 estaciones para una de las comunas más densas).
3. **Usar el flujo Vitacura → Ñuñoa/Providencia**: los camiones podrían aprovechar el sentido natural del flujo — sacar bicis de Ñuñoa llena y llevarlas a Vitacura vacía.

---

## Outputs generados

| Archivo | Descripción |
|---|---|
| `output/saturacion_top20.png` | Top 20 estaciones sin anclajes |
| `output/vaciado_top20.png` | Top 20 estaciones sin bicis |
| `output/patron_horario.png` | Saturación/vaciado promedio por hora (red completa) |
| `output/saturacion_por_comuna.png` | Comparación de comunas |
| `output/horario_por_comuna.png` | Patrón horario desglosado por comuna |
| `output/barrio_italia.png` | Detalle de las 7 estaciones de cercanías Barrio Italia |
| `output/mapa_disponibilidad.html` | Mapa interactivo con slider de hora |
