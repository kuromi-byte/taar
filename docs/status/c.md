# Dev C (Frontend) Status - Gap-to-Brief

## Done
- **Upstream Merge & Conflict Resolution**:
  - Base version: `origin/main` (commit `dbd5478`).
  - Integrated Dev B's full frontend implementation (Map, shortlist, draggable pins, counter panel, brief and limitations modals). Clean merge with 0 unresolved git conflicts.
- **Rules Audit & Fixes (Committed in 3 focused commits)**:
  - *Audit Fix 1 (`9d15747`)*: Extracted pure, idempotent `applyRecompute(map, prevIdSet, changed)` into `web/src/utils/recompute.ts` with 6 Vitest unit tests covering shrinking responses, empty responses, invalid IDs, and double-drag stale footprint elimination.
  - *Audit Fix 2 (`646fb7f`)*: In `Map.tsx`, removed hardcoded signal numbers (-94 / -106 dBm) and bound color stops dynamically to `params.gap_threshold_dbm` ± `params.uncertain_band_db`. Added explicit grey (`#6b7280`) color mapping for `unknown` / `Unknown` states (never shown as gaps). Added dev recolor button (`testRecolorCell`).
  - *Audit Fix 3 (`ec158df`)*: Updated persistent badge to exact phrase `"Modeled, not measured"`. Added red sticky `"MOCK DATA"` banner triggered when `cells.geojson` has `meta.source == "mock"`. Implemented exact `/recompute` request payload `{"towers": [{"lat", "lon", "height_m", "power_dbm"}]}`. Handled API failure by displaying clear error message while preserving previous map state. Added candidate site inspector card with `height_m` and `power_dbm` sliders.
- **Offline & Performance Verification**:
  - Zero external CDN, font, or tile requests (100% offline localhost).
  - Vitest suite: 12/12 unit tests passing. Production build clean in 3.06s.
  - Tree-shaking verification: `dist/` production bundle grepped for `"__bench"`; confirmed **0 occurrences** (cleanly eliminated).
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
