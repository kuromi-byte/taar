"""COST-231 Hata propagation model.

Reference: COST Action 231, "Digital mobile radio towards future generation systems",
Final Report, European Communities, EUR 18957, 1999.
Path loss formula with suburban/rural correction term Cm set to 0.
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


def cost231_hata(
    distance_m: Union[float, np.ndarray],
    freq_mhz: float = 1800.0,
    hb: float = 30.0,
    hm: float = 1.5,
    cm: float = 0.0,
    min_dist_m: float = 30.0,
) -> Union[float, np.ndarray]:
    """Calculate path loss in dB using the COST-231 Hata model.

    L = 46.3 + 33.9*log10(f) - 13.82*log10(hb) - a(hm) + (44.9 - 6.55*log10(hb))*log10(d) + Cm

    Args:
        distance_m: Distance from transmitter to receiver in meters (scalar or numpy array).
        freq_mhz: Carrier frequency in MHz (default 1800.0 MHz).
        hb: Effective transmitter antenna height above ground in meters (default 30.0 m).
        hm: Receiver antenna height above ground in meters (default 1.5 m).
        cm: Suburban/rural correction factor (set to 0.0 as required).
        min_dist_m: Minimum clamp distance to prevent singularities near d=0.

    Returns:
        Path loss in dB (scalar or numpy array matching distance_m).
    """
    d_m = np.maximum(distance_m, min_dist_m)
    d_km = d_m / 1000.0  # Formula requires distance in km

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
