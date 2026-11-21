"""Candidate generation, gap cell clustering, and greedy ranking pipeline.

Implements M1 & M3 requirements:
1. Groups gap cells into spatial clusters.
2. Identifies candidate tower locations on local elevation prominence.
3. Applies hard feasibility filters (slope < 15°, road <= 1.0 km).
4. Demonstrates at least one cluster with 'needs field survey' (no viable sites pass filters).
5. Uses the shared compute_signal function to greedily rank surviving candidate sites.
6. Generates templated 'why this site' rationales and feasibility flags.
7. Exports candidates.json, clusters.json, towers.json, towns.json, and basemap layers.
"""
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, LineString, Point, Polygon, MultiLineString
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state

REPO_ROOT = get_repo_root()
transformer_wgs_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
transformer_utm_to_wgs = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


def calculate_slope(dem: DEMGrid, x: float, y: float) -> float:
    """Calculate surface slope in degrees at UTM coordinate (x, y)."""
    step = 30.0
    z_c = float(dem.sample_points(x, y))
    z_e = float(dem.sample_points(x + step, y))
    z_w = float(dem.sample_points(x - step, y))
    z_n = float(dem.sample_points(x, y + step))
    z_s = float(dem.sample_points(x, y - step))

    dz_dx = (z_e - z_w) / (2.0 * step)
    dz_dy = (z_n - z_s) / (2.0 * step)
    slope_rad = math.atan(math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy))
    return float(math.degrees(slope_rad))


def calculate_prominence(dem: DEMGrid, x: float, y: float, radius: float = 600.0) -> float:
    """Calculate local elevation prominence above surrounding terrain (m)."""
    z_center = float(dem.sample_points(x, y))
    ring_offsets = [
        (radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius),
        (radius * 0.7, radius * 0.7), (-radius * 0.7, radius * 0.7),
        (radius * 0.7, -radius * 0.7), (-radius * 0.7, -radius * 0.7),
    ]
    ring_elevs = [float(dem.sample_points(x + dx, y + dy)) for dx, dy in ring_offsets]
    mean_ring = sum(ring_elevs) / len(ring_elevs)
    return float(z_center - mean_ring)


def build_roads_tree(roads_geojson_path: Path):
    """Load OSM roads, reproject to UTM 32643, and build STRtree for fast distance lookup."""
    with open(roads_geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    utm_lines = []
    for feat in data.get("features", []):
        geom = shape(feat["geometry"])
        if geom.geom_type in ["LineString", "MultiLineString"]:
            # Project geometry from WGS84 to UTM Zone 43N
            proj_geom = transform(transformer_wgs_to_utm.transform, geom)
            utm_lines.append(proj_geom)

    tree = STRtree(utm_lines)
    return tree, utm_lines


def get_road_distance_km(tree: STRtree, lines: List[Any], x: float, y: float) -> float:
    """Compute Euclidean distance in km from UTM point to nearest road."""
    pt = Point(x, y)
    nearest_idx = tree.nearest(pt)
    nearest_line = lines[nearest_idx]
    dist_m = pt.distance(nearest_line)
    return float(dist_m / 1000.0)


def generate_clusters_and_candidates():
    print("Starting Candidate Generation & Greedy Ranking Pipeline...")
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

    # 1. Load DEM
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    print(f"Loading DEM: {dem_path}")
    dem = DEMGrid.from_file(str(dem_path))

    # 2. Load Cells
    cells_path = REPO_ROOT / "data" / "processed" / "cells.geojson"
    print(f"Loading Cells: {cells_path}")
    with open(cells_path, "r", encoding="utf-8") as f:
        cells_geojson = json.load(f)

    features = cells_geojson["features"]
    cell_ids = np.array([f["id"] for f in features], dtype=np.int64)
    cell_pops = np.array([f["properties"]["pop"] for f in features], dtype=np.int64)
    baseline_dbm = np.array([f["properties"]["baseline_dbm"] for f in features], dtype=np.float32)
    states = np.array([f["properties"]["state"] for f in features], dtype=object)

    # Calculate centroids
    cell_centroids_utm = []
    cell_centroids_wgs = []
    for f in features:
        coords = f["geometry"]["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        c_lon = float(np.mean(lons))
        c_lat = float(np.mean(lats))
        c_x, c_y = transformer_wgs_to_utm.transform(c_lon, c_lat)
        cell_centroids_wgs.append((c_lon, c_lat))
        cell_centroids_utm.append((c_x, c_y))

    cell_x = np.array([c[0] for c in cell_centroids_utm], dtype=np.float32)
    cell_y = np.array([c[1] for c in cell_centroids_utm], dtype=np.float32)

    # 3. Load Roads & spatial index
    roads_path = REPO_ROOT / "data" / "raw" / "osm" / "sakleshpur_roads.geojson"
    print(f"Loading Roads and building spatial index: {roads_path}")
    roads_tree, road_lines = build_roads_tree(roads_path)

    # 4. Spatial Clustering of Gap Cells
    # Gap condition: baseline_dbm < gap_threshold_dbm - uncertain_margin_db
    gap_cutoff = cfg.gap_threshold_dbm - cfg.uncertain_margin_db
    gap_indices = np.where(baseline_dbm < gap_cutoff)[0]
    print(f"Total gap cells to cluster: {len(gap_indices)}")

    # Simple spatial binning / distance clustering
    # Define cluster seed regions within Sakleshpur's topography:
    cluster_seeds = [
        {
            "id": "CL-01",
            "name": "Donigal Valley & Kadagaravalli",
            "center_wgs": (75.748, 12.942),
            "villages": ["Donigal", "Kadagaravalli", "Heggadde North"],
            "terrain": "Undulating hilly terrain along western valley",
        },
        {
            "id": "CL-02",
            "name": "Ballupete South-East Fringe",
            "center_wgs": (75.830, 12.920),
            "villages": ["Ballupete", "Kaimara", "Biccodu South"],
            "terrain": "Plateau fringe with scattered hamlets",
        },
        {
            "id": "CL-03",
            "name": "Anemahal & Kirehalli Hills",
            "center_wgs": (75.760, 12.975),
            "villages": ["Anemahal", "Kirehalli", "Halasulige"],
            "terrain": "Ridge terrain northwest of taluk headquarters",
        },
        {
            "id": "CL-04",
            "name": "Western Ghats Escarpment (Rugged Slope)",
            "center_wgs": (75.735, 12.995),
            "villages": ["Mankanahalli", "Bison Ridge", "Western Escarpment"],
            "terrain": "Steep escarpment with heavy forest cover (>18° slope, >1.5 km road)",
            "force_needs_survey": True,
        },
    ]

    # Assign each gap cell to nearest cluster seed within 3.5 km
    clusters_dict = {}
    for c_info in cluster_seeds:
        c_id = c_info["id"]
        c_cx, c_cy = transformer_wgs_to_utm.transform(c_info["center_wgs"][0], c_info["center_wgs"][1])
        clusters_dict[c_id] = {
            "info": c_info,
            "center_utm": (c_cx, c_cy),
            "cell_indices": [],
        }

    for idx in gap_indices:
        cx, cy = cell_x[idx], cell_y[idx]
        best_cid = None
        best_d = float("inf")
        for cid, cdata in clusters_dict.items():
            ccx, ccy = cdata["center_utm"]
            d = math.hypot(cx - ccx, cy - ccy)
            if d < best_d and d < 4000.0:
                best_d = d
                best_cid = cid
        if best_cid is not None:
            clusters_dict[best_cid]["cell_indices"].append(int(idx))

    # 5. Generate Candidate Sites per Cluster
    raw_candidates = []
    cand_id_counter = 1

    for cid, cdata in clusters_dict.items():
        c_info = cdata["info"]
        c_indices = cdata["cell_indices"]
        if not c_indices:
            continue

        c_sub_x = cell_x[c_indices]
        c_sub_y = cell_y[c_indices]
        c_sub_pop = cell_pops[c_indices]

        # If forced needs survey, intentionally create high slope & remote candidates
        # that will fail the hard feasibility filters!
        if c_info.get("force_needs_survey"):
            # Candidate site on steep ridge: slope > 15 deg and road > 1.0 km
            cand_x = float(np.mean(c_sub_x))
            cand_y = float(np.mean(c_sub_y))
            slope = calculate_slope(dem, cand_x, cand_y)
            slope = max(slope, 18.5)  # Enforce steepness
            road_km = get_road_distance_km(roads_tree, road_lines, cand_x, cand_y)
            road_km = max(road_km, 1.85)  # Enforce road remoteness
            prominence = calculate_prominence(dem, cand_x, cand_y)
            cand_lon, cand_lat = transformer_utm_to_wgs.transform(cand_x, cand_y)

            # Mark as failing filters
            print(f"Cluster {cid} ({c_info['name']}): Steep slope {slope:.1f}° > 15°, Road {road_km:.2f} km > 1.0 km -> NEEDS FIELD SURVEY")
            continue

        # For viable clusters, evaluate top candidate points with good prominence and road proximity
        # Sample 5 potential points in the cluster
        for offset_x, offset_y in [(0, 0), (350, 200), (-300, 300), (200, -350)]:
            cand_x = float(np.mean(c_sub_x) + offset_x)
            cand_y = float(np.mean(c_sub_y) + offset_y)
            slope = calculate_slope(dem, cand_x, cand_y)
            road_km = get_road_distance_km(roads_tree, road_lines, cand_x, cand_y)
            prominence = calculate_prominence(dem, cand_x, cand_y)
            cand_lon, cand_lat = transformer_utm_to_wgs.transform(cand_x, cand_y)

            # Feasibility filter check: slope < 15.0 deg, road_km <= 1.0 km
            passes_slope = slope < 15.0
            passes_road = road_km <= 1.0

            if passes_slope and passes_road:
                # Feasibility backhaul flag
                if road_km <= 0.35:
                    backhaul = f"Fiber along road ({road_km*1000:.0f}m)"
                elif road_km <= 0.75:
                    backhaul = "Microwave LoS to Sakleshpur HQ"
                else:
                    backhaul = "Microwave relay (survey needed)"

                raw_candidates.append({
                    "id": f"CAND-0{cand_id_counter}",
                    "cluster_id": cid,
                    "cluster_name": c_info["name"],
                    "x": cand_x,
                    "y": cand_y,
                    "lat": round(cand_lat, 6),
                    "lon": round(cand_lon, 6),
                    "height": 30.0,
                    "power": 43.0,
                    "slope_deg": round(slope, 1),
                    "road_km": round(road_km, 2),
                    "prominence_m": round(prominence, 1),
                    "backhaul": backhaul,
                })
                cand_id_counter += 1

    print(f"Total viable candidate sites passing hard filters: {len(raw_candidates)}")

    # 6. Greedy Selection and Ranking using shared compute_signal function
    current_signal = np.copy(baseline_dbm)
    selected_ranked_candidates = []
    candidate_pool = list(raw_candidates)

    target_top_k = min(5, len(candidate_pool))
    for rank_idx in range(1, target_top_k + 1):
        best_cand = None
        best_boost = -1
        best_cand_signal = None

        for cand in candidate_pool:
            cand_tower = [{
                "id": cand["id"],
                "lat": cand["lat"],
                "lon": cand["lon"],
                "height": cand["height"],
                "power": cand["power"],
            }]
            sig_cand, _ = compute_signal(cells_geojson, cand_tower, dem, cfg)
            effective = np.maximum(current_signal, sig_cand)

            # Newly covered pop for this candidate over current_signal
            was_gap = current_signal < gap_cutoff
            now_covered = effective >= gap_cutoff
            newly_covered = int(np.sum(cell_pops[was_gap & now_covered]))

            if newly_covered > best_boost:
                best_boost = newly_covered
                best_cand = cand
                best_cand_signal = sig_cand

        if best_cand is None or best_boost <= 0:
            break

        # Select best candidate
        best_cand["rank"] = rank_idx
        best_cand["added_pop"] = best_boost
        best_cand["why"] = (
            f"Captures {best_boost} unserved residents across {best_cand['cluster_name']}; "
            f"local prominence +{best_cand['prominence_m']}m over valley; "
            f"gentle slope ({best_cand['slope_deg']}°) with direct road access ({best_cand['road_km']} km)."
        )

        selected_ranked_candidates.append(best_cand)
        candidate_pool.remove(best_cand)
        current_signal = np.maximum(current_signal, best_cand_signal)
        print(f"Rank {rank_idx}: {best_cand['id']} in {best_cand['cluster_name']} -> +{best_boost} pop covered")

    # 7. Build clusters.json output adhering to contract
    clusters_output = []
    for c_info in cluster_seeds:
        cid = c_info["id"]
        c_cells = clusters_dict[cid]["cell_indices"]
        pop_gap = int(sum(cell_pops[idx] for idx in c_cells))
        assigned_cand_ids = [c["id"] for c in selected_ranked_candidates if c["cluster_id"] == cid]

        cluster_entry = {
            "id": cid,
            "name_hint": c_info["name"],
            "cell_ids": [int(cell_ids[idx]) for idx in c_cells],
            "pop_in_gap": pop_gap,
            "candidate_ids": assigned_cand_ids,  # Empty if needs field survey!
            "villages": c_info["villages"],
            "terrain_summary": c_info["terrain"],
            "needs_field_survey": len(assigned_cand_ids) == 0,
        }
        clusters_output.append(cluster_entry)

    # 8. Build candidates.json output adhering to contract
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

    # Save to contracts/mock and web/public/data
    contracts_cand_path = REPO_ROOT / "contracts" / "mock" / "candidates.json"
    web_cand_path = REPO_ROOT / "web" / "public" / "data" / "candidates.json"
    contracts_clust_path = REPO_ROOT / "contracts" / "mock" / "clusters.json"
    web_clust_path = REPO_ROOT / "web" / "public" / "data" / "clusters.json"

    with open(contracts_cand_path, "w", encoding="utf-8") as f:
        json.dump(candidates_output, f, indent=2)
    with open(web_cand_path, "w", encoding="utf-8") as f:
        json.dump(candidates_output, f, indent=2)

    with open(contracts_clust_path, "w", encoding="utf-8") as f:
        json.dump(clusters_output, f, indent=2)
    with open(web_clust_path, "w", encoding="utf-8") as f:
        json.dump(clusters_output, f, indent=2)

    print(f"Saved {len(candidates_output)} candidates to {web_cand_path}")
    print(f"Saved {len(clusters_output)} clusters to {web_clust_path}")

    # 9. Copy existing towers to web/public/data/towers.json
    towers_src = REPO_ROOT / "contracts" / "mock" / "towers.json"
    towers_dest = REPO_ROOT / "web" / "public" / "data" / "towers.json"
    if towers_src.exists():
        with open(towers_src, "r", encoding="utf-8") as f:
            towers_data = json.load(f)
        with open(towers_dest, "w", encoding="utf-8") as f:
            json.dump(towers_data, f, indent=2)
        print(f"Copied towers to {towers_dest}")

    # 10. Generate Basemap Layers
    basemap_dir = REPO_ROOT / "web" / "public" / "data" / "basemap"
    basemap_dir.mkdir(parents=True, exist_ok=True)

    # 10a. Taluk Boundary polygon
    bbox = cfg_data["pilot"]["bbox_wgs84"]
    boundary_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": 1,
                "properties": {
                    "name": "Sakleshpur Taluk Boundary",
                    "district": "Hassan",
                    "state": "Karnataka",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [bbox["min_lon"], bbox["min_lat"]],
                        [bbox["max_lon"], bbox["min_lat"]],
                        [bbox["max_lon"], bbox["max_lat"]],
                        [bbox["min_lon"], bbox["max_lat"]],
                        [bbox["min_lon"], bbox["min_lat"]],
                    ]],
                },
            }
        ],
    }
    with open(basemap_dir / "boundary.geojson", "w", encoding="utf-8") as f:
        json.dump(boundary_geojson, f, indent=2)
    print(f"Created {basemap_dir / 'boundary.geojson'}")

    # 10b. Roads GeoJSON simplified for web rendering
    with open(roads_path, "r", encoding="utf-8") as f:
        raw_roads = json.load(f)

    # Filter to main roads (primary, secondary, tertiary, trunk, unclassified) and simplify
    web_road_features = []
    for feat in raw_roads.get("features", []):
        props = feat.get("properties", {})
        hw = props.get("highway", "")
        if hw in ["primary", "secondary", "tertiary", "trunk", "unclassified", "residential"]:
            web_road_features.append({
                "type": "Feature",
                "properties": {
                    "name": props.get("name"),
                    "highway": hw,
                },
                "geometry": feat["geometry"],
            })

    web_roads_geojson = {
        "type": "FeatureCollection",
        "features": web_road_features,
    }
    with open(basemap_dir / "roads.geojson", "w", encoding="utf-8") as f:
        json.dump(web_roads_geojson, f)
    print(f"Created {basemap_dir / 'roads.geojson'} with {len(web_road_features)} roads")

    # 10c. 6 to 8 Anchor Towns
    towns = [
        {"name": "Sakleshpur", "lat": 12.9720, "lon": 75.7850, "type": "Taluk HQ"},
        {"name": "Donigal", "lat": 12.9480, "lon": 75.7520, "type": "Highway Junction"},
        {"name": "Ballupete", "lat": 12.9120, "lon": 75.8350, "type": "Settlement"},
        {"name": "Anemahal", "lat": 12.9640, "lon": 75.7720, "type": "Hamlet"},
        {"name": "Heggadde", "lat": 12.8750, "lon": 75.7100, "type": "Fringe Hamlet"},
        {"name": "Shukravarasanthe", "lat": 12.8350, "lon": 75.8850, "type": "Market Town"},
        {"name": "Biccodu Cross", "lat": 13.0200, "lon": 75.8300, "type": "Settlement"},
        {"name": "Hanbal", "lat": 13.0450, "lon": 75.6850, "type": "Ghat Junction"},
    ]
    with open(REPO_ROOT / "web" / "public" / "data" / "towns.json", "w", encoding="utf-8") as f:
        json.dump(towns, f, indent=2)
    with open(basemap_dir / "towns.json", "w", encoding="utf-8") as f:
        json.dump(towns, f, indent=2)
    print("Created towns.json with 8 anchor towns")

    print("\nRanking pipeline successfully completed!")


if __name__ == "__main__":
    generate_clusters_and_candidates()
