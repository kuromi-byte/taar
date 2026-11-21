# Dev A — Model Engine Status
# Updated: Task 0, Task 1 (fallback/OpenCellID guidance), Calibration check, Benchmark, Ingestion pipeline

## Pilot Area
- Taluk: Sakleshpur, Hassan District, Karnataka
- BBox (WGS84): min_lon 75.60, max_lon 75.95, min_lat 12.80, max_lat 13.10
- Source of truth: `contracts/config.json`
- Internal CRS: `EPSG:32643` (UTM Zone 43N)

## Assumptions (all flagged "assumed")
| Item | Assumed Value | Reason |
|---|---|---|
| Frequency | 900 MHz (Okumura-Hata) or 1800 MHz (COST-231) | Configurable in `config.json` |
| Tower height | 30 m | No operator data; flagged `assumed=true` |
| EIRP | 43 dBm (20 W) | Baseline macrocell; see calibration notes |
| Shadow penalty | 15 dB (flat) | Diffraction loss behind ridges; not field measured |
| Gap threshold | -100 dBm (±6 dB uncertain band) | Evaluated in calibration; see CHANGE REQUEST below |
| Earth curvature | Ignored | Sagitta ≈ 8 m at 10 km; within DEM noise |

---

## Task Status Summary

### Task 0 — DEM Coverage
- **Status: ✅ COMPLETE**
- Tiles: N12E075, N12E076, N13E075, N13E076 downloaded and merged.
- Processed DEM: `data/processed/dem_utm43n.tif` (1777 × 1923 cells @ 30 m resolution, 0 NoData inside area).
- Elevation range: 89.5 m to 1376.5 m.

### Task 1 — Tower Data (OpenCellID & OSM Fallback)
- **Status: ⚠️ SPARSE FALLBACK IDENTIFIED**
- Overpass API query executed across 5 mirrors (mail.ru, private.coffee, lz4, overpass-api.de, kumi.systems) for buffered bbox [12.71, 75.51, 13.19, 76.04].
- Direct OpenStreetMap inspection confirmed 0 tagged mobile communication masts in the rural Western Ghats section of Sakleshpur.
- OpenCellID is REQUIRED for real crowdsourced tower coverage. See manual instructions below.

### Task 2 & 6 — Benchmark & Performance
- **Status: ✅ COMPLETE**
- Direct `compute_signal()` (720 rays × 333 steps = 239,760 samples + Hata + Shadows): **19.75 ms** (Min: 16.40 ms).
- Through API `recompute()`: **29.08 ms** (Min: 18.51 ms).
- Requirement (< 1000 ms): **PASS** ($34\times$ faster than target).

### Task 3 — Unit Tests
- **Status: ✅ COMPLETE**
- 11 unit tests passing (`pytest tests -v` in 1.32s).
- Covers Hata hand calculation, synthetic ridge shadow penalty, 10 km radius cutoff, best-server logic, state classification, API import, and data contracts.

### Task 4 — Core Model Functions
- **Status: ✅ COMPLETE**
- Importable functions in `pipeline.model.engine`: `compute_signal()` and `classify_state()`.
- Validated units, inputs, and best-server maximum power logic.

### Task 5 — Ingestion & State Shares
- **Status: ✅ READY (Waiting for Dev B's final cells_base.geojson)**
- Validator and enricher implemented in `pipeline/model/process_cells.py`.
- Outputs `data/processed/cells.geojson` and `web/public/data/cells.geojson` with `"meta": {"source": "worldpop"}`.
- Current mock baseline shares (900 cells):
  - Covered: 10.0% (90 cells)
  - Uncertain: 17.0% (153 cells)
  - Gap: 73.0% (657 cells)
  - Unknown: 0.0%

---

## Calibration Sanity Check Findings

### 1. Flat Terrain Crossing Distances
With `EIRP = 43 dBm` and `gap_threshold_dbm = -100 dBm` (Band: `[-106, -94] dBm`):
* **1800 MHz (COST-231 Hata)**:
  - Covered ($\ge -94\text{ dBm}$): only up to **1.06 km**!
  - Uncertain: 1.06 km to 2.31 km.
  - Gap ($< -106\text{ dBm}$): **beyond 2.31 km**!
  - *Assessment*: Too pessimistic for rural macrocells where inter-site distances are 5–10 km.
* **900 MHz (Okumura-Hata Suburban)**:
  - Covered ($\ge -94\text{ dBm}$): up to **3.83 km**.
  - Uncertain: 3.83 km to 8.40 km.
  - Gap ($< -106\text{ dBm}$): **beyond 8.40 km**.
  - *Assessment*: Balanced for a 10 km maximum sweep radius.
* **900 MHz (Okumura-Hata Open/Rural)**:
  - Signal at 10 km is **-90.12 dBm** (never drops below -100 dBm on flat ground).
  - *Assessment*: On flat terrain, no gaps appear; gaps only appear when blocked by terrain shadows.

### 2. Real DEM Ridge-Top Shadowing
- Ridge tower at UTM (572533.6, 1431330.7), elevation 1,293.3 m (antenna 1,323.3 m).
- **70.66% of surrounding ground points within 10 km are shadowed** behind adjacent ridges and deep valleys.

---

## CHANGE REQUEST: Propagation Calibration Tuning
* **Issue**: At 1800 MHz, EIRP = 43 dBm only accounts for transmitter power (20W) without directional antenna gain (typically +15 to +18 dBi) or realistic macro link budgets. Consequently, cell coverage drops off at only 2.3 km, making even flat terrain appear as 90% dead zone. Conversely, at 900 MHz open-area, signal never drops below -100 dBm within 10 km.
* **Proposal**:
  - **Option 1 (Realistic Macro EIRP at 1800 MHz)**: Set `eirp_dbm: 56.0` (43 dBm conducted + 15 dBi antenna gain - 2 dB loss) with `gap_threshold_dbm: -105.0` (band: `[-111, -99] dBm`). Gives covered radius ~3.0 km, gap beyond 6.5 km.
  - **Option 2 (Suburban Baseline at 900 MHz)**: Use Okumura-Hata Suburban with `eirp_dbm: 43.0` and `gap_threshold_dbm: -100.0`. Gives covered radius ~3.8 km, gap beyond 8.4 km.
* **Affected Roles**: Dev A (model parameters), Dev B (API ranking threshold), Dev C (heatmap calibration legend).

---

## Review of Dev B's `api/main.py`
* Clean architecture: directly imports `compute_signal` and `classify_state` from `pipeline.model.engine`.
* Loads `config.json` dynamically for propagation tunables.
* Caches DEM and baseline cells in memory at startup.
* Endpoints provided: `/health`, `/config`, `/towers`, `/candidates`, `/clusters`, and `POST /recompute`.
* `POST /recompute` is idempotent, correctly calculates newly covered population, and executes in ~29 ms.
