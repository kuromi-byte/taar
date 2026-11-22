"""Shared coverage computation function for candidate towers.

Contract 6:
- newly_covered_pop: population of cells whose baseline state was "gap" and whose new state is "covered" (>= threshold + band).
- total_unserved_pop: population of cells whose state remains "gap" (< threshold - band), strictly excluding "unknown" cells.
- changed: list of [cell_id, effective_dbm] for cells where effective signal increased by > 0.1 dB.

Used by both:
- pipeline/clustering_and_ranking.py
- api/main.py
"""
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union
from pathlib import Path
import json
import numpy as np

# Requirement 2: Classify states by calling Dev A's single state function from pipeline.model.
# If Dev A's function cannot be imported, fail with informative error.
try:
    from pipeline.model.engine import compute_signal, classify_state
    from pipeline.model.config import PropagationConfig
    from pipeline.model.dem import DEMGrid
except ImportError as err:
    raise ImportError(
        f"CRITICAL: Cannot import compute_signal or classify_state from pipeline.model: {err}"
    )


class CoverageResult(NamedTuple):
    newly_covered_pop: int
    total_unserved_pop: int
    changed: List[List[Union[int, float]]]


# Module-level cache for default baseline assets when called without explicit arrays
_CACHED_CONTEXT: Dict[str, Any] = {
    "cfg": None,
    "dem": None,
    "cells_json": None,
    "baseline_dbm": None,
    "baseline_states": None,
    "cell_pops": None,
    "cell_ids": None,
}


def _get_default_context() -> Dict[str, Any]:
    global _CACHED_CONTEXT
    if _CACHED_CONTEXT["cells_json"] is not None:
        return _CACHED_CONTEXT

    repo_root = Path(__file__).resolve().parents[2]
    cfg = PropagationConfig()
    cfg_file = repo_root / "contracts" / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            prop = cdata.get("propagation", {})
            cfg = PropagationConfig(
                freq_mhz=float(prop.get("frequency_mhz", 900.0)),
                receiver_height_m=float(prop.get("rx_height_m", 1.5)),
                default_tower_height_m=float(prop.get("tower_height_m", 30.0)),
                default_power_dbm=float(prop.get("eirp_dbm", 43.0)),
                shadow_penalty_db=float(prop.get("shadow_penalty_db", 15.0)),
                max_radius_km=float(prop.get("max_radius_km", 10.0)),
                ray_step_m=float(prop.get("ray_step_m", 30.0)),
                num_rays=int(prop.get("n_rays", 720)),
                gap_threshold_dbm=float(prop.get("gap_threshold_dbm", -100.0)),
                uncertain_margin_db=float(prop.get("uncertain_band_db", 6.0)),
            )
        except Exception:
            pass

    dem_path = repo_root / "data" / "processed" / "dem_utm43n.tif"
    if dem_path.exists():
        dem = DEMGrid.from_file(str(dem_path))
    else:
        dem = DEMGrid.create_synthetic()

    # Load cells.geojson
    cells_paths = [
        repo_root / "web" / "public" / "data" / "cells.geojson",
        repo_root / "data" / "processed" / "cells.geojson",
        repo_root / "contracts" / "mock" / "cells_base.geojson",
    ]
    cells_path = next((p for p in cells_paths if p.exists()), None)
    if not cells_path:
        raise FileNotFoundError("Could not find cells.geojson")

    with open(cells_path, "r", encoding="utf-8") as f:
        cells_json = json.load(f)

    features = cells_json["features"]
    cell_ids = np.array([f.get("id", f.get("properties", {}).get("id")) for f in features], dtype=np.int64)
    cell_pops = np.array([f.get("properties", {}).get("pop", 0) for f in features], dtype=np.int64)

    raw_dbm = [
        f.get("properties", {}).get("baseline_dbm")
        if f.get("properties", {}).get("baseline_dbm") is not None
        else -139.0
        for f in features
    ]
    clean_dbm = np.array(raw_dbm, dtype=np.float32)
    clean_dbm.flags.writeable = False

    raw_states = [f.get("properties", {}).get("state", "gap") for f in features]
    baseline_states = np.array([str(s).lower() for s in raw_states], dtype=object)

    _CACHED_CONTEXT = {
        "cfg": cfg,
        "dem": dem,
        "cells_json": cells_json,
        "baseline_dbm": clean_dbm,
        "baseline_states": baseline_states,
        "cell_pops": cell_pops,
        "cell_ids": cell_ids,
    }
    return _CACHED_CONTEXT


def _normalize_tower(t: Any, default_height: float, default_power: float) -> Dict[str, Any]:
    if isinstance(t, dict):
        lat = float(t["lat"])
        lon = float(t["lon"])
        h = t.get("height_m") if t.get("height_m") is not None else t.get("height")
        p = t.get("power_dbm") if t.get("power_dbm") is not None else t.get("power")
        height = float(h if h is not None else default_height)
        power = float(p if p is not None else default_power)
        tid = str(t.get("id", "cand"))
    else:
        lat = float(getattr(t, "lat"))
        lon = float(getattr(t, "lon"))
        h = getattr(t, "height_m", None) if getattr(t, "height_m", None) is not None else getattr(t, "height", None)
        p = getattr(t, "power_dbm", None) if getattr(t, "power_dbm", None) is not None else getattr(t, "power", None)
        height = float(h if h is not None else default_height)
        power = float(p if p is not None else default_power)
        tid = str(getattr(t, "id", "cand"))
    return {"id": tid, "lat": lat, "lon": lon, "height": height, "power": power}


def compute_coverage(
    towers: Union[List[Dict[str, Any]], List[Any]],
    dem: Optional[DEMGrid] = None,
    cfg: Optional[PropagationConfig] = None,
    cells_json: Optional[Dict[str, Any]] = None,
    baseline_dbm: Optional[np.ndarray] = None,
    baseline_states: Optional[np.ndarray] = None,
    cell_pops: Optional[np.ndarray] = None,
    cell_ids: Optional[np.ndarray] = None,
) -> CoverageResult:
    """Compute newly_covered_pop, total_unserved_pop, and changed cells for a candidate tower set.

    State classification is delegated directly to Dev A's classify_state from pipeline.model.
    """
    if (
        dem is None
        or cfg is None
        or cells_json is None
        or baseline_dbm is None
        or baseline_states is None
        or cell_pops is None
        or cell_ids is None
    ):
        ctx = _get_default_context()
        dem = dem if dem is not None else ctx["dem"]
        cfg = cfg if cfg is not None else ctx["cfg"]
        cells_json = cells_json if cells_json is not None else ctx["cells_json"]
        baseline_dbm = baseline_dbm if baseline_dbm is not None else ctx["baseline_dbm"]
        baseline_states = baseline_states if baseline_states is not None else ctx["baseline_states"]
        cell_pops = cell_pops if cell_pops is not None else ctx["cell_pops"]
        cell_ids = cell_ids if cell_ids is not None else ctx["cell_ids"]

    baseline_gap_mask = (baseline_states == "gap")

    # Empty candidate list case
    if not towers:
        total_unserved = int(np.sum(cell_pops[baseline_gap_mask]))
        return CoverageResult(newly_covered_pop=0, total_unserved_pop=total_unserved, changed=[])

    # Normalize tower specifications
    tower_specs = [_normalize_tower(t, cfg.default_tower_height_m, cfg.default_power_dbm) for t in towers]

    # Shared propagation engine
    cand_signal_arr, _ = compute_signal(cells_json, tower_specs, dem, cfg)
    cand_safe = np.where(np.isnan(cand_signal_arr), -np.inf, cand_signal_arr)

    # IMMUTABLE BASELINE: np.maximum creates a new array
    effective_dbm = np.maximum(baseline_dbm, cand_safe)

    # Requirement 2: Classify state using Dev A's classify_state
    new_states = classify_state(effective_dbm, cfg=cfg)

    # Contract 6: newly_covered_pop is baseline "gap" -> new "covered"
    newly_covered_mask = baseline_gap_mask & (new_states == "covered")
    newly_covered_pop = int(np.sum(cell_pops[newly_covered_mask]))

    # Contract 6: total_unserved_pop is cells remaining in state "gap" (< gap_cutoff)
    still_gap_mask = baseline_gap_mask & (new_states == "gap")
    total_unserved_pop = int(np.sum(cell_pops[still_gap_mask]))

    # Changed cells (> 0.1 dB increase over baseline)
    changed_mask = effective_dbm > (baseline_dbm + 0.1)
    changed_cells = [
        [int(cid), round(float(dbm), 1)]
        for cid, dbm in zip(cell_ids[changed_mask], effective_dbm[changed_mask])
    ]

    return CoverageResult(
        newly_covered_pop=newly_covered_pop,
        total_unserved_pop=total_unserved_pop,
        changed=changed_cells,
    )
