"""Tests verifying consistency between candidates.json added_pop and /recompute API endpoint.

Contract 6 Consistency Rule:
- For any cluster, the first candidate's added_pop must equal /recompute with that single tower.
- Candidate k's added_pop must equal /recompute(first k candidates) minus /recompute(first k-1 candidates).
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app, load_baseline

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    load_baseline()
    with TestClient(app) as c:
        yield c


def test_candidates_consistency_with_recompute(client):
    candidates_path = REPO_ROOT / "pipeline" / "data" / "candidates.json"
    clusters_path = REPO_ROOT / "pipeline" / "data" / "clusters.json"
    config_path = REPO_ROOT / "contracts" / "config.json"

    assert candidates_path.exists(), "pipeline/data/candidates.json must exist"
    assert clusters_path.exists(), "pipeline/data/clusters.json must exist"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    default_height = float(cfg["propagation"]["tower_height_m"])
    default_power = float(cfg["propagation"]["eirp_dbm"])

    with open(candidates_path, "r", encoding="utf-8") as f:
        cands_data = json.load(f)
    candidates_list = cands_data.get("items", cands_data) if isinstance(cands_data, dict) else cands_data
    cands_by_id = {c["id"]: c for c in candidates_list}

    with open(clusters_path, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)
    clusters_list = clusters_data.get("items", clusters_data) if isinstance(clusters_data, dict) else clusters_data

    tested_clusters = 0
    for cluster in clusters_list:
        cand_ids = cluster.get("candidate_ids", [])
        if not cand_ids:
            continue

        tested_clusters += 1
        cluster_cands = [cands_by_id[cid] for cid in cand_ids]

        cumulative_towers = []
        prev_cov = 0

        for k, cand in enumerate(cluster_cands):
            h = float(cand.get("height_m") or cand.get("height") or default_height)
            p = float(cand.get("power_dbm") or cand.get("power") or default_power)
            tower_spec = {
                "lat": float(cand["lat"]),
                "lon": float(cand["lon"]),
                "height_m": h,
                "power_dbm": p,
            }
            cumulative_towers.append(tower_spec)

            resp = client.post("/recompute", json={"towers": cumulative_towers})
            assert resp.status_code == 200, f"/recompute failed with status {resp.status_code}: {resp.text}"
            cum_cov = resp.json()["newly_covered_pop"]

            incremental_pop = cum_cov - prev_cov
            expected_added_pop = cand["added_pop"]

            if k == 0:
                assert expected_added_pop == cum_cov, (
                    f"Cluster {cluster['id']}: candidate 1 ({cand['id']}) added_pop {expected_added_pop} "
                    f"differs from standalone /recompute {cum_cov}"
                )
            else:
                assert expected_added_pop == incremental_pop, (
                    f"Cluster {cluster['id']}: candidate {k+1} ({cand['id']}) added_pop {expected_added_pop} "
                    f"differs from incremental /recompute ({cum_cov} - {prev_cov} = {incremental_pop})"
                )

            prev_cov = cum_cov

    print(f"Verified consistency for {tested_clusters} cluster(s) with candidates.")
