# Dev C (Frontend) Status - Gap-to-Brief

## Done
- **Task 1: Project Scaffolding & Configuration**
  - Scaffolded React 18 + Vite + TypeScript inside `/web`.
  - Configured plain `maplibre-gl` running on a 100% offline blank dark background (no CDN styles, no tiles, no font glyph network requests).
  - Configured `/web/src/config/data.ts`: isolated location for data paths, pilot metadata, and API URL (`VITE_API_URL` or fallback).
  - Configured `/web/src/config/params.ts`: loads contract thresholds from `/contracts/config.json` via Vite alias (with `/web/src/config/contracts-fallback.json` marked `TODO-STUB` until team commits shared contract).
  - Rendered placeholder pilot taluk bounding box rectangle on the map.

## In Progress
- Waiting for user confirmation to begin **Task 2: Load cells.geojson with feature-state color expression and legend**.

## Assumptions
- Pilot area aligned with Dev A & Dev B: **Sakleshpur Taluk** (Hassan District, Western Ghats, Karnataka).
  - Center: `[75.785, 12.972]` (Sakleshpur Town / NH-75 corridor)
  - Bounding Box (WGS84): `[75.60, 12.80, 75.95, 13.10]`
- MapLibre GL runs completely offline with a custom local dark vector specification.

## INTEGRATION TODO
- [ ] Dev A: When real `cells.geojson` arrives, ensure `id` is a 0..N integer and geometry is WGS84 polygon.
- [ ] Dev B: When `/contracts/config.json` is committed in repo root, verify `params.ts` picks up final threshold numbers.
- [ ] Dev B: When candidate ranking and `POST /recompute` endpoint are ready, test switching `apiUrl` in `data.ts` or `VITE_API_URL`.
- [ ] Dev D: When basemap GeoJSON (`boundary.geojson`, `roads.geojson`) and `towns.json` are placed in `/web/public/data/`, verify layer order and labels.
