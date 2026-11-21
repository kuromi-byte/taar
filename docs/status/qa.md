# Gap-to-Brief: QA & Offline Verification Log
**File:** `/docs/status/qa.md`  
**Tester / Owner:** Dev D (Basemap, Brief & QA)  
**Last Updated:** Hackathon Sprint Hour 12 Readiness  

---

## 1. Automated Test Suite Status

| Test Suite | Scope | Target | Result | Status |
|---|---|---|---|---|
| **Pytest** | Propagation engine, polar sweep, Hata, API endpoints, contract validation | `python -m pytest tests` | 11 passed (6.12s) | ✅ PASS |
| **Vitest** | Frontend params sync, data config, contract interfaces, component contracts | `npm --prefix web test` | 6 passed (0.50s) | ✅ PASS |

---

## 2. Offline Resilience Audit (Zero External Network Call)

- **Network disabled test:** Simulates offline execution.
- **Tiles & Map Styles:** 
  - Verified: No Mapbox or Carto CDN style URLs.
  - Plain MapLibre GL instance initialized with an empty inline style JSON (`sources: {}`, `layers: [background]`).
- **Fonts / Glyphs:**
  - Verified: No `glyphs: "https://..."` specified.
  - All town labels rendered as HTML DOM markers (`maplibregl.Marker`) using system fonts.
- **Static Datasets:**
  - `boundary.geojson`, `roads.geojson`, and `towns.json` are loaded purely from `/public/data/basemap/`.

---

## 3. Data Integrity & Contract Compliance

- **Single Source of Truth:**
  - Coordinates, bounds, thresholds strictly read from `/contracts/config.json`.
- **Honest Labeling Audit:**
  - [x] All user-facing views carry the persistent `MODELED DATA` badge.
  - [x] `Uncertain` amber band applied to $\pm 6\text{ dB}$ around $-100\text{ dBm}$ threshold.
  - [x] `Unknown` cells (tower evidence distance $> 15\text{ km}$) are distinguished and never labeled as dead zones.
  - [x] Cluster without viable macrocell candidates (`CL-04`) explicitly marked with `Needs Field Survey`.

---

## 4. Real Data Handoff QA Checklist

When Dev B runs the pipeline on real OpenCellID + WorldPop datasets:
- [ ] 1. Clean clone test in isolated directory:
  ```bash
  git clone https://github.com/kuromi-byte/taar.git taar-clean
  cd taar-clean
  ```
- [ ] 2. Disable network adapter (or `ipconfig /release` / flight mode).
- [ ] 3. Launch FastAPI backend: `uvicorn api.main:app --port 8000`
- [ ] 4. Launch Vite frontend: `npm --prefix web run dev`
- [ ] 5. Verify map loads smoothly at `http://localhost:5173`.
- [ ] 6. Drag candidate tower pin twice: verify `setFeatureState` leaves zero residual footprint on second drop.
- [ ] 7. Click "Generate Brief" on a normal cluster and on the "Needs Field Survey" cluster; verify print layout fits on 1 sheet of A4.
- [ ] 8. Log any regressions or latency delays directly in this file.
