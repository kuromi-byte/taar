"""FastAPI application for Rural Coverage Gap Mapper.

Demonstrates that the exact same compute_signal and classify_state functions
authored in /pipeline/model are directly imported and served via the API.
"""
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import json
import os

from pipeline.model.config import PropagationConfig
from pipeline.model.dem import DEMGrid
from pipeline.model.engine import compute_signal, classify_state

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
    """Load DEM and baseline cells into memory once at startup."""
    dem_path = "d:/taar/data/processed/dem_utm43n.tif"
    if os.path.exists(dem_path):
        STATE["dem"] = DEMGrid.from_file(dem_path)
    else:
        STATE["dem"] = DEMGrid.create_synthetic()

    cells_path = "d:/taar/data/processed/cells.geojson"
    if os.path.exists(cells_path):
        with open(cells_path, "r") as f:
            data = json.load(f)
            STATE["cells_json"] = data
            features = data["features"]
            STATE["cell_ids"] = np.array([f["id"] for f in features], dtype=np.int64)
            STATE["cell_pops"] = np.array([f["properties"]["pop"] for f in features], dtype=np.int64)
            STATE["baseline_dbm"] = np.array([f["properties"]["baseline_dbm"] for f in features], dtype=np.float32)
            STATE["baseline_states"] = np.array([f["properties"]["state"] for f in features], dtype=object)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_baseline()
    yield


app = FastAPI(title="Rural Coverage Gap Mapper API", version="1.0.0", lifespan=lifespan)


class CandidateTower(BaseModel):
    id: Optional[int] = None
    lat: float
    lon: float
    height: float = 30.0
    power: float = 43.0


class RecomputeResponse(BaseModel):
    changed: List[List[float]]  # [[id, dbm], ...]
    newly_covered_pop: int
    total_unserved_pop: int


@app.get("/health")
def health():
    return {"status": "ok", "cells_loaded": len(STATE["cell_ids"]) if STATE["cell_ids"] is not None else 0}


@app.post("/recompute", response_model=RecomputeResponse)
def recompute(candidates: List[CandidateTower]):
    """Compute updated signal when user moves or adds candidate towers."""
    if STATE["dem"] is None or STATE["cells_json"] is None:
        load_baseline()

    cfg = STATE["cfg"]
    dem = STATE["dem"]
    baseline_dbm = STATE["baseline_dbm"]
    cell_pops = STATE["cell_pops"]
    cell_ids = STATE["cell_ids"]

    if not candidates:
        # No candidate towers: no changes
        unserved_mask = baseline_dbm < (cfg.gap_threshold_dbm - cfg.uncertain_margin_db)
        total_unserved = int(np.sum(cell_pops[unserved_mask]))
        return RecomputeResponse(changed=[], newly_covered_pop=0, total_unserved_pop=total_unserved)

    # Compute signal contribution of candidate towers using the exact shared compute_signal function
    candidate_dicts = [c.model_dump() for c in candidates]
    cand_dbm, _ = compute_signal(STATE["cells_json"], candidate_dicts, dem, cfg)

    # Effective signal is max(baseline, candidate)
    effective_dbm = np.maximum(baseline_dbm, cand_dbm)

    # Find changed cells (where effective_dbm differs from baseline_dbm)
    changed_mask = effective_dbm > baseline_dbm + 0.1
    changed_cells = []
    for cid, dbm in zip(cell_ids[changed_mask], effective_dbm[changed_mask]):
        changed_cells.append([int(cid), round(float(dbm), 1)])

    # Newly covered population calculation:
    # Baseline gap cells that became covered (>= gap_threshold - margin)
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
