# Rural Coverage Gap Mapper (Gap-to-Brief)

> **Find the gaps worth verifying. Shortlist the sites worth surveying.**  
> A geospatial screening and triage tool combining rural mobile network dead-zone mapping, terrain shadow modeling, candidate tower ranking, interactive what-if simulation, and automated executive brief generation.

---

## 1. Quickstart (One-Command Guide)

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** and **npm**

### Installation

From the repository root:

```bash
# 1. Install Python package and dependencies in editable mode
pip install -e .

# 2. Install web frontend dependencies
cd web && npm install && cd ..
```

### Running the Application

Open two terminal windows:

**Terminal 1 — Start the API Backend (Port 8000):**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
*API docs are available at `http://localhost:8000/docs`.*

**Terminal 2 — Start the Web Dashboard (Port 5173):**
```bash
cd web && npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 2. Running Tests

```bash
# Backend unit tests (26 passed)
pytest tests/

# Frontend unit tests (12 passed)
cd web && npm test
```

---

## 3. Data Sources & Provenance

Raw raster and vector datasets are large and are excluded from Git commits via `.gitignore`. Pre-processed GeoJSON layers are included in `data/processed/` and `web/public/data/` for immediate offline demonstration.

To regenerate processed layers from raw datasets:

| Data Layer | Source Dataset | Placement Location | Description |
|---|---|---|---|
| **Population Raster** | [WorldPop India 2020 (100m)](https://www.worldpop.org/) | `data/raw/worldpop/worldpop_india_100m.tif` | Unconstrained individual country 100m population counts. |
| **Road Network** | [OpenStreetMap (OSM)](https://www.openstreetmap.org/) | `data/raw/osm/sakleshpur_roads.geojson` | OSM highway line geometries extracted for Sakleshpur taluk. |
| **Elevation (DEM)** | [Copernicus GLO-30 / SRTM](https://spacedata.copernicus.eu/) | `data/processed/dem_utm43n.tif` | 30m digital elevation model reprojected to EPSG:32643 (UTM Zone 43N). |
| **Existing Towers** | [OpenCellID](https://opencellid.org/) | `contracts/mock/towers.json` & `pipeline/data/towers.json` | Crowdsourced cell tower locations with radio types and assumed EIRP power. |
| **Boundary & Basemap** | OpenStreetMap / Survey of India | `web/public/data/basemap/` | Taluk boundary GeoJSON, road lines, and anchor town points (`towns.json`). |
| **Configuration** | Project Specification | `contracts/config.json` | Single source of truth: pilot bbox, 900 MHz baseline, EIRP 43 dBm, -100 dBm gap threshold. |

### Data Generation Pipeline

If raw datasets are placed as indicated above, regenerate baseline cells and rankings:

```bash
# 1. Aggregate WorldPop raster to 300m cells & sample DEM + road distances
python -m pipeline.build_real_cells

# 2. Run Okumura-Hata propagation & polar sweep terrain diffraction
python -m pipeline.model.process_cells

# 3. Cluster gap cells (8-connectivity) & greedily rank candidate sites
python -m pipeline.clustering_and_ranking
```

---

## 4. API Endpoints (Port 8000)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Service status, pilot area, and cell count. |
| `/config` | `GET` | Pilot bounds, propagation parameters, and thresholds. |
| `/towers` | `GET` | Existing mobile network towers (`meta.source = OpenCellID`). |
| `/candidates` | `GET` | Prioritized candidate tower sites (`meta.source = WorldPop`). |
| `/clusters` | `GET` | Gap settlement clusters and survey flags (`meta.source = WorldPop`). |
| `/recompute` | `POST` | Accepts candidate tower coordinates `{"towers": [...]}`; returns changed cell diffs and live population gain. |

---

## 5. Architecture Notes & Honest Limitations

1. **Modeled, Not Measured**: Signal strength is estimated using Okumura/COST-231 Hata empirical propagation combined with a 720-ray polar sweep terrain shadow obstruction model. It does not replace drive-test measurement equipment.
2. **Conservative Tower Lower Bound**: OpenCellID data represents a lower bound on active towers. Hamlets with no nearby tower observations are designated as *Unknown* or potential gaps.
3. **Uncertainty Band**: Cells within $\pm 6\text{ dB}$ of the $-100\text{ dBm}$ threshold are transparently displayed as **Uncertain** (amber), avoiding false precision.
4. **Survey Triage, Not Siting Authority**: Outputs provide prioritized candidate sites based on terrain prominence, slope ($< 15^\circ$), and road access ($\le 1.0\text{ km}$). Final construction requires physical survey for land title, grid power, and backhaul.
