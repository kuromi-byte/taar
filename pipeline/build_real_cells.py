"""Build real cells_base.geojson from WorldPop, DEM, and OSM roads.

Implements Task 2:
1. Reads window of worldpop_india_100m.tif around config.json bbox.
2. Aggregates 3x3 blocks on native grid (300m cells), preserving total population.
3. Computes integer ids, cx/cy in EPSG:32643, elev_m and slope_deg from dem_utm43n.tif.
4. Computes road_km from real OSM roads using STRtree.
5. Sets tower_evidence = "TODO-STUB".
6. Adds top-level meta: {"source": "worldpop", "cell_size_m": 300, ...}.
7. Reports cell count, total population, and population lost to threshold.
"""
import json
import math
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
from shapely.geometry import shape, Point
from shapely.ops import transform
from shapely.strtree import STRtree

# Project root
REPO_ROOT = Path(__file__).resolve().parent.parent

# Transformers
trans_wgs_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def calculate_slope(dem_data: np.ndarray, res_x: float, res_y: float, col: int, row: int, width: int, height: int) -> float:
    """Calculate slope in degrees at raster col, row using finite difference."""
    c_w = max(0, col - 1)
    c_e = min(width - 1, col + 1)
    r_n = max(0, row - 1)
    r_s = min(height - 1, row + 1)

    dz_dx = (float(dem_data[row, c_e]) - float(dem_data[row, c_w])) / (2.0 * res_x)
    dz_dy = (float(dem_data[r_s, col]) - float(dem_data[r_n, col])) / (2.0 * res_y)
    slope_rad = math.atan(math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy))
    return float(math.degrees(slope_rad))


def build_real_cells(pop_threshold: float = 1.0) -> dict:
    config_path = REPO_ROOT / "contracts" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    bbox = cfg["pilot"]["bbox_wgs84"]
    min_lon = bbox["min_lon"]
    max_lon = bbox["max_lon"]
    min_lat = bbox["min_lat"]
    max_lat = bbox["max_lat"]

    worldpop_path = REPO_ROOT / "data" / "raw" / "worldpop" / "worldpop_india_100m.tif"
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    roads_path = REPO_ROOT / "data" / "raw" / "osm" / "sakleshpur_roads.geojson"

    print(f"Loading WorldPop raster: {worldpop_path}")
    with rasterio.open(worldpop_path) as src:
        win = from_bounds(min_lon, min_lat, max_lon, max_lat, src.transform)
        # Round window to integer pixel offsets and lengths
        win = win.round_offsets().round_lengths()
        win_transform = rasterio.windows.transform(win, src.transform)
        raw_pop = src.read(1, window=win)

    # Clean nodata / negatives
    raw_pop = np.where(raw_pop < 0, 0.0, raw_pop)
    raw_pop = np.nan_to_num(raw_pop, nan=0.0)

    rows, cols = raw_pop.shape
    agg_rows = rows // 3
    agg_cols = cols // 3
    trimmed_pop = raw_pop[: agg_rows * 3, : agg_cols * 3]
    raw_pop_total = float(trimmed_pop.sum())

    # Aggregate 3x3 blocks preserving total population
    blocks = trimmed_pop.reshape(agg_rows, 3, agg_cols, 3).sum(axis=(1, 3))

    print(f"Aggregated {rows}x{cols} raw 100m pixels into {agg_rows}x{agg_cols} = {agg_rows * agg_cols} 300m blocks.")
    print(f"Total raw population in window: {raw_pop_total:,.2f}")

    # Load DEM for elevation and slope
    print(f"Loading DEM raster: {dem_path}")
    with rasterio.open(dem_path) as dem_src:
        dem_data = dem_src.read(1)
        dem_trans = dem_src.transform
        dem_inv_trans = ~dem_trans
        dem_width = dem_src.width
        dem_height = dem_src.height
        dem_res_x = float(dem_trans.a)
        dem_res_y = float(-dem_trans.e)
        dem_nodata = dem_src.nodata if dem_src.nodata is not None else -9999.0

    # Load OSM Roads and build STRtree
    print(f"Loading OSM roads: {roads_path}")
    with open(roads_path, "r", encoding="utf-8") as f:
        roads_geojson = json.load(f)

    utm_lines = []
    for feat in roads_geojson.get("features", []):
        geom = shape(feat["geometry"])
        if geom.geom_type in ["LineString", "MultiLineString"]:
            proj_geom = transform(trans_wgs_to_utm.transform, geom)
            utm_lines.append(proj_geom)
    roads_tree = STRtree(utm_lines)
    print(f"Built STRtree with {len(utm_lines)} road line segments.")

    features = []
    cell_id = 1
    retained_pop = 0.0
    lost_pop = 0.0

    # Temporary lists for batch road distance computation
    cell_metadata = []
    utm_points = []

    for r in range(agg_rows):
        for c in range(agg_cols):
            block_pop = float(blocks[r, c])
            if block_pop < pop_threshold:
                lost_pop += block_pop
                continue

            retained_pop += block_pop

            # Bounding box of 3x3 block in WGS84
            c0 = c * 3
            r0 = r * 3
            c1 = (c + 1) * 3
            r1 = (r + 1) * 3

            lon_left, lat_top = win_transform * (c0, r0)
            lon_right, lat_bottom = win_transform * (c1, r1)
            lon_c = (lon_left + lon_right) / 2.0
            lat_c = (lat_top + lat_bottom) / 2.0

            # Project center to UTM Zone 43N
            cx, cy = trans_wgs_to_utm.transform(lon_c, lat_c)

            # Sample DEM at cell center
            d_col, d_row = dem_inv_trans * (cx, cy)
            d_col_i = int(round(d_col))
            d_row_i = int(round(d_row))

            if 0 <= d_col_i < dem_width and 0 <= d_row_i < dem_height:
                elev = float(dem_data[d_row_i, d_col_i])
                if elev == dem_nodata:
                    elev = 0.0
                slope = calculate_slope(dem_data, dem_res_x, dem_res_y, d_col_i, d_row_i, dem_width, dem_height)
            else:
                elev = 0.0
                slope = 0.0

            poly_coords = [
                [round(lon_left, 6), round(lat_bottom, 6)],
                [round(lon_right, 6), round(lat_bottom, 6)],
                [round(lon_right, 6), round(lat_top, 6)],
                [round(lon_left, 6), round(lat_top, 6)],
                [round(lon_left, 6), round(lat_bottom, 6)],
            ]

            cell_metadata.append({
                "id": cell_id,
                "pop": int(round(block_pop)),
                "raw_pop": round(block_pop, 2),
                "cx": round(float(cx), 2),
                "cy": round(float(cy), 2),
                "elev_m": round(float(elev), 1),
                "slope_deg": round(float(slope), 1),
                "poly_coords": poly_coords,
            })
            utm_points.append(Point(cx, cy))
            cell_id += 1

    print(f"Computing road distances for {len(utm_points)} cells...")
    nearest_road_indices = roads_tree.nearest(utm_points)
    for idx, (meta, pt) in enumerate(zip(cell_metadata, utm_points)):
        nearest_line = utm_lines[nearest_road_indices[idx]]
        dist_km = round(float(pt.distance(nearest_line)) / 1000.0, 3)

        features.append({
            "type": "Feature",
            "id": meta["id"],
            "geometry": {
                "type": "Polygon",
                "coordinates": [meta["poly_coords"]],
            },
            "properties": {
                "id": meta["id"],
                "pop": meta["pop"],
                "cx": meta["cx"],
                "cy": meta["cy"],
                "elev_m": meta["elev_m"],
                "slope_deg": meta["slope_deg"],
                "road_km": dist_km,
                "tower_evidence": "TODO-STUB",
            },
        })

    geojson_out = {
        "type": "FeatureCollection",
        "meta": {
            "source": "worldpop",
            "cell_size_m": 300,
            "population_total": int(round(retained_pop)),
            "raw_population_total": int(round(raw_pop_total)),
            "population_lost_to_threshold": int(round(lost_pop)),
            "pop_threshold": pop_threshold,
            "cell_count": len(features),
        },
        "features": features,
    }

    out_paths = [
        REPO_ROOT / "contracts" / "mock" / "cells_base.geojson",
        REPO_ROOT / "data" / "processed" / "cells_base.geojson",
    ]
    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(geojson_out, f)
        print(f"Saved {len(features)} cells to {p}")

    print("\n================== SUMMARY ==================")
    print(f"Cell count: {len(features):,}")
    print(f"Total population (retained): {int(round(retained_pop)):,}")
    print(f"Raw population: {int(round(raw_pop_total)):,}")
    print(f"Population lost to threshold ({pop_threshold}): {lost_pop:,.2f} ({lost_pop/raw_pop_total*100:.2f}%)")
    print("=============================================\n")

    return geojson_out["meta"]


if __name__ == "__main__":
    build_real_cells(pop_threshold=1.0)
