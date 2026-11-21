"""
inspect_cells.py  –  Dev B audit tool (read-only, no data files modified)

Reads web/public/data/cells.geojson and prints:
  - cell count
  - min / max id
  - total pop
  - missing + null counts for every tracked field
  - count of each state value
  - total pop in "gap" state
  - how many "gap" cells have a non-null baseline_dbm
"""

import json
import os
import sys

CELLS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "web", "public", "data", "cells.geojson"
)

TRACKED_FIELDS = [
    "pop", "cx", "cy",
    "elev_m", "slope_deg", "road_km",
    "tower_evidence", "baseline_dbm", "state",
]


def main():
    path = os.path.abspath(CELLS_PATH)
    if not os.path.exists(path):
        print(f"ERROR: cells.geojson not found at {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as fh:
        fc = json.load(fh)

    features = fc.get("features", [])
    n = len(features)
    print(f"Cell count           : {n}")

    if n == 0:
        print("No features – nothing else to report.")
        return

    # --- id stats ---
    ids = []
    for f in features:
        fid = f.get("properties", {}).get("id")
        if fid is not None:
            ids.append(fid)

    if ids:
        print(f"Min id               : {min(ids)}")
        print(f"Max id               : {max(ids)}")
    else:
        print("Min id               : (no id field found)")
        print("Max id               : (no id field found)")

    # --- total pop ---
    total_pop = 0
    for f in features:
        p = f.get("properties", {}).get("pop")
        if isinstance(p, (int, float)):
            total_pop += p
    print(f"Total pop            : {total_pop:,.0f}")

    # --- missing / null per field ---
    print()
    print(f"{'Field':<20} {'Missing':>10} {'Null':>10}   (of {n} cells)")
    print("-" * 50)
    for field in TRACKED_FIELDS:
        missing = 0
        null = 0
        for f in features:
            props = f.get("properties", {})
            if field not in props:
                missing += 1
            elif props[field] is None:
                null += 1
        print(f"{field:<20} {missing:>10} {null:>10}")

    # --- state breakdown ---
    state_counts: dict = {}
    for f in features:
        s = f.get("properties", {}).get("state")
        state_counts[s] = state_counts.get(s, 0) + 1

    print()
    print("State breakdown:")
    for state, cnt in sorted(state_counts.items(), key=lambda x: -(x[1])):
        pct = cnt / n * 100
        print(f"  {str(state):<15} : {cnt:>6}  ({pct:.1f}%)")

    # --- gap stats ---
    gap_pop = 0
    gap_with_dbm = 0
    for f in features:
        props = f.get("properties", {})
        if props.get("state") == "gap":
            p = props.get("pop")
            if isinstance(p, (int, float)):
                gap_pop += p
            if props.get("baseline_dbm") is not None:
                gap_with_dbm += 1

    gap_total = state_counts.get("gap", 0)
    print()
    print(f"Gap cells total pop  : {gap_pop:,.0f}")
    print(f"Gap cells with non-null baseline_dbm: {gap_with_dbm} / {gap_total}")

    # --- meta block (if present) ---
    meta = fc.get("meta")
    if meta:
        print()
        print("Top-level meta:")
        for k, v in meta.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
