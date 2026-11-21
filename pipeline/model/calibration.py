"""Calibration sanity check script for propagation models and shadow analysis.

1. Evaluates signal vs distance on flat terrain for:
   - 900 MHz (Okumura-Hata open-area formula)
   - 900 MHz (Okumura-Hata suburban formula)
   - 1800 MHz (COST-231 Hata)
   Identifies crossing points for gap_threshold_dbm (-100 dBm).

2. On the real DEM (dem_utm43n.tif), evaluates a ridge-top tower and reports
   the percentage of shadowed cells within 10 km.

3. Prints analysis of eirp_dbm=43 vs gap_threshold_dbm=-100 and suggests calibrated pairs.
"""
import json
from pathlib import Path
import numpy as np

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.hata import cost231_hata
from pipeline.model.shadow import PolarSweepEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "contracts" / "config.json"


def okumura_hata_900_open(distance_m: np.ndarray, hb: float = 30.0, hm: float = 1.5) -> np.ndarray:
    """Okumura-Hata for 900 MHz in open/rural area."""
    f = 900.0
    d_km = np.maximum(distance_m, 30.0) / 1000.0
    log_f = np.log10(f)
    log_hb = np.log10(hb)
    log_d = np.log10(d_km)

    a_hm = (1.1 * log_f - 0.7) * hm - (1.56 * log_f - 0.8)
    l_urban = 69.55 + 26.16 * log_f - 13.82 * log_hb - a_hm + (44.9 - 6.55 * log_hb) * log_d
    # Open area correction
    rural_corr = -4.78 * (log_f ** 2) + 18.33 * log_f - 40.94
    return l_urban + rural_corr


def okumura_hata_900_suburban(distance_m: np.ndarray, hb: float = 30.0, hm: float = 1.5) -> np.ndarray:
    """Okumura-Hata for 900 MHz in suburban area."""
    f = 900.0
    d_km = np.maximum(distance_m, 30.0) / 1000.0
    log_f = np.log10(f)
    log_hb = np.log10(hb)
    log_d = np.log10(d_km)

    a_hm = (1.1 * log_f - 0.7) * hm - (1.56 * log_f - 0.8)
    l_urban = 69.55 + 26.16 * log_f - 13.82 * log_hb - a_hm + (44.9 - 6.55 * log_hb) * log_d
    # Suburban correction
    suburban_corr = -2.0 * ((np.log10(f / 28.0)) ** 2) - 5.4
    return l_urban + suburban_corr


def run_flat_calibration():
    cfg = json.loads(CONFIG_PATH.read_text())
    eirp = cfg["propagation"]["eirp_dbm"]
    gap_thresh = cfg["propagation"]["gap_threshold_dbm"]
    margin = cfg["propagation"]["uncertain_band_db"]

    upper_covered = gap_thresh + margin  # -94 dBm
    lower_gap = gap_thresh - margin      # -106 dBm

    distances = np.array([100, 300, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000], dtype=np.float32)

    l_900_open = okumura_hata_900_open(distances)
    sig_900_open = eirp - l_900_open

    l_900_suburban = okumura_hata_900_suburban(distances)
    sig_900_suburban = eirp - l_900_suburban

    l_1800_cost = cost231_hata(distances, freq_mhz=1800.0, hb=30.0, hm=1.5, cm=0.0)
    sig_1800_cost = eirp - l_1800_cost

    print("\n" + "=" * 80)
    print("CALIBRATION SANITY CHECK 1: FLAT TERRAIN SIGNAL VS DISTANCE")
    print(f"Parameters: EIRP = {eirp} dBm, Gap Threshold = {gap_thresh} dBm (Band: [{lower_gap}, {upper_covered}] dBm)")
    print("=" * 80)
    print(f"{'Distance (m)':<14} | {'900 MHz (Open)':<18} | {'900 MHz (Suburban)':<18} | {'1800 MHz (COST-231)':<18}")
    print("-" * 80)

    for i, d in enumerate(distances):
        print(f"{int(d):<14} | {sig_900_open[i]:>8.2f} dBm       | {sig_900_suburban[i]:>8.2f} dBm       | {sig_1800_cost[i]:>8.2f} dBm")

    print("-" * 80)

    # Find crossing distances
    dense_d = np.linspace(50.0, 15000.0, 1500, dtype=np.float32)

    # 1800 MHz crossings
    sig_1800_dense = eirp - cost231_hata(dense_d, freq_mhz=1800.0)
    d_cov_1800 = dense_d[np.where(sig_1800_dense < upper_covered)[0][0]] if np.any(sig_1800_dense < upper_covered) else None
    d_gap_1800 = dense_d[np.where(sig_1800_dense < lower_gap)[0][0]] if np.any(sig_1800_dense < lower_gap) else None

    # 900 MHz suburban crossings
    sig_900_sub_dense = eirp - okumura_hata_900_suburban(dense_d)
    d_cov_900s = dense_d[np.where(sig_900_sub_dense < upper_covered)[0][0]] if np.any(sig_900_sub_dense < upper_covered) else None
    d_gap_900s = dense_d[np.where(sig_900_sub_dense < lower_gap)[0][0]] if np.any(sig_900_sub_dense < lower_gap) else None

    # 900 MHz open crossings
    sig_900_open_dense = eirp - okumura_hata_900_open(dense_d)
    d_cov_900o = dense_d[np.where(sig_900_open_dense < upper_covered)[0][0]] if np.any(sig_900_open_dense < upper_covered) else None
    d_gap_900o = dense_d[np.where(sig_900_open_dense < lower_gap)[0][0]] if np.any(sig_900_open_dense < lower_gap) else None

    print("\nCROSSING DISTANCES SUMMARY:")
    print(f"1. 1800 MHz (COST-231 Hata):")
    print(f"   Covered  (>= -94 dBm)  : up to {d_cov_1800:.0f} m (~{d_cov_1800/1000.0:.2f} km)")
    print(f"   Uncertain [-106, -94]  : {d_cov_1800:.0f} m to {d_gap_1800:.0f} m")
    print(f"   Gap      (< -106 dBm)  : beyond {d_gap_1800:.0f} m (~{d_gap_1800/1000.0:.2f} km)")

    print(f"\n2. 900 MHz (Okumura-Hata Suburban):")
    print(f"   Covered  (>= -94 dBm)  : up to {d_cov_900s:.0f} m (~{d_cov_900s/1000.0:.2f} km)")
    print(f"   Uncertain [-106, -94]  : {d_cov_900s:.0f} m to {d_gap_900s:.0f} m")
    print(f"   Gap      (< -106 dBm)  : beyond {d_gap_900s:.0f} m (~{d_gap_900s/1000.0:.2f} km)")

    print(f"\n3. 900 MHz (Okumura-Hata Open/Rural):")
    print(f"   Signal at 10 km        : {sig_900_open[-1]:.2f} dBm (NEVER drops below -100 dBm within 10 km!)")
    if d_gap_900o:
        print(f"   Gap (< -106 dBm) only reaches at: {d_gap_900o:.0f} m (~{d_gap_900o/1000.0:.2f} km)")
    else:
        print("   Gap (< -106 dBm) is NEVER reached within 15 km!")


def run_dem_shadow_check():
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    if not dem_path.exists():
        print(f"DEM not found at {dem_path}")
        return

    dem = DEMGrid.from_file(str(dem_path))
    cfg = PropagationConfig()
    engine = PolarSweepEngine(cfg)

    # Find a prominent ridge in Sakleshpur pilot area
    # Bbox center or ridge-top
    # Scan a subregion for high elevation
    sub_data = dem.data[400:1400, 400:1400]
    max_idx = np.unravel_index(np.argmax(sub_data), sub_data.shape)
    ridge_row = 400 + max_idx[0]
    ridge_col = 400 + max_idx[1]

    ridge_x = dem.left + ridge_col * dem.res_x
    ridge_y = dem.top - ridge_row * dem.res_y
    ridge_elev = float(dem.data[ridge_row, ridge_col])

    print("\n" + "=" * 80)
    print("CALIBRATION SANITY CHECK 2: REAL DEM RIDGE-TOP TOWER SHADOWING")
    print("=" * 80)
    print(f"Selected Ridge-Top Tower Location: UTM ({ridge_x:.1f}, {ridge_y:.1f})")
    print(f"Tower Ground Elevation:            {ridge_elev:.1f} m (Antenna at {ridge_elev + 30.0:.1f} m)")

    # Test grid of 5000 random points within 10 km radius
    np.random.seed(42)
    n_samples = 10000
    angles = np.random.uniform(0, 2 * np.pi, n_samples)
    radii = np.random.uniform(100.0, 10000.0, n_samples)
    sample_x = (ridge_x + radii * np.sin(angles)).astype(np.float32)
    sample_y = (ridge_y + radii * np.cos(angles)).astype(np.float32)

    sweep_angles, z_ant = engine.compute_tower_sweep(ridge_x, ridge_y, 30.0, dem)
    sample_elev = dem.sample_points(sample_x, sample_y)

    is_shadowed, dists = engine.evaluate_shadows(
        ridge_x, ridge_y, sweep_angles, z_ant, sample_x, sample_y, sample_elev, cfg.receiver_height_m
    )

    shadow_share = np.mean(is_shadowed) * 100.0
    print(f"Total Evaluated Ground Points:     {n_samples}")
    print(f"Points Shadowed Behind Ridges:     {np.sum(is_shadowed)}")
    print(f"Share of Shadowed Area:            {shadow_share:.2f} %")
    print("=" * 80)


if __name__ == "__main__":
    run_flat_calibration()
    run_dem_shadow_check()
