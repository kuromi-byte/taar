# Gap-to-Brief: Rural Coverage Gap Mapper
## Hackathon Presentation Slides & 3-Minute Demo Guide

**Problem Statements:** SW-27 (Rural Coverage Gap Mapper) + SW-34 (Coverage Dead-Zone Heatmap Tool)  
**Pilot Taluk:** Sakleshpur, Hassan District, Karnataka  
**Repository:** https://github.com/kuromi-byte/taar.git  

---

## Slide 1: Title & Pitch
### Gap-to-Brief: Rural Coverage Gap Mapper
> *"Find the gaps worth verifying. Shortlist the sites worth surveying."*

- **The Problem:** Government coverage statistics track coverage at the village level. A village gram panchayat can be marked as "covered", while agricultural hamlets 2 km away behind a ridge have zero usable signal.
- **The Solution:** A rapid triage screening tool that maps modeled signal over 300m population cells, shortlists candidate tower sites with hard terrain and road filters, enables dynamic what-if simulation, and generates an executive briefing document per cluster.

---

## Slide 2: Target User & Problem Fit
- **Who this is for:** State IT departments, Digital Bharat Nidhi (USOF) planners, district administration, telecom policy analysts, and rural development NGOs.
- **The Gap in Current Tools:**
  - Telco RF planning suites (Atoll, Asset) require proprietary drive-test datasets, exact antenna azimuths, and licensed parameters that public planners do not possess.
  - On-the-ground manual surveys are slow and cost tens of thousands of rupees per village.
- **Value Proposition:** Tells planners *where to dispatch survey teams first* and gives them defensible mathematical justification for capital expenditure.

---

## Slide 3: Unified System Architecture
```
                                 [ contracts/config.json ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [ pipeline / model ]                         [ FastAPI: api/main.py ]
         - DEMGrid (30m Copernicus)                  - GET /health, /towers, /candidates
         - PolarSweepEngine (720 rays)               - POST /recompute (what-if drop)
         - COST-231 Hata (900 MHz)                                 │
         - classify_state (Uncertain Band)                         │
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                                  [ web / React + MapLibre ]
                              - 100% Offline Blank Canvas Style
                              - Idempotent setFeatureState Diffing
                              - Draggable Candidate Pins
                              - One-Page Printable Brief (PDF)
```
- **Rule of Truth:** Baseline computation, greedy candidate ranking, and the live `/recompute` endpoint all call the **exact same `compute_signal` function**.
- **No Inconsistencies:** Moving a tower can never produce a contradiction between the live counter and the heatmap.

---

## Slide 4: Propagation Model & Terrain Physics
1. **Frequency Baseline:** 900 MHz (Okumura-Hata open-area formulation) with 30m macrocell tower height ($h_b$) and 1.5m mobile receiver ($h_m$).
2. **Polar Sweep Shadowing:**
   - 720 rays cast at $0.5^\circ$ angular resolution out to 10 km (333 steps of 30m).
   - Vectorized running maximum elevation angle along each ray (`np.maximum.accumulate`).
   - Obstructed cells receive a flat 15 dB shadow diffraction penalty.
3. **Best-Server Aggregation:**
   - For every cell, received power $P_{rx} = \max_{t \in \text{towers}} (P_{tx} - L_{hata}(d) - L_{shadow})$.
4. **Honest State Classification:**
   - **Likely Covered:** $\ge -94\text{ dBm}$ (emerald green)
   - **Uncertain Band:** $-106\text{ to } -94\text{ dBm}$ ($\pm 6\text{ dB}$ around threshold; amber)
   - **Likely Gap:** $< -106\text{ dBm}$ (red)
   - **Unknown:** Distance to nearest recorded tower $> 15\text{ km}$ (missing data, not confirmed gap)

---

## Slide 5: Pilot Region — Sakleshpur Taluk (Karnataka)
- **Topography:** Western Ghats highland (elevation 89.5m to 1,376.5m) with steep ridges, dense valleys, and coffee plantations.
- **Coordinates:** Lat $12.80^\circ - 13.10^\circ\text{N}$, Lon $75.60^\circ - 75.95^\circ\text{E}$ (UTM Zone 43N).
- **Population Analyzed:** 25,684 rural residents across 900 grid cells ($300\text{m} \times 300\text{m}$).
- **Baseline Gap:** 19,309 unserved residents across 802 gap cells.

---

## Slide 6: Candidate Siting, Filters & Greedy Ranking
- **Feasibility Pass/Fail Filters:**
  - **Surface Slope:** Must be $< 15.0^\circ$ (calculated from 2D DEM gradient).
  - **Road Access:** Must be $\le 1.0\text{ km}$ from OpenStreetMap verified roads (calculated via STRtree spatial index).
- **Top 5 Ranked Shortlist:**
  1. **CAND-09** (Anemahal Hills): **+5,269** newly covered | Road: 0.79 km | Slope: 6.0°
  2. **CAND-07** (Ballupete Fringe): **+4,532** newly covered | Road: 0.11 km | Slope: 5.6° | Fiber along road
  3. **CAND-02** (Donigal Valley): **+1,370** newly covered | Road: 0.17 km | Slope: 6.0° | Fiber along road
  4. **CAND-010** (Anemahal Ridge): **+476** newly covered | Road: 0.81 km | Slope: 7.2°
  5. **CAND-05** (Ballupete East): **+298** newly covered | Road: 0.35 km | Slope: 5.1°
- **Overall Impact:** Top sites bring over **11,947** rural residents into reliable mobile coverage (a **61.8% gap reduction**).

---

## Slide 7: The "Needs Field Survey" Cluster
- **Cluster CL-04 (Western Ghats Escarpment):**
  - Population in gap: 2,840 residents.
  - Slope: $> 18.5^\circ$ (exceeds $15^\circ$ macrocell threshold).
  - Distance to road: $> 3.4\text{ km}$ (exceeds $1\text{ km}$ vehicular access limit).
- **Honest Automated Failure:** The system outputs `candidate_ids: []` with an explicit alert: **"Needs Field Survey"**.
- **Actionable Value:** Recommends off-grid solar micro-masts or localized cable relays rather than misleading planners with unbuildable macrocell coordinates.

---

## Slide 8: 3-Minute Demo Walkthrough Script
1. **0:00 - 0:45 | Baseline Map & Unserved Numbers:**
   - Open Map view centered on Sakleshpur.
   - Point out the 300m cells colored by signal strength.
   - Show the **MODELED DATA** badge and the **Uncertain band** (amber cells).
   - Highlight the **19,309 unserved population counter**.
2. **0:45 - 1:45 | Shortlist Table & Zoom:**
   - Switch to the Ranked Sites table.
   - Click **CAND-07** (+4,532 pop covered). The map smoothly flies to the site.
   - Point out the visible feasibility columns (Road: 0.11 km, Slope: 5.6°, Fiber backhaul).
   - Click the **Gap Clusters** tab and highlight **CL-04 (Western Ghats Escarpment)** marked *"Needs Field Survey"*.
3. **1:45 - 2:30 | Dynamic What-If Simulation:**
   - Grab Candidate #1 pin and drag it 1.5 km west into the valley.
   - On drop, the FastAPI engine recalculates in **~8.6 ms**.
   - Show the **+Newly Covered Population** counter dynamically updating.
   - Drag it back or click **"Reset Sites"** to prove idempotent updates with zero leftover footprints.
   - Click **"Viewing: After"** to toggle before/after baseline.
4. **2:30 - 3:00 | Printable One-Page Brief:**
   - Click **"Generate Cluster Brief"** on Cluster CL-01.
   - Show the clean executive briefing document ready for Digital Bharat Nidhi planners.
   - Click **"Print / Save as PDF"** to demonstrate browser print formatting.
   - Close on the **Honest Limitations** slide.

---

## Slide 9: Transparent Limitations (Judge Q&A Defense)
| Reviewer / Judge Question | Our Defensible Engineering Answer |
|---|---|
| *Why not use standard RF software?* | Commercial suites require proprietary drive tests and antenna radiation patterns that public bodies lack. This is a triage screening tool. |
| *How accurate is the signal prediction?* | Modeled, not measured. Academic literature reports 5 to 11 dB error in complex terrain; our $\pm 6\text{ dB}$ Uncertain band reflects this margin explicitly. |
| *What if OpenCellID has missing towers?* | OpenCellID is treated strictly as a lower bound. Cells without evidence are labeled *Unknown*, never claimed as confirmed dead zones. |
| *What about land ownership and power?* | Land tenure, 3-phase grid power, and fiber backhaul rights cannot be known from open data. Our output is a survey shortlist with visible flags, not a final civil engineering decision. |
