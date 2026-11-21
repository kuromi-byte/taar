## Rural Coverage Gap Mapper: Project Documentation and 18-Hour Implementation Guide

Bits2Wave hackathon, SW-27 + SW-34, team of four, 21 November 2026

This is the working reference for the sprint. Part 1 explains the project. Part 2 fixes the stack and the technical rules. Part 3 is the step-by-step build guide with a task list for each of the four developers. Part 4 covers the demo, the risks and the definition of done. Numbers marked "starting value" are assumptions to tune, not findings.

## Part 1. Project documentation

## 1.1 The problem in plain terms

In many Indian villages, phone signal is weak or missing, which blocks telemedicine, online classes, emergency calls and digital payments. New towers are expensive, so the people who fund them need to know which areas to look at first and be able to justify the choice.

Government tracks coverage village by village. A village can count as covered while a hamlet behind a hill gets nothing. Telcos know their own networks well, but there is no simple open view at hamlet level that tells an outside planner where a survey is worth sending a team. Whether this is the real gap is a hypothesis we are building toward, not something verified.

## 1.2 The two problem statements and how they combine

- SW-27, Rural Coverage Gap Mapper: find underserved settlements and recommend candidate tower locations.

- SW-34, Coverage Dead-Zone Heatmap Tool: estimate weak-signal areas from tower location and power, and let the user change them and compare before and after.

One product covers both: see the gaps, get a ranked shortlist, test changes, and produce a brief.


## 1.3 What we are building

Name: Gap-to-Brief

Pitch: a screening tool that finds places likely to be underserved, shows how confident we are, shortlists feasible sites worth surveying, and produces a one-page brief per cluster.

Tagline: Find the gaps worth verifying. Shortlist the sites worth surveying.

Intended user: a state IT or Digital Bharat Nidhi-side planner, policy analyst or NGO deciding which clusters to survey and fund next.

What it is not: a replacement for telco RF planning suites, a siting decision tool, or a measurement of real signal. Everything shown is modeled and labeled as such.

## 1.4 Features

## Must-have

- 1. Gap map: 300 m population cells colored by modeled signal, with the total unserved population.

- 2. Uncertainty band: cells near the gap threshold are shown as uncertain, not as hard red or green.

- 3. Ranked site shortlist with hard feasibility filters and visible flags.

- 4. What-if editor: drag a candidate tower, change height and power, see the heatmap and a "+N newly covered" counter update on drop.

- 5. One-page printable brief per cluster.

- 6. Persistent Modeled badge and a methods and limitations slide.

## Stretch, only if ahead of schedule

- Sensitivity test: add random noise to signals, rerun the ranking about 20 times, and report how stable the top 5 sites are.

- Scenario comparison table, for example top 5 sites versus cheapest 3.

- Validation against real phone logs (see 2.7). This is cut by default.

## Cut

- deck.gl, H3, the building-footprint mask, OSM power lines and GP offices, VIIRS night lights, PDF libraries, and any synthetic validation data.


## 1.5 Honest limits (these go on the limitations slide)

- Signal is estimated from a standard propagation formula plus a terrain penalty, not measured.

- OpenCellID is crowd-sourced and biased toward highways and towns, so it is a lower bound on real towers. Missing data is shown as Unknown, never as a dead zone.

- Published studies in other regions report model errors of roughly 5 to 11 dB. We have not validated this for Karnataka.

- Land, grid power and fiber backhaul cannot be known from open data, so output is a survey shortlist, not a siting decision.

- Operators differ. The map uses one stated frequency baseline and a combined tower view, and says so.

## Part 2. Technical specification

## 2.1 Stack

- Data prep and model: Python 3.11, numpy, rasterio, geopandas, shapely, pyproj. Add numba only if the benchmark misses the target.

- API: FastAPI with uvicorn. Arrays load into memory at startup.

- Storage: static files only (GeoJSON, JSON, .npy ). No database.

- Frontend: React with Vite, plain MapLibre GL. No deck.gl.

- CSV parsing (stretch only): PapaParse.

- Brief: an HTML page with a print stylesheet, saved as PDF from the browser.

- Run mode: everything local on one laptop, with data cached and no external requests.

## 2.2 Fixed technical rules

- 1. One coordinate system. Reproject everything to UTM zone 43N (EPSG:32643) early. Mixed coordinate systems are the usual cause of silent bugs. Only convert back to lat/lon for the map.

- 2. Cell grid. Sum 3x3 blocks of WorldPop's 100 m raster to get 300 m cells. Drop cells below a population threshold calibrated by comparing against satellite imagery (a starting value is about 5 people per cell, to be checked). Assign each remaining cell an integer id from 0 to N.


- 3. One model function. The baseline map, the candidate ranking and the recompute endpoint all call the same function. This guarantees the live counter never contradicts the base map.

- 4. Existing towers are fixed. Only candidate towers can be added, moved or deleted. An existing tower's contribution lives inside the baseline and cannot be undone by taking a maximum.

- 5. Baseline is immutable. baseline_dbm never changes in memory on either side.

- 6. Offline by default. No external tiles and no font glyph requests.

## 2.3 Propagation model

- Frequency baseline: 900 MHz or 1800 MHz, one chosen and stated. COST-231 Hata is meant for roughly 500 to 2000 MHz.

- Path loss: COST-231 Hata with the suburban/rural correction term set to 0. Dev A implements it from a reference and checks it against one hand-calculated value before using it.

- Defaults, all flagged "assumed" in the data: tower height, transmit power, receiver height. Starting values to tune: tower height 30 m, receiver height 1.5 m.

- Terrain by polar sweep:

- 1. From the tower, cast 720 rays (0.5 degree spacing) outward at 30 m steps, out to a maximum radius (starting value 10 km).

- 2. Sample the DEM at the native 30 m resolution along each ray.

- 3. For each sample, compute the elevation angle from the antenna to that ground point.

- 4. Take the running maximum of those angles along the ray in one vectorized pass ( np.maximum.accumulate ).

- 5. Map each population cell to its nearest ray and distance bin. If the cell's own elevation angle is below the running maximum at that distance, it is shadowed.

- 6. Add a flat penalty to shadowed cells (starting value 15 to 20 dB, flagged as assumed).

- Best server: a cell's signal is the maximum received power across towers.

- Gap threshold: configurable (starting value around -105 dBm). Uncertain band: cells within a configurable margin of the threshold (starting value about 6 dB, tune so it stays informative).


- Cell states: Likely covered, Likely gap, Uncertain, Unknown (no tower evidence nearby).

## 2.4 Candidate generation and ranking

- 1. Group gap cells into clusters (connected components or simple density grouping).

- 2. Propose candidate sites inside or near each cluster, favouring cells with high local elevation prominence. Prominence is a score feature, not a filter, because roads in hills usually follow valleys.

- 3. Apply hard pass/fail filters (starting values): slope below about 15 degrees at the site, road within about 1 km. Add a forest exclusion only if WorldCover is easy to include.

- 4. Compute added population per surviving candidate using the shared model function.

- 5. Select greedily: take the best, mark its cells as covered, recompute the rest, repeat to get the top N.

- 6. Show feasibility flags as visible columns (road distance, slope, backhaul unknown). Do not fold them into a multiplied score.

- 7. If a cluster has no surviving candidate, output "needs field survey".

- 8. Generate a templated "why this site" sentence from the numbers.

## 2.5 Data contracts (lock in Hour 1)

These files let all four people work in parallel. Dev C and Dev D build against hand-made mock versions until the real ones land.

- cells.geojson : static, loaded once. Each feature has integer id 0..N , a polygon or point, and properties: pop , baseline_dbm , state .

- towers.json : existing towers with id , lat , lon , height , power , assumed (boolean).

- candidates.json : each entry has id , lat , lon , cluster_id , added_pop , flags ( road_km , slope_deg , backhaul ), why .

- where available). clusters.json : id , cell_ids , pop_in_gap , candidate_ids , villages (names

- lon , height , power ). Response is { "changed": [[id, dbm], ...], "newly_covered_pop": N, "total_unserved_pop": M } , containing only cells that differ from baseline. POST /recompute : request body is the full current list of candidate towers ( lat ,


- basemap/*.geojson : taluk boundary, roads, and optionally water polygons.

## 2.6 Frontend technical rules

- Cells layer: a fill or circle layer over the static GeoJSON. Color is a data-driven expression that uses feature-state dbm if present and falls back to the baseline_dbm property. Do not use MapLibre's heatmap layer, which is a density layer, not a signal layer.

- Applying a recompute response: keep a set of ids currently overridden. For each response, call removeFeatureState on ids that dropped out of the response and setFeatureState for the rest. This makes the update idempotent and prevents stale footprints after a second drag.

- Drag: use MapLibre's draggable marker for candidate towers, and call /recompute on drop only, never on every mouse move.

- Orientation: 6 to 8 HTML markers for the taluk headquarters, major towns and landmarks. HTML text needs no font glyph files, so it works offline.

- Counter: takes newly_covered_pop and total_unserved_pop straight from the server response.

- Time it: measure how long setFeatureState takes for the number of cells in a 10 km radius before depending on it.

## 2.7 Validation policy

- Default: cut. The project does not depend on it. The limitations slide states that results are modeled and unvalidated for Karnataka.

- Stretch, with real data only: a short walk logged with a phone signal app can show that the CSV parser and a held-out error calculation work. Fit any bias offset on one part of the route and report error on the held-out part. Frame it as a method demo, not an accuracy claim. It needs that area's DEM and the matching operator's towers, so do not plan the sprint around it.

- Never show synthetic data as if it were measurements.

## 2.8 Repository layout

- /pipeline : data prep and model (Python)

- /api : FastAPI app


- /web : React and MapLibre app, including /web/public/data for the static files

- /data/raw (not committed) and /data/processed

- /brief : brief template

- /docs : slides and this guide

Git rules: merge to main at least every two hours, one feature per branch, and never commit raw data files.

## Part 3. Step-by-step implementation guide

## 3.1 Roles at a glance

- Dev A: Model engine (M2). Propagation, polar sweep, best-server signal, gap flags, performance.

- Dev B: Data and ranking (M1 and M3). Population grid, towers, roads and slope, then candidates, ranking and the API.

- Dev C: Frontend (M4). Map, layers, shortlist table, drag-and-drop, counter.

- Dev D: Basemap, brief and demo (M5). Local basemap data, brief template, slides, demo script, QA and integration support.

Dev B carries two modules, but they are sequential. Dev D also takes the basemap data so Dev B is not the bottleneck. If B falls behind, A and D help B first.

## 3.2 Before Hour 0

- Pick the pilot taluk. Prefer a hilly fringe area with real elevation shadows, not a flat peri-urban one. This must be decided before the clock starts because every download depends on it.

- Check that every team member has Python 3.11, Node 20 or later, and git working.

## 3.3 Hour 0 to 1: kickoff, all four

- 1. Create the repo and folders above.

- 2. Start downloads immediately (they are the slowest step):

- Dev A: SRTM or Copernicus DEM tiles and OpenCellID.


- Dev B: WorldPop 100 m raster and the OSM extract for roads.

- 3. Lock the data contracts in 2.5 by committing small hand-made mock files.

- 4. Dev A: write the polar-sweep benchmark (Hata plus 720 rays for one tower on a small DEM crop) and time it.

- 5. Dev B: run the smear audit. Aggregate WorldPop to 300 m for a sample area, overlay on satellite imagery, and try thresholds until the lit cells match settlements.

- 6. Dev C: scaffold Vite, React and MapLibre, and render the mock cells with the feature- state color expression.

- 7. Dev D: draft the brief template with mock data, and start exporting the taluk boundary and roads to GeoJSON.

Checkpoint, end of Hour 1: contracts committed, downloads running, benchmark number known. If the benchmark misses about 500 ms, Dev A tries numba, and if still slow the team switches to a click-to-recompute button.

## 3.4 Hour 1 to 6: parallel build

## Dev A: Model engine

- 1. Implement COST-231 Hata and check it against one hand-calculated value. (45 min)

- 2. Implement the polar sweep: DEM sampling along rays, running maximum obstruction angle, cell-to-ray mapping, flat penalty for shadowed cells. (2 hours)

- 3. Implement best-server received power from a tower list. (45 min)

- 4. Test on the real DEM with hand-entered towers, then with Dev B's cell grid as soon as it lands. (1 hour)

- 5. Write baseline_dbm and state into cells.geojson through a single function that both the pipeline and the API import. (45 min)

- Done when: the model runs for a small real area and produces plausible signal that drops off with distance and behind ridges.

## Dev B: Data (M1)

- 1. Build the 300 m cell grid with population, filtered by the calibrated threshold, with integer ids. Deliver this as a plain file by about Hour 2, before anything else, so Dev A is unblocked. (about 1.5 hours)

- 2. Load OpenCellID towers for the pilot area. Mark default height and power as assumed. (45 min)

- 3. Compute slope from the DEM and road distance per cell from OSM. (1 hour)


- 4. Mark cells with no tower evidence nearby as Unknown. (30 min)

- Done when: towers.json and a cell file with pop , slope and road distance exist for the pilot area.

## Dev C: Frontend

- 1. Load static cells and render with the feature-state expression. (1 hour)

- 2. Add the basemap layers from Dev D's GeoJSON and 6 to 8 HTML town markers. (45 min)

- 3. Build the counter panel, the Modeled badge, and an empty shortlist table fed by mock candidates.json . (1.5 hours)

- 4. Add the draggable candidate marker and a stub that logs the recompute request body. (1 hour)

- Done when: the map renders mock data, labeled and oriented, with a draggable marker.

## Dev D: Basemap, brief and slides

- 1. Export the taluk boundary, roads and optionally water to light GeoJSON files. Simplify geometry so they load fast. (1.5 hours)

- 2. Build the printable brief template with mock data: cluster summary, top candidate sites with flags, the limitations paragraph, the Modeled disclaimer. (2 hours)

- 3. Outline the slides and draft the methods and limitations slide using the points in 1.5. (1 hour)

- Done when: basemap files are in /web/public/data and the brief prints cleanly to PDF.

Checkpoint, end of Hour 6: the baseline map renders real data end to end. If Dev B is more than about an hour late, Dev C and Dev D keep going on mock data and Dev A and Dev D help Dev B.

## 3.5 Hour 6 to 12: features

## Dev B: Ranking and API (M3)

- 1. Cluster gap cells and generate candidate sites with an elevation prominence score. (1.5 hours)


- 2. Apply hard filters, then greedy selection using the shared model function. Output candidates.json and clusters.json , including needs-field-survey clusters. (2 hours)

- 3. Templated "why this site" text. (30 min)

- 4. FastAPI app: load baseline arrays at startup, implement POST /recompute returning only cells that differ from baseline. (2 hours)

- Done when: the endpoint returns a correct changed list, and a second call with a moved tower returns no leftover cells from the first.

## Dev A: Performance and correctness

- 1. Optimize the sweep (precomputed ray indices, numba if needed) until /recompute is comfortably under a second. (2 hours)

- 2. Add the uncertain band and the Unknown handling to the state logic. (1 hour)

- 3. Write unit tests for Hata and for the shadow logic (a synthetic ridge must shadow cells behind it). (1 hour)

- 4. If time remains, start the sensitivity test script (stretch).

## Dev C: Wire real data

- 1. Replace mock files with real ones. (45 min)

- 2. Ranked shortlist table with click to zoom, showing flags as columns. (1.5 hours)

- 3. Connect the drag on drop to /recompute , apply the idempotent update with setFeatureState and removeFeatureState , and update the counter. (2 hours)

- 4. Before and after toggle. (45 min)

- Done when: dragging a candidate twice shows correct footprints with no leftovers.

## Dev D: Brief and supporting views

- 1. Connect the brief template to real clusters.json and candidates.json and a "Generate brief" button for the selected cluster. (2 hours)

- 2. Prepare the demo script and the Q&A answers from 4.3. (1 hour)

- 3. Test the full flow on a second laptop. (1 hour)

Checkpoint, end of Hour 11: what-if works end to end. If not, switch to a place-tower-and- click-recompute button.


## 3.6 Hour 12 to 13: integration and freeze, all four

- Merge everything to main , run the full flow from a clean checkout, and fix integration bugs.

- Feature freeze at the end of Hour 13. Anything unfinished is cut.

## 3.7 Hour 13 to 16: hardening

- Dev A and Dev B: edge cases (clusters with no candidates, empty responses, towers dragged outside the data area), and correctness spot-checks against the sample towers.

- Dev C: polish, loading states, error messages, and a test with the network disabled to confirm nothing requests external resources.

- Dev D: fill the brief from real output, finish all slides, and add the limitations slide.

## 3.8 Hour 16 to 18: demo prep

- Two full rehearsals with timing.

- Record a backup screen capture of a clean run.

- Cache all data locally. No code changes in the last hour.

- Charge laptops, prepare a second machine, and carry the data on a USB drive.

## 3.9 Cut order if behind

- 1. Stretch items (sensitivity test, scenario table, validation).

- 2. Live drag (fall back to click-to-recompute).

- 3. Water polygons and extra markers.

- 4. Templated explanations (keep the table).

Never cut: the Modeled labels, the uncertain and Unknown states, the brief, and the limitations slide.


## Part 4. Demo, risks and completion

## 4.1 Three-minute demo flow

- 1. Open the pilot taluk. Show the signal map, the Modeled badge, the uncertain band, and the unserved population number.

- 2. Open the ranked shortlist and click a site to zoom. Point out the feasibility flags and a cluster marked needs field survey.

- 3. Drag a candidate tower. Show the heatmap and the "+N newly covered" counter change. Drag it a second time to show it resets cleanly.

- 4. Open the one-page brief for a cluster.

- 5. Close with the limitations slide: modeled, not measured, and a triage tool.

## 4.2 Risk register

- Pilot area has no real dead zones. Choose a hilly fringe taluk and check early that the baseline map shows gaps. If it shows almost none, move the pilot before Hour 1 ends.

- Data wrangling overruns. Dev B delivers the plain cell grid first. If anything slips, A and D help B.

- Recompute is too slow. Benchmark in Hour 0. Fall back to click-to-recompute. Never silently drop the terrain penalty.

- Feature-state update is slow. Time it early. If it lags, reduce the radius or the cell count.

- Venue Wi-Fi fails. Everything runs locally, with no external tiles or glyphs. Test with the network disabled.

- Official uncovered-village list is messy. Not part of the core pipeline. Use it only as an optional overlay if it joins cleanly.

- Sparse tower data creates a sea of Unknown. Measure the Unknown share early. If it is very high, say so openly and lean on the shortlist and brief.

## 4.3 Likely judge questions

- Why not use an existing RF tool? Those need proprietary drive-test and antenna data. This is a screening and justification tool for people who do not have it.


- Why not just walk around with a phone? One walk covers one village. Ranking many villages and deciding where to send survey teams is a different job.

- How accurate is it? Say plainly that it is modeled and unvalidated for Karnataka. Cite the 5 to 11 dB range from studies in other regions, and point to the uncertain band. If the sensitivity test was run, give the top-5 stability result.

- What about land, power and backhaul? These cannot be known from open data. The output is a survey shortlist with visible flags.

- What if OpenCellID is missing towers? It is treated as a lower bound, and cells without evidence are shown as Unknown, not dead.

## 4.4 Definition of done

- The app runs from a clean checkout on one laptop with the network disabled.

- The map shows real data for the pilot area with labels and the Modeled badge.

- A ranked shortlist with flags is visible, and at least one cluster demonstrates the needs-field-survey outcome.

- Dragging a candidate tower updates the heatmap and counter, and a second drag leaves no stale footprint.

- A one-page brief prints cleanly for a selected cluster.

- The slide deck includes the methods and limitations slide.

- A backup screen recording exists.

## 4.5 Open items to settle in Hour 0

- Which pilot taluk, and does its baseline map show real gaps?

- Which frequency baseline (900 or 1800 MHz)?

- Exact thresholds (population cutoff, gap threshold, uncertain band), all starting values to tune.

- Confirmed role owners, and whether the team size changes the split.
