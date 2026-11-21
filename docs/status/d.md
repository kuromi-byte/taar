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

- **Task 5 (Post-Gate 0 Task 1): Real Run Data Integration**
  - Replaced all placeholders in [`docs/presentation_slides.md`](file:///D:/git/taar/docs/presentation_slides.md) and [`brief/template.html`](file:///D:/git/taar/brief/template.html) with verified REAL numbers from Dev A (`docs/status/a.md`), Dev B (`docs/status/b.md`), and `data/processed/cells.geojson`.
  - Grid & Population Metrics: 404,254 rural residents across 11,394 cells ($300\text{m} \times 300\text{m}$); 361,044 unserved residents in 10,176 gap cells ($< -106\text{ dBm}$); 28,364 in Uncertain band (721 cells); 10,885 Covered (308 cells); 3,961 Unknown (189 cells).
  - Benchmark: Direct engine 19.75 ms, API `/recompute` 29.08 ms (34x faster than < 1000 ms target).
  - Top 5 Ranked Sites Populated: CAND-09 (+6,936, road 0.12 km, slope 7.9°), CAND-011 (+4,572, road 0.32 km, slope 3.9°), CAND-02 (+1,427, road 0.58 km, slope 5.7°), CAND-05 (+708, road 0.21 km, slope 11.8°), CAND-08 (+584, road 0.62 km, slope 0.3°). Total added pop: 14,227 residents (3.94% gap reduction).
  - Needs Field Survey: Cluster CL-04 (Heggadde) with 17,376 gap residents, slope 19.2° > 15°, road distance 1.95 km > 1.0 km, `candidate_ids: []`.
  - Executive Brief template (`brief/template.html`) populated with real CL-01 Donigal baseline (23,545 unserved, 675 cells, CAND-02 & CAND-05).

## In Progress
- Task 2: Provenance verification report of basemap features and town names (OSM place tags inside pilot box).

## Assumptions
- Pilot area: Sakleshpur Taluk (Hassan, Karnataka).
- Offline by default: Zero external font, tile, CDN, or analytics requests.
- All numbers shown during demo must come from real runs, with mock numbers strictly forbidden from being presented as findings.

## INTEGRATION TODO
- [x] Dev B & A: Provide final real data run numbers for unserved pop, top candidate sites, and cluster metrics (Integrated into slides and brief).
- [ ] Dev D: Execute clean clone offline checkout test and log in `/docs/status/qa.md`.
