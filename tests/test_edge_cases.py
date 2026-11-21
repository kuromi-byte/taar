"""Unit tests for edge cases in compute_signal and classify_state:

1. Tower outside DEM/cell bounding box: no crash, no fake values; out-of-range cells get NaN.
2. Tower on a nodata DEM pixel: no crash, and nodata samples must not block rays (treated as no obstruction).
3. Cell at exactly the tower location (distance 0): finite result, not shadowed by itself.
4. Empty tower list: returns correct shape; all cells null/NaN; state follows tower_evidence ("unknown").
"""
import numpy as np
import pytest
from rasterio.transform import Affine

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state
from pipeline.model.shadow import PolarSweepEngine


def test_tower_outside_dem_bounding_box():
    """Case 1: Tower far outside the DEM and cells bounding box.

    Expectations:
      - No crash.
      - Out-of-range cells get NaN signal (not a fake number).
      - State classification maps NaN signal to 'unknown'.
    """
    center_x = 580000.0
    center_y = 1430000.0
    dem = DEMGrid.create_synthetic(center_x=center_x, center_y=center_y, width_m=10000.0, height_m=10000.0)
    cfg = PropagationConfig(max_radius_km=10.0)

    # Tower 100 km away to the East (far outside DEM bounds [575000, 585000])
    outside_tower = {
        "id": "TOW-OUT",
        "x": center_x + 100000.0,
        "y": center_y,
        "height": 30.0,
        "power": 43.0,
    }

    cells = {
        "x": np.array([center_x, center_x + 1000.0], dtype=np.float32),
        "y": np.array([center_y, center_y + 1000.0], dtype=np.float32),
    }

    signals, dists = compute_signal(cells, [outside_tower], dem, cfg)

    # 1. Shape matches cell count
    assert signals.shape == (2,)
    assert dists.shape == (2,)

    # 2. Distance is > 90 km (correct Euclidean distance, no crash)
    assert dists[0] >= 90.0

    # 3. Signals are NaN (out of range, not a fake number)
    assert np.isnan(signals[0])
    assert np.isnan(signals[1])

    # 4. State classification for out-of-range / NaN cells
    states = classify_state(signals, dists, cfg)
    assert list(states) == ["unknown", "unknown"]


def test_tower_on_nodata_dem_pixel_and_ray_transparency():
    """Case 2: Tower located on a nodata DEM pixel, and rays crossing nodata holes.

    Expectations:
      - No crash.
      - Tower base elevation falls back to valid terrain elevation, not 0 m sea-level pit.
      - Nodata samples along rays do NOT block line-of-sight (treated as no obstruction).
    """
    center_x = 580000.0
    center_y = 1430000.0
    res = 30.0
    rows, cols = 200, 200
    left = center_x - (cols * res) / 2.0
    top = center_y + (rows * res) / 2.0
    transform = Affine(res, 0.0, left, 0.0, -res, top)

    # Base elevation 900m
    data = np.full((rows, cols), 900.0, dtype=np.float32)

    # Punch a 5x5 nodata hole right in the center (tower location)
    mid_r, mid_c = rows // 2, cols // 2
    nodata_val = -9999.0
    data[mid_r - 2 : mid_r + 3, mid_c - 2 : mid_c + 3] = nodata_val

    # Also punch another nodata hole 500m to the East (along ray)
    hole_c = mid_c + int(500.0 / res)
    data[mid_r - 2 : mid_r + 3, hole_c - 2 : hole_c + 3] = nodata_val

    dem = DEMGrid(data=data, transform=transform, nodata=nodata_val)
    cfg = PropagationConfig(max_radius_km=10.0, shadow_penalty_db=15.0)

    tower = {
        "id": "TOW-NODATA",
        "x": center_x,
        "y": center_y,
        "height": 30.0,
        "power": 43.0,
    }

    # Cell 1000m East (beyond the nodata hole along flat ground)
    cells = {
        "x": np.array([center_x + 1000.0], dtype=np.float32),
        "y": np.array([center_y], dtype=np.float32),
    }

    engine = PolarSweepEngine(cfg)

    # 1. Sweep must execute without crash
    sweep_angles, z_antenna = engine.compute_tower_sweep(tower["x"], tower["y"], tower["height"], dem)

    # 2. Antenna elevation must be 900 + 30 = 930m (not 0 + 30 = 30m)
    assert np.isclose(z_antenna, 930.0, atol=1.0), f"Antenna elevation should be ~930m, got {z_antenna}"

    # 3. Ray passing through nodata hole must not be blocked
    cell_elev = dem.sample_points(cells["x"], cells["y"])
    is_shadowed, _ = engine.evaluate_shadows(
        tower["x"], tower["y"], sweep_angles, z_antenna, cells["x"], cells["y"], cell_elev
    )
    assert not is_shadowed[0], "Nodata hole along ray MUST NOT shadow the cell behind it (no obstruction)"

    # 4. Signal must be finite, unshadowed, and classified as covered
    signals, dists = compute_signal(cells, [tower], dem, cfg, polar_engine=engine)
    assert np.isfinite(signals[0])
    # At 1 km with 900 MHz open-area: ~ -54.9 dBm
    assert signals[0] > -70.0
    assert classify_state(signals[0], dists[0], cfg) == "covered"


def test_cell_at_exact_tower_location():
    """Case 3: A cell at exactly the tower location (distance 0).

    Expectations:
      - Finite result (no division by zero).
      - Not shadowed by itself (distance 0 is direct line-of-sight).
      - Covered state.
    """
    center_x = 580000.0
    center_y = 1430000.0
    dem = DEMGrid.create_synthetic(center_x=center_x, center_y=center_y, base_elevation_m=900.0)
    cfg = PropagationConfig(max_radius_km=10.0, shadow_penalty_db=15.0)

    tower = {
        "id": "TOW-COINCIDENT",
        "x": center_x,
        "y": center_y,
        "height": 30.0,
        "power": 43.0,
    }

    # Cell at exactly the tower location (distance = 0.0)
    cells = {
        "x": np.array([center_x], dtype=np.float32),
        "y": np.array([center_y], dtype=np.float32),
    }

    engine = PolarSweepEngine(cfg)
    sweep_angles, z_antenna = engine.compute_tower_sweep(tower["x"], tower["y"], tower["height"], dem)
    cell_elev = dem.sample_points(cells["x"], cells["y"])

    # 1. Verify not shadowed by itself
    is_shadowed, dists = engine.evaluate_shadows(
        tower["x"], tower["y"], sweep_angles, z_antenna, cells["x"], cells["y"], cell_elev
    )
    assert not is_shadowed[0], "Cell at tower location MUST NOT be shadowed by its own tower base"
    assert dists[0] == 0.0

    # 2. Verify signal computation is finite
    signals, min_dists = compute_signal(cells, [tower], dem, cfg, polar_engine=engine)
    assert np.isfinite(signals[0]), f"Signal at distance 0 must be finite, got {signals[0]}"
    assert signals[0] > -50.0, f"Signal directly under tower should be strong, got {signals[0]} dBm"

    # 3. State classification
    state = classify_state(signals[0], min_dists[0], cfg)
    assert state == "covered"


def test_empty_tower_list():
    """Case 4: Empty tower list.

    Expectations:
      - Returns correct shape (N cells).
      - All cells return null/NaN signal.
      - State follows tower_evidence rule (no tower evidence means 'unknown').
    """
    center_x = 580000.0
    center_y = 1430000.0
    dem = DEMGrid.create_synthetic(center_x=center_x, center_y=center_y)
    cfg = PropagationConfig()

    cells = {
        "x": np.array([center_x, center_x + 500.0, center_x + 1000.0], dtype=np.float32),
        "y": np.array([center_y, center_y + 500.0, center_y + 1000.0], dtype=np.float32),
    }
    n_cells = len(cells["x"])

    signals, min_dists_km = compute_signal(cells, [], dem, cfg)

    # 1. Correct shape
    assert signals.shape == (n_cells,)
    assert min_dists_km.shape == (n_cells,)

    # 2. All signals are NaN (null)
    assert np.all(np.isnan(signals)), "All signals must be NaN when no towers exist"

    # 3. Minimum distances are infinite
    assert np.all(np.isinf(min_dists_km))

    # 4. State follows tower_evidence rule -> 'unknown'
    states_from_dist = classify_state(signals, min_dists_km, cfg)
    assert list(states_from_dist) == ["unknown", "unknown", "unknown"]

    # Also test passing boolean tower_evidence array
    tower_evidence = np.array([False, False, False], dtype=bool)
    states_from_evidence = classify_state(signals, tower_evidence, cfg)
    assert list(states_from_evidence) == ["unknown", "unknown", "unknown"]
