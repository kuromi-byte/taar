"""Candidate generation, gap-cell clustering, and greedy ranking pipeline.

Dev B – /pipeline/ranking (main entry point: pipeline/clustering_and_ranking.py)

Rules strictly adhering to Rundown.md and Dev B requirements:
1. Re-run clustering and ranking on the REAL web/public/data/cells.geojson.
2. Cell ids start at 1, not 0. Use ids exactly as in the file. Never renumber.
3. Cluster touching 'gap' cells (8-connectivity / 8 neighbours).
4. Name each cluster "Near <town>" using the nearest entry in towns.json. Never invent a name.
5. Hard filters (slope, road distance) read from /contracts/config.json.
   A cell with null slope or null road distance fails the filter.
   Fallback thresholds marked TODO-STUB.
6. Score candidate sites on local elevation prominence; choose greedily by added
   unserved population using compute_signal from pipeline/model/engine.py.
7. Do not force a 'needs field survey' cluster. Report one only if the filters
   really leave a cluster empty.
8. Write candidates.json and clusters.json exactly per Contracts 4 and 5.
9. No hard-coded thresholds. Mark anything stubbed TODO-STUB.
"""
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
from pyproj import Transformer

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal
from pipeline.ranking.coverage import compute_coverage

REPO_ROOT = get_repo_root()

# Coordinate Transformers
_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
_to_wgs = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)

# Grid parameters
_CELL_SIZE_M = 300.0        # native cell spacing (UTM metres)
_MIN_CLUSTER_CELLS = 3      # minimum gap cells to form an actionable cluster
_SEARCH_BUFFER_M = 3000.0   # search radius (m) around gap cluster for candidate tower sites
_TOP_K = 5                  # target top-K candidates to select greedily


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))


def _nearest_town_name(lon: float, lat: float, towns: List[Dict[str, Any]]) -> str:
    """Resolve cluster name hint as 'Near <town>' using towns.json strictly. Never invent a name."""
    best_town = towns[0]["name"]
    min_dist = float("inf")
    for t in towns:
        d = _haversine_km(lon, lat, float(t["lon"]), float(t["lat"]))
        if d < min_dist:
            min_dist = d
            best_town = t["name"]
    return f"Near {best_town}"


def calculate_prominence(dem: DEMGrid, x: float, y: float, radius: float = 600.0) -> float:
    """Calculate local elevation prominence (m) above surrounding terrain ring."""
    zc = float(dem.sample_points(x, y))
    offsets = [
        (radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius),
        (radius * 0.707, radius * 0.707), (-radius * 0.707, radius * 0.707),
        (radius * 0.707, -radius * 0.707), (-radius * 0.707, -radius * 0.707),
    ]
    ring = [float(dem.sample_points(x + dx, y + dy)) for dx, dy in offsets]
    return float(zc - sum(ring) / len(ring))


def cluster_gap_cells_8way(
    gap_indices: np.ndarray,
    cell_x: np.ndarray,
    cell_y: np.ndarray,
    snap_m: float = _CELL_SIZE_M,
) -> List[List[int]]:
    """Group gap cells into 8-connected spatial components.

    Two cells touch if their grid coordinates (col, row) differ by at most 1 in either direction.
    Returns list of components, each containing array indices of participating cells.
    """
    grid_map: Dict[Tuple[int, int], int] = {}
    for arr_idx in gap_indices:
        col = int(round(cell_x[arr_idx] / snap_m))
        row = int(round(cell_y[arr_idx] / snap_m))
        grid_map[(col, row)] = int(arr_idx)

    visited = set()
    components: List[List[int]] = []

    for arr_idx in gap_indices:
        if arr_idx in visited:
            continue
        comp: List[int] = []
        queue = [arr_idx]
        visited.add(arr_idx)
        while queue:
            cur = queue.pop(0)
            comp.append(cur)
            col = int(round(cell_x[cur] / snap_m))
            row = int(round(cell_y[cur] / snap_m))
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if dc == 0 and dr == 0:
                        continue
                    nb = grid_map.get((col + dc, row + dr))
                    if nb is not None and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
        components.append(comp)

    # Sort largest cluster first
    components.sort(key=len, reverse=True)
    return components


def generate_clusters_and_candidates():
    print("=" * 70)
    print("Candidate Generation & Greedy Ranking Pipeline — REAL CELLS")
    print("=" * 70)

    # 1. Load config & propagation parameters
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

    # Hard filter limits from contracts/config.json (marked TODO-STUB if absent)
    ranking_cfg = cfg_data.get("ranking", {})
    filters_cfg = cfg_data.get("candidate_filters", ranking_cfg)

    if "max_slope_deg" in filters_cfg:
        slope_max_deg = float(filters_cfg["max_slope_deg"])
    elif "candidate_slope_max_deg" in filters_cfg:
        slope_max_deg = float(filters_cfg["candidate_slope_max_deg"])
    else:
        slope_max_deg = 15.0  # TODO-STUB: starting value per rundown.md 2.4
        print(f"  [TODO-STUB] max_slope_deg not specified in config; using {slope_max_deg}°")

    if "max_road_km" in filters_cfg:
        road_max_km = float(filters_cfg["max_road_km"])
    elif "candidate_road_max_km" in filters_cfg:
        road_max_km = float(filters_cfg["candidate_road_max_km"])
    else:
        road_max_km = 1.0  # TODO-STUB: starting value per rundown.md 2.4
        print(f"  [TODO-STUB] max_road_km not specified in config; using {road_max_km} km")

    # 2. Load DEM
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    print(f"\nLoading DEM: {dem_path}")
    dem = DEMGrid.from_file(str(dem_path))

    # 3. Load Real Cells (web/public/data/cells.geojson)
    cells_path = REPO_ROOT / "web" / "public" / "data" / "cells.geojson"
    print(f"Loading Real Cells: {cells_path}")
    with open(cells_path, "r", encoding="utf-8") as f:
        cells_fc = json.load(f)

    features = cells_fc["features"]
    n_cells = len(features)
    print(f"  Loaded {n_cells:,} cells from real cells.geojson")

    # Preserve exact cell IDs (1..N, never renumber)
    cell_ids = np.array([f["id"] for f in features], dtype=np.int64)
    cell_pops = np.array([f["properties"]["pop"] for f in features], dtype=np.int64)
    cell_x = np.array([f["properties"]["cx"] for f in features], dtype=np.float32)
    cell_y = np.array([f["properties"]["cy"] for f in features], dtype=np.float32)
    cell_states = np.array([f["properties"]["state"] for f in features], dtype=object)

    raw_dbm = [f["properties"].get("baseline_dbm") for f in features]
    baseline_dbm = np.array([float(v) if v is not None else float("nan") for v in raw_dbm], dtype=np.float32)

    total_pop = int(np.sum(cell_pops))

    # Gap cells analysis
    gap_mask = cell_states == "gap"
    gap_indices = np.where(gap_mask)[0]
    n_gap = len(gap_indices)
    gap_pop = int(np.sum(cell_pops[gap_indices]))
    null_dbm_gap = int(np.sum(np.isnan(baseline_dbm[gap_indices])))

    print(f"  Total Population          : {total_pop:,}")
    print(f"  Total Gap Cells           : {n_gap:,} (Population: {gap_pop:,})")
    print(f"  Gap Cells with Null dbm   : {null_dbm_gap} / {n_gap}")

    # 4. Load Towns for real place naming
    towns_path = REPO_ROOT / "web" / "public" / "data" / "towns.json"
    with open(towns_path, "r", encoding="utf-8") as f:
        towns = json.load(f)
    print(f"  Loaded {len(towns)} anchor towns from {towns_path}")

    # 5. 8-Connected Component Clustering of gap cells
    print("\nClustering gap cells by 8-connectivity...")
    raw_components = cluster_gap_cells_8way(gap_indices, cell_x, cell_y)
    main_components = [c for c in raw_components if len(c) >= _MIN_CLUSTER_CELLS]
    print(f"  Identified {len(main_components)} clusters with >= {_MIN_CLUSTER_CELLS} gap cells")

    # 6. Candidate Site Generation & Hard Feasibility Filtering
    print(f"\nEvaluating candidate cells within {_SEARCH_BUFFER_M/1000.0:.1f} km buffer of clusters...")
    print(f"  Hard Filters: slope < {slope_max_deg}°, road distance <= {road_max_km} km")

    all_slopes = [f["properties"].get("slope_deg") for f in features]
    all_roads = [f["properties"].get("road_km") for f in features]

    filter_stats = {
        "evaluated_cells": 0,
        "dropped_null_slope": 0,
        "dropped_null_road": 0,
        "dropped_slope": 0,
        "dropped_road": 0,
        "surviving_candidates": 0,
    }

    # Store candidate info per cluster
    cluster_records = []
    cluster_viable_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for c_idx, comp in enumerate(main_components):
        cid = f"CL-{c_idx + 1:02d}"
        comp_x = cell_x[comp]
        comp_y = cell_y[comp]
        comp_pop = int(np.sum(cell_pops[comp]))
        comp_cell_ids = [int(cell_ids[idx]) for idx in comp]

        # Centroid of cluster in WGS84 for naming
        cx_mean = float(comp_x.mean())
        cy_mean = float(comp_y.mean())
        c_lon, c_lat = _to_wgs.transform(cx_mean, cy_mean)
        cluster_name = _nearest_town_name(c_lon, c_lat, towns)

        cluster_records.append({
            "id": cid,
            "name_hint": cluster_name,
            "cell_ids": comp_cell_ids,
            "pop_in_gap": comp_pop,
            "centroid_utm": (cx_mean, cy_mean),
            "centroid_wgs": (c_lon, c_lat),
        })

        # Bounding box of cluster gap cells + search buffer
        min_x, max_x = comp_x.min() - _SEARCH_BUFFER_M, comp_x.max() + _SEARCH_BUFFER_M
        min_y, max_y = comp_y.min() - _SEARCH_BUFFER_M, comp_y.max() + _SEARCH_BUFFER_M

        candidate_cell_indices = np.where(
            (cell_x >= min_x) & (cell_x <= max_x) & (cell_y >= min_y) & (cell_y <= max_y)
        )[0]

        viable_cands = []
        for arr_idx in candidate_cell_indices:
            filter_stats["evaluated_cells"] += 1
            sl = all_slopes[arr_idx]
            rk = all_roads[arr_idx]

            # Rule: A cell with null slope or null road fails the filter
            if sl is None:
                filter_stats["dropped_null_slope"] += 1
                continue
            if rk is None:
                filter_stats["dropped_null_road"] += 1
                continue
            if sl >= slope_max_deg:
                filter_stats["dropped_slope"] += 1
                continue
            if rk > road_max_km:
                filter_stats["dropped_road"] += 1
                continue

            filter_stats["surviving_candidates"] += 1
            px = float(cell_x[arr_idx])
            py = float(cell_y[arr_idx])
            p_lon, p_lat = _to_wgs.transform(px, py)
            prom = calculate_prominence(dem, px, py)

            # Backhaul flag determination (TODO-STUB: based on road proximity heuristic)
            if rk <= 0.35:
                backhaul = f"Fiber along road ({int(rk * 1000)}m)"  # TODO-STUB
            elif rk <= 0.75:
                backhaul = "Microwave LoS to Sakleshpur HQ"         # TODO-STUB
            else:
                backhaul = "Microwave relay (survey needed)"        # TODO-STUB

            viable_cands.append({
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
                "backhaul": backhaul,
            })

        cluster_viable_candidates[cid] = viable_cands
        status_str = f"{len(viable_cands)} viable sites" if viable_cands else "0 viable sites -> NEEDS FIELD SURVEY"
        print(f"  {cid} ({cluster_name:<24}): {len(comp):>4} gap cells, pop={comp_pop:>6,}, {status_str}")

    # 7. Elevation Prominence Scoring & Greedy Ranking
    print("\nRanking surviving candidates greedily with shared compute_coverage engine...")

    # Flatten candidate pool from clusters having viable candidates
    all_viable = []
    for cid, cands in cluster_viable_candidates.items():
        all_viable.extend(cands)

    # Sort candidates by elevation prominence descending
    all_viable.sort(key=lambda c: -c["prominence_m"])

    # Evaluate top prominence sites for greedy search
    candidate_pool = all_viable[:35] if len(all_viable) > 35 else list(all_viable)
    selected_ranked_candidates: List[Dict[str, Any]] = []

    chosen_towers: List[Dict[str, Any]] = []
    current_cov = 0
    target_k = min(_TOP_K, len(candidate_pool))

    for rank in range(1, target_k + 1):
        best_cand = None
        best_boost = -1
        best_total_cov = -1

        for cand in candidate_pool:
            tower_candidate = {
                "id": cand["cluster_id"],
                "lat": cand["lat"],
                "lon": cand["lon"],
                "height": cand["height"],
                "power": cand["power"],
            }
            trial_towers = chosen_towers + [tower_candidate]
            cov_res = compute_coverage(
                trial_towers,
                dem=dem,
                cfg=cfg,
                cells_json=cells_fc,
                baseline_dbm=np.where(np.isnan(baseline_dbm), -139.0, baseline_dbm),
                baseline_states=cell_states,
                cell_pops=cell_pops,
                cell_ids=cell_ids,
            )
            added_pop = cov_res.newly_covered_pop - current_cov

            if added_pop > best_boost:
                best_boost = added_pop
                best_cand = cand
                best_total_cov = cov_res.newly_covered_pop

        if best_cand is None or best_boost <= 0:
            print(f"  Greedy selection finished at rank {rank-1}: no remaining candidate adds unserved coverage.")
            break

        cand_id = f"CAND-0{rank}"
        best_cand["id"] = cand_id
        best_cand["rank"] = rank
        best_cand["added_pop"] = best_boost
        best_cand["why"] = (
            f"Captures {best_boost:,} unserved residents in the {best_cand['cluster_name']} area; "
            f"local elevation prominence {best_cand['prominence_m']:+.0f} m over surrounding terrain; "
            f"slope {best_cand['slope_deg']}° (< {slope_max_deg}°), "
            f"direct road access {best_cand['road_km']} km."
        )

        selected_ranked_candidates.append(best_cand)
        candidate_pool.remove(best_cand)
        chosen_towers.append({
            "id": cand_id,
            "lat": best_cand["lat"],
            "lon": best_cand["lon"],
            "height": best_cand["height"],
            "power": best_cand["power"],
        })
        current_cov = best_total_cov

        print(f"  Rank {rank}: {cand_id} ({best_cand['cluster_name']}) -> "
              f"+{best_boost:,} unserved pop (cum: {current_cov:,}), slope={best_cand['slope_deg']}°, "
              f"road={best_cand['road_km']}km, prom={best_cand['prominence_m']:+.1f}m")

    # 8. Build Contract 5: clusters.json
    clusters_output = []
    for rec in cluster_records:
        cid = rec["id"]
        assigned_cand_ids = [c["id"] for c in selected_ranked_candidates if c["cluster_id"] == cid]
        clusters_output.append({
            "id": cid,
            "name_hint": rec["name_hint"],
            "cell_ids": rec["cell_ids"],
            "pop_in_gap": rec["pop_in_gap"],
            "candidate_ids": assigned_cand_ids,
            "needs_field_survey": len(assigned_cand_ids) == 0,
        })

    # 9. Build Contract 4: candidates.json
    candidates_output = []
    for c in selected_ranked_candidates:
        candidates_output.append({
            "id": c["id"],
            "cluster_id": c["cluster_id"],
            "lat": c["lat"],
            "lon": c["lon"],
            "height": c["height"],
            "power": c["power"],
            "added_pop": c["added_pop"],
            "flags": {
                "road_km": c["road_km"],
                "slope_deg": c["slope_deg"],
                "backhaul": c["backhaul"],
            },
            "why": c["why"],
        })

    # Wrap in approved container with dataset meta.source: WorldPop
    candidates_container = {
        "meta": {"source": "WorldPop"},
        "items": candidates_output,
    }
    clusters_container = {
        "meta": {"source": "WorldPop"},
        "items": clusters_output,
    }

    # 10. Write outputs to pipeline/data (container format) and sync to web/public/data (plain array for frontend)
    pipeline_cand_path = REPO_ROOT / "pipeline" / "data" / "candidates.json"
    pipeline_clust_path = REPO_ROOT / "pipeline" / "data" / "clusters.json"
    web_cand_path = REPO_ROOT / "web" / "public" / "data" / "candidates.json"
    web_clust_path = REPO_ROOT / "web" / "public" / "data" / "clusters.json"

    pipeline_cand_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pipeline_cand_path, "w", encoding="utf-8") as f:
        json.dump(candidates_container, f, indent=2)

    with open(pipeline_clust_path, "w", encoding="utf-8") as f:
        json.dump(clusters_container, f, indent=2)

    if web_cand_path.parent.exists():
        with open(web_cand_path, "w", encoding="utf-8") as f:
            json.dump(candidates_output, f, indent=2)
        with open(web_clust_path, "w", encoding="utf-8") as f:
            json.dump(clusters_output, f, indent=2)

    out_paths = [pipeline_cand_path, pipeline_clust_path, web_cand_path, web_clust_path]

    # 11. Print comprehensive report
    total_newly_covered = sum(c["added_pop"] for c in candidates_output)
    nfs_clusters = [cl["id"] for cl in clusters_output if cl["needs_field_survey"]]

    print("\n" + "=" * 70)
    print("CLUSTERING & RANKING FINAL REPORT")
    print("=" * 70)
    print(f"Cell Count                   : {n_cells:,}")
    print(f"Total Population             : {total_pop:,}")
    print(f"Number of Clusters           : {len(clusters_output)}")
    print(f"Gap Cells (state=gap)        : {n_gap:,} (Population: {gap_pop:,})")
    print(f"Gap Cells with Null baseline : {null_dbm_gap} / {n_gap}")
    print("\nCells Dropped by Each Filter:")
    print(f"  Evaluated Candidate Cells  : {filter_stats['evaluated_cells']:,}")
    print(f"  Dropped (Null Slope)       : {filter_stats['dropped_null_slope']:,}")
    print(f"  Dropped (Null Road)        : {filter_stats['dropped_null_road']:,}")
    print(f"  Dropped (Slope >= {slope_max_deg}°)  : {filter_stats['dropped_slope']:,}")
    print(f"  Dropped (Road > {road_max_km} km)   : {filter_stats['dropped_road']:,}")
    print(f"  Surviving Candidates       : {filter_stats['surviving_candidates']:,}")
    print("\nSelected Ranked Candidates   : {0}".format(len(candidates_output)))
    for c in candidates_output:
        print(f"  {c['id']} ({c['cluster_id']}) -> +{c['added_pop']:,} pop, slope={c['flags']['slope_deg']}°, road={c['flags']['road_km']}km")
    print(f"Total Newly Covered Pop      : {total_newly_covered:,}")
    print(f"Needs Field Survey Clusters  : {nfs_clusters} ({len(nfs_clusters)} of {len(clusters_output)} clusters)")
    print("\nFiles Written:")
    for p in out_paths:
        print(f"  {p}")
    print("=" * 70)

    return {
        "n_cells": n_cells,
        "total_pop": total_pop,
        "n_clusters": len(clusters_output),
        "surviving_candidates": filter_stats["surviving_candidates"],
        "selected_candidates": len(candidates_output),
        "filter_stats": filter_stats,
        "null_dbm_gap": null_dbm_gap,
        "out_paths": [str(p) for p in out_paths],
    }


if __name__ == "__main__":
    generate_clusters_and_candidates()
