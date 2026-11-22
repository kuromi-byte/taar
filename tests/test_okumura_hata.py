"""Unit test for Okumura-Hata open-area formula with one hand-calculated value.

Parameters:
  f = 900 MHz, hb = 30 m, hm = 1.5 m, d = 1 km, open-area correction.

Step-by-step hand calculation:
  log10(900) = 2.95424251
  a(1.5) = (1.1 * 2.95424251 - 0.7) * 1.5 - (1.56 * 2.95424251 - 0.8)
         = (3.24966676 - 0.7) * 1.5 - (4.60861832 - 0.8)
         = 2.54966676 * 1.5 - 3.80861832
         = 3.82450014 - 3.80861832
         = 0.01588182

  L_urban = 69.55 + 26.16 * 2.95424251 - 13.82 * log10(30) - 0.01588182
            + (44.9 - 6.55 * log10(30)) * log10(1)
  log10(30) = 1.47712125
  L_urban = 69.55 + 77.283 - 20.4138 - 0.01588 + 0.0
          = 126.4033

  C_open = -4.78 * (2.95424251)^2 + 18.33 * 2.95424251 - 40.94
         = -4.78 * 8.72754 + 54.1313 - 40.94
         = -41.6377 + 54.1313 - 40.94
         = -28.4464

  L = 126.4033 + (-28.4464) = 97.9569 dB
"""
import numpy as np
import pytest
from pipeline.model.hata import okumura_hata, compute_path_loss, formula_name


def test_hand_calculated_okumura_hata_open():
    """Verify Okumura-Hata open-area at 900 MHz, 1 km against hand calc."""
    f = 900.0
    hb = 30.0
    hm = 1.5
    d_m = 1000.0

    loss = okumura_hata(d_m, freq_mhz=f, hb=hb, hm=hm)

    # Hand-calculated: L ≈ 97.96 dB
    # Allow ±0.1 dB for floating-point
    assert np.isclose(loss, 97.96, atol=0.1), f"Expected ~97.96 dB, got {loss:.4f}"

    # With EIRP = 43 dBm: Prx = 43 - 97.96 = -54.96 dBm at 1 km
    prx = 43.0 - loss
    assert np.isclose(prx, -54.96, atol=0.1), f"Expected ~-54.96 dBm, got {prx:.4f}"


def test_dispatch_900mhz():
    """Verify compute_path_loss dispatches to Okumura-Hata at 900 MHz."""
    loss_dispatch = compute_path_loss(1000.0, 900.0, hb=30.0, hm=1.5)
    loss_direct = okumura_hata(1000.0, freq_mhz=900.0, hb=30.0, hm=1.5)
    assert np.isclose(loss_dispatch, loss_direct)


def test_formula_name_dispatch():
    assert "Okumura-Hata" in formula_name(900.0)
    assert "COST-231" in formula_name(1800.0)


def test_okumura_distance_decay():
    """Path loss must increase with distance."""
    distances = np.array([100, 500, 1000, 2000, 5000, 10000], dtype=np.float64)
    losses = okumura_hata(distances, freq_mhz=900.0)
    assert np.all(np.diff(losses) > 0)
