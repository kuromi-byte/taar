# Dev D (Basemap, Brief & Demo) Status - Gap-to-Brief

## Done
- **Task 0: Repo, Branch, Tools & Config Verification**
  - Git repository on `main` branch, working tree clean.
  - Python 3.11.6 verified with required geospatial tooling (`shapely`, `geopandas`, `rasterio`, `pyproj`, `requests`).
  - Node `v24.15.0`, npm `11.12.1`.
  - Verified `contracts/config.json`:
    - Pilot: Sakleshpur Taluk (Hassan, Karnataka).
    - Bounding Box (WGS84): `min_lon: 75.60, max_lon: 75.95, min_lat: 12.80, max_lat: 13.10`.
    - Internal CRS: `EPSG:32643`, Exchange CRS: `EPSG:4326`.
  - Verified assigned folders: `/brief`, `/docs`, `/web/public/data/basemap`.

## In Progress
- Waiting for user confirmation to begin **Task 1: Basemap export (boundary, roads, water GeoJSON & towns.json)**.

## Assumptions
- Pilot bounds are strictly derived from `contracts/config.json` (`pilot.bbox_wgs84`: `[75.60, 12.80, 75.95, 13.10]`).
- Administrative taluk boundary will be extracted from OSM within bounding box; if unavailable or fragmented, fallback to bbox rectangle.
- 6–8 anchor towns will be extracted from verified OSM place tags inside bbox (anchored by Sakleshpur town: `12.972°N, 75.785°E`).
- All displayed signal/gap data is modeled, not measured.

## INTEGRATION TODO
- [ ] Dev C: Deliver simplified GeoJSON files to `/web/public/data/basemap/` (`boundary.geojson`, `roads.geojson`, optional `water.geojson`) and `towns.json` to both `/web/public/data/basemap/` and `/web/public/data/`.
- [ ] Dev B: Await real `clusters.json` and `candidates.json` (or supply valid mock contracts adhering to bbox).
- [ ] Dev C: Wire one-page brief template hook when Dev C adds "Generate brief" trigger for selected cluster.
