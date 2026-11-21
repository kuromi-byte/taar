"""Benchmark script for Polar Sweep and COST-231 Hata computation.

Measures the execution time (in milliseconds) of casting 720 rays at 30 m steps
out to 10 km on a DEM, evaluating terrain shadowing, and computing received power
for thousands of population cells.
"""
import time
import numpy as np
from pathlib import Path
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.model.shadow import PolarSweepEngine

_REPO_ROOT = Path(__file__).resolve().parents[2]


def run_benchmark(num_cells: int = 5000, num_iterations: int = 10):
    print("=" * 60)
    print("POLAR SWEEP & PROPAGATION MODEL BENCHMARK")
    print("=" * 60)

    # 1. Setup DEM
    dem_path = _REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    try:
        print(f"Loading real DEM from {dem_path}...")
        dem = DEMGrid.from_file(str(dem_path))
        print(f"DEM loaded successfully: {dem.width}x{dem.height} pixels (resolution {dem.res_x}m)")
    except Exception as e:
        print(f"Using synthetic DEM due to: {e}")
        dem = DEMGrid.create_synthetic(base_elevation_m=900.0, ridge_distance_m=1200.0)

    cfg = PropagationConfig()
    engine = PolarSweepEngine(cfg)

    # 2. Setup Tower
    tower_x = (dem.left + dem.right) / 2.0
    tower_y = (dem.top + dem.bottom) / 2.0
    tower = {
        "id": 101,
        "x": tower_x,
        "y": tower_y,
        "height": 30.0,
        "power": 43.0,
    }

    # 3. Setup Cells: distribute randomly within 10 km radius
    np.random.seed(42)
    angles = np.random.uniform(0, 2 * np.pi, num_cells)
    radii = np.random.uniform(100.0, 10000.0, num_cells)
    cell_x = (tower_x + radii * np.sin(angles)).astype(np.float32)
    cell_y = (tower_y + radii * np.cos(angles)).astype(np.float32)
    cells = {"x": cell_x, "y": cell_y}

    print(f"Benchmarking with 1 tower and {num_cells} population cells over {num_iterations} runs...")

    # Warmup
    compute_signal(cells, [tower], dem, cfg, polar_engine=engine)

    # Time tower polar sweep alone
    sweep_times = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        sweep_angles, z_ant = engine.compute_tower_sweep(tower_x, tower_y, tower["height"], dem)
        t1 = time.perf_counter()
        sweep_times.append((t1 - t0) * 1000.0)

    # Time end-to-end compute_signal
    total_times = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        sig, dists = compute_signal(cells, [tower], dem, cfg, polar_engine=engine)
        t1 = time.perf_counter()
        total_times.append((t1 - t0) * 1000.0)

    avg_sweep_ms = np.mean(sweep_times)
    min_sweep_ms = np.min(sweep_times)
    avg_total_ms = np.mean(total_times)
    min_total_ms = np.min(total_times)

    print("-" * 60)
    print(f"Polar Sweep (720 rays x 333 steps = 239,760 DEM samples):")
    print(f"  Average time: {avg_sweep_ms:.2f} ms (Min: {min_sweep_ms:.2f} ms)")
    print(f"End-to-end compute_signal ({num_cells} cells + Hata + Shadows):")
    print(f"  Average time: {avg_total_ms:.2f} ms (Min: {min_total_ms:.2f} ms)")
    print("-" * 60)

    if avg_total_ms < 1000.0:
        print(f"RESULT: PASS! Latency ({avg_total_ms:.2f} ms) is well under target (< 1000 ms).")
    else:
        print(f"RESULT: FAIL! Latency ({avg_total_ms:.2f} ms) exceeded 1000 ms.")
    print("=" * 60)
    return avg_total_ms


if __name__ == "__main__":
    run_benchmark()
