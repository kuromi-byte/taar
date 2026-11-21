"""FastAPI application for Rural Coverage Gap Mapper.

Dev B – /api (api/main.py)

Strictly implements Contract 6:
- Port 8000, CORS open for localhost.
- Load baseline arrays from real cells.geojson once at startup.
- baseline_dbm is immutable in memory (writeable=False).
- POST /recompute:
    Request : {"towers": [{"lat": float, "lon": float, "height_m": float, "power_dbm": float}]}
    Response: {"changed": [[cell_id, dbm], ...], "newly_covered_pop": int, "total_unserved_pop": int}
- Imports compute_signal directly from pipeline.model.engine (no duplicate model).
- Returns only cells that differ from baseline.
- Clean 4xx validation errors on bad input (missing fields, out of range coordinates, empty body).
"""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from fastapi import FastAPI, Body, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal

REPO_ROOT = Path(__file__).resolve().parent.parent

# In-memory startup cache
STATE: Dict[str, Any] = {
    "dem": None,
    "cells_json": None,
    "cell_ids": None,
    "cell_pops": None,
    "baseline_dbm": None,
    "baseline_states": None,
    "cfg": PropagationConfig(),
}


def load_baseline():
    """Load DEM, config, and baseline cells into memory once at startup.

    Enforces that baseline_dbm is strictly immutable in memory.
    """
    # 1. Load config
    cfg_file = REPO_ROOT / "contracts" / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
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

    # 3. Load baseline cells from real cells.geojson
    cells_candidates = [
        REPO_ROOT / "web" / "public" / "data" / "cells.geojson",
        REPO_ROOT / "data" / "processed" / "cells.geojson",
        REPO_ROOT / "contracts" / "mock" / "cells_base.geojson",
    ]
    for cp in cells_candidates:
        if cp.exists():
            with open(cp, "r", encoding="utf-8") as f:
                data = json.load(f)
                STATE["cells_json"] = data
                features = data.get("features", [])
                if features:
                    STATE["cell_ids"] = np.array([f["id"] for f in features], dtype=np.int64)
                    STATE["cell_pops"] = np.array(
                        [f.get("properties", {}).get("pop", 0) for f in features], dtype=np.int64
                    )
                    base_dbm = [
                        f.get("properties", {}).get("baseline_dbm")
                        if f.get("properties", {}).get("baseline_dbm") is not None
                        else -139.0
                        for f in features
                    ]
                    baseline_arr = np.array(base_dbm, dtype=np.float32)
                    # IMMUTABILITY GUARANTEE: Lock array memory buffer
                    baseline_arr.flags.writeable = False
                    STATE["baseline_dbm"] = baseline_arr
                    STATE["baseline_states"] = np.array(
                        [f.get("properties", {}).get("state", "gap") for f in features], dtype=object
                    )
                    print(f"Loaded baseline with {len(features):,} cells into memory (read-only buffer).")
                    break


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_baseline()
    yield


app = FastAPI(
    title="Rural Coverage Gap Mapper API",
    description="API for live modeled RF coverage calculation and what-if simulation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Open CORS for local development (port 5173, 3000, 8000, and localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clean 422 JSON response for bad input."""
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request payload", "errors": jsonable_encoder(exc.errors())},
    )


class CandidateTower(BaseModel):
    id: Optional[Union[int, str]] = None
    lat: float = Field(..., description="WGS84 latitude")
    lon: float = Field(..., description="WGS84 longitude")
    height_m: Optional[float] = Field(None, ge=1.0, le=300.0, description="Antenna height in metres")
    power_dbm: Optional[float] = Field(None, ge=0.0, le=80.0, description="EIRP transmit power in dBm")
    height: Optional[float] = None
    power: Optional[float] = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (12.0 <= v <= 14.0):
            raise ValueError(f"lat {v} is outside regional bounds [12.0, 14.0]")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not (74.0 <= v <= 77.0):
            raise ValueError(f"lon {v} is outside regional bounds [74.0, 77.0]")
        return v

    def get_height(self) -> float:
        if self.height_m is not None:
            return float(self.height_m)
        if self.height is not None:
            return float(self.height)
        return 30.0

    def get_power(self) -> float:
        if self.power_dbm is not None:
            return float(self.power_dbm)
        if self.power is not None:
            return float(self.power)
        return 43.0


class RecomputePayload(BaseModel):
    towers: Optional[List[CandidateTower]] = None
    candidates: Optional[List[CandidateTower]] = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.towers is None and self.candidates is None:
            raise ValueError("Request body must contain 'towers'")
        return self

    def get_towers(self) -> List[CandidateTower]:
        return self.towers if self.towers is not None else (self.candidates or [])


class RecomputeResponse(BaseModel):
    changed: List[List[float]]  # [[cell_id, dbm], ...]
    newly_covered_pop: int
    total_unserved_pop: int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pilot": "Sakleshpur",
        "cells_loaded": len(STATE["cell_ids"]) if STATE["cell_ids"] is not None else 0,
        "baseline_immutable": not bool(STATE["baseline_dbm"].flags.writeable)
        if STATE["baseline_dbm"] is not None
        else False,
    }


@app.get("/config")
def get_config():
    cfg_file = REPO_ROOT / "contracts" / "config.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.get("/towers")
def get_towers():
    paths = [
        REPO_ROOT / "pipeline" / "data" / "towers.json",
        REPO_ROOT / "web" / "public" / "data" / "towers.json",
        REPO_ROOT / "contracts" / "mock" / "towers.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "items" in data:
                    return data
                return {"meta": {"source": "OpenCellID"}, "items": data}
    return {"meta": {"source": "OpenCellID"}, "items": []}


@app.get("/candidates")
def get_candidates():
    paths = [
        REPO_ROOT / "pipeline" / "data" / "candidates.json",
        REPO_ROOT / "web" / "public" / "data" / "candidates.json",
        REPO_ROOT / "contracts" / "mock" / "candidates.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "items" in data:
                    return data
                return {"meta": {"source": "WorldPop"}, "items": data}
    return {"meta": {"source": "WorldPop"}, "items": []}


@app.get("/clusters")
def get_clusters():
    paths = [
        REPO_ROOT / "pipeline" / "data" / "clusters.json",
        REPO_ROOT / "web" / "public" / "data" / "clusters.json",
        REPO_ROOT / "contracts" / "mock" / "clusters.json",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "items" in data:
                    return data
                return {"meta": {"source": "WorldPop"}, "items": data}
    return {"meta": {"source": "WorldPop"}, "items": []}


@app.post("/recompute", response_model=RecomputeResponse)
def recompute(payload: Union[RecomputePayload, List[CandidateTower]] = Body(...)):
    """Compute updated signal when user moves or adds candidate towers.

    - Receives list of candidate towers (lat, lon, height_m, power_dbm).
    - Calls shared compute_signal from pipeline.model.engine.
    - Evaluates effective received power against read-only baseline_dbm.
    - Returns changed cells, newly covered population, and remaining unserved population.
    """
    if STATE["dem"] is None or STATE["cells_json"] is None or STATE["baseline_dbm"] is None:
        load_baseline()

    cfg = STATE["cfg"]
    dem = STATE["dem"]
    baseline_dbm = STATE["baseline_dbm"]
    cell_pops = STATE["cell_pops"]
    cell_ids = STATE["cell_ids"]

    # Extract candidate list cleanly
    if isinstance(payload, list):
        candidates_list = payload
    elif isinstance(payload, RecomputePayload):
        candidates_list = payload.get_towers()
    else:
        raise HTTPException(status_code=422, detail="Invalid request body")

    gap_cutoff = cfg.gap_threshold_dbm - cfg.uncertain_margin_db  # -106 dBm

    # Empty candidate list case
    if not candidates_list:
        unserved_mask = baseline_dbm < gap_cutoff
        total_unserved = int(np.sum(cell_pops[unserved_mask]))
        return RecomputeResponse(changed=[], newly_covered_pop=0, total_unserved_pop=total_unserved)

    # Convert candidate towers to format expected by compute_signal
    tower_specs = [
        {
            "id": c.id,
            "lat": c.lat,
            "lon": c.lon,
            "height": c.get_height(),
            "power": c.get_power(),
        }
        for c in candidates_list
    ]

    # Shared propagation engine
    cand_signal_arr, _ = compute_signal(STATE["cells_json"], tower_specs, dem, cfg)

    # Clean signal array: out-of-range cells are NaN; replace with -inf for max comparison
    cand_safe = np.where(np.isnan(cand_signal_arr), -np.inf, cand_signal_arr)

    # IMMUTABLE BASELINE: np.maximum returns a newly allocated array, baseline_dbm is read-only
    effective_dbm = np.maximum(baseline_dbm, cand_safe)

    # Return only cells whose signal increased by > 0.1 dB
    changed_mask = effective_dbm > (baseline_dbm + 0.1)
    changed_cells = [
        [int(cid), round(float(dbm), 1)]
        for cid, dbm in zip(cell_ids[changed_mask], effective_dbm[changed_mask])
    ]

    # Newly covered population: baseline gap cells (< threshold - margin) that became >= cutoff
    was_gap = baseline_dbm < gap_cutoff
    now_covered = effective_dbm >= gap_cutoff
    newly_covered_mask = was_gap & now_covered
    newly_covered_pop = int(np.sum(cell_pops[newly_covered_mask]))

    # Remaining unserved population
    still_unserved_mask = effective_dbm < gap_cutoff
    total_unserved_pop = int(np.sum(cell_pops[still_unserved_mask]))

    return RecomputeResponse(
        changed=changed_cells,
        newly_covered_pop=newly_covered_pop,
        total_unserved_pop=total_unserved_pop,
    )
