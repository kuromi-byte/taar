# Dev C (Frontend) Status - Gap-to-Brief

## Done
- **Upstream Merge & Conflict Resolution**:
  - Base version: `origin/main` (commit `dbd5478`).
  - Integrated Dev B's full frontend implementation (Map, shortlist, draggable pins, counter panel, brief and limitations modals). Clean merge with 0 unresolved git conflicts.
- **Rules Audit & Fixes (Committed in 3 focused commits)**:
  - *Audit Fix 1 (`9d15747`)*: Extracted pure, idempotent `applyRecompute(map, prevIdSet, changed)` into `web/src/utils/recompute.ts` with 6 Vitest unit tests covering shrinking responses, empty responses, invalid IDs, and double-drag stale footprint elimination.
  - *Audit Fix 2 (`646fb7f`)*: In `Map.tsx`, removed hardcoded signal numbers (-94 / -106 dBm) and bound color stops dynamically to `params.gap_threshold_dbm` ± `params.uncertain_band_db`. Added explicit grey (`#6b7280`) color mapping for `unknown` / `Unknown` states (never shown as gaps). Added dev recolor button (`testRecolorCell`).
  - *Audit Fix 3 (`ec158df`)*: Updated persistent badge to exact phrase `"Modeled, not measured"`. Added red sticky `"MOCK DATA"` banner triggered when `cells.geojson` has `meta.source == "mock"`. Implemented exact `/recompute` request payload `{"towers": [{"lat", "lon", "height_m", "power_dbm"}]}`. Handled API failure by displaying clear error message while preserving previous map state. Added candidate site inspector card with `height_m` and `power_dbm` sliders.
- **Task 1c Real File Verification (11,394 cells) [REAL]**:
  - **Data Audit (web/public/data/cells.geojson)**:
    - Feature count: **11,394 cells** (full Sakleshpur taluk grid).
    - `meta`: `{ "source": "worldpop", "model": "Okumura-Hata/COST-231 + Polar Sweep Shadowing", "frequency_mhz": 900, "eirp_dbm": 43, "gap_threshold_dbm": -100, "uncertain_band_db": 6 }`.
    - ID Range: **1 .. 11394** (1-based integer indexing, verified supported across MapLibre and `applyRecompute`). Duplicate IDs: 0, Non-integer IDs: 0.
    - State Counts: `gap`: 10,176 (89.3%), `uncertain`: 721 (6.3%), `covered`: 308 (2.7%), `unknown`: 189 (1.7%).
    - Cells with `baseline_dbm == null`: 2,050 `gap` cells and 189 `unknown` cells (0 in `covered` / `uncertain`).
  - **Cross-File Integrity Check**:
    - `clusters.json`: 5 clusters with 4,934 cell IDs in range `[16, 10099]`. Missing in `cells.geojson`: **0**.
    - `candidates.json`: 5 candidates (`CAND-09`, `CAND-011`, `CAND-02`, `CAND-05`, `CAND-08`), all mapped to valid cluster IDs (`CL-01`, `CL-03`).
    - Property fields: all contract 2 required fields present (`pop`, `baseline_dbm`, `state`). Extra pipeline fields: `id`, `cx`, `cy`, `elev_m`, `slope_deg`, `road_km`, `tower_evidence`.
  - **Null Rendering Fix (Map.tsx & styleExpressions.ts)**:
    - Layer fill-color expression extracted to pure helper [`styleExpressions.ts`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/utils/styleExpressions.ts): cells with `baseline_dbm == null` and no feature-state override are colored strictly by their `state` property (`covered` -> `#10b981`, `uncertain` -> `#f59e0b`, `gap` -> `#ef4444`, `unknown` -> `#6b7280`), never defaulting to gap.
    - Popup text for null baseline dBm updated to exact string `"No modeled signal"`.
    - Unit tests: 8 tests in `styleExpressions.test.ts` verifying all state/dBm permutations.
  - **Real Dataset Performance Benchmark [REAL]**:
    - Context: Headless Chromium with CPU software WebGL (`ANGLE / SwiftShader Device LLVM 10.0.0`).
    - File size: **4.16 MB**.
    - Fetch + response.json() parse: **76.10 ms**.
    - Draw to idle: **20.60 ms** (Total load: **96.70 ms** -> **PASS**, target < 3.0 s).
    - 3s Pan/Zoom Avg FPS: **35.6 FPS** (worst frame: 66.60 ms) -> **PASS**, target ≥ 30.0 FPS.
    - Cells within 10.0 km radius of candidate `CAND-09` ($N$): **3,345 cells**.
    - `setFeatureState` Loop: median **0.60 ms** (p95: 0.80 ms).
    - `setFeatureState` + Idle: median **36.50 ms** (p95: 63.50 ms) -> **PASS**, target < 100.0 ms.
    - `removeFeatureState` Loop / Idle: median **0.40 ms** / **35.95 ms**.
    - `applyRecompute` Loop / Idle: median **0.90 ms** / **36.90 ms**.
    - Shrinking Response ($N \to N/2$) Stale Clear Check: **CONFIRMED**.
    - Unknown Cells Rendered: **189 cells** (all verified grey `#6b7280`).
    - Overall Real File Target Verdict: **PASS**.
- **Task 1 & 1b Synthetic Scale Performance Benchmarking**:
  - **Hardware & Render Context**: Run in headless Chromium with CPU software WebGL (`ANGLE / SwiftShader Vulkan 1.3.0`). Real GPU hardware numbers on the demo laptop will exceed these software-rasterized metrics.
  - **Unknown State Verification**: Verified that cells with `state: "unknown"` evaluate to `#6b7280` (grey) via the first `case` branch in the MapLibre layer expression and are **never** colored as gaps (`#ef4444`), regardless of feature-state or baseline dBm overrides. Rendered count: 350 (at 3.5k), 1,400 (at 14k), 3,000 (at 30k).
  - **Combined Benchmark Results (All Tagged SYNTHETIC)**:

| Metric / Target | 3,500 Cells (~10 km radius) | 14,000 Cells (~full taluk) | 30,000 Cells (headroom) | Target Condition | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Grid Generation & Parse** | 25.2 ms | 42.4 ms | 125.7 ms | — | — |
| **Draw to Idle** | 14.3 ms | 14.8 ms | 29.8 ms | — | — |
| **Initial Load Total** | **39.5 ms** | **57.2 ms** | **155.5 ms** | **< 3.0 s** | **PASS** |
| **3s Pan/Zoom Avg FPS** | **58.5 FPS** | **47.9 FPS** | **43.0 FPS** | **≥ 30.0 FPS** | **PASS** |
| **Worst Frame Time** | 66.7 ms | 50.1 ms | 66.6 ms | — | — |
| **Cells in 10 km Radius ($N$)** | 3,064 cells | 3,477 cells | 3,482 cells | ~3.5k mobile radius | — |
| **`setFeatureState` Loop (Median / p95)** | 0.8 ms / 1.0 ms | 0.6 ms / 0.8 ms | 0.9 ms / 1.2 ms | — | — |
| **`setFeatureState` + Idle Median** | **16.45 ms** | **25.70 ms** | **36.80 ms** | **< 100.0 ms** | **PASS** |
| **`setFeatureState` + Idle p95** | 24.1 ms | 42.5 ms | 54.9 ms | — | — |
| **`removeFeatureState` Loop / Idle Med.** | 0.6 ms / 16.5 ms | 0.5 ms / 24.8 ms | 0.7 ms / 37.3 ms | — | — |
| **`applyRecompute` Loop / Idle Med.** | 0.9 ms / 16.25 ms | 1.0 ms / 24.55 ms | 1.2 ms / 36.75 ms | — | — |
| **Shrinking Footprint Stale Clear** | **CONFIRMED** | **CONFIRMED** | **CONFIRMED** | $N \to N/2$ stale drop | **PASS** |
| **Unknown Cells Rendered** | 350 cells (grey) | 1,400 cells (grey) | 3,000 cells (grey) | Verified `#6b7280` | **PASS** |
| **Overall Scale Target Verdict** | **PASS** | **PASS** | **PASS** | All criteria met | **PASS** |

## In Progress
- End-to-end integration with live FastAPI server on port 8000.

## Assumptions
- Pilot area is **Sakleshpur Taluk** (Hassan District, Western Ghats, Karnataka).
  - Center: `[75.775, 12.95]`
  - Bounding Box (WGS84): `[75.60, 12.80, 75.95, 13.10]`
  - Signal threshold: `-100.0 dBm` (uncertain band `±6.0 dB`, max radius `10.0 km`).
- MapLibre GL runs completely offline with a custom local dark vector specification.

## INTEGRATION TODO
- [x] Dev B: `/contracts/config.json` received. `params.ts` adapted to `propagation` object.
- [x] Dev A & B: `web/public/data/cells.geojson` verified (900 features, integer IDs, WGS84 polygons within Sakleshpur box).
- [x] Dev B: Draggable candidate markers and shortlist table wired with click-to-zoom and briefing generator.
- [x] Dev C: Idempotent `applyRecompute` pure function and test suite verified.
- [x] Dev C: Task 2 Double-Drag Test & API Contract Verification (CDP automation, request sequence guard, stale footprint elimination).
- [x] Dev C: Task 3 Visual Verification, State Colors & Legend Synchronization (CDP automation, pixel sampling, unknown-as-grey invariant).
- [ ] Dev B: Run FastAPI backend concurrently (`uvicorn api.main:app --port 8000`) for live multi-tower what-if testing.

## Task 2 Double-Drag Test & Contract Verification [MOCK HANDLER]

### A. API Reachability & CORS
- **Host Environment Check**: Attempted `uvicorn api.main:app --port 8000`. Python 3.14 on host system lacks `uvicorn`, `fastapi`, `numpy`, and `rasterio` (Python environment owned by Dev A/B). Per Section A.1 rule, real-API startup stopped and evaluated against the mock handler on port 8000 labeled **MOCK HANDLER**.
- **CORS Verification**: `OPTIONS http://localhost:8000/recompute` and `GET /docs` tested from `http://localhost:5173`. Confirmed header `Access-Control-Allow-Origin: *` -> **PASS**.

### B. Contract Checks (No UI Fetch / Curl) [MOCK HANDLER]
1. **Empty Towers (`POST {"towers": []}`)**:
   - Response: `changed: []`, `newly_covered_pop: 0`, `total_unserved_pop: 364,978`.
   - Independent baseline gap pop from `cells.geojson` (cells with `state == "gap"`): **361,044**.
   - **Finding (Mismatch)**: `total_unserved_pop` (364,978) vs independent gap pop (361,044) is a difference of **3,934**. This exactly equals the population of the 189 `unknown` cells whose baseline dBm is `null` (< -106 dBm). The API counts all cells below -106 dBm as unserved regardless of whether `state` is `"gap"` or `"unknown"`.
2. **First Candidate Tower (`CAND-09`: lat 12.960828, lon 75.774295, height_m 30.0, power_dbm 43.0)**:
   - Response time: **24.8 ms**.
   - `changed` count: **2,653 cells**.
   - `newly_covered_pop`: **38,141**.
   - `total_unserved_pop`: **326,837** (364,978 - 38,141 = 326,837).
3. **Newly Covered Population Check**:
   - Independent calculation from `cells.geojson` (cells in `changed` with baseline state `"gap"` and new dBm $\ge -94.0\text{ dBm}$ [`gap_threshold + uncertain_band`]): **5,010**.
   - Server `newly_covered_pop`: **38,141**.
   - **Finding (Mismatch)**: Server classifies any cell lifted to $\ge -106.0\text{ dBm}$ (above gap threshold - margin) as newly covered (`now_covered = effective_dbm >= -106.0`), whereas strict covered band $\ge -94.0\text{ dBm}$ captures only high-confidence coverage. Reported as contract finding, not modified.
4. **Idempotence & Footprint Overlap**:
   - Duplicate request: identical responses -> **PASS (Idempotent)**.
   - Moved tower (~3 km away at `12.975, 75.782`): Footprint 1 has 2,653 cells; Footprint 2 has 2,601 cells; intersection is 1,859 cells. Exactly **794 cells** from Footprint 1 are absent in Footprint 2 (candidate footprint successfully shifted).
5. **Contract Edge Cases**:
   - Tower far outside taluk (`0.0, 0.0`): HTTP 200 OK (`changed: []`, `newly_covered_pop: 0`, `total_unserved_pop: 364,978`). Shape valid -> **PASS**.
   - Extra unknown fields (`{"towers": [...], "foo": "bar"}`): HTTP 200 OK. Shape valid -> **PASS**.
   - Missing `height_m`: HTTP 200 OK (server defaults to 30.0m). Shape valid -> **PASS**.

### C. Browser Double-Drag Automation (CDP in Headless Chromium) [MOCK HANDLER]
Automated via [`scratch/run_double_drag_cdp.mjs`](file:///C:/Users/20635/.gemini/antigravity/brain/ada43e68-e0e2-4fb7-b0e8-99fdeed257b1/scratch/run_double_drag_cdp.mjs):
- **Request Throttling (Drag vs Drop)**:
  - Intercepted network requests over 20 discrete mousemove steps: **0 `/recompute` requests** during drag movement -> **PASS**.
  - On mouse release (Drop): **EXACTLY ONE `/recompute` request** triggered -> **PASS**.
  - Payload audit: contains only the 5 candidate towers with valid coordinates -> **PASS**.
- **Drop 1 Verification (Point P1: `12.965, 75.778`)**:
  - Overridden cells populated: **3,967 cells**.
  - Sample cells verified with numeric `dbm` feature-state. Counter panel updated to `55,155` newly covered -> **PASS**.
  - Screenshot: [`web/e2e-output/drop1.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/drop1.png) (92.3 KB).
- **Drop 2 Verification (Point P2: ~3 km away at `12.975, 75.782`)**:
  - Overridden cells populated: **4,083 cells**.
  - Union footprint audit across 4,103 cells:
    - Active cells in Drop 2: **4,083** all have valid `dbm` feature-state -> **PASS**.
    - Dropped cells only in Drop 1: `staleFound === 0` (all stale feature-state completely removed) -> **PASS**.
  - Screenshot: [`web/e2e-output/drop2.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/drop2.png) (93.1 KB).
- **Far-Away Drop (Footprint Cleared)**:
  - Candidates moved outside taluk (`changed = []`):
    - `newlyCoveredPop === 0` -> **PASS**.
    - Overridden IDs count: **0** -> **PASS**.
    - All cell feature-states cleared: **PASS**.
  - Screenshot: [`web/e2e-output/drop_far.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/drop_far.png) (90.8 KB).
- **Rapid Double-Drop (<100 ms) & Out-of-Order Guard**:
  - Built pure [`RequestSequenceGuard`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/utils/requestSequence.ts) with monotonic sequence counters.
  - Triggered Drop A and Drop B separated by 30 ms. Intermediate out-of-order response was safely ignored; final map state converged exactly on the last drop (`CAND-09` at `12.975, 75.782`, 2,659 cells, 35,644 newly covered) -> **PASS**.
- **React Dev Mode Bug Discovery & Fix**:
  - Identified that calling `runRecompute` inside `setCandidates(prev => ...)` caused double-invocation under React 18 development mode.
  - Fixed in [`App.tsx`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/App.tsx) by holding `candidatesRef.current`, updating the ref synchronously, and calling `runRecompute` outside the React setState updater.

### D. Verification & Build
- Vitest: **25 / 25 unit tests passed** across all 5 test files (`styleExpressions`, `recompute`, `params`, `components`, `requestSequence`).
- Production build: `npm run build` completed cleanly; `dist/assets/*.js` contains **0 occurrences** of `__bench` (tree-shaking verified).

## Task 3 Visual Verification, Colors & Legend Synchronization [REAL DATA]

### A. One Source of Truth for Colors & Thresholds
- **Single Source of Truth**: Created [`web/src/config/stateColors.ts`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/config/stateColors.ts) exporting `STATE_COLORS` (`covered: '#10b981'`, `uncertain: '#f59e0b'`, `gap: '#ef4444'`, `unknown: '#6b7280'`).
  - Used directly by [`styleExpressions.ts`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/utils/styleExpressions.ts) for MapLibre GPU rendering.
  - Used directly by [`Map.tsx`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/src/components/Map.tsx) for inline swatch styles in `.map-floating-legend`.
  - Expression and legend colors cannot drift.
- **Dynamic Threshold Derivation**:
  - `coveredThreshold = params.gap_threshold_dbm + params.uncertain_band_db` (-100 + 6 = -94.0 dBm).
  - `gapThreshold = params.gap_threshold_dbm - params.uncertain_band_db` (-100 - 6 = -106.0 dBm).
  - Legend labels dynamically render `coveredThreshold.toFixed(0)` and `gapThreshold.toFixed(0)`.
  - Grep check for hardcoded `-94`, `-100`, `-106` across `/web/src`: Confirmed 0 hardcoded signal numbers in layout/business logic (only CSS `transform: translate(-50%, -100%)` and parameter fallbacks).

### B. Unit Testing & Boundary Specification (Vitest: 35/35 Passed)
- **Boundary Rule Specification**:
  - **Covered**: $dbm \ge -94.0\text{ dBm}$ (inclusive) -> `#10b981`
  - **Uncertain**: $-106.0\text{ dBm} \le dbm < -94.0\text{ dBm}$ (inclusive of -106.0, exclusive of -94.0) -> `#f59e0b`
  - **Gap**: $dbm < -106.0\text{ dBm}$ (exclusive) -> `#ef4444`
  - **Unknown**: Always grey (`#6b7280`), regardless of signal strength or feature-state overrides.
- **Vitest Boundary Tests (`styleExpressions.test.ts`)**:
  - `dbm = -93.9`: `covered` (`#10b981`) -> **PASS**
  - `dbm = -94.0`: `covered` (`#10b981`, inclusive boundary) -> **PASS**
  - `dbm = -94.1`: `uncertain` (`#f59e0b`, just below covered boundary) -> **PASS**
  - `dbm = -105.9`: `uncertain` (`#f59e0b`, inside uncertain band) -> **PASS**
  - `dbm = -106.0`: `uncertain` (`#f59e0b`, inclusive lower boundary of band) -> **PASS**
  - `dbm = -106.1`: `gap` (`#ef4444`, below band) -> **PASS**
- **Param-Driven Test**: Validated custom thresholds (e.g. -90 dBm / -110 dBm) adjust stops in generated MapLibre expressions -> **PASS**.
- **Unknown-as-Grey Invariant**: Verified unknown cells evaluate to `#6b7280` under baseline -120 dBm, baseline -80 dBm, feature-state -75 dBm, and capitalized `'Unknown'` -> **PASS**.
- **Pure MOCK Banner Condition**: `isMockSource('mock') === true`, `isMockSource('worldpop') === false`, `isMockSource(null/undefined/'') === false` -> **PASS**.

### C. Visual Check in Browser (CDP Automation, Real Cells File)
- **Rendered Cell Counts (11,394 Total Cells in `cells.geojson`)**:
  - `covered`: **308 cells** (2.7%)
  - `uncertain`: **721 cells** (6.3%)
  - `gap`: **10,176 cells** (89.3%), comprising 8,126 with modeled `baseline_dbm` and 2,050 with `baseline_dbm == null`
  - `unknown`: **189 cells** (1.7%)
- **Pixel Sampling for 5 Cell Categories (Alpha Blend $0.75 \times \text{layer} + 0.25 \times \text{bg}$ `#090d16`)**:
  - Basemap lines (`osm-roads-line`, `cells-line`, `taluk-boundary-line`) hidden during sampling.
  - Coordinates projected from true polygon centroids.

| Category | Real Cell ID | Expected RGB | Sampled Actual RGB | Max Channel Diff | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Covered** | 668 | `rgb(14, 142, 102)` | `rgb(15, 144, 104)` | 2 (tolerance 12) | **PASS** |
| **Uncertain** | 96 | `rgb(186, 122, 14)` | `rgb(187, 124, 15)` | 2 (tolerance 12) | **PASS** |
| **Gap (with baseline_dbm)** | 11 | `rgb(182, 54, 57)` | `rgb(182, 56, 58)` | 2 (tolerance 12) | **PASS** |
| **Gap (baseline_dbm null)** | 1 | `rgb(182, 54, 57)` | `rgb(182, 56, 58)` | 2 (tolerance 12) | **PASS** |
| **Unknown** | 8737 | `rgb(83, 89, 102)` | `rgb(83, 91, 103)` | 2 (tolerance 12) | **PASS** |

- **Feature-State Override Test**:
  - Unknown cell #8737 with -80.0 dBm feature-state: sampled `rgb(83, 91, 103)` (expected grey `rgb(83, 89, 102)`, diff 2) -> **PASS (Remains Grey)**.
  - Gap cell #11 with -80.0 dBm feature-state: sampled `rgb(15, 144, 104)` (expected green `rgb(14, 142, 102)`, diff 2) -> **PASS (Turns Covered Green)**.
  - Feature-state cleared and layers restored -> **CONFIRMED**.
- **Legend & Layout Verification**:
  - Swatches match `STATE_COLORS`: Covered (`#10b981`), Uncertain (`#f59e0b`), Gap (`#ef4444`), Unknown (`#6b7280`).
  - Labels verified: `Likely covered (≥ -94 dBm)`, `Uncertain (-106 to -94 dBm)`, `Likely gap (< -106 dBm)`, `Unknown: no tower evidence`.
  - Viewport 1366x768: Modeled badge (`top: 12, left: 383`) and Legend (`top: 528, left: 646`) visible and non-overlapping with shortlist panel and modal open -> **PASS**.
  - Viewport 1920x1080: Modeled badge (`top: 12, left: 383`) and Legend (`top: 840, left: 1200`) visible and non-overlapping with shortlist panel and modal open -> **PASS**.
  - Screenshots captured in `web/e2e-output/`:
    - `viewport_1366x768.png` (152.1 KB)
    - `viewport_1366x768_modal.png` (147.4 KB)
    - `viewport_1920x1080.png` (158.8 KB)
    - `viewport_1920x1080_modal.png` (187.4 KB)
- **Modeled Badge Text & Modals Presence**:
  - Header badge text: exactly `"Modeled, not measured"` -> **PASS**.
  - LimitationsModal: Features `"Modeled, Not Measured"` as Core Principle 1.
  - BriefModal: Section 4 features `"Modeled, Not Measured"` transparency declaration.

### D. Final Build & Tree-Shaking
- Vitest: **35 / 35 tests passed** across all 5 test files.
- `npm run build`: Production build succeeded in 3.20s; `dist/assets/*.js` contains **0 occurrences** of `__bench`.

## Task 4 Loading & Error States Verification [REAL DATA & CDP]

### A. Pure Logic & State Machine (Vitest)
1. **Contract Validation (`web/src/utils/validateRecompute.ts`)**:
   - `validateRecomputeResponse(x)` strictly validates recompute payload shape:
     - `changed`: Array of `[integer id, finite number]` tuples.
     - `newly_covered_pop`: Non-negative integer.
     - `total_unserved_pop`: Non-negative integer.
     - Empty `changed: []` is valid.
     - Extra/unknown keys in response are safely ignored.
     - IDs not present in loaded cells are tolerated without throwing.
   - Comprehensive unit tests: **7 / 7 passed** (`web/src/utils/validateRecompute.test.ts`).
2. **Recompute State Machine (`web/src/utils/recomputeStatus.ts`)**:
   - Transitions: `idle -> loading -> slow (after SLOW_MS) -> success | error | empty`.
   - Timing constants declared in `web/src/config/data.ts`: `SLOW_MS = 1500` ms, `TIMEOUT_MS = 15000` ms (with dev overrides).
   - Sequence tracking: Newer requests immediately cancel older status updates.
   - Timer transitions verified with fake timers: **9 / 9 passed** (`web/src/utils/recomputeStatus.test.ts`).

### B. App Integration & Error Handling
1. **Request Lifecycle & AbortController**:
   - Every candidate marker drop instantiates an `AbortController` coupled with `TIMEOUT_MS`.
   - Subsequent candidate drops immediately abort in-flight requests while incrementing `requestSeqRef`.
2. **Loading States**:
   - Non-blocking `.counter-loading-pill` displayed beside metrics.
   - Counter values remain visible but dimmed (`.dimmed`) while awaiting response.
   - Transitions automatically to `"Still computing, this is taking longer than usual..."` when request duration exceeds 1,500 ms.
   - Map remains fully interactive during calculation.
3. **Error Banner & Non-Destructive Failure**:
   - Failure (network down, HTTP 500, timeout, schema violation) preserves existing feature-state, overridden IDs, and counter numbers.
   - Counters tagged with `"from previous result"` (`.metric-stale-tag`).
   - Accessible banner rendered with `role="alert"` displaying human-friendly error messages (no stack traces or raw JSON).
   - `"Retry"` button triggers immediate recalculation with current candidates.
   - `"Revert marker"` restores candidate marker coordinates to the last successfully computed configuration and dismisses the alert.
4. **Empty Footprint State**:
   - Valid responses with `changed: []` clear previous footprint overrides, set newly covered population to 0, and display a neutral note: `"This position adds no new coverage."`.
5. **Data Asset Boundaries**:
   - `cells.geojson` failure displays a full-panel error overlay with a Retry button while keeping the signal classification legend visible.
   - `candidates.json` failure displays an error state within the shortlist sidebar with Retry while the map and baseline cells remain functional.
   - Modeled badge, legend, and MOCK banner remain visible in all states.

### C. Browser CDP Verification Results Matrix
Automated in headless browser using Chrome DevTools Protocol request interception (`Fetch.enable`):

| Test Case | Scenario / Interception | Expected Message / Behavior | Actual Result | Status | `ids_changed_on_failure` |
|:---|:---|:---|:---|:---:|:---:|
| **(a)** | Connection Refused / Network Down | `"Can't reach the server"` banner (`role="alert"`), counters unchanged, Retry button recovers on network restoration | Exact banner, stale tag shown, Retry restored footprint (1,200 pop) | **PASS** | 0 |
| **(b)** | HTTP 500 Internal Error | `"The server returned an error (HTTP 500)"` banner, counters unchanged | Exact banner displayed, stale tag shown | **PASS** | 0 |
| **(c)** | Slow Request (3s delay) | Pill shows `"Still computing, this is taking longer than usual..."` at 2s; final result applies at 3s | Slow text observed at 2s, final footprint applied at 3.5s (1,500 pop), pill hidden | **PASS** | 0 |
| **(d)** | Request Timeout | `"The server took too long to respond"` banner after timeout exceeds threshold | Abort fired on timeout, exact banner displayed, stale tag shown | **PASS** | 0 |
| **(e)** | Unexpected Response (Bad JSON & Shape) | `"The server sent an unexpected response"` for HTML body and malformed payload | Exact banner displayed for both bad JSON and bad shape | **PASS** | 0 |
| **(f)** | Empty Response (`changed: []`) | Overrides cleared, newly covered = 0, neutral note: `"This position adds no new coverage."`, no error banner | Footprint cleared, note visible, no error banner displayed | **PASS** | 0 |
| **(g)** | Failure After Successful Drop | Previous footprint retained, counters show previous values marked `"from previous result"` | Footprint retained, counter marked with stale tag, error banner displayed | **PASS** | 0 |
| **(h)** | Revert Marker Action | Restores marker position to last successful coordinates, dismisses error banner | Marker restored to `(12.910000, 75.810000)`, error dismissed, active status restored | **PASS** | 0 |
| **(i)** | Rapid Drops (Abort / Sequence Guard) | Drop 1 (delayed) aborted; Drop 2 applies immediately; Drop 1 never overwrites Drop 2 | Drop 2 applied immediately (2,500 pop); Drop 1 response discarded by sequence guard | **PASS** | 0 |
| **Cells Load** | Block `cells.geojson` (HTTP 404) | Full-panel error overlay with Retry button; map legend kept visible | Full-panel overlay rendered; Retry button recovers on unblock | **PASS** | 0 |
| **Shortlist Load** | Block `candidates.json` (HTTP 404) | Shortlist sidebar error state with Retry; map remains interactive | Shortlist error displayed; map functional; Retry recovers on unblock | **PASS** | 0 |

### D. Captured E2E Screenshots
All test states captured in [`web/e2e-output/`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output):
- [`task4_a_connection_error.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_a_connection_error.png) (83.8 KB)
- [`task4_b_http_500.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_b_http_500.png) (84.8 KB)
- [`task4_c_slow_loading.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_c_slow_loading.png) (90.5 KB)
- [`task4_d_timeout.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_d_timeout.png) (84.0 KB)
- [`task4_e_unexpected_response.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_e_unexpected_response.png) (84.3 KB)
- [`task4_f_empty_coverage.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_f_empty_coverage.png) (93.3 KB)
- [`task4_g_stale_result_retained.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_g_stale_result_retained.png) (83.6 KB)
- [`task4_h_reverted_marker.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_h_reverted_marker.png) (93.9 KB)
- [`task4_i_rapid_drops_superseded.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_i_rapid_drops_superseded.png) (94.2 KB)
- [`task4_cells_error_full_panel.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_cells_error_full_panel.png) (59.9 KB)
- [`task4_shortlist_error.png`](file:///c:/Users/20635/OneDrive/Desktop/taar/web/e2e-output/task4_shortlist_error.png) (79.8 KB)

### E. Final Test Suite & Build Verification
- **Vitest Unit Test Suite**: **51 / 51 tests passed** across all 7 test files (`recompute`, `validateRecompute`, `recomputeStatus`, `styleExpressions`, `requestSequence`, `components`, `params`).
- **Production Build**: `tsc && vite build` completed cleanly in 6.83s.
- **Tree-Shaking Verification**: `dist/assets/*.js` contains **0 occurrences** of `__bench`.
