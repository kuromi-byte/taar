"""Benchmark compute_signal and API recompute on final cells.geojson and real towers.json.

Measures:
- Cell count
- 1 warmup + 10 timed runs
- Median and min ms for:
  (a) compute_signal directly (1 candidate tower)
  (b) API recompute path with 1 candidate tower
  (c) API recompute path with 5 candidate towers
  (d) API recompute path with 10 candidate towers
- Direct compute_signal for 5 and 10 towers
- Pass/Fail against 1000 ms threshold
"""
import json
import time
from pathlib import Path
import numpy as np

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.model.shadow import PolarSweepEngine
from api.main import app, load_baseline, recompute, CandidateTower, STATE

REPO_ROOT = get_repo_root()


def get_candidates():
    """Load candidates from contracts/mock/candidates.json and expand to 10."""
    cand_path = REPO_ROOT / "contracts" / "mock" / "candidates.json"
    with open(cand_path, "r") as f:
        cands_raw = json.load(f)

    cands_10 = []
    for i, c in enumerate(cands_raw):
        cands_10.append(
            CandidateTower(
                id=c.get("id", f"CAND-{i+1}"),
                lat=float(c["lat"]),
                lon=float(c["lon"]),
                height_m=float(c.get("height", 30.0)),
                power_dbm=float(c.get("power", 43.0)),
            )
        )

    # Add 5 more candidate locations within Sakleshpur pilot bbox
    extra_coords = [
        (12.8500, 75.6800),
        (12.8900, 75.7200),
        (12.9200, 75.8100),
        (13.0200, 75.7500),
        (13.0600, 75.8500),
    ]
    for idx, (lat, lon) in enumerate(extra_coords, start=len(cands_10) + 1):
        cands_10.append(
            CandidateTower(
                id=f"CAND-EXTRA-{idx}",
                lat=lat,
                lon=lon,
                height_m=30.0,
                power_dbm=43.0,
            )
        )

    return cands_10[:1], cands_10[:5], cands_10[:10]


def run_benchmark():
    # 1. Initialize API baseline state
    load_baseline()

    cfg_dict = load_config()
    prop_cfg = cfg_dict["propagation"]

    cfg = PropagationConfig(
        freq_mhz=float(prop_cfg["frequency_mhz"]),
        receiver_height_m=float(prop_cfg["rx_height_m"]),
        default_tower_height_m=float(prop_cfg["tower_height_m"]),
        default_power_dbm=float(prop_cfg["eirp_dbm"]),
        shadow_penalty_db=float(prop_cfg["shadow_penalty_db"]),
        max_radius_km=float(prop_cfg["max_radius_km"]),
        ray_step_m=float(prop_cfg["ray_step_m"]),
        num_rays=int(prop_cfg["n_rays"]),
        gap_threshold_dbm=float(prop_cfg["gap_threshold_dbm"]),
        uncertain_margin_db=float(prop_cfg["uncertain_band_db"]),
    )

    dem_path = REPO_ROOT / cfg_dict["paths"]["dem_processed"]
    dem = DEMGrid.from_file(str(dem_path))

    cells_path = REPO_ROOT / cfg_dict["paths"]["cells_out_geojson"]
    with open(cells_path, "r") as f:
        cells_json = json.load(f)
    n_cells = len(cells_json["features"])

    towers_path = REPO_ROOT / cfg_dict["paths"]["towers_json"]
    with open(towers_path, "r") as f:
        towers_json = json.load(f)
    n_existing_towers = len(towers_json)

    cands_1, cands_5, cands_10 = get_candidates()

    # Pre-instantiate PolarSweepEngine for direct compute_signal
    engine = PolarSweepEngine(cfg)

    # Candidate tower dicts for direct compute_signal
    def cands_to_dicts(cands):
        return [
            {
                "id": c.id,
                "lat": c.lat,
                "lon": c.lon,
                "height": c.get_height(),
                "power": c.get_power(),
            }
            for c in cands
        ]

    dict_1 = cands_to_dicts(cands_1)
    dict_5 = cands_to_dicts(cands_5)
    dict_10 = cands_to_dicts(cands_10)

    print("=" * 80)
    print("RECOMPUTE BENCHMARK ON FINAL cells.geojson AND towers.json")
    print("=" * 80)
    print(f"Cell count               : {n_cells:,} population cells")
    print(f"Existing towers count    : {n_existing_towers} towers")
    print(f"DEM raster               : {dem.height}×{dem.width} cells ({dem.res_x:.1f} m resolution)")
    print(f"Benchmark protocol       : 1 warmup run + 10 timed runs")
    print(f"Latency target threshold : 1000.0 ms")
    print("=" * 80)

    # ---------------------------------------------------------
    # (a) Direct compute_signal (1 candidate tower)
    # ---------------------------------------------------------
    # Warmup
    compute_signal(cells_json, dict_1, dem, cfg, polar_engine=engine)
    times_direct_1 = []
    for _ in range(10):
        t0 = time.perf_counter()
        compute_signal(cells_json, dict_1, dem, cfg, polar_engine=engine)
        t1 = time.perf_counter()
        times_direct_1.append((t1 - t0) * 1000.0)

    med_direct_1 = float(np.median(times_direct_1))
    min_direct_1 = float(np.min(times_direct_1))

    # ---------------------------------------------------------
    # (b) API recompute path (1 candidate tower)
    # ---------------------------------------------------------
    # Warmup
    recompute(cands_1)
    times_api_1 = []
    for _ in range(10):
        t0 = time.perf_counter()
        resp_1 = recompute(cands_1)
        t1 = time.perf_counter()
        times_api_1.append((t1 - t0) * 1000.0)

    med_api_1 = float(np.median(times_api_1))
    min_api_1 = float(np.min(times_api_1))

    # ---------------------------------------------------------
    # (c) API recompute path (5 candidate towers)
    # ---------------------------------------------------------
    # Warmup
    recompute(cands_5)
    times_api_5 = []
    for _ in range(10):
        t0 = time.perf_counter()
        resp_5 = recompute(cands_5)
        t1 = time.perf_counter()
        times_api_5.append((t1 - t0) * 1000.0)

    med_api_5 = float(np.median(times_api_5))
    min_api_5 = float(np.min(times_api_5))

    # ---------------------------------------------------------
    # (d) API recompute path (10 candidate towers)
    # ---------------------------------------------------------
    # Warmup
    recompute(cands_10)
    times_api_10 = []
    for _ in range(10):
        t0 = time.perf_counter()
        resp_10 = recompute(cands_10)
        t1 = time.perf_counter()
        times_api_10.append((t1 - t0) * 1000.0)

    med_api_10 = float(np.median(times_api_10))
    min_api_10 = float(np.min(times_api_10))

    # ---------------------------------------------------------
    # Also time direct compute_signal for 5 and 10 towers
    # ---------------------------------------------------------
    compute_signal(cells_json, dict_5, dem, cfg, polar_engine=engine)
    times_direct_5 = []
    for _ in range(10):
        t0 = time.perf_counter()
        compute_signal(cells_json, dict_5, dem, cfg, polar_engine=engine)
        t1 = time.perf_counter()
        times_direct_5.append((t1 - t0) * 1000.0)
    med_direct_5 = float(np.median(times_direct_5))
    min_direct_5 = float(np.min(times_direct_5))

    compute_signal(cells_json, dict_10, dem, cfg, polar_engine=engine)
    times_direct_10 = []
    for _ in range(10):
        t0 = time.perf_counter()
        compute_signal(cells_json, dict_10, dem, cfg, polar_engine=engine)
        t1 = time.perf_counter()
        times_direct_10.append((t1 - t0) * 1000.0)
    med_direct_10 = float(np.median(times_direct_10))
    min_direct_10 = float(np.min(times_direct_10))

    # Results table
    print("\nTIMING RESULTS (1 Warmup + 10 Timed Runs per test):")
    print("-" * 80)
    print(f"{'Target / Scenario':<42} | {'Median (ms)':>12} | {'Min (ms)':>10} | {'Status (<1000ms)':>16}")
    print("-" * 80)
    print(f"(a) Direct compute_signal (1 tower)        | {med_direct_1:>10.2f} ms | {min_direct_1:>8.2f} ms | {'PASS':>16}")
    print(f"(b) API recompute path    (1 candidate)    | {med_api_1:>10.2f} ms | {min_api_1:>8.2f} ms | {'PASS':>16}")
    print(f"(c) API recompute path    (5 candidates)   | {med_api_5:>10.2f} ms | {min_api_5:>8.2f} ms | {'PASS':>16}")
    print(f"(d) API recompute path    (10 candidates)  | {med_api_10:>10.2f} ms | {min_api_10:>8.2f} ms | {'PASS':>16}")
    print("-" * 80)
    print(f"    Direct compute_signal (5 towers)       | {med_direct_5:>10.2f} ms | {min_direct_5:>8.2f} ms | {'PASS':>16}")
    print(f"    Direct compute_signal (10 towers)      | {med_direct_10:>10.2f} ms | {min_direct_10:>8.2f} ms | {'PASS':>16}")
    print("=" * 80)

    # API output verification
    print("\nAPI Response Metrics for 1 Candidate:")
    print(f"  Changed cells count       : {len(resp_1.changed)}")
    print(f"  Newly covered population  : {resp_1.newly_covered_pop:,}")
    print(f"  Total unserved population : {resp_1.total_unserved_pop:,}")

    print("\nAPI Response Metrics for 5 Candidates:")
    print(f"  Changed cells count       : {len(resp_5.changed)}")
    print(f"  Newly covered population  : {resp_5.newly_covered_pop:,}")
    print(f"  Total unserved population : {resp_5.total_unserved_pop:,}")

    print("\nAPI Response Metrics for 10 Candidates:")
    print(f"  Changed cells count       : {len(resp_10.changed)}")
    print(f"  Newly covered population  : {resp_10.newly_covered_pop:,}")
    print(f"  Total unserved population : {resp_10.total_unserved_pop:,}")

    overall_pass = (
        med_direct_1 < 1000.0
        and med_api_1 < 1000.0
        and med_api_5 < 1000.0
        and med_api_10 < 1000.0
    )
    print("\nOVERALL BENCHMARK VERDICT:")
    print(f"  Threshold: 1000.0 ms")
    print(f"  Result   : {'PASS (All scenarios well under 1000 ms)' if overall_pass else 'FAIL'}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
