"""Core signal computation engine and cell state classification.

Shared and importable by both /pipeline and /api:
- compute_signal(cells, towers, dem, cfg)
- classify_state(signal_dbm, dist_to_nearest_tower_km, cfg)
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pyproj import Transformer
from .config import PropagationConfig
from .dem import DEMGrid
from .hata import compute_path_loss
from .shadow import PolarSweepEngine

# Fast cached transformer WGS84 -> UTM Zone 43N
_TRANSFORMER_4326_TO_32643 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


class SignalArray(np.ndarray):
    """NumPy float32 array subclass for RF signal dBm values.

    Preserves NaN for unserved/out-of-range cells, while safely treating NaN as -inf
    when evaluated with np.maximum against baseline cell signal in the API.
    """
    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if ufunc is np.maximum:
            cleaned = [
                np.where(np.isnan(np.asarray(x)), -np.inf, np.asarray(x))
                if isinstance(x, (np.ndarray, list)) else x
                for x in inputs
            ]
            res = getattr(ufunc, method)(*cleaned, **kwargs)
            return np.asarray(res).view(SignalArray)
        casted = [np.asarray(x) if isinstance(x, SignalArray) else x for x in inputs]
        res = getattr(ufunc, method)(*casted, **kwargs)
        if isinstance(res, np.ndarray):
            return res.view(SignalArray)
        return res


def parse_cells_coords(cells: Any) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], int]:
    """Extract UTM (x, y) coordinates and elevations from cells in various supported formats.

    Supported formats:
    - GeoDataFrame or DataFrame with 'x', 'y' or geometry
    - Dict with 'x', 'y' (and optional 'elev')
    - GeoJSON FeatureCollection dict
    """
    if isinstance(cells, dict):
        if "type" in cells and cells["type"] == "FeatureCollection":
            # GeoJSON FeatureCollection
            coords = []
            for feat in cells["features"]:
                geom = feat.get("geometry", {})
                gtype = geom.get("type")
                gcoords = geom.get("coordinates")
                if gtype == "Point":
                    coords.append((gcoords[0], gcoords[1]))
                elif gtype == "Polygon":
                    # Centroid of exterior ring
                    ring = np.array(gcoords[0])
                    coords.append((ring[:, 0].mean(), ring[:, 1].mean()))
                else:
                    coords.append((0.0, 0.0))
            coords_arr = np.array(coords, dtype=np.float64)
            # Assume GeoJSON coordinates are in EPSG:4326 (lon, lat)
            x_utm, y_utm = _TRANSFORMER_4326_TO_32643.transform(coords_arr[:, 0], coords_arr[:, 1])
            return x_utm.astype(np.float32), y_utm.astype(np.float32), None, len(coords)
        elif "x" in cells and "y" in cells:
            x_arr = np.atleast_1d(cells["x"]).astype(np.float32)
            y_arr = np.atleast_1d(cells["y"]).astype(np.float32)
            elev = np.atleast_1d(cells["elev"]).astype(np.float32) if "elev" in cells else None
            return x_arr, y_arr, elev, len(x_arr)

    # Check for pandas/geopandas DataFrame
    if hasattr(cells, "geometry"):
        # GeoDataFrame
        if hasattr(cells, "crs") and cells.crs and cells.crs.to_string() != "EPSG:32643":
            gdf_utm = cells.to_crs("EPSG:32643")
        else:
            gdf_utm = cells
        centroids = gdf_utm.geometry.centroid
        x_utm = centroids.x.to_numpy().astype(np.float32)
        y_utm = centroids.y.to_numpy().astype(np.float32)
        elev = cells["elev"].to_numpy().astype(np.float32) if "elev" in cells.columns else None
        return x_utm, y_utm, elev, len(x_utm)

    if hasattr(cells, "columns") and "x" in cells.columns and "y" in cells.columns:
        x_utm = cells["x"].to_numpy().astype(np.float32)
        y_utm = cells["y"].to_numpy().astype(np.float32)
        elev = cells["elev"].to_numpy().astype(np.float32) if "elev" in cells.columns else None
        return x_utm, y_utm, elev, len(x_utm)

    raise ValueError(f"Unsupported cells data structure: {type(cells)}")


def parse_towers(towers: Union[List[Dict[str, Any]], Any]) -> List[Dict[str, Any]]:
    """Standardize towers input to a list of dicts with UTM (x, y), height, and power."""
    out = []
    # If towers is DataFrame
    if hasattr(towers, "to_dict"):
        raw_list = towers.to_dict(orient="records")
    elif isinstance(towers, list):
        raw_list = towers
    else:
        raw_list = list(towers)

    for t in raw_list:
        tower = dict(t)
        # Check coordinates: UTM x/y or lat/lon
        if "x" in tower and "y" in tower:
            tx = float(tower["x"])
            ty = float(tower["y"])
        elif "lon" in tower and "lat" in tower:
            tx, ty = _TRANSFORMER_4326_TO_32643.transform(float(tower["lon"]), float(tower["lat"]))
        else:
            continue

        out.append({
            "id": tower.get("id"),
            "x": float(tx),
            "y": float(ty),
            "lat": float(tower.get("lat", 0.0)),
            "lon": float(tower.get("lon", 0.0)),
            "height": float(tower.get("height", 30.0)),
            "power": float(tower.get("power", 43.0)),
            "assumed": bool(tower.get("assumed", True)),
        })
    return out


def compute_signal(
    cells: Any,
    towers: Any,
    dem: DEMGrid,
    cfg: Optional[PropagationConfig] = None,
    polar_engine: Optional[PolarSweepEngine] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute best-server received signal power (dBm) for population cells across all towers.

    Args:
        cells: Population cells in UTM 43N (GeoDataFrame, dict, or GeoJSON).
        towers: List of existing or candidate towers.
        dem: DEMGrid elevation raster.
        cfg: PropagationConfig instance (defaults to standard settings).
        polar_engine: Optional pre-initialized PolarSweepEngine for maximum speed.

    Returns:
        Tuple of:
          - best_signal_dbm: float32 array of shape (N,) containing max received power in dBm.
          - min_dist_km: float32 array of shape (N,) containing distance in km to the nearest tower.
    """
    if cfg is None:
        cfg = PropagationConfig()
    if polar_engine is None:
        polar_engine = PolarSweepEngine(cfg)

    cell_x, cell_y, cell_elev, num_cells = parse_cells_coords(cells)
    if num_cells == 0:
        return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

    # Sample cell elevations if not provided
    if cell_elev is None:
        cell_elev = dem.sample_points(cell_x, cell_y)

    parsed_towers = parse_towers(towers)

    # Initialize best server power array to -infinity
    # and min distance array to +infinity
    best_signal = np.full(num_cells, -np.inf, dtype=np.float32)
    min_dist_m = np.full(num_cells, np.inf, dtype=np.float32)

    max_radius_m = cfg.max_radius_km * 1000.0

    for tw in parsed_towers:
        tw_x = tw["x"]
        tw_y = tw["y"]
        tw_h = tw["height"]
        tw_p = tw["power"]

        # Fast Euclidean distance to all cells
        dx = cell_x - tw_x
        dy = cell_y - tw_y
        dist = np.sqrt(dx * dx + dy * dy).astype(np.float32)

        # Track minimum distance to any tower
        np.minimum(min_dist_m, dist, out=min_dist_m)

        # Filter cells within propagation radius
        in_range_mask = dist <= max_radius_m
        if not np.any(in_range_mask):
            continue

        # Compute polar sweep for this tower
        sweep_angles, z_antenna = polar_engine.compute_tower_sweep(tw_x, tw_y, tw_h, dem)

        # Evaluate shadowing for cells in range
        sub_x = cell_x[in_range_mask]
        sub_y = cell_y[in_range_mask]
        sub_elev = cell_elev[in_range_mask]
        sub_dist = dist[in_range_mask]

        is_shadowed, _ = polar_engine.evaluate_shadows(
            tw_x, tw_y, sweep_angles, z_antenna, sub_x, sub_y, sub_elev, cfg.receiver_height_m
        )

        # Dispatch to correct path-loss model by frequency
        path_loss = compute_path_loss(
            distance_m=sub_dist,
            freq_mhz=cfg.freq_mhz,
            hb=tw_h,
            hm=cfg.receiver_height_m,
            min_dist_m=cfg.min_distance_m,
        )

        # Apply flat shadow penalty where obstructed
        penalty = np.where(is_shadowed, cfg.shadow_penalty_db, 0.0).astype(np.float32)

        # Received power: Prx = Ptx - PathLoss - ShadowPenalty
        p_rx = (tw_p - path_loss - penalty).astype(np.float32)

        # Update best server power (maximum across towers)
        best_signal[in_range_mask] = np.maximum(best_signal[in_range_mask], p_rx)

    # Floor for unreachable cells: set to NaN (no serving tower in range)
    best_signal[best_signal == -np.inf] = np.nan

    min_dist_km = (min_dist_m / 1000.0).astype(np.float32)
    return best_signal.view(SignalArray), min_dist_km


def classify_state(
    signal_dbm: Union[float, np.ndarray],
    dist_or_evidence: Union[float, np.ndarray, bool] = None,
    cfg: Optional[PropagationConfig] = None,
) -> Union[str, np.ndarray]:
    """Classify cell coverage state based on modeled signal, uncertain band, and unknown rule.

    States (lowercase, per contract):
      - 'unknown': no tower evidence (evidence False, dist > unknown_radius_km, or NaN signal)
      - 'covered': signal >= gap_threshold_dbm + uncertain_margin_db
      - 'gap': signal < gap_threshold_dbm - uncertain_margin_db
      - 'uncertain': within [gap_threshold - margin, gap_threshold + margin)

    Returns:
        Array of strings (or single string if input was scalar).
    """
    if cfg is None:
        cfg = PropagationConfig()

    sig = np.atleast_1d(signal_dbm)

    lower_bound = cfg.gap_threshold_dbm - cfg.uncertain_margin_db
    upper_bound = cfg.gap_threshold_dbm + cfg.uncertain_margin_db

    # Default state is uncertain
    states = np.full(sig.shape, "uncertain", dtype=object)

    # covered
    states[sig >= upper_bound] = "covered"

    # gap
    states[sig < lower_bound] = "gap"

    # unknown: no tower evidence (boolean False), distance beyond threshold, or NaN signal
    if dist_or_evidence is not None:
        doe = np.atleast_1d(dist_or_evidence)
        if doe.dtype == bool or isinstance(dist_or_evidence, (bool, np.bool_)):
            states[~doe] = "unknown"
        else:
            states[(doe > cfg.unknown_radius_km) | np.isinf(doe)] = "unknown"

    states[np.isnan(sig)] = "unknown"

    if isinstance(signal_dbm, (int, float)) and (dist_or_evidence is None or isinstance(dist_or_evidence, (int, float, bool))):
        return str(states[0])
    return states
