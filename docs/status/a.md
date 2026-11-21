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

### Task 2 & 6 — Benchmark & Performance (Final 11,394 Cells & Real Towers)
- **Status: ✅ COMPLETE**
- **Test Setup**: Full final `cells.geojson` (11,394 population cells), real `dem_utm43n.tif` (1777×1923, 30 m resolution), 1 warmup + 10 timed runs per scenario.
- **Results**:
  - Direct `compute_signal()` (1 tower): **Median: 144.05 ms** (Min: 124.92 ms)
  - API `recompute()` (1 candidate): **Median: 144.82 ms** (Min: 122.64 ms)
  - API `recompute()` (5 candidates): **Median: 190.00 ms** (Min: 158.63 ms)
  - API `recompute()` (10 candidates): **Median: 234.69 ms** (Min: 207.81 ms)
  - Direct `compute_signal()` (5 towers): **Median: 166.74 ms** (Min: 154.69 ms)
  - Direct `compute_signal()` (10 towers): **Median: 209.98 ms** (Min: 203.29 ms)
- **Requirement (< 1000 ms)**: **PASS** across all scenarios (even 10 candidate towers recompute in ~235 ms, > 4× faster than the 1000 ms limit). No numba required.

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

## Calibration Sanity Check Findings (Exact Current config.json Run)

### Current Values in `contracts/config.json`:
- `frequency_mhz`: 900.0 (Okumura-Hata open-area formula)
- `tower_height_m`: 30.0 (ASSUMED)
- `rx_height_m`: 1.5
- `eirp_dbm`: 43.0 (ASSUMED 20 W conducted power)
- `gap_threshold_dbm`: -100.0
- `uncertain_band_db`: 6.0 (band: `[-106.0, -94.0]` dBm)
- `shadow_penalty_db`: 15.0 (ASSUMED flat terrain penalty)
- `max_radius_km`: 10.0

### 1. Flat Synthetic Terrain Signal vs Distance
Formula: **Okumura-Hata open-area (rural) @ 900 MHz**

| Distance | Path Loss (dB) | Signal (dBm) | State |
|---|---|---|---|
| **0.5 km** | 87.29 dB | -44.29 dBm | covered |
| **1.0 km** | 97.90 dB | -54.90 dBm | covered |
| **2.0 km** | 108.50 dB | -65.50 dBm | covered |
| **3.0 km** | 114.70 dB | -71.70 dBm | covered |
| **5.0 km** | 122.52 dB | -79.52 dBm | covered |
| **8.0 km** | 129.71 dB | -86.71 dBm | covered |
| **10.0 km** | 133.12 dB | -90.12 dBm | covered |

- **Covered edge** ($\ge -94.0$ dBm): **12.89 km**
- **Gap threshold** ($-100.0$ dBm): **19.07 km**
- **Gap edge** ($< -106.0$ dBm): **NEVER within 20 km**

### 2. Real DEM Analysis (Ridge-Top Tower at 1,293 m elev, 1,323 m antenna)
- **(a) Distance to threshold crossing in open terrain**: Never drops below $-100.0$ dBm within 10 km (signal at 10 km is $-90.1$ dBm).
- **(b) Median signal at 3–6 km**:
  - Unshadowed: **-76.6 dBm** ($n=1,754$)
  - Shadowed: **-93.2 dBm** ($n=4,290$)
  - Difference: **16.7 dB** (shadow penalty + elevation geometry)
- **(c) Shadowed cells below gap threshold ($-100.0$ dBm)**:
  - Total shadowed cells within 10 km: **14,150 / 20,000 (70.8%)**
  - Shadowed cells below threshold ($-100.0$ dBm): **4,704 / 14,150 (33.2%)**
  - Cells in definitive `gap` ($< -106.0$ dBm): **0.0%** (minimum possible signal at 10 km with shadow penalty is $-90.12 - 15 = -105.12$ dBm, which sits inside the uncertain band $[-106, -94]$ dBm).
- **Overall state shares across 20,000 samples**:
  - `covered`: 57.8% (11,568)
  - `uncertain`: 42.2% (8,432)
  - `gap`: 0.0% (0)

---

## Verdict (3 Lines)
1. **Open terrain is covered out to 10+ km** (flat crossing at 19.1 km), well beyond the 10 km radius.
2. **At 3–6 km, shadowed cells are heavily degraded** (median $-93.2$ dBm vs $-76.6$ dBm unshadowed, $-16.7$ dB drop), but sit mostly in the `uncertain` band.
3. **No definitive gaps ($< -106$ dBm) appear under 900 MHz open-area** because path loss is too low, meaning rural gaps are suppressed without calibration tuning; all values are **ASSUMPTIONS**.

---

## PENDING CHANGE REQUEST: Propagation Calibration Tuning
- **Issue**: Under pure 900 MHz open-area (rural) with EIRP 43 dBm, signal at 10 km is $-90.1$ dBm. Even with the 15 dB shadow penalty, maximum loss yields $-105.1$ dBm, so $0\%$ of cells ever classify as `gap` ($< -106$ dBm). The map shows only `covered` and `uncertain`, defeating gap detection.
- **Proposed Calibrated Pairs (ASSUMPTIONS — not measured)**:
  - **Option A (Suburban / Vegetated Hata at 900 MHz)**: Use Okumura-Hata Suburban formula (representing heavy Western Ghats foliage/hills) with `eirp_dbm: 43.0` and `gap_threshold_dbm: -100.0` (band `[-106, -94]` dBm).
    - Result: Covered to ~3.8 km, uncertain 3.8–8.4 km, gap beyond 8.4 km. Realistic balance for 10 km cells.
  - **Option B (1800 MHz Macro with realistic EIRP)**: Set `frequency_mhz: 1800.0`, `eirp_dbm: 56.0` (43 dBm transmitter + 15 dBi directional antenna gain - 2 dB feeder loss), and `gap_threshold_dbm: -105.0` (band `[-111, -99]` dBm).
    - Result: Covered to ~3.2 km, uncertain 3.2–6.8 km, gap beyond 6.8 km.
- **Affected Roles**: Dev A (formula dispatch/parameters), Dev B (ranking & API), Dev C (map legend).

---

## Review of Dev B's `api/main.py`
* Clean architecture: directly imports `compute_signal` and `classify_state` from `pipeline.model.engine`.
* Loads `config.json` dynamically for propagation tunables.
* Caches DEM and baseline cells in memory at startup.
* Endpoints provided: `/health`, `/config`, `/towers`, `/candidates`, `/clusters`, and `POST /recompute`.
* `POST /recompute` is idempotent, correctly calculates newly covered population, and executes in ~29 ms.
