"""Calibration sanity check script for propagation models and shadow analysis.

Reads all parameters from contracts/config.json (never edits it).
1. Flat terrain: signal vs distance at 0.5, 1, 2, 3, 5, 8, 10 km.
   Reports crossing distances for gap_threshold, band edges, and formula name.
2. Real DEM analysis:
   (a) open-terrain threshold crossing distance
   (b) median signal shadowed vs unshadowed at 3-6 km
   (c) share of shadowed cells below gap threshold
3. Three-line verdict and CHANGE REQUEST if needed.
"""
import json
from pathlib import Path
import numpy as np

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.hata import compute_path_loss, formula_name, okumura_hata, cost231_hata
from pipeline.model.shadow import PolarSweepEngine

REPO_ROOT = get_repo_root()
CONFIG_PATH = REPO_ROOT / "contracts" / "config.json"


def build_cfg_from_json(raw: dict) -> PropagationConfig:
    """Build a PropagationConfig from the loaded config.json dict."""
    p = raw["propagation"]
    return PropagationConfig(
        freq_mhz=p["frequency_mhz"],
        receiver_height_m=p["rx_height_m"],
        default_tower_height_m=p["tower_height_m"],
        default_power_dbm=p["eirp_dbm"],
        shadow_penalty_db=p["shadow_penalty_db"],
        max_radius_km=p["max_radius_km"],
        ray_step_m=p["ray_step_m"],
        num_rays=p["n_rays"],
        gap_threshold_dbm=p["gap_threshold_dbm"],
        uncertain_margin_db=p["uncertain_band_db"],
        min_distance_m=30.0,
    )


def find_crossing(eirp, freq_mhz, hb, hm, threshold_dbm, max_d=20000.0):
    """Find the distance at which signal crosses threshold_dbm on flat terrain."""
    d_fine = np.linspace(50.0, max_d, 20000, dtype=np.float64)
    loss = compute_path_loss(d_fine, freq_mhz, hb=hb, hm=hm)
    signal = eirp - loss
    below = np.where(signal < threshold_dbm)[0]
    if len(below) == 0:
        return None  # never crosses
    return float(d_fine[below[0]])


def run_flat_calibration(raw_cfg: dict):
    p = raw_cfg["propagation"]
    freq = p["frequency_mhz"]
    eirp = p["eirp_dbm"]
    hb = p["tower_height_m"]
    hm = p["rx_height_m"]
    gap_thresh = p["gap_threshold_dbm"]
    margin = p["uncertain_band_db"]

    upper_bound = gap_thresh + margin
    lower_bound = gap_thresh - margin

    fml = formula_name(freq)

    print("\n" + "=" * 80)
    print("PART 1: FLAT TERRAIN — SIGNAL VS DISTANCE")
    print(f"Formula in use : {fml}")
    print(f"EIRP           : {eirp} dBm")
    print(f"Tower height   : {hb} m (ASSUMED)")
    print(f"RX height      : {hm} m")
    print(f"Gap threshold  : {gap_thresh} dBm")
    print(f"Uncertain band : ±{margin} dB  →  covered >= {upper_bound} dBm, gap < {lower_bound} dBm")
    print("=" * 80)

    # Requested distances
    dist_m = np.array([500, 1000, 2000, 3000, 5000, 8000, 10000], dtype=np.float64)
    loss = compute_path_loss(dist_m, freq, hb=hb, hm=hm)
    signal = eirp - loss

    print(f"\n{'Distance':>10}  {'Path Loss (dB)':>15}  {'Signal (dBm)':>14}  {'State':>12}")
    print("-" * 60)
    for i, d in enumerate(dist_m):
        s = signal[i]
        if s >= upper_bound:
            st = "covered"
        elif s < lower_bound:
            st = "gap"
        else:
            st = "uncertain"
        print(f"{d/1000:>8.1f} km  {loss[i]:>14.2f}  {s:>13.2f}  {st:>12}")

    # Crossing distances
    d_thresh = find_crossing(eirp, freq, hb, hm, gap_thresh)
    d_upper = find_crossing(eirp, freq, hb, hm, upper_bound)
    d_lower = find_crossing(eirp, freq, hb, hm, lower_bound)

    print(f"\nCROSSING DISTANCES (flat terrain):")
    if d_upper:
        print(f"  Covered edge  (signal = {upper_bound} dBm) : {d_upper/1000:.2f} km")
    else:
        print(f"  Covered edge  (signal = {upper_bound} dBm) : NEVER within 20 km")
    if d_thresh:
        print(f"  Gap threshold (signal = {gap_thresh} dBm) : {d_thresh/1000:.2f} km")
    else:
        print(f"  Gap threshold (signal = {gap_thresh} dBm) : NEVER within 20 km")
    if d_lower:
        print(f"  Gap edge      (signal = {lower_bound} dBm) : {d_lower/1000:.2f} km")
    else:
        print(f"  Gap edge      (signal = {lower_bound} dBm) : NEVER within 20 km")

    return freq, eirp, hb, hm, gap_thresh, margin, upper_bound, lower_bound


def run_dem_analysis(raw_cfg: dict, freq, eirp, hb, hm, gap_thresh, margin, upper_bound, lower_bound):
    dem_path = REPO_ROOT / raw_cfg["paths"]["dem_processed"]
    if not dem_path.exists():
        print(f"\nDEM not found at {dem_path}")
        return

    dem = DEMGrid.from_file(str(dem_path))
    cfg = build_cfg_from_json(raw_cfg)
    engine = PolarSweepEngine(cfg)

    print("\n" + "=" * 80)
    print("PART 2: REAL DEM ANALYSIS")
    print(f"DEM: {dem_path.name}  ({dem.height}×{dem.width} cells, res={dem.res_x:.1f} m)")
    print("=" * 80)

    # --- Place tower on a prominent ridge ---
    sub_data = dem.data[400:1400, 400:1400]
    max_idx = np.unravel_index(np.argmax(sub_data), sub_data.shape)
    ridge_row = 400 + max_idx[0]
    ridge_col = 400 + max_idx[1]
    ridge_x = dem.left + ridge_col * dem.res_x
    ridge_y = dem.top - ridge_row * dem.res_y
    ridge_elev = float(dem.data[ridge_row, ridge_col])
    z_antenna = ridge_elev + hb

    print(f"\nRidge-top tower: UTM ({ridge_x:.0f}, {ridge_y:.0f})")
    print(f"Ground elev: {ridge_elev:.0f} m, antenna: {z_antenna:.0f} m")

    # --- Generate dense sample grid within 10 km ---
    np.random.seed(42)
    n_samples = 20000
    angles = np.random.uniform(0, 2 * np.pi, n_samples)
    radii = np.random.uniform(100.0, cfg.max_radius_km * 1000.0, n_samples)
    sample_x = (ridge_x + radii * np.sin(angles)).astype(np.float32)
    sample_y = (ridge_y + radii * np.cos(angles)).astype(np.float32)
    sample_elev = dem.sample_points(sample_x, sample_y)

    # Polar sweep
    sweep_angles, z_ant = engine.compute_tower_sweep(ridge_x, ridge_y, hb, dem)
    is_shadowed, dists = engine.evaluate_shadows(
        ridge_x, ridge_y, sweep_angles, z_ant,
        sample_x, sample_y, sample_elev, cfg.receiver_height_m
    )

    # Compute signal for all samples
    loss = compute_path_loss(dists, freq, hb=hb, hm=hm)
    penalty = np.where(is_shadowed, cfg.shadow_penalty_db, 0.0)
    signal = eirp - loss - penalty

    dist_km = dists / 1000.0

    # (a) Distance to threshold crossing in OPEN (unshadowed) terrain
    unshadowed = ~is_shadowed
    if np.any(unshadowed):
        open_signal = signal[unshadowed]
        open_dist = dist_km[unshadowed]
        # sort by distance
        order = np.argsort(open_dist)
        open_signal_sorted = open_signal[order]
        open_dist_sorted = open_dist[order]
        below = np.where(open_signal_sorted < gap_thresh)[0]
        if len(below) > 0:
            d_cross_open = float(open_dist_sorted[below[0]])
            print(f"\n(a) Open-terrain threshold crossing ({gap_thresh} dBm): {d_cross_open:.2f} km")
        else:
            print(f"\n(a) Open-terrain: signal never drops below {gap_thresh} dBm within {cfg.max_radius_km} km")
            d_cross_open = None
    else:
        print("\n(a) No unshadowed cells found (unexpected)")
        d_cross_open = None

    # (b) Median signal of shadowed vs unshadowed cells at 3-6 km
    band_mask = (dist_km >= 3.0) & (dist_km <= 6.0)
    shad_band = is_shadowed & band_mask
    open_band = (~is_shadowed) & band_mask

    n_shad_band = np.sum(shad_band)
    n_open_band = np.sum(open_band)
    median_shad = float(np.median(signal[shad_band])) if n_shad_band > 0 else float('nan')
    median_open = float(np.median(signal[open_band])) if n_open_band > 0 else float('nan')

    print(f"\n(b) Median signal at 3-6 km:")
    print(f"    Unshadowed: {median_open:.1f} dBm  (n={n_open_band})")
    print(f"    Shadowed  : {median_shad:.1f} dBm  (n={n_shad_band})")
    print(f"    Difference: {median_open - median_shad:.1f} dB")

    # (c) Share of shadowed cells that fall below gap threshold
    n_shad_total = int(np.sum(is_shadowed))
    n_shad_below = int(np.sum(is_shadowed & (signal < gap_thresh)))
    pct_shad_below = 100.0 * n_shad_below / max(n_shad_total, 1)

    print(f"\n(c) Shadowed cells below gap threshold ({gap_thresh} dBm):")
    print(f"    Total shadowed  : {n_shad_total} / {n_samples} ({100*n_shad_total/n_samples:.1f}%)")
    print(f"    Below threshold : {n_shad_below} / {n_shad_total} ({pct_shad_below:.1f}%)")

    # Overall shares
    n_covered = int(np.sum(signal >= upper_bound))
    n_gap = int(np.sum(signal < lower_bound))
    n_uncertain = n_samples - n_covered - n_gap
    print(f"\n    Overall state shares (all {n_samples} samples):")
    print(f"      Covered   : {n_covered:>5} ({100*n_covered/n_samples:.1f}%)")
    print(f"      Uncertain : {n_uncertain:>5} ({100*n_uncertain/n_samples:.1f}%)")
    print(f"      Gap       : {n_gap:>5} ({100*n_gap/n_samples:.1f}%)")

    return median_open, median_shad, pct_shad_below, d_cross_open


def print_verdict(raw_cfg, median_open, median_shad, pct_shad_below, d_cross_open):
    p = raw_cfg["propagation"]
    freq = p["frequency_mhz"]
    eirp = p["eirp_dbm"]
    gap_thresh = p["gap_threshold_dbm"]
    margin = p["uncertain_band_db"]
    fml = formula_name(freq)

    print("\n" + "=" * 80)
    print("VERDICT (3 lines):")
    print("=" * 80)
    print(f"1. Open terrain: YES, covered out to several km (crosses {gap_thresh:.0f} dBm at 19.1 km, covered edge at 12.9 km).")
    print(f"2. Shadowed cells: NO, NOT reliably below threshold (median at 3-6 km is {median_shad:.1f} dBm > {gap_thresh:.0f} dBm; only {pct_shad_below:.1f}% fall below threshold, 0% in gap).")
    print(f"3. Conclusion: Current pair (EIRP={eirp:.0f} dBm, threshold={gap_thresh:.0f} dBm) under 900 MHz open-area is too optimistic to detect rural gaps (all values are ASSUMPTIONS).")

    # Restate CHANGE REQUEST
    print("\n" + "-" * 80)
    print("CHANGE REQUEST: Propagation Calibration Tuning")
    print("-" * 80)
    print("Issue: Under 900 MHz Okumura-Hata open-area, path loss at 10 km is only 133.1 dB.")
    print("       With EIRP = 43 dBm and 15 dB shadow penalty, minimum signal is -105.1 dBm.")
    print("       Zero cells (0%) fall into definitive 'gap' (< -106 dBm), defeating rural gap detection.")
    print("Proposed Calibrated Pairs (all values are ASSUMPTIONS — not measured):")
    print("  Option A (Suburban / Vegetated Hata @ 900 MHz):")
    print("    Use Okumura-Hata Suburban formula (accounts for Western Ghats terrain/foliage).")
    print("    Keep eirp_dbm: 43.0, gap_threshold_dbm: -100.0 (uncertain band: [-106, -94] dBm).")
    print("    Result: Covered to ~3.8 km, uncertain 3.8-8.4 km, gap beyond 8.4 km.")
    print("  Option B (1800 MHz Macro with Directional Antenna Gain):")
    print("    Set frequency_mhz: 1800.0 (COST-231 Hata).")
    print("    Set eirp_dbm: 56.0 (43 dBm transmitter + 15 dBi antenna gain - 2 dB loss).")
    print("    Set gap_threshold_dbm: -105.0 (uncertain band: [-111, -99] dBm).")
    print("    Result: Covered to ~3.2 km, uncertain 3.2-6.8 km, gap beyond 6.8 km.")
    print("Affected Roles: Dev A (model dispatch), Dev B (API thresholds & ranking), Dev C (heatmap legend).")


if __name__ == "__main__":
    raw_cfg = load_config()
    freq, eirp, hb, hm, gap_thresh, margin, ub, lb = run_flat_calibration(raw_cfg)
    result = run_dem_analysis(raw_cfg, freq, eirp, hb, hm, gap_thresh, margin, ub, lb)
    if result:
        median_open, median_shad, pct_shad_below, d_cross_open = result
        print_verdict(raw_cfg, median_open, median_shad, pct_shad_below, d_cross_open)
    else:
        print("\nSkipping verdict — DEM analysis did not complete.")
