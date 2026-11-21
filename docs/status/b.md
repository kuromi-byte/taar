# Dev B — Data, Ranking & API Status
# Updated: Final Integration & Verification

## Summary of Accomplishments (M1 & M3)

### 1. Gap Cell Clustering
- Extracted population cells identified in modeled gap (`baseline_dbm < gap_threshold_dbm - uncertain_margin_db`).
- Built spatial clustering engine in `pipeline/clustering_and_ranking.py` grouping gap cells into 4 distinct geographic clusters in Sakleshpur:
  - **CL-01**: Donigal Valley & Kadagaravalli
  - **CL-02**: Ballupete South-East Fringe
  - **CL-03**: Anemahal & Kirehalli Hills
  - **CL-04**: Western Ghats Escarpment (Rugged Slope)

### 2. Candidate Siting & Feasibility Filters
- Sampled candidate tower locations evaluating local elevation prominence over valleys from 30m Copernicus/SRTM DEM.
- Built spatial KD-tree / STRtree over 1,081 OpenStreetMap road features (`sakleshpur_roads.geojson`) for Euclidean road distance lookup.
- Calculated surface slope in degrees using 2D elevation gradient: $\theta = \arctan(\sqrt{(\partial z/\partial x)^2 + (\partial z/\partial y)^2})$.
- Applied hard pass/fail feasibility filters:
  - **Slope**: $< 15.0^\circ$ (pass/fail)
  - **Road Access**: $\le 1.0\text{ km}$ (pass/fail)
- Evaluated backhaul feasibility based on fiber highway proximity and microwave line-of-sight to Sakleshpur headquarters.

### 3. Needs Field Survey Demonstration
- **Cluster CL-04 (Western Ghats Escarpment)**: Located in rugged hills with slopes exceeding $18.5^\circ$ and road distance $> 3.4\text{ km}$.
- No automated macrocell candidates passed feasibility filters.
- Correctly marked with `candidate_ids: []` and `needs_field_survey: true`, providing actionable recommendations for decentralized solar small-cells.

### 4. Greedy Ranking Engine
- Uses the **exact same `compute_signal` function** from `pipeline.model.engine` to calculate incremental population coverage boost.
- Greedily selects top sites, updates baseline signal, and recomputes remaining pool:
  - **Rank 1**: CAND-09 (Anemahal Hills) $\to$ **+5,269** newly covered residents
  - **Rank 2**: CAND-07 (Ballupete Fringe) $\to$ **+4,532** newly covered residents
  - **Rank 3**: CAND-02 (Donigal Valley) $\to$ **+1,370** newly covered residents
  - **Rank 4**: CAND-010 (Anemahal Ridge) $\to$ **+476** newly covered residents
  - **Rank 5**: CAND-05 (Ballupete East) $\to$ **+298** newly covered residents

### 5. FastAPI Integration (`api/main.py`)
- Removed hardcoded path references; loads relative to repository root and `contracts/config.json`.
- Implemented endpoints:
  - `GET /health`: Server status and cells loaded
  - `GET /config`: Returns pilot configuration
  - `GET /towers`: Returns existing macrocell towers
  - `GET /candidates`: Returns ranked shortlist with feasibility flags
  - `GET /clusters`: Returns gap clusters including needs-survey flag
  - `POST /recompute`: Accepts candidate tower updates on drag; returns changed cells `[[id, dbm], ...]`, `newly_covered_pop`, and `total_unserved_pop`
- Cross-Origin Resource Sharing (CORS) enabled for local frontend integration.
