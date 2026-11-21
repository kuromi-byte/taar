"""FastAPI application for Rural Coverage Gap Mapper.

Demonstrates that the exact same compute_signal and classify_state functions
authored in /pipeline/model are directly imported and served via the API.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import json
import os

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state

REPO_ROOT = Path(__file__).resolve().parent.parent

# In-memory startup cache
STATE = {
    "dem": None,
    "cells_json": None,
    "cell_ids": None,
    "cell_pops": None,
    "baseline_dbm": None,
    "baseline_states": None,
    "cfg": PropagationConfig(),
}


def load_baseline():
    """Load DEM, config, and baseline cells into memory once at startup."""
    # 1. Load config if available
    cfg_file = REPO_ROOT / "contracts" / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r") as f:
                cdata = json.load(f)
                prop = cdata.get("propagation", {})
                STATE["cfg"] = PropagationConfig(
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
        except Exception as e:
            print(f"Warning: could not parse config.json: {e}")

    # 2. Load DEM
    dem_path = REPO_ROOT / "data" / "processed" / "dem_utm43n.tif"
    if dem_path.exists():
        STATE["dem"] = DEMGrid.from_file(str(dem_path))
    else:
        STATE["dem"] = DEMGrid.create_synthetic()

    # 3. Load cells
    cells_candidates = [
        REPO_ROOT / "data" / "processed" / "cells.geojson",
        REPO_ROOT / "web" / "public" / "data" / "cells.geojson",
        REPO_ROOT / "contracts" / "mock" / "cells_base.geojson",
    ]
    for cp in cells_candidates:
        if cp.exists():
            with open(cp, "r") as f:
                data = json.load(f)
                STATE["cells_json"] = data
                features = data.get("features", [])
                if features:
                    STATE["cell_ids"] = np.array([f["id"] for f in features], dtype=np.int64)
                    STATE["cell_pops"] = np.array([f.get("properties", {}).get("pop", 10) for f in features], dtype=np.int64)
                    base_dbm = [f.get("properties", {}).get("baseline_dbm", -120.0) for f in features]
                    STATE["baseline_dbm"] = np.array([float(d if d is not None else -120.0) for d in base_dbm], dtype=np.float32)
                    STATE["baseline_states"] = np.array([f.get("properties", {}).get("state", "Likely gap") for f in features], dtype=object)
                    break


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_baseline()
    yield


app = FastAPI(title="Rural Coverage Gap Mapper API", version="1.0.0", lifespan=lifespan)

# Enable CORS for frontend local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CandidateTower(BaseModel):
    id: Optional[Union[int, str]] = None
    lat: float
    lon: float
    height: Optional[float] = None
    height_m: Optional[float] = None
    power: Optional[float] = None
    power_dbm: Optional[float] = None

    def get_height(self) -> float:
        if self.height is not None:
            return float(self.height)
        if self.height_m is not None:
            return float(self.height_m)
        return 30.0

    def get_power(self) -> float:
        if self.power is not None:
            return float(self.power)
        if self.power_dbm is not None:
            return float(self.power_dbm)
        return 43.0


class RecomputePayload(BaseModel):
    towers: Optional[List[CandidateTower]] = None
    candidates: Optional[List[CandidateTower]] = None


class RecomputeResponse(BaseModel):
    changed: List[List[float]]  # [[id, dbm], ...]
    newly_covered_pop: int
    total_unserved_pop: int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pilot": "Sakleshpur",
        "cells_loaded": len(STATE["cell_ids"]) if STATE["cell_ids"] is not None else 0,
    }


@app.get("/config")
def get_config():
    cfg_file = REPO_ROOT / "contracts" / "config.json"
    if cfg_file.exists():
        with open(cfg_file, "r") as f:
            return json.load(f)
    return {}


@app.get("/towers")
def get_towers():
    paths = [
        REPO_ROOT / "web" / "public" / "data" / "towers.json",
        REPO_ROOT / "contracts" / "mock" / "towers.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    return []


@app.get("/candidates")
def get_candidates():
    paths = [
        REPO_ROOT / "web" / "public" / "data" / "candidates.json",
        REPO_ROOT / "contracts" / "mock" / "candidates.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    return []


@app.get("/clusters")
def get_clusters():
    paths = [
        REPO_ROOT / "web" / "public" / "data" / "clusters.json",
        REPO_ROOT / "contracts" / "mock" / "clusters.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r") as f:
                return json.load(f)
    return []


@app.post("/recompute", response_model=RecomputeResponse)
def recompute(payload: Union[List[CandidateTower], RecomputePayload, Dict[str, Any]] = Body(...)):
    """Compute updated signal when user moves or adds candidate towers."""
    if STATE["dem"] is None or STATE["cells_json"] is None or STATE["baseline_dbm"] is None:
        load_baseline()

    cfg = STATE["cfg"]
    dem = STATE["dem"]
    baseline_dbm = STATE["baseline_dbm"]
    cell_pops = STATE["cell_pops"]
    cell_ids = STATE["cell_ids"]

    # Parse candidate towers from any accepted input shape
    candidates_list: List[CandidateTower] = []
    if isinstance(payload, list):
        candidates_list = [c if isinstance(c, CandidateTower) else CandidateTower(**c) for c in payload]
    elif isinstance(payload, RecomputePayload):
        raw_list = payload.towers or payload.candidates or []
        candidates_list = raw_list
    elif isinstance(payload, dict):
        raw_list = payload.get("towers") or payload.get("candidates") or []
        candidates_list = [CandidateTower(**c) for c in raw_list]

    if not candidates_list:
        # No candidate towers: no changes
        unserved_mask = baseline_dbm < (cfg.gap_threshold_dbm - cfg.uncertain_margin_db)
        total_unserved = int(np.sum(cell_pops[unserved_mask]))
        return RecomputeResponse(changed=[], newly_covered_pop=0, total_unserved_pop=total_unserved)

    # Convert candidate towers to dicts expected by compute_signal
    candidate_dicts = [
        {
            "id": c.id,
            "lat": c.lat,
            "lon": c.lon,
            "height": c.get_height(),
            "power": c.get_power(),
        }
        for c in candidates_list
    ]

    # Compute signal contribution of candidate towers using the exact shared compute_signal function
    cand_dbm, _ = compute_signal(STATE["cells_json"], candidate_dicts, dem, cfg)

    # Effective signal is max(baseline, candidate)
    effective_dbm = np.maximum(baseline_dbm, cand_dbm)

    # Find changed cells (where effective_dbm differs from baseline_dbm by > 0.1 dB)
    changed_mask = effective_dbm > baseline_dbm + 0.1
    changed_cells = []
    for cid, dbm in zip(cell_ids[changed_mask], effective_dbm[changed_mask]):
        changed_cells.append([int(cid), round(float(dbm), 1)])

    # Newly covered population calculation:
    # Baseline gap cells (< threshold - margin) that became covered (>= threshold - margin)
    was_gap = baseline_dbm < (cfg.gap_threshold_dbm - cfg.uncertain_margin_db)
    now_covered = effective_dbm >= (cfg.gap_threshold_dbm - cfg.uncertain_margin_db)
    newly_covered_mask = was_gap & now_covered
    newly_covered_pop = int(np.sum(cell_pops[newly_covered_mask]))

    still_gap = effective_dbm < (cfg.gap_threshold_dbm - cfg.uncertain_margin_db)
    total_unserved_pop = int(np.sum(cell_pops[still_gap]))

    return RecomputeResponse(
        changed=changed_cells,
        newly_covered_pop=newly_covered_pop,
        total_unserved_pop=total_unserved_pop,
    )
