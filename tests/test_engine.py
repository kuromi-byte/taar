"""Unit tests for the compute_signal engine and classify_state function."""
import numpy as np
import pytest
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import classify_state, compute_signal


def test_classify_state_logic():
    """Verify state classification rules: uncertain band, gap, covered, and unknown (lowercase per contract)."""
    cfg = PropagationConfig(
        gap_threshold_dbm=-100.0,
        uncertain_margin_db=6.0,
        unknown_radius_km=15.0,
    )
    # Threshold = -100, Margin = 6
    # Upper bound = -94 dBm
    # Lower bound = -106 dBm

    # 1. covered (>= -94 dBm, near tower)
    assert classify_state(-90.0, 2.0, cfg) == "covered"
    assert classify_state(-94.0, 2.0, cfg) == "covered"

    # 2. uncertain (between -106 and -94 dBm)
    assert classify_state(-95.0, 3.0, cfg) == "uncertain"
    assert classify_state(-100.0, 3.0, cfg) == "uncertain"
    assert classify_state(-105.9, 3.0, cfg) == "uncertain"

    # 3. gap (< -106 dBm, with tower nearby)
    assert classify_state(-107.0, 5.0, cfg) == "gap"
    assert classify_state(-125.0, 8.0, cfg) == "gap"

    # 4. unknown: no tower evidence nearby (> 15 km), regardless of signal
    assert classify_state(-125.0, 16.0, cfg) == "unknown"
    assert classify_state(-80.0, 20.0, cfg) == "unknown"

    # Vectorized test
    signals = np.array([-90.0, -99.0, -115.0, -130.0])
    dists = np.array([2.0, 4.0, 8.0, 18.0])
    states = classify_state(signals, dists, cfg)
    assert list(states) == ["covered", "uncertain", "gap", "unknown"]


def test_best_server_maximum():
    """Verify best-server received power selects max power across towers."""
    dem = DEMGrid.create_synthetic(base_elevation_m=800.0)
    cfg = PropagationConfig()

    cell = {"x": np.array([580000.0]), "y": np.array([1430000.0])}

    # Tower 1: at cell location (strong signal)
    t1 = {"id": 1, "x": 580000.0, "y": 1430000.0, "height": 30.0, "power": 43.0}
    # Tower 2: 5 km away (weaker signal)
    t2 = {"id": 2, "x": 585000.0, "y": 1430000.0, "height": 30.0, "power": 43.0}

    sig_t1_only, _ = compute_signal(cell, [t1], dem, cfg)
    sig_t2_only, _ = compute_signal(cell, [t2], dem, cfg)
    assert sig_t1_only[0] > sig_t2_only[0]

    # Combined towers
    sig_both, _ = compute_signal(cell, [t1, t2], dem, cfg)
    assert np.isclose(sig_both[0], sig_t1_only[0])


def test_ten_kilometer_radius():
    """Verify that cells beyond 10 km are outside tower propagation range."""
    dem = DEMGrid.create_synthetic(base_elevation_m=800.0)
    cfg = PropagationConfig(max_radius_km=10.0)

    tower = {"id": 1, "x": 580000.0, "y": 1430000.0, "height": 30.0, "power": 43.0}

    cells = {
        # Cell 0 at 9 km (within range)
        # Cell 1 at 12 km (outside 10 km range)
        "x": np.array([580000.0, 580000.0]),
        "y": np.array([1439000.0, 1442000.0]),
    }

    signals, dists = compute_signal(cells, [tower], dem, cfg)

    assert dists[0] == pytest.approx(9.0, abs=0.1)
    assert dists[1] == pytest.approx(12.0, abs=0.1)

    assert signals[0] > -140.0, "Cell at 9 km should have modeled signal"
    assert np.isnan(signals[1]), "Cell at 12 km (> 10 km) should be NaN"
