"""Unit tests for COST-231 Hata propagation model.

Verifies hand-calculated values, distance decay, and frequency/height scaling.
"""
import numpy as np
import pytest
from pipeline.model.hata import cost231_hata, mobile_antenna_correction


def test_hand_calculated_cost231_hata():
    """Verify COST-231 Hata against step-by-step hand calculation.

    Parameters:
      f = 1800.0 MHz
      hb = 30.0 m
      hm = 1.5 m
      d = 1.0 km (1000.0 m)
      Cm = 0.0 dB

    Step-by-step:
      log10(1800) = 3.2552725
      33.9 * log10(1800) = 110.353738
      13.82 * log10(30) = 20.413816
      a(1.5) = (1.1 * 3.2552725 - 0.7) * 1.5 - (1.56 * 3.2552725 - 0.8)
             = 2.8807998 * 1.5 - 4.2782251 = 4.3211996 - 4.2782251 = 0.0429745 dB
      log10(1.0 km) = 0.0
      L = 46.3 + 110.353738 - 20.413816 - 0.0429745 + 0.0 = 136.196948 dB
    """
    f = 1800.0
    hb = 30.0
    hm = 1.5
    d_m = 1000.0

    # 1. Verify correction factor a(hm)
    a_hm = mobile_antenna_correction(f, hm)
    expected_a_hm = (1.1 * np.log10(1800.0) - 0.7) * 1.5 - (1.56 * np.log10(1800.0) - 0.8)
    assert np.isclose(a_hm, expected_a_hm, atol=1e-6)
    assert np.isclose(a_hm, 0.0429745, atol=1e-4)

    # 2. Verify path loss at 1.0 km
    l_1km = cost231_hata(distance_m=d_m, freq_mhz=f, hb=hb, hm=hm, cm=0.0)
    expected_l_1km = 136.196948
    assert np.isclose(l_1km, expected_l_1km, atol=1e-4)

    # 3. Verify path loss at 2.0 km
    # distance term: (44.9 - 6.55*log10(30)) * log10(2) = 35.224856 * 0.301030 = 10.603738 dB
    # total L = 136.196948 + 10.603738 = 146.800686 dB
    l_2km = cost231_hata(distance_m=2000.0, freq_mhz=f, hb=hb, hm=hm, cm=0.0)
    assert np.isclose(l_2km, 146.800686, atol=1e-4)

    # 4. Verify received power with Ptx = 43.0 dBm (20W)
    ptx = 43.0
    prx_1km = ptx - l_1km
    assert np.isclose(prx_1km, -93.196948, atol=1e-4)
    prx_2km = ptx - l_2km
    assert np.isclose(prx_2km, -103.800686, atol=1e-4)


def test_distance_decay():
    """Verify that path loss monotonically increases (signal decreases) with distance."""
    distances = np.array([100.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0])
    losses = cost231_hata(distances, freq_mhz=1800.0, hb=30.0, hm=1.5)
    # Differences must all be positive
    diffs = np.diff(losses)
    assert np.all(diffs > 0)


def test_frequency_dependence():
    """Verify that 900 MHz has significantly lower path loss than 1800 MHz."""
    d = 1000.0
    loss_900 = cost231_hata(d, freq_mhz=900.0, hb=30.0, hm=1.5)
    loss_1800 = cost231_hata(d, freq_mhz=1800.0, hb=30.0, hm=1.5)
    # 33.9 * log10(1800/900) = 33.9 * log10(2) approx 10.2 dB difference
    assert loss_1800 > loss_900
    assert 9.0 < (loss_1800 - loss_900) < 11.5


def test_tower_height_dependence():
    """Verify that taller towers produce lower path loss."""
    d = 2000.0
    loss_30m = cost231_hata(d, freq_mhz=1800.0, hb=30.0, hm=1.5)
    loss_60m = cost231_hata(d, freq_mhz=1800.0, hb=60.0, hm=1.5)
    assert loss_60m < loss_30m
