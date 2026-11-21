"""Unit tests for candidate ranking, clustering, and contract adherence."""
import json
import pytest
from pathlib import Path
from api.main import (
    app,
    load_baseline,
    recompute,
    health,
    get_config,
    get_towers,
    get_candidates,
    get_clusters,
    CandidateTower,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_candidates_and_clusters_contracts():
    """Verify candidates.json and clusters.json match required schemas and approved meta.source."""
    # Check pipeline/data (approved format) or web/public/data
    cand_path = REPO_ROOT / "pipeline" / "data" / "candidates.json"
    if not cand_path.exists():
        cand_path = REPO_ROOT / "web" / "public" / "data" / "candidates.json"

    clust_path = REPO_ROOT / "pipeline" / "data" / "clusters.json"
    if not clust_path.exists():
        clust_path = REPO_ROOT / "web" / "public" / "data" / "clusters.json"

    assert cand_path.exists(), f"candidates.json must exist at {cand_path}"
    assert clust_path.exists(), f"clusters.json must exist at {clust_path}"

    with open(cand_path, "r", encoding="utf-8") as f:
        cand_data = json.load(f)
    with open(clust_path, "r", encoding="utf-8") as f:
        clust_data = json.load(f)

    # Validate approved meta.source container shape
    if isinstance(cand_data, dict) and "items" in cand_data:
        assert "meta" in cand_data, "candidates.json container must contain 'meta'"
        assert cand_data["meta"]["source"] == "WorldPop", f"candidates source must be 'WorldPop', got {cand_data['meta'].get('source')}"
        candidates = cand_data["items"]
    else:
        candidates = cand_data

    if isinstance(clust_data, dict) and "items" in clust_data:
        assert "meta" in clust_data, "clusters.json container must contain 'meta'"
        assert clust_data["meta"]["source"] == "WorldPop", f"clusters source must be 'WorldPop', got {clust_data['meta'].get('source')}"
        clusters = clust_data["items"]
    else:
        clusters = clust_data

    assert len(candidates) > 0, "Should have ranked candidate sites"
    assert len(clusters) > 0, "Should have gap clusters"

    # 1. Verify candidate fields and feasibility filters
    for c in candidates:
        assert "id" in c
        assert "cluster_id" in c
        assert "lat" in c and 12.8 <= c["lat"] <= 13.1
        assert "lon" in c and 75.6 <= c["lon"] <= 75.95
        assert "added_pop" in c and c["added_pop"] >= 0
        assert "flags" in c
        flags = c["flags"]
        assert "road_km" in flags and flags["road_km"] <= 1.0, f"Candidate {c['id']} must be within 1 km of road"
        assert "slope_deg" in flags and flags["slope_deg"] < 15.0, f"Candidate {c['id']} slope must be < 15 deg"
        assert "backhaul" in flags
        assert "why" in c and len(c["why"]) > 10

    # 2. Verify clusters and ensure at least one cluster demonstrates 'needs field survey'
    needs_survey_found = False
    for cl in clusters:
        assert "id" in cl
        assert "cell_ids" in cl and len(cl["cell_ids"]) > 0
        assert "pop_in_gap" in cl and cl["pop_in_gap"] > 0
        assert "candidate_ids" in cl
        if len(cl["candidate_ids"]) == 0:
            needs_survey_found = True

    assert needs_survey_found, "At least one cluster must demonstrate the 'needs field survey' outcome (candidate_ids == [])"


def test_towers_meta_source():
    """Verify towers.json meta.source is OpenCellID."""
    towers_path = REPO_ROOT / "pipeline" / "data" / "towers.json"
    if towers_path.exists():
        with open(towers_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "items" in data:
            assert data.get("meta", {}).get("source") == "OpenCellID"
            assert len(data["items"]) > 0


def test_sources_metadata_sidecar():
    """Verify pipeline/data/sources.json has correct dataset mapping."""
    sources_path = REPO_ROOT / "pipeline" / "data" / "sources.json"
    if sources_path.exists():
        with open(sources_path, "r", encoding="utf-8") as f:
            sources = json.load(f)
        assert sources.get("towers", {}).get("source") == "OpenCellID"
        assert sources.get("cells", {}).get("source") == "WorldPop"
        assert sources.get("candidates", {}).get("source") == "WorldPop"
        assert sources.get("clusters", {}).get("source") == "WorldPop"


def test_api_endpoints():
    """Test API health, config, towers, candidates, clusters, and recompute functions."""
    load_baseline()

    # Health
    h = health()
    assert h["status"] == "ok"
    assert h["cells_loaded"] > 0

    # Config
    cfg = get_config()
    assert "pilot" in cfg

    # Towers (validates OpenCellID meta.source)
    towers = get_towers()
    if isinstance(towers, dict) and "items" in towers:
        assert towers.get("meta", {}).get("source") == "OpenCellID"
        tower_items = towers["items"]
    else:
        tower_items = towers
    assert len(tower_items) > 0

    # Candidates (validates WorldPop meta.source)
    cands = get_candidates()
    if isinstance(cands, dict) and "items" in cands:
        assert cands.get("meta", {}).get("source") == "WorldPop"
        cand_items = cands["items"]
    else:
        cand_items = cands
    assert len(cand_items) > 0

    # Clusters (validates WorldPop meta.source)
    clust = get_clusters()
    if isinstance(clust, dict) and "items" in clust:
        assert clust.get("meta", {}).get("source") == "WorldPop"
        clust_items = clust["items"]
    else:
        clust_items = clust
    assert len(clust_items) > 0

    # Recompute with tower payload
    cand_payload = [CandidateTower(lat=12.973, lon=75.785, height=30.0, power=43.0)]
    res = recompute(cand_payload)
    assert len(res.changed) > 0
    assert res.newly_covered_pop >= 0
    assert res.total_unserved_pop > 0
