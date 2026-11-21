"""Re-time one-tower recompute on real cell count, and through the API."""
import time
import numpy as np
from pathlib import Path
import json

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.model.shadow import PolarSweepEngine
from api.main import app, load_baseline, recompute, CandidateTower

REPO_ROOT = Path(__file__).resolve().parents[2]


def benchmark_recompute():
    load_baseline()
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    dem = DEMGrid.from_file(str(dem_path))
    cfg = PropagationConfig()

    cells_path = REPO_ROOT / "data" / "processed" / "cells.geojson"
    with open(cells_path, "r") as f:
        cells_json = json.load(f)
    n_cells = len(cells_json["features"])

    test_tower_dict = {
        "id": 999,
        "lat": 12.972,
        "lon": 75.785,
        "height": 30.0,
        "power": 43.0,
    }
    test_cand_obj = [CandidateTower(
        id=999,
        lat=12.972,
        lon=75.785,
        height_m=30.0,
        power_dbm=43.0,
    )]

    # 1. Benchmark direct compute_signal
    engine = PolarSweepEngine(cfg)
    # Warmup
    compute_signal(cells_json, [test_tower_dict], dem, cfg, polar_engine=engine)

    n_runs = 20
    t_direct = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        sig, dists = compute_signal(cells_json, [test_tower_dict], dem, cfg, polar_engine=engine)
        t1 = time.perf_counter()
        t_direct.append((t1 - t0) * 1000.0)

    # 2. Benchmark through API recompute function
    recompute(test_cand_obj)
    t_api = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        resp = recompute(test_cand_obj)
        t1 = time.perf_counter()
        t_api.append((t1 - t0) * 1000.0)

    avg_direct = np.mean(t_direct)
    min_direct = np.min(t_direct)
    avg_api = np.mean(t_api)
    min_api = np.min(t_api)

    print("\n" + "=" * 70)
    print(f"ONE-TOWER RECOMPUTE BENCHMARK ({n_cells} cells)")
    print("=" * 70)
    print(f"1. Direct compute_signal() (720-ray polar sweep + Hata + shadows):")
    print(f"   Average: {avg_direct:.2f} ms | Min: {min_direct:.2f} ms")
    print(f"2. Through API recompute() (payload parsing + model + changed mask):")
    print(f"   Average: {avg_api:.2f} ms | Min: {min_api:.2f} ms")
    print(f"Changed cells returned: {len(resp.changed)}")
    print(f"Newly covered population: {resp.newly_covered_pop}")
    print(f"Remaining unserved population: {resp.total_unserved_pop}")
    print(f"Requirement (< 1000 ms): {'PASS' if avg_api < 1000.0 else 'FAIL'}")
    print("=" * 70)


if __name__ == "__main__":
    benchmark_recompute()
