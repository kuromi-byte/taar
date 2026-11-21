"""Generate evaluated baseline cells.geojson from cells_base.geojson using compute_signal."""
import json
import time
from pathlib import Path
import numpy as np

from pipeline.model.cfg_loader import load_config, get_repo_root
from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state

REPO_ROOT = get_repo_root()


def generate_baseline_cells():
    raw_cfg = load_config()
    prop_cfg = raw_cfg.get("propagation", {})
    cfg = PropagationConfig(
        freq_mhz=float(prop_cfg.get("frequency_mhz", 900.0)),
        receiver_height_m=float(prop_cfg.get("rx_height_m", 1.5)),
        default_tower_height_m=float(prop_cfg.get("tower_height_m", 30.0)),
        default_power_dbm=float(prop_cfg.get("eirp_dbm", 43.0)),
        shadow_penalty_db=float(prop_cfg.get("shadow_penalty_db", 15.0)),
        max_radius_km=float(prop_cfg.get("max_radius_km", 10.0)),
        ray_step_m=float(prop_cfg.get("ray_step_m", 30.0)),
        num_rays=int(prop_cfg.get("n_rays", 720)),
        gap_threshold_dbm=float(prop_cfg.get("gap_threshold_dbm", -100.0)),
        uncertain_margin_db=float(prop_cfg.get("uncertain_band_db", 6.0)),
    )

    cells_base_path = REPO_ROOT / "data" / "processed" / "cells_base.geojson"
    towers_path = REPO_ROOT / "contracts" / "mock" / "towers.json"
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    out_path = REPO_ROOT / "data" / "processed" / "cells.geojson"

    print(f"Reading base cells: {cells_base_path}")
    with open(cells_base_path, "r", encoding="utf-8") as f:
        cells_base = json.load(f)

    print(f"Reading towers: {towers_path}")
    with open(towers_path, "r", encoding="utf-8") as f:
        towers = json.load(f)

    print(f"Reading DEM: {dem_path}")
    dem = DEMGrid.from_file(str(dem_path))

    t0 = time.time()
    signals, min_dists_km = compute_signal(cells_base, towers, dem, cfg)
    states = classify_state(signals, min_dists_km, cfg)
    elapsed = time.time() - t0

    print(f"Computed signal for {len(signals)} cells in {elapsed:.3f} s")

    features = []
    base_features = cells_base.get("features", [])
    for idx, feat in enumerate(base_features):
        props = dict(feat.get("properties", {}))
        props["baseline_dbm"] = round(float(signals[idx]), 1)
        props["state"] = str(states[idx])
        features.append({
            "type": "Feature",
            "id": feat["id"],
            "geometry": feat["geometry"],
            "properties": props,
        })

    meta = dict(cells_base.get("meta", {}))
    meta["signal_computation_s"] = round(elapsed, 3)

    cells_out = {
        "type": "FeatureCollection",
        "meta": meta,
        "features": features,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cells_out, f)

    print(f"Saved {len(features)} evaluated cells to {out_path}")
    return cells_out


if __name__ == "__main__":
    generate_baseline_cells()
