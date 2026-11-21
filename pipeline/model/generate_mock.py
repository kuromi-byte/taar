"""Script to generate mock contracts and baseline cells.geojson for Hour 0-1 kickoff.

Produces:
- /contracts/mock/towers.json
- /contracts/mock/cells_base.geojson
- /data/raw/opencellid_pilot.csv
- /data/processed/cells.geojson (baseline with baseline_dbm and state)
"""
import json
import numpy as np
from pyproj import Transformer
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state

transformer_utm_to_wgs = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)
transformer_wgs_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def generate_mock_data():
    # Center around Sakleshpur, Karnataka: ~12.972 N, 75.785 E
    center_lon, center_lat = 75.785, 12.972
    center_x, center_y = transformer_wgs_to_utm.transform(center_lon, center_lat)

    # 1. Existing Towers (OpenCellID sample in town and along NH-75 highway)
    # Towers located in Sakleshpur town, Donigal, and Ballupete
    towers_data = [
        {"id": 1, "lat": 12.9735, "lon": 75.7842, "height": 30.0, "power": 43.0, "assumed": True, "name": "Sakleshpur Town Mast"},
        {"id": 2, "lat": 12.9480, "lon": 75.7520, "height": 30.0, "power": 43.0, "assumed": True, "name": "Donigal Highway Tower"},
        {"id": 3, "lat": 12.9120, "lon": 75.8350, "height": 30.0, "power": 43.0, "assumed": True, "name": "Ballupete Junction Mast"},
    ]

    # Save /contracts/mock/towers.json
    with open("d:/taar/contracts/mock/towers.json", "w") as f:
        json.dump(towers_data, f, indent=2)
    print("Created d:/taar/contracts/mock/towers.json")

    # 2. Raw OpenCellID CSV: data/raw/opencellid_pilot.csv
    csv_lines = ["radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal"]
    for i, t in enumerate(towers_data):
        csv_lines.append(f"LTE,404,45,1024,{10000 + i},0,{t['lon']:.6f},{t['lat']:.6f},2500,120,1,1600000000,1650000000,-85")
    with open("d:/taar/data/raw/opencellid_pilot.csv", "w") as f:
        f.write("\n".join(csv_lines) + "\n")
    print("Created d:/taar/data/raw/opencellid_pilot.csv")

    # 3. Cells Base: 300m population grid
    # Generate ~400 cells covering 6 km x 6 km around the taluk
    cell_size = 300.0  # 300 m grid
    grid_radius = 4500.0  # 4.5 km extent
    x_steps = np.arange(center_x - grid_radius, center_x + grid_radius, cell_size)
    y_steps = np.arange(center_y - grid_radius, center_y + grid_radius, cell_size)

    np.random.seed(123)
    features_base = []
    cell_id = 0

    dem_path = "d:/taar/data/processed/dem_utm43n.tif"
    dem = DEMGrid.from_file(dem_path)

    cell_x_list = []
    cell_y_list = []

    for x in x_steps:
        for y in y_steps:
            # Distance from town center
            dist_center = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            # Simulated settlement probability / population
            # Higher population near center and roads, smaller in hills
            if dist_center < 1500:
                pop = int(np.random.poisson(85)) + 15
            elif dist_center < 3500:
                pop = int(np.random.poisson(30)) + 5
            else:
                pop = int(np.random.poisson(10)) + 3

            # Only retain cells with pop >= 5 as per rundown rule
            if pop < 5:
                continue

            # Polygon bounding box for 300m cell
            half = cell_size / 2.0
            p_sw = transformer_utm_to_wgs.transform(x - half, y - half)
            p_se = transformer_utm_to_wgs.transform(x + half, y - half)
            p_ne = transformer_utm_to_wgs.transform(x + half, y + half)
            p_nw = transformer_utm_to_wgs.transform(x - half, y + half)

            coords_polygon = [[
                [round(p_sw[0], 6), round(p_sw[1], 6)],
                [round(p_se[0], 6), round(p_se[1], 6)],
                [round(p_ne[0], 6), round(p_ne[1], 6)],
                [round(p_nw[0], 6), round(p_nw[1], 6)],
                [round(p_sw[0], 6), round(p_sw[1], 6)],
            ]]

            feat = {
                "type": "Feature",
                "id": cell_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coords_polygon,
                },
                "properties": {
                    "id": cell_id,
                    "pop": pop,
                }
            }
            features_base.append(feat)
            cell_x_list.append(x)
            cell_y_list.append(y)
            cell_id += 1

    cells_base_geojson = {
        "type": "FeatureCollection",
        "features": features_base,
    }

    with open("d:/taar/contracts/mock/cells_base.geojson", "w") as f:
        json.dump(cells_base_geojson, f)
    print(f"Created d:/taar/contracts/mock/cells_base.geojson with {len(features_base)} cells")

    # 4. Generate cells.geojson (with baseline_dbm and state)
    cfg = PropagationConfig()
    cells_coords = {
        "x": np.array(cell_x_list, dtype=np.float32),
        "y": np.array(cell_y_list, dtype=np.float32),
    }

    signals, min_dists_km = compute_signal(cells_coords, towers_data, dem, cfg)
    states = classify_state(signals, min_dists_km, cfg)

    features_full = []
    for i, feat in enumerate(features_base):
        feat_full = {
            "type": "Feature",
            "id": feat["id"],
            "geometry": feat["geometry"],
            "properties": {
                "id": feat["id"],
                "pop": feat["properties"]["pop"],
                "baseline_dbm": round(float(signals[i]), 1),
                "state": str(states[i]),
            }
        }
        features_full.append(feat_full)

    cells_full_geojson = {
        "type": "FeatureCollection",
        "features": features_full,
    }

    # Save to data/processed/cells.geojson and web/public/data/cells.geojson
    with open("d:/taar/data/processed/cells.geojson", "w") as f:
        json.dump(cells_full_geojson, f)
    print(f"Created d:/taar/data/processed/cells.geojson with {len(features_full)} features")

    with open("d:/taar/web/public/data/cells.geojson", "w") as f:
        json.dump(cells_full_geojson, f)
    print("Copied to d:/taar/web/public/data/cells.geojson for Frontend")


if __name__ == "__main__":
    generate_mock_data()
