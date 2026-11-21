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
    """Verify candidates.json and clusters.json match the required schemas."""
    cand_path = REPO_ROOT / "web" / "public" / "data" / "candidates.json"
    clust_path = REPO_ROOT / "web" / "public" / "data" / "clusters.json"

    assert cand_path.exists(), "candidates.json must exist in web/public/data"
    assert clust_path.exists(), "clusters.json must exist in web/public/data"

    with open(cand_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    with open(clust_path, "r", encoding="utf-8") as f:
        clusters = json.load(f)

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

    # Towers
    towers = get_towers()
    assert len(towers) > 0

    # Candidates
    cands = get_candidates()
    assert len(cands) > 0

    # Clusters
    clust = get_clusters()
    assert len(clust) > 0

    # Recompute with tower payload
    cand_payload = [CandidateTower(lat=12.973, lon=75.785, height=30.0, power=43.0)]
    res = recompute(cand_payload)
    assert len(res.changed) > 0
    assert res.newly_covered_pop >= 0
    assert res.total_unserved_pop > 0

