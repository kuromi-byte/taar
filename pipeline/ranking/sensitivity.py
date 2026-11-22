"""Sensitivity analysis for candidate site ranking under signal uncertainty.

Dev B – /pipeline/ranking/sensitivity.py

Methodology (per Rundown.md 1.4 & 4.3):
1. Loads the baseline cells and candidate pool from the verified pipeline.
2. Extracts noise standard deviation (dB) from config (uncertain_band_db).
3. Uses a fixed random seed (42) for deterministic, reproducible evaluation.
4. Adds zero-mean Gaussian random noise (sigma = config dB) to modeled signals.
5. Reruns greedy ranking 20 times with perturbed signals.
6. Evaluates top-5 site stability: tracks how many of the baseline top-5 sites
   stay in the top-5 ranking across runs.
7. Prints a concise results table and stability summary.
"""
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np
from pyproj import Transformer

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.clustering_and_ranking import (
    calculate_prominence,
    cluster_gap_cells_8way,
    _nearest_town_name,
)

REPO_ROOT = get_repo_root()
_to_wgs = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)

# Configuration defaults
_NUM_RUNS = 20
_RANDOM_SEED = 42
_TOP_K = 5
_SEARCH_BUFFER_M = 3000.0
_CANDIDATE_POOL_SIZE = 25


def build_candidate_pool(
    cells_fc: Dict[str, Any],
    dem: DEMGrid,
    cfg: PropagationConfig,
    towns: List[Dict[str, Any]],
    slope_max_deg: float,
    road_max_km: float,
) -> Tuple[List[Dict[str, Any]], np.ndarray, np.ndarray, np.ndarray, float]:
    """Extract candidate pool of surviving sites passing hard feasibility filters."""
    features = cells_fc["features"]
    cell_ids = np.array([f["id"] for f in features], dtype=np.int64)
    cell_pops = np.array([f["properties"]["pop"] for f in features], dtype=np.int64)
    cell_x = np.array([f["properties"]["cx"] for f in features], dtype=np.float32)
    cell_y = np.array([f["properties"]["cy"] for f in features], dtype=np.float32)
    cell_states = np.array([f["properties"]["state"] for f in features], dtype=object)

    raw_dbm = [f["properties"].get("baseline_dbm") for f in features]
    baseline_dbm = np.array(
        [float(v) if v is not None else float("nan") for v in raw_dbm],
        dtype=np.float32,
    )

    gap_cutoff = cfg.gap_threshold_dbm - cfg.uncertain_margin_db

    # 8-connectivity clustering of gap cells
    gap_indices = np.where(cell_states == "gap")[0]
    raw_components = cluster_gap_cells_8way(gap_indices, cell_x, cell_y)
    main_components = [c for c in raw_components if len(c) >= 3]

    all_slopes = [f["properties"].get("slope_deg") for f in features]
    all_roads = [f["properties"].get("road_km") for f in features]

    viable_candidates = []
    seen_cells: Set[int] = set()

    for c_idx, comp in enumerate(main_components):
        cid = f"CL-{c_idx + 1:02d}"
        comp_x = cell_x[comp]
        comp_y = cell_y[comp]
        cx_mean = float(comp_x.mean())
        cy_mean = float(comp_y.mean())
        c_lon, c_lat = _to_wgs.transform(cx_mean, cy_mean)
        cluster_name = _nearest_town_name(c_lon, c_lat, towns)

        min_x, max_x = comp_x.min() - _SEARCH_BUFFER_M, comp_x.max() + _SEARCH_BUFFER_M
        min_y, max_y = comp_y.min() - _SEARCH_BUFFER_M, comp_y.max() + _SEARCH_BUFFER_M

        candidate_cell_indices = np.where(
            (cell_x >= min_x) & (cell_x <= max_x) & (cell_y >= min_y) & (cell_y <= max_y)
        )[0]

        for arr_idx in candidate_cell_indices:
            if arr_idx in seen_cells:
                continue
            sl = all_slopes[arr_idx]
            rk = all_roads[arr_idx]

            if sl is None or rk is None or sl >= slope_max_deg or rk > road_max_km:
                continue

            seen_cells.add(arr_idx)
            px = float(cell_x[arr_idx])
            py = float(cell_y[arr_idx])
            p_lon, p_lat = _to_wgs.transform(px, py)
            prom = calculate_prominence(dem, px, py)

            viable_candidates.append({
                "cell_id": int(cell_ids[arr_idx]),
                "cell_idx": arr_idx,
                "cluster_id": cid,
                "cluster_name": cluster_name,
                "x": px,
                "y": py,
                "lat": round(float(p_lat), 6),
                "lon": round(float(p_lon), 6),
                "height": cfg.default_tower_height_m,
                "power": cfg.default_power_dbm,
                "slope_deg": round(float(sl), 1),
                "road_km": round(float(rk), 3),
                "prominence_m": round(float(prom), 1),
            })

    # Sort candidates by prominence descending and select top pool
    viable_candidates.sort(key=lambda c: -c["prominence_m"])
    candidate_pool = viable_candidates[:_CANDIDATE_POOL_SIZE]

    # Assign stable identifiers based on cell ID
    for c in candidate_pool:
        c["site_label"] = f"Site-{c['cell_id']}"

    return candidate_pool, baseline_dbm, cell_pops, cell_ids, gap_cutoff


def run_greedy_ranking(
    candidate_pool: List[Dict[str, Any]],
    precomputed_signals: List[np.ndarray],
    initial_signal: np.ndarray,
    cell_pops: np.ndarray,
    gap_cutoff: float,
    top_k: int = _TOP_K,
) -> List[str]:
    """Execute greedy selection on candidate pool with given initial signal array."""
    current_signal = initial_signal.copy()
    pool_indices = list(range(len(candidate_pool)))
    selected_labels = []

    for _ in range(top_k):
        best_idx = None
        best_boost = -1
        best_sig = None

        for idx in pool_indices:
            cand_sig = precomputed_signals[idx]
            effective = np.maximum(current_signal, cand_sig)

            was_gap = current_signal < gap_cutoff
            now_covered = effective >= gap_cutoff
            added_pop = int(np.sum(cell_pops[was_gap & now_covered]))

            if added_pop > best_boost:
                best_boost = added_pop
                best_idx = idx
                best_sig = cand_sig

        if best_idx is None or best_boost <= 0:
            break

        selected_labels.append(candidate_pool[best_idx]["site_label"])
        pool_indices.remove(best_idx)
        current_signal = np.maximum(current_signal, best_sig)

    return selected_labels


def run_sensitivity_analysis():
    print("=" * 75)
    print(f"RANKING SENSITIVITY ANALYSIS ({_NUM_RUNS} Iterations, Fixed Seed {_RANDOM_SEED})")
    print("=" * 75)

    # 1. Load configuration and model parameters
    cfg_data = load_config()
    prop_cfg = cfg_data.get("propagation", {})
    cfg = PropagationConfig(
        freq_mhz=float(prop_cfg.get("frequency_mhz", 900.0)),
        receiver_height_m=float(prop_cfg.get("rx_height_m", 1.5)),
        default_tower_height_m=float(prop_cfg.get("tower_height_m", 30.0)),
        default_power_dbm=float(prop_cfg.get("eirp_dbm", 43.0)),
        shadow_penalty_db=float(prop_cfg.get("shadow_penalty_db", 15.0)),
        max_radius_km=float(prop_cfg.get("max_radius_km", 10.0)),
        gap_threshold_dbm=float(prop_cfg.get("gap_threshold_dbm", -100.0)),
        uncertain_margin_db=float(prop_cfg.get("uncertain_band_db", 6.0)),
    )

    # Noise magnitude: uncertain_band_db (6.0 dB default from contracts/config.json)
    ranking_cfg = cfg_data.get("ranking", {})
    if "sensitivity_noise_db" in ranking_cfg:
        noise_sigma_db = float(ranking_cfg["sensitivity_noise_db"])
    elif "uncertain_band_db" in prop_cfg:
        noise_sigma_db = float(prop_cfg["uncertain_band_db"])
    else:
        noise_sigma_db = 6.0  # TODO-STUB fallback
        print(f"  [TODO-STUB] noise_sigma_db not in config; using {noise_sigma_db} dB")

    slope_max_deg = float(ranking_cfg.get("max_slope_deg", 15.0))  # TODO-STUB
    road_max_km = float(ranking_cfg.get("max_road_km", 1.0))        # TODO-STUB

    print(f"Noise Parameter: Gaussian sigma = {noise_sigma_db:.1f} dB (from config uncertain band)")
    print(f"Fixed Random Seed: {_RANDOM_SEED}")

    # 2. Load DEM and real cells
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    dem = DEMGrid.from_file(str(dem_path))

    cells_path = REPO_ROOT / "web" / "public" / "data" / "cells.geojson"
    with open(cells_path, "r", encoding="utf-8") as f:
        cells_fc = json.load(f)

    towns_path = REPO_ROOT / "web" / "public" / "data" / "towns.json"
    with open(towns_path, "r", encoding="utf-8") as f:
        towns = json.load(f)

    # 3. Extract candidate pool
    print("\nBuilding viable candidate site pool...")
    candidate_pool, baseline_dbm, cell_pops, cell_ids, gap_cutoff = build_candidate_pool(
        cells_fc, dem, cfg, towns, slope_max_deg, road_max_km
    )
    print(f"Candidate pool size: {len(candidate_pool)} viable sites passing slope < {slope_max_deg}° & road <= {road_max_km} km")

    # 4. Precompute candidate signals (exact shared compute_signal function)
    print("Precomputing raw propagation signals for candidate pool (calling compute_signal)...")
    precomputed_signals = []
    for cand in candidate_pool:
        tower_spec = [{
            "id": cand["site_label"],
            "lat": cand["lat"],
            "lon": cand["lon"],
            "height": cand["height"],
            "power": cand["power"],
        }]
        sig, _ = compute_signal(cells_fc, tower_spec, dem, cfg)
        sig_safe = np.where(np.isnan(sig), -np.inf, sig)
        precomputed_signals.append(sig_safe)

    # Clean baseline signal for ranking
    clean_baseline = np.where(np.isnan(baseline_dbm), -np.inf, baseline_dbm)

    # 5. Baseline ranking (0 noise)
    baseline_top_5 = run_greedy_ranking(
        candidate_pool, precomputed_signals, clean_baseline, cell_pops, gap_cutoff, top_k=_TOP_K
    )
    print("\nBaseline Top 5 Sites (No Noise):")
    for r, site in enumerate(baseline_top_5, 1):
        cand_match = next(c for c in candidate_pool if c["site_label"] == site)
        print(f"  Rank {r}: {site} ({cand_match['cluster_name']}) at ({cand_match['lat']}, {cand_match['lon']}), prom={cand_match['prominence_m']:+.1f}m")

    # 6. Run 20 sensitivity iterations with fixed RNG
    rng = np.random.default_rng(seed=_RANDOM_SEED)
    results = []

    print("\n" + "-" * 75)
    print(f"{'Run':<6} {'Top-5 Selected Sites':<42} {'Matches':<10} {'Stability':<10}")
    print("-" * 75)

    baseline_set = set(baseline_top_5)

    for run_idx in range(1, _NUM_RUNS + 1):
        # Generate random Gaussian noise with sigma from config
        noise = rng.normal(loc=0.0, scale=noise_sigma_db, size=clean_baseline.shape).astype(np.float32)

        # Perturb finite baseline signal values
        noisy_baseline = np.where(
            clean_baseline > -139.0,
            clean_baseline + noise,
            clean_baseline,
        )

        # Run ranking on perturbed signals
        run_top_5 = run_greedy_ranking(
            candidate_pool, precomputed_signals, noisy_baseline, cell_pops, gap_cutoff, top_k=_TOP_K
        )

        matches = len(set(run_top_5).intersection(baseline_set))
        stability_pct = (matches / _TOP_K) * 100.0

        sites_str = ", ".join(run_top_5)
        print(f"#{run_idx:<5} {sites_str:<42} {matches:>2} / {_TOP_K:<4} {stability_pct:>6.1f} %")

        results.append({
            "run": run_idx,
            "top_5": run_top_5,
            "matches": matches,
            "stability_pct": stability_pct,
        })

    print("-" * 75)

    # 7. Summary metrics
    all_matches = [r["matches"] for r in results]
    all_pcts = [r["stability_pct"] for r in results]
    mean_matches = float(np.mean(all_matches))
    mean_pct = float(np.mean(all_pcts))
    min_matches = int(np.min(all_matches))
    max_matches = int(np.max(all_matches))

    # Frequency of each site appearing in top 5
    site_frequencies: Dict[str, int] = {}
    for r in results:
        for s in r["top_5"]:
            site_frequencies[s] = site_frequencies.get(s, 0) + 1

    print("\n" + "=" * 75)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("=" * 75)
    print(f"Total Runs                   : {_NUM_RUNS}")
    print(f"Noise Magnitude (sigma)      : {noise_sigma_db:.1f} dB")
    print(f"Average Top-5 Match Count    : {mean_matches:.2f} / {_TOP_K} ({mean_pct:.1f} % stability)")
    print(f"Min / Max Matches in Any Run : {min_matches} / {max_matches} out of {_TOP_K}")
    print("\nSite Retention Frequency Across 20 Perturbed Runs:")
    for site, count in sorted(site_frequencies.items(), key=lambda x: -x[1]):
        in_baseline = "✓ (in baseline top 5)" if site in baseline_set else "  (alternative site)"
        print(f"  {site:<12}: {count:>2} / {_NUM_RUNS} runs ({count/_NUM_RUNS*100:>5.1f} %)  {in_baseline}")
    print("=" * 75)

    return {
        "num_runs": _NUM_RUNS,
        "noise_sigma_db": noise_sigma_db,
        "mean_matches": mean_matches,
        "mean_pct": mean_pct,
        "baseline_top_5": baseline_top_5,
        "results": results,
    }


if __name__ == "__main__":
    run_sensitivity_analysis()
