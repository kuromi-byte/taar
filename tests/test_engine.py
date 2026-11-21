"""Unit tests for the compute_signal engine and classify_state function."""
import numpy as np
import pytest
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import classify_state, compute_signal


def test_classify_state_logic():
    """Verify state classification rules: Uncertain band, gap, covered, and Unknown."""
    cfg = PropagationConfig(
        gap_threshold_dbm=-105.0,
        uncertain_margin_db=6.0,
        unknown_radius_km=15.0,
    )
    # Threshold = -105, Margin = 6
    # Upper bound = -99 dBm
    # Lower bound = -111 dBm

    # 1. Likely covered (>= -99 dBm, near tower)
    assert classify_state(-90.0, 2.0, cfg) == "Likely covered"
    assert classify_state(-99.0, 2.0, cfg) == "Likely covered"

    # 2. Uncertain (between -111 and -99 dBm)
    assert classify_state(-100.0, 3.0, cfg) == "Uncertain"
    assert classify_state(-105.0, 3.0, cfg) == "Uncertain"
    assert classify_state(-110.9, 3.0, cfg) == "Uncertain"

    # 3. Likely gap (< -111 dBm, with tower nearby)
    assert classify_state(-112.0, 5.0, cfg) == "Likely gap"
    assert classify_state(-125.0, 8.0, cfg) == "Likely gap"

    # 4. Unknown: no tower evidence nearby (> 15 km), regardless of signal
    assert classify_state(-125.0, 16.0, cfg) == "Unknown"
    assert classify_state(-80.0, 20.0, cfg) == "Unknown"

    # Vectorized test
    signals = np.array([-90.0, -104.0, -115.0, -130.0])
    dists = np.array([2.0, 4.0, 8.0, 18.0])
    states = classify_state(signals, dists, cfg)
    assert list(states) == ["Likely covered", "Uncertain", "Likely gap", "Unknown"]


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
    assert signals[1] == -140.0, "Cell at 12 km (> 10 km) should be floored at baseline -140 dBm"
