# Dev C (Frontend) Status - Gap-to-Brief

## Done
- **Upstream Merge & Conflict Resolution**:
  - Base version: `origin/main` (commit `dbd5478`).
  - Integrated Dev B's full frontend implementation (Map, shortlist, draggable pins, counter panel, brief and limitations modals). Clean merge with 0 unresolved git conflicts.
- **Rules Audit & Fixes (Committed in 3 focused commits)**:
  - *Audit Fix 1 (`9d15747`)*: Extracted pure, idempotent `applyRecompute(map, prevIdSet, changed)` into `web/src/utils/recompute.ts` with 6 Vitest unit tests covering shrinking responses, empty responses, invalid IDs, and double-drag stale footprint elimination.
  - *Audit Fix 2 (`646fb7f`)*: In `Map.tsx`, removed hardcoded signal numbers (-94 / -106 dBm) and bound color stops dynamically to `params.gap_threshold_dbm` ± `params.uncertain_band_db`. Added explicit grey (`#6b7280`) color mapping for `unknown` / `Unknown` states (never shown as gaps). Added dev recolor button (`testRecolorCell`).
  - *Audit Fix 3 (`ec158df`)*: Updated persistent badge to exact phrase `"Modeled, not measured"`. Added red sticky `"MOCK DATA"` banner triggered when `cells.geojson` has `meta.source == "mock"`. Implemented exact `/recompute` request payload `{"towers": [{"lat", "lon", "height_m", "power_dbm"}]}`. Handled API failure by displaying clear error message while preserving previous map state. Added candidate site inspector card with `height_m` and `power_dbm` sliders.
- **Task 1c Real File Verification (11,394 cells) [REAL]**:
  - **Data Audit (web/public/data/cells.geojson)**:
    - Feature count: **11,394 cells** (full Sakleshpur taluk grid).
    - `meta`: `{ "source": "worldpop", "model": "Okumura-Hata/COST-231 + Polar Sweep Shadowing", "frequency_mhz": 900, "eirp_dbm": 43, "gap_threshold_dbm": -100, "uncertain_band_db": 6 }`.
    - ID Range: **1 .. 11394** (1-based integer indexing, verified supported across MapLibre and `applyRecompute`). Duplicate IDs: 0, Non-integer IDs: 0.
    - State Counts: `gap`: 10,176 (89.3%), `uncertain`: 721 (6.3%), `covered`: 308 (2.7%), `unknown`: 189 (1.7%).
    - Cells with `baseline_dbm == null`: 2,050 `gap` cells and 189 `unknown` cells (0 in `covered` / `uncertain`).
  - **Cross-File Integrity Check**:
    - `clusters.json`: 5 clusters with 4,934 cell IDs in range `[16, 10099]`. Missing in `cells.geojson`: **0**.
    - `candidates.json`: 5 candidates (`CAND-09`, `CAND-011`, `CAND-02`, `CAND-05`, `CAND-08`), all mapped to valid cluster IDs (`CL-01`, `CL-03`).
    - Property fields: all contract 2 required fields present (`pop`, `baseline_dbm`, `state`). Extra pipeline fields: `id`, `cx`, `cy`, `elev_m`, `slope_deg`, `road_km`, `tower_evidence`.
  - **Null Rendering Fix (Map.tsx & styleExpressions.ts)**:
    - Layer fill-color expression extracted to pure helper [`styleExpressions.ts`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/utils/styleExpressions.ts): cells with `baseline_dbm == null` and no feature-state override are colored strictly by their `state` property (`covered` -> `#10b981`, `uncertain` -> `#f59e0b`, `gap` -> `#ef4444`, `unknown` -> `#6b7280`), never defaulting to gap.
    - Popup text for null baseline dBm updated to exact string `"No modeled signal"`.
    - Unit tests: 8 tests in `styleExpressions.test.ts` verifying all state/dBm permutations.
  - **Real Dataset Performance Benchmark [REAL]**:
    - Context: Headless Chromium with CPU software WebGL (`ANGLE / SwiftShader Device LLVM 10.0.0`).
    - File size: **4.16 MB**.
    - Fetch + response.json() parse: **76.10 ms**.
    - Draw to idle: **20.60 ms** (Total load: **96.70 ms** -> **PASS**, target < 3.0 s).
    - 3s Pan/Zoom Avg FPS: **35.6 FPS** (worst frame: 66.60 ms) -> **PASS**, target ≥ 30.0 FPS.
    - Cells within 10.0 km radius of candidate `CAND-09` ($N$): **3,345 cells**.
    - `setFeatureState` Loop: median **0.60 ms** (p95: 0.80 ms).
    - `setFeatureState` + Idle: median **36.50 ms** (p95: 63.50 ms) -> **PASS**, target < 100.0 ms.
    - `removeFeatureState` Loop / Idle: median **0.40 ms** / **35.95 ms**.
    - `applyRecompute` Loop / Idle: median **0.90 ms** / **36.90 ms**.
    - Shrinking Response ($N \to N/2$) Stale Clear Check: **CONFIRMED**.
    - Unknown Cells Rendered: **189 cells** (all verified grey `#6b7280`).
    - Overall Real File Target Verdict: **PASS**.
- **Task 1 & 1b Synthetic Scale Performance Benchmarking**:
  - **Hardware & Render Context**: Run in headless Chromium with CPU software WebGL (`ANGLE / SwiftShader Vulkan 1.3.0`). Real GPU hardware numbers on the demo laptop will exceed these software-rasterized metrics.
  - **Unknown State Verification**: Verified that cells with `state: "unknown"` evaluate to `#6b7280` (grey) via the first `case` branch in the MapLibre layer expression and are **never** colored as gaps (`#ef4444`), regardless of feature-state or baseline dBm overrides. Rendered count: 350 (at 3.5k), 1,400 (at 14k), 3,000 (at 30k).
  - **Combined Benchmark Results (All Tagged SYNTHETIC)**:

| Metric / Target | 3,500 Cells (~10 km radius) | 14,000 Cells (~full taluk) | 30,000 Cells (headroom) | Target Condition | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Grid Generation & Parse** | 25.2 ms | 42.4 ms | 125.7 ms | — | — |
| **Draw to Idle** | 14.3 ms | 14.8 ms | 29.8 ms | — | — |
| **Initial Load Total** | **39.5 ms** | **57.2 ms** | **155.5 ms** | **< 3.0 s** | **PASS** |
| **3s Pan/Zoom Avg FPS** | **58.5 FPS** | **47.9 FPS** | **43.0 FPS** | **≥ 30.0 FPS** | **PASS** |
| **Worst Frame Time** | 66.7 ms | 50.1 ms | 66.6 ms | — | — |
| **Cells in 10 km Radius ($N$)** | 3,064 cells | 3,477 cells | 3,482 cells | ~3.5k mobile radius | — |
| **`setFeatureState` Loop (Median / p95)** | 0.8 ms / 1.0 ms | 0.6 ms / 0.8 ms | 0.9 ms / 1.2 ms | — | — |
| **`setFeatureState` + Idle Median** | **16.45 ms** | **25.70 ms** | **36.80 ms** | **< 100.0 ms** | **PASS** |
| **`setFeatureState` + Idle p95** | 24.1 ms | 42.5 ms | 54.9 ms | — | — |
| **`removeFeatureState` Loop / Idle Med.** | 0.6 ms / 16.5 ms | 0.5 ms / 24.8 ms | 0.7 ms / 37.3 ms | — | — |
| **`applyRecompute` Loop / Idle Med.** | 0.9 ms / 16.25 ms | 1.0 ms / 24.55 ms | 1.2 ms / 36.75 ms | — | — |
| **Shrinking Footprint Stale Clear** | **CONFIRMED** | **CONFIRMED** | **CONFIRMED** | $N \to N/2$ stale drop | **PASS** |
| **Unknown Cells Rendered** | 350 cells (grey) | 1,400 cells (grey) | 3,000 cells (grey) | Verified `#6b7280` | **PASS** |
| **Overall Scale Target Verdict** | **PASS** | **PASS** | **PASS** | All criteria met | **PASS** |

## In Progress
- End-to-end integration with live FastAPI server on port 8000.

## Assumptions
- Pilot area is **Sakleshpur Taluk** (Hassan District, Western Ghats, Karnataka).
  - Center: `[75.775, 12.95]`
  - Bounding Box (WGS84): `[75.60, 12.80, 75.95, 13.10]`
  - Signal threshold: `-100.0 dBm` (uncertain band `±6.0 dB`, max radius `10.0 km`).
- MapLibre GL runs completely offline with a custom local dark vector specification.

## INTEGRATION TODO
- [x] Dev B: `/contracts/config.json` received. `params.ts` adapted to `propagation` object.
- [x] Dev A & B: `web/public/data/cells.geojson` verified (900 features, integer IDs, WGS84 polygons within Sakleshpur box).
- [x] Dev B: Draggable candidate markers and shortlist table wired with click-to-zoom and briefing generator.
- [x] Dev C: Idempotent `applyRecompute` pure function and test suite verified.
- [ ] Dev B: Run FastAPI backend concurrently (`uvicorn api.main:app --port 8000`) for live multi-tower what-if testing.
