# Dev C (Frontend) Status - Gap-to-Brief

## Done
- **Task 1: Project Scaffolding & Configuration**
  - Scaffolded React 18 + Vite + TypeScript inside `/web`.
  - Configured plain `maplibre-gl` running on a 100% offline blank dark background (no CDN styles, no tiles, no font glyph network requests).
  - Pulled shared contracts and mock files from remote (`contracts/config.json`, `contracts/mock/cells_base.geojson`, `contracts/mock/towers.json`, `web/public/data/cells.geojson`).
  - Adapted `web/src/config/params.ts` to real `contracts/config.json` key structure (thresholds nested under `propagation`: `gap_threshold_dbm = -100.0`, `uncertain_band_db = 6.0`, `max_radius_km = 10.0`).
  - Derived map center (`[75.775, 12.95]`) and bounds dynamically from `pilot.bbox_wgs84`.
  - Validated spatial bounds: All 900 features in `web/public/data/cells.geojson` and all towers in `towers.json` strictly reside inside the Sakleshpur bounding box `[75.60, 12.80, 75.95, 13.10]`.
  - Untracked `node_modules` and `dist` from git repository and updated `.gitignore`.
  - Passing Vitest tests and production build.

## In Progress
- Ready to execute **Task 2: Load cells.geojson with feature-state color expression and legend**.

## Assumptions
- Pilot area is **Sakleshpur Taluk** (Hassan District, Western Ghats, Karnataka).
  - Center: `[75.775, 12.95]`
  - Bounding Box (WGS84): `[75.60, 12.80, 75.95, 13.10]`
  - Signal threshold: `-100.0 dBm` (uncertain band `±6.0 dB`, max radius `10.0 km`).
- MapLibre GL runs completely offline with a custom local dark vector specification.

## INTEGRATION TODO
- [x] Dev B: `/contracts/config.json` received. `params.ts` adapted to `propagation` object.
- [x] Dev A & B: `web/public/data/cells.geojson` verified (900 features, integer IDs, WGS84 polygons within Sakleshpur box).
- [ ] Dev B: Candidate ranking and `POST /recompute` endpoint integration.
- [ ] Dev D: When basemap GeoJSON (`boundary.geojson`, `roads.geojson`) and `towns.json` are placed in `/web/public/data/`, verify layer order and labels.
