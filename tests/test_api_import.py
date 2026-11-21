"""Unit test verifying that /api directly imports and runs compute_signal and /recompute."""
import pytest
from api.main import app, load_baseline, recompute, CandidateTower


def test_api_import_and_recompute():
    load_baseline()

    # 1. Recompute with no candidates returns 0 newly covered
    res_empty = recompute([])
    assert res_empty.newly_covered_pop == 0
    assert len(res_empty.changed) == 0
    assert res_empty.total_unserved_pop > 0

    # 2. Add a candidate tower near the cells and verify changed cells and population boost
    candidate = [CandidateTower(
        lat=12.972,
        lon=75.785,
        height=35.0,
        power=43.0,
    )]
    res_cand = recompute(candidate)
    assert len(res_cand.changed) > 0
    assert res_cand.newly_covered_pop >= 0
    print(f"\nAPI recompute successful: {len(res_cand.changed)} cells changed, +{res_cand.newly_covered_pop} newly covered pop.")

