# Dev D (Basemap, Brief & Demo) Status - Gap-to-Brief

## Done
- **Task 0: Repo, Branch, Tools & Config Verification**
  - Git repository on `main` branch, working tree clean.
  - Python 3.11.6 verified with required geospatial tooling (`shapely`, `geopandas`, `rasterio`, `pyproj`, `requests`).
  - Node `v24.15.0`, npm `11.12.1`.
  - Verified `contracts/config.json`: Sakleshpur Taluk (Hassan, Karnataka), WGS84 bbox `[75.60, 12.80, 75.95, 13.10]`, `EPSG:32643`.
- **Task 1: Provenance Audit of Basemap & Towns**
  - `boundary.geojson`: Extracted exact bounding box polygon `[[75.6, 12.8], [75.95, 12.8], [75.95, 13.1], [75.6, 13.1]]` per config.
  - `roads.geojson`: 1,074 road segments filtered from OpenStreetMap road extract (`data/raw/osm/sakleshpur_roads.geojson`), including verified highways and arterial roads (`NH-75`, `SH-8`, Sakleshpur Bypass).
  - `towns.json`: 8 verified real settlements inside the pilot bbox with OSM place tags: Sakleshpur (HQ), Donigal, Ballupete, Anemahal, Heggadde, Shukravarasanthe, Biccodu Cross, Hanbal.
- **Task 2: Slide Deck & BriefModal Audit (Mock Data Removal)**
  - Audited `docs/presentation_slides.md` and `BriefModal.tsx`.
  - Replaced all synthetic/mock-derived figures with `[N from real run]` placeholders (population, cell counts, site gains, percentages, benchmark ms).
  - Created standalone single-page printable executive brief template in [`brief/template.html`](file:///D:/git/taar/brief/template.html) with print CSS (`@media print`) and field survey alert block.
- **Task 3: Limitations & Honest Disclosure Audit**
  - Explicitly verified all 5 required disclaimers in `docs/presentation_slides.md`, `brief/template.html`, and `BriefModal.tsx`:
    1. Modeled, not measured (empirical propagation + terrain occlusion, not drive-test).
    2. Unvalidated for Karnataka (regional validation pending).
    3. 5 to 11 dB error band cited from published literature in complex terrain.
    4. OpenCellID bias toward highways/towns (lower bound; missing data is *Unknown*, never claimed as gap).
    5. Survey shortlist, not a siting decision (power, land tenure, and fiber cannot be known from open data).
- **Task 4: QA & Offline Verification Checklist Initialized**
  - Initialized [`docs/status/qa.md`](file:///D:/git/taar/docs/status/qa.md) documenting offline resilience and clean clone verification plan.

## In Progress
- Awaiting Dev B's real data pipeline execution to run the clean clone offline test and log results in `/docs/status/qa.md`.

## Assumptions
- Pilot area: Sakleshpur Taluk (Hassan, Karnataka).
- Offline by default: Zero external font, tile, CDN, or analytics requests.
- All numbers shown during demo must come from real runs, with mock numbers strictly forbidden from being presented as findings.

## INTEGRATION TODO
- [ ] Dev B: Provide final real data run numbers for unserved pop, top candidate sites, and cluster metrics.
- [ ] Dev D: Execute clean clone offline checkout test and log in `/docs/status/qa.md`.
