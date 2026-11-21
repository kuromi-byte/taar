"""Configuration for RF propagation and state classification."""
from dataclasses import dataclass


@dataclass
class PropagationConfig:
    """RF propagation model parameters and gap classification rules.

    Defaults match contracts/config.json. Always load from config.json
    at runtime; these defaults are only for unit tests.
    """
    freq_mhz: float = 900.0          # 900 MHz → Okumura-Hata open-area
    receiver_height_m: float = 1.5   # Standard handheld mobile height hm (m)
    default_tower_height_m: float = 30.0  # Base station height hb (m)
    default_power_dbm: float = 43.0  # Transmit EIRP / power (43 dBm = 20W macrocell)
    shadow_penalty_db: float = 15.0  # Flat terrain shadow penalty (dB, assumed)
    max_radius_km: float = 10.0      # Maximum sweep radius (km)
    ray_step_m: float = 30.0         # Polar sweep distance step (m)
    num_rays: int = 720              # 720 rays = 0.5 degree angular resolution
    gap_threshold_dbm: float = -100.0 # Modeled signal gap threshold (dBm)
    uncertain_margin_db: float = 6.0 # Margin around gap threshold (+/- 6 dB)
    unknown_radius_km: float = 15.0  # Radius beyond which cells are marked unknown
    min_distance_m: float = 30.0     # Minimum distance to prevent log10(0)
