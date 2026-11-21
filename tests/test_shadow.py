"""Unit tests for polar sweep terrain shadowing model.

Tests line of sight, running maximum obstruction angle, and verifies that
a synthetic ridge creates shadowing and applies the flat penalty behind it.
"""
import numpy as np
import pytest
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.model.shadow import PolarSweepEngine


def test_synthetic_ridge_shadowing():
    """Verify that a synthetic ridge shadows cells behind it and leaves front/perpendicular cells clear."""
    center_x = 580000.0
    center_y = 1430000.0

    # 1. Create synthetic DEM: flat 900m with a 100m tall North-South ridge at 1000m East
    dem = DEMGrid.create_synthetic(
        center_x=center_x,
        center_y=center_y,
        width_m=20000.0,
        height_m=20000.0,
        resolution_m=30.0,
        base_elevation_m=900.0,
        ridge_distance_m=1000.0,  # at x = 581000.0
        ridge_height_m=100.0,
        ridge_width_m=200.0,
    )

    tower = {
        "id": 1,
        "x": center_x,
        "y": center_y,
        "height": 30.0,
        "power": 43.0,
    }

    # Three test cells:
    # Cell 0: In front of ridge (500m East) -> NOT shadowed
    # Cell 1: Behind ridge (2000m East) -> SHADOWED
    # Cell 2: Perpendicular unobstructed (2000m North, flat terrain) -> NOT shadowed
    cells = {
        "x": np.array([center_x + 500.0, center_x + 2000.0, center_x], dtype=np.float32),
        "y": np.array([center_y, center_y, center_y + 2000.0], dtype=np.float32),
    }

    cfg = PropagationConfig(
        freq_mhz=1800.0,
        shadow_penalty_db=18.0,
        max_radius_km=10.0,
    )
    engine = PolarSweepEngine(cfg)

    # 2. Test polar sweep evaluation directly
    sweep_angles, z_antenna = engine.compute_tower_sweep(tower["x"], tower["y"], tower["height"], dem)
    cell_elev = dem.sample_points(cells["x"], cells["y"])

    is_shadowed, dists = engine.evaluate_shadows(
        tower["x"], tower["y"], sweep_angles, z_antenna, cells["x"], cells["y"], cell_elev, cfg.receiver_height_m
    )

    assert not is_shadowed[0], "Cell in front of ridge (500m) should NOT be shadowed"
    assert is_shadowed[1], "Cell behind ridge (2000m) MUST be shadowed"
    assert not is_shadowed[2], "Cell along flat north corridor (2000m) should NOT be shadowed"

    # 3. Test full signal calculation
    signals, min_dists = compute_signal(cells, [tower], dem, cfg, polar_engine=engine)

    # Cell 0 (500m) has high signal
    assert signals[0] > -90.0, f"Expected strong signal in front of ridge, got {signals[0]}"

    # Cell 1 (behind ridge at 2000m) vs Cell 2 (clear at 2000m):
    # Both are at 2000m, so path loss is identical.
    # The only difference is the 18 dB shadow penalty!
    signal_diff = signals[2] - signals[1]
    assert np.isclose(signal_diff, cfg.shadow_penalty_db, atol=0.5), (
        f"Expected ~18 dB difference between clear and shadowed cells at 2000m, got {signal_diff:.2f} dB"
    )
