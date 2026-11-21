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
  - Benchmarked `applyRecompute` over all 900 cells: executes in < 5 ms in the browser runtime.
  - Vitest suite: 12/12 unit tests passing. Production build clean in 3.04s.

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
