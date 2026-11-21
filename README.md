# Rural Coverage Gap Mapper (Gap-to-Brief)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg)](https://react.dev/)
[![MapLibre GL](https://img.shields.io/badge/MapLibre%20GL-4.7.1-blueviolet.svg)](https://maplibre.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4.11-646CFF.svg)](https://vitejs.dev/)
[![Tests: Pytest](https://img.shields.io/badge/Pytest-11%20passed-brightgreen.svg)]()
[![Tests: Vitest](https://img.shields.io/badge/Vitest-6%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Find the gaps worth verifying. Shortlist the sites worth surveying.**  
> A geospatial screening and triage tool that combines rural coverage dead-zone mapping, terrain shadow modeling, candidate tower ranking, interactive what-if simulation, and automated executive brief generation.

---

## 1. Project Overview

Government mobile coverage statistics in India are tracked village-by-village. A gram panchayat can be officially counted as "covered" while hamlets only 1 to 2 kilometers away behind a ridge receive zero usable signal. Commercial RF planning tools require proprietary drive-test logs and exact antenna azimuths that public planners do not have.

**Gap-to-Brief** addresses two complementary hackathon challenges:
- **SW-27 (Rural Coverage Gap Mapper):** Identifies underserved rural population clusters and recommends prioritized candidate mobile tower locations.
- **SW-34 (Coverage Dead-Zone Heatmap Tool):** Estimates weak-signal areas from tower locations and transmission power, and provides an interactive what-if sandbox allowing planners to move candidate towers and dynamically evaluate before-and-after coverage gains.

> **IMPORTANT DISCLAIMER:**  
> This is a **modeled coverage estimation screening tool**, not a physical RF drive-test measurement system or a final telecommunication tower-siting authority. All outputs are clearly badged as **MODELED DATA**.

---

## 2. Working Pilot Area

The team aligned on **Sakleshpur Taluk**, Hassan District, Karnataka, as the working pilot area:
- **Geographic Extent:** Western Ghats highland fringe
- **Bounding Box (WGS84):** $75.60^\circ - 75.95^\circ\text{E}$, $12.80^\circ - 13.10^\circ\text{N}$
- **Internal CRS:** EPSG:32643 (UTM Zone 43N)
- **Topography:** Elevation ranging from 89.5m in valley floors to 1,376.5m along mountain ridges.
- **Analyzed Population:** 25,684 rural residents across 900 uniform 300m population cells.
- **Baseline Unserved Population:** 19,309 residents across 802 gap cells ($< -106\text{ dBm}$).

---

## 3. Key Features

1. **Topographic Gap Map:**
   - 300m population cells colored dynamically by modeled signal strength.
   - 100% offline MapLibre GL canvas with zero CDN styles, external tiles, or font glyph requests.
2. **Transparent Uncertainty Band:**
   - Cells within $\pm 6\text{ dB}$ of the $-100\text{ dBm}$ threshold are explicitly colored as **Uncertain** (amber), avoiding misleading false-positive green or false-negative red classifications.
3. **Ranked Siting Shortlist with Feasibility Filters:**
   - Proposes candidate tower locations based on local elevation prominence.
   - Enforces hard pass/fail filters: **Slope $< 15.0^\circ$** (from DEM gradient) and **Road Access $\le 1.0\text{ km}$** (from OpenStreetMap).
   - Greedily selects top sites based on incremental newly covered population.
4. **"Needs Field Survey" Demonstration:**
   - Demonstrates that when a remote cluster (e.g. Cluster CL-04, Western Ghats Escarpment) fails automated slope ($> 18.5^\circ$) or road ($> 3.4\text{ km}$) filters, it outputs an explicit **"Needs Field Survey"** alert recommending decentralized solar small-cells instead of generating unbuildable macrocell coordinates.
5. **Interactive What-If Simulation:**
   - Drag candidate tower pins directly on the map.
   - Recalculates coverage latency in **$\sim 8.6\text{ ms}$** via FastAPI backend.
   - Idempotent `setFeatureState` diffing removes stale footprints upon drop.
   - Before/After toggle for visual comparison against baseline.
6. **One-Page Printable Brief:**
   - Generates an executive briefing sheet formatted for printing and PDF export via browser print stylesheets (`@media print`).

---

## 4. Architecture & Single Source of Truth

```
contracts/config.json (Single source of truth: bounds, frequencies, thresholds)
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
[ pipeline / model ]       [ FastAPI Backend: api/main.py ]
- dem.py (30m DEM)         - GET /health, /towers, /candidates, /clusters
- hata.py (COST-231 Hata)  - POST /recompute (what-if drop)
- shadow.py (Polar Sweep)                 │
- engine.py (compute_signal)              │
        │                                 │
        └─────────────┬───────────────────┘
                      ▼
         [ web / React + MapLibre GL ]
         - Header & Modeled Badge
         - Counter Panel (+Newly Covered Counter)
         - Draggable Candidate Tower Pins
         - Ranked Shortlist & Clusters Table
         - One-Page Printable Brief Modal
```

- **Single Model Function:** Baseline generation, candidate greedy ranking, and the live API `/recompute` endpoint all call the exact same `compute_signal` function. This ensures the live counter never contradicts the heatmap.

---

## 5. Repository Structure

```
taar/
├── api/
│   └── main.py                     # FastAPI application serving /recompute & data contracts
├── contracts/
│   ├── config.json                 # Shared configuration (pilot bbox, propagation parameters)
│   └── mock/                       # Data contracts (cells_base.geojson, towers.json, candidates.json)
├── data/
│   ├── processed/
│   │   ├── dem_utm43n.tif          # 30m Copernicus DEM raster reprojected to EPSG:32643
│   │   └── cells.geojson           # 300m population grid with baseline dBm and states
│   └── raw/
│       ├── osm/sakleshpur_roads.geojson # 1,081 OpenStreetMap road segments
│       └── worldpop/               # WorldPop India 100m raster
├── docs/
│   ├── presentation_slides.md      # Hackathon presentation slides & 3-minute demo flow
│   └── status/                     # Developer module status logs (a.md, b.md, c.md, d.md)
├── pipeline/
│   ├── clustering_and_ranking.py   # Clustering, feasibility filtering & greedy ranking pipeline
│   └── model/
│       ├── config.py               # PropagationConfig dataclass
│       ├── dem.py                  # Rasterio DEMGrid handler with vectorized point sampling
│       ├── hata.py                 # COST-231 & Okumura-Hata propagation path loss
│       ├── shadow.py               # PolarSweepEngine (720 rays terrain diffraction)
│       ├── engine.py               # Shared compute_signal & classify_state functions
│       └── benchmark.py            # Performance benchmark (< 10ms execution)
├── tests/
│   ├── test_api_import.py          # FastAPI direct import and recompute tests
│   ├── test_engine.py              # compute_signal and classify_state tests
│   ├── test_hata.py                # COST-231 Hata hand-calculated value validation
│   ├── test_ranking_and_contracts.py # Siting filters & contract integrity tests
│   └── test_shadow.py              # Synthetic ridge shadow diffraction tests
├── web/
│   ├── public/data/                # Static contracts (cells, towers, candidates, basemap)
│   ├── src/
│   │   ├── components/             # React components (Map, Header, Counter, Shortlist, Brief)
│   │   ├── config/                 # Dynamic config loader from contracts/config.json
│   │   ├── types/contracts.ts      # TypeScript contract interfaces
│   │   └── App.tsx                 # Main application dashboard
│   ├── package.json
│   └── vite.config.ts
├── rundown.md                      # Comprehensive 18-hour sprint guide & requirements
└── README.md                       # Main project documentation
```

---

## 6. Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+ and npm

### 1. Backend Setup & Run
Activate your virtual environment and start the FastAPI server:

```powershell
# In repository root:
& C:\Users\aanya\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```
API documentation is automatically available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup & Run
In a separate terminal, navigate to `/web`, install dependencies, and launch Vite:

```bash
cd web
npm install
npm run dev
```
Open `http://localhost:5173` in your web browser.

---

## 7. Running Tests & Benchmarks

### Backend Test Suite (Pytest)
Run all 11 unit tests covering propagation formulas, synthetic ridge diffraction, API recompute, and contract adherence:

```powershell
& C:\Users\aanya\venv\Scripts\python.exe -m pytest -v
```

### Frontend Test Suite (Vitest)
Run the React and configuration unit tests:

```bash
cd web
npm test
```

### Performance Benchmark
Run the polar sweep and propagation benchmark:

```powershell
& C:\Users\aanya\venv\Scripts\python.exe -m pipeline.model.benchmark
```
*Sample output:*
```
Polar Sweep (720 rays x 333 steps = 239,760 DEM samples): 9.04 ms
End-to-end compute_signal (5000 cells + Hata + Shadows): 8.64 ms
RESULT: PASS! Latency (8.64 ms) is well under target (< 1000 ms).
```

---

## 8. API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Returns service status and number of loaded cells |
| `/config` | `GET` | Returns active pilot and propagation configuration from `contracts/config.json` |
| `/towers` | `GET` | Returns list of existing macrocell towers in the pilot area |
| `/candidates` | `GET` | Returns prioritized candidate sites with feasibility flags |
| `/clusters` | `GET` | Returns gap cell clusters, population in gap, and needs-survey status |
| `/recompute` | `POST` | Accepts candidate tower coordinates; returns changed cells, newly covered population, and remaining unserved population |

---

## 9. Honest Limitations & Methodology Statement

1. **Signal is Modeled, Not Measured:**  
   Path loss is computed using Okumura/COST-231 Hata empirical equations and 30m DEM elevation raycasting. It does not model localized tree canopy, micro-clutter, or building penetration.
2. **OpenCellID is a Lower Bound:**  
   Existing tower evidence comes from crowd-sourced OpenCellID logs. Regions without recorded towers are conservatively labeled *Unknown* or potential gaps, not guaranteed dead zones.
3. **Empirical Error Band ($\pm 5\text{ to }11\text{ dB}$):**  
   Published literature for Hata and knife-edge diffraction in complex topography demonstrates 5 to 11 dB standard errors. Cells within $\pm 6\text{ dB}$ of the gap threshold are clearly labeled as **Uncertain**.
4. **Siting Output is a Screening Shortlist:**  
   Civil feasibility (land title, grid power availability, fiber backhaul rights-of-way) cannot be deduced from open geospatial data. This tool prioritizes where to dispatch field survey teams, rather than replacing physical site engineering.
