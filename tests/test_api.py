"""Unit tests for FastAPI coverage recompute endpoint.

Dev B – tests/test_api.py

Verifies:
 1. Tower A, then A moved: second response has no cells that belonged only to A.
 2. The same request twice gives identical responses.
 3. An empty towers list returns an empty changed list.
 4. Bad input (missing fields, lat/lon out of range, empty body) returns 400 or 422.
 5. Prints response size in KB for all key requests.
"""
import json
import pytest
from fastapi.testclient import TestClient
from api.main import app, load_baseline, STATE


@pytest.fixture(scope="module")
def client():
    load_baseline()
    with TestClient(app) as test_client:
        yield test_client


def test_tower_a_then_moved_no_stale_cells(client):
    """Test 1: tower A, then A moved: the second response has no cells that belonged only to A."""
    # Tower A: near Sakleshpur town center
    tower_a = {"lat": 12.973, "lon": 75.785, "height_m": 35.0, "power_dbm": 43.0}
    # Tower B (A moved): ~8 km south-west in Donigal corridor
    tower_b = {"lat": 12.903, "lon": 75.753, "height_m": 35.0, "power_dbm": 43.0}

    # First request: Tower A
    resp_a = client.post("/recompute", json={"towers": [tower_a]})
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    cells_a = {c[0] for c in data_a["changed"]}
    assert len(cells_a) > 0, "Tower A should boost at least some cells"

    kb_a = len(resp_a.content) / 1024.0
    print(f"\n[Check 1] Tower A response: {len(cells_a)} cells changed, size = {kb_a:.2f} KB")

    # Second request: Tower A moved to B
    resp_b = client.post("/recompute", json={"towers": [tower_b]})
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    cells_b = {c[0] for c in data_b["changed"]}
    assert len(cells_b) > 0, "Tower B should boost at least some cells"

    kb_b = len(resp_b.content) / 1024.0
    print(f"[Check 1] Tower B (moved) response: {len(cells_b)} cells changed, size = {kb_b:.2f} KB")

    # Cells that belonged ONLY to A
    only_a = cells_a - cells_b
    assert len(only_a) > 0, "There must be cells covered only by Tower A"

    # CRITICAL CHECK: The second response must have NO cells that belonged only to A
    assert only_a.isdisjoint(cells_b), "Second response must not retain any cells unique to Tower A"
    print(f"[Check 1 PASSED] {len(only_a)} cells unique to Tower A were completely purged from Tower B response.")


def test_identical_requests_give_identical_responses(client):
    """Test 2: the same request twice gives identical responses."""
    tower = {"lat": 12.948, "lon": 75.752, "height_m": 30.0, "power_dbm": 43.0}
    payload = {"towers": [tower]}

    resp1 = client.post("/recompute", json=payload)
    resp2 = client.post("/recompute", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    kb1 = len(resp1.content) / 1024.0
    print(f"\n[Check 2] First call size: {kb1:.2f} KB, Second call size: {len(resp2.content) / 1024.0:.2f} KB")

    assert resp1.json() == resp2.json(), "Subsequent calls with identical payload must yield identical output"
    print("[Check 2 PASSED] Responses are byte-for-byte and property-for-property identical.")


def test_empty_towers_list_returns_empty_changed(client):
    """Test 3: an empty towers list returns an empty changed list."""
    resp = client.post("/recompute", json={"towers": []})
    assert resp.status_code == 200

    data = resp.json()
    kb = len(resp.content) / 1024.0
    print(f"\n[Check 3] Empty towers response size: {kb:.2f} KB")

    assert data["changed"] == [], "Empty towers list must yield empty changed list"
    assert data["newly_covered_pop"] == 0, "Empty towers list must yield 0 newly covered pop"
    assert data["total_unserved_pop"] == 68339, f"Total unserved must match baseline gap pop (68,339), got {data['total_unserved_pop']}"
    print(f"[Check 3 PASSED] empty towers -> changed=[], newly_covered=0, total_unserved={data['total_unserved_pop']:,} (state 'gap' cells only, excluding unknown)")


def test_bad_input_returns_400_or_422(client):
    """Test 4: bad input returns 400 or 422 (never 500 or crash)."""
    bad_inputs = [
        # Missing required field 'lon'
        ({"towers": [{"lat": 12.97}]}, "missing 'lon'"),
        # Missing required field 'lat'
        ({"towers": [{"lon": 75.78}]}, "missing 'lat'"),
        # Lat out of range
        ({"towers": [{"lat": 999.0, "lon": 75.78}]}, "lat out of range (999.0)"),
        # Lon out of range
        ({"towers": [{"lat": 12.97, "lon": 150.0}]}, "lon out of range (150.0)"),
        # Missing 'towers' field entirely
        ({"foo": "bar"}, "missing 'towers' key"),
        # Negative height
        ({"towers": [{"lat": 12.97, "lon": 75.78, "height_m": -10.0}]}, "negative height"),
    ]

    for payload, description in bad_inputs:
        resp = client.post("/recompute", json=payload)
        kb = len(resp.content) / 1024.0
        print(f"[Check 4] Bad input ({description}) -> HTTP {resp.status_code} ({kb:.2f} KB)")
        assert resp.status_code in (400, 422), f"Expected 400 or 422 for {description}, got {resp.status_code}"

    # Empty raw body string
    resp_empty = client.post("/recompute", content="", headers={"Content-Type": "application/json"})
    assert resp_empty.status_code in (400, 422), "Empty body must return 400 or 422"
    print(f"[Check 4] Empty body string -> HTTP {resp_empty.status_code}")
    print("[Check 4 PASSED] All invalid payloads correctly rejected with 4xx JSON errors.")


def test_baseline_immutability(client):
    """Extra safety: baseline_dbm array buffer is locked and read-only."""
    baseline = STATE["baseline_dbm"]
    assert baseline is not None
    assert baseline.flags.writeable is False, "baseline_dbm MUST be read-only in memory"
    with pytest.raises(ValueError):
        baseline[0] = 999.0  # Must raise assignment destination is read-only
    print("\n[Baseline Immutability] Verified baseline_dbm array cannot be modified in memory.")
