"""Propagation path-loss models: Okumura-Hata and COST-231 Hata.

References:
- Okumura-Hata: M. Hata, "Empirical formula for propagation loss in land mobile radio
  services", IEEE Trans. VT, vol. VT-29, No. 3, 1980.
  Valid range: 150-1500 MHz, 1-20 km, hb 30-200 m, hm 1-10 m.
- COST-231 Hata: COST Action 231, Final Report, EUR 18957, 1999.
  Valid range: 1500-2000 MHz, 1-20 km, hb 30-200 m, hm 1-10 m.
  Cm = 0 for suburban/rural.

Frequency dispatch (per spec):
  <= 1500 MHz  → okumura_hata() with open-area correction (rural Western Ghats)
  1500-2000 MHz → cost231_hata() with Cm = 0
"""
from typing import Union
import numpy as np


def mobile_antenna_correction(freq_mhz: float, hm: float) -> float:
    """Compute receiver antenna height correction factor a(hm).

    Formula for medium/small cities and rural areas:
    a(hm) = (1.1 * log10(f) - 0.7) * hm - (1.56 * log10(f) - 0.8)
    """
    log_f = np.log10(freq_mhz)
    return (1.1 * log_f - 0.7) * hm - (1.56 * log_f - 0.8)


def okumura_hata(
    distance_m: Union[float, np.ndarray],
    freq_mhz: float = 900.0,
    hb: float = 30.0,
    hm: float = 1.5,
    min_dist_m: float = 30.0,
) -> Union[float, np.ndarray]:
    """Calculate path loss in dB using Okumura-Hata with open-area (rural) correction.

    L_urban = 69.55 + 26.16*log10(f) - 13.82*log10(hb) - a(hm)
              + (44.9 - 6.55*log10(hb))*log10(d_km)
    Open-area correction:
      C_open = -4.78*(log10(f))^2 + 18.33*log10(f) - 40.94
    L = L_urban + C_open

    Valid range: 150-1500 MHz, 1-20 km, hb 30-200 m, hm 1-10 m.
    Distance clamped to min_dist_m to avoid log10(0).

    Args:
        distance_m: Distance in meters (scalar or numpy array).
        freq_mhz: Carrier frequency in MHz (default 900.0).
        hb: Base station antenna height in meters.
        hm: Mobile antenna height in meters.
        min_dist_m: Minimum distance clamp.

    Returns:
        Path loss in dB.
    """
    d_m = np.maximum(distance_m, min_dist_m)
    d_km = d_m / 1000.0

    log_f = np.log10(freq_mhz)
    log_hb = np.log10(hb)
    log_d = np.log10(d_km)

    a_hm = mobile_antenna_correction(freq_mhz, hm)

    l_urban = (
        69.55
        + 26.16 * log_f
        - 13.82 * log_hb
        - a_hm
        + (44.9 - 6.55 * log_hb) * log_d
    )
    # Open-area (rural) correction — subtracts ~20 dB from urban loss
    c_open = -4.78 * (log_f ** 2) + 18.33 * log_f - 40.94

    return l_urban + c_open


def cost231_hata(
    distance_m: Union[float, np.ndarray],
    freq_mhz: float = 1800.0,
    hb: float = 30.0,
    hm: float = 1.5,
    cm: float = 0.0,
    min_dist_m: float = 30.0,
) -> Union[float, np.ndarray]:
    """Calculate path loss in dB using the COST-231 Hata model.

    L = 46.3 + 33.9*log10(f) - 13.82*log10(hb) - a(hm)
        + (44.9 - 6.55*log10(hb))*log10(d_km) + Cm

    Valid range: 1500-2000 MHz, 1-20 km, hb 30-200 m, hm 1-10 m.
    Cm = 0 for suburban/rural.

    Args:
        distance_m: Distance in meters (scalar or numpy array).
        freq_mhz: Carrier frequency in MHz (default 1800.0).
        hb: Base station antenna height in meters.
        hm: Mobile antenna height in meters.
        cm: Metropolitan correction (0 for suburban/rural).
        min_dist_m: Minimum distance clamp.

    Returns:
        Path loss in dB.
    """
    d_m = np.maximum(distance_m, min_dist_m)
    d_km = d_m / 1000.0

    log_f = np.log10(freq_mhz)
    log_hb = np.log10(hb)
    log_d = np.log10(d_km)

    a_hm = mobile_antenna_correction(freq_mhz, hm)

    path_loss = (
        46.3
        + 33.9 * log_f
        - 13.82 * log_hb
        - a_hm
        + (44.9 - 6.55 * log_hb) * log_d
        + cm
    )
    return path_loss


def compute_path_loss(
    distance_m: Union[float, np.ndarray],
    freq_mhz: float,
    hb: float = 30.0,
    hm: float = 1.5,
    min_dist_m: float = 30.0,
) -> Union[float, np.ndarray]:
    """Dispatch to the correct path-loss formula based on frequency.

    <= 1500 MHz  → Okumura-Hata open-area (rural)
    1500-2000 MHz → COST-231 Hata with Cm = 0

    Returns:
        Path loss in dB.
    """
    if freq_mhz <= 1500.0:
        return okumura_hata(distance_m, freq_mhz=freq_mhz, hb=hb, hm=hm,
                            min_dist_m=min_dist_m)
    else:
        return cost231_hata(distance_m, freq_mhz=freq_mhz, hb=hb, hm=hm,
                            cm=0.0, min_dist_m=min_dist_m)


def formula_name(freq_mhz: float) -> str:
    """Return human-readable name of the formula selected for this frequency."""
    if freq_mhz <= 1500.0:
        return f"Okumura-Hata open-area (rural) @ {freq_mhz:.0f} MHz"
    else:
        return f"COST-231 Hata (Cm=0, suburban/rural) @ {freq_mhz:.0f} MHz"
