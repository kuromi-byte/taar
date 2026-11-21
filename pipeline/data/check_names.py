"""
check_names.py – Dev B verification script

Reads clusters.json and towns.json and:
1. Validates approved meta.source container shape and verifies source is "WorldPop".
2. Verifies that every cluster's name_hint is "Near <town>" where <town> is a real
   entry in towns.json (prints any invalid ones).
3. Prints total number of clusters.
4. Prints how many clusters have empty candidate_ids (needs field survey).
"""
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CLUSTERS_PATHS = [
    os.path.join(REPO_ROOT, "pipeline", "data", "clusters.json"),
    os.path.join(REPO_ROOT, "web", "public", "data", "clusters.json"),
    os.path.join(REPO_ROOT, "contracts", "mock", "clusters.json"),
]

TOWNS_PATHS = [
    os.path.join(REPO_ROOT, "web", "public", "data", "towns.json"),
    os.path.join(REPO_ROOT, "web", "public", "data", "basemap", "towns.json"),
]


def load_first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f), p
    return None, None


def main():
    raw_clusters, cpath = load_first_existing(CLUSTERS_PATHS)
    towns, tpath = load_first_existing(TOWNS_PATHS)

    if raw_clusters is None:
        print(f"ERROR: clusters.json not found in {CLUSTERS_PATHS}", file=sys.stderr)
        sys.exit(1)
    if towns is None:
        print(f"ERROR: towns.json not found in {TOWNS_PATHS}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded clusters from : {cpath}")
    print(f"Loaded towns from    : {tpath}")

    # Validate approved container format and meta.source
    if isinstance(raw_clusters, dict) and "items" in raw_clusters:
        meta = raw_clusters.get("meta", {})
        source = meta.get("source")
        print(f"Cluster meta.source   : {source}")
        if source == "WorldPop":
            print("PASSED: Cluster meta.source is verified as 'WorldPop'.")
        else:
            print(f"WARNING: Cluster meta.source is '{source}', expected 'WorldPop'.")
        clusters = raw_clusters["items"]
    else:
        clusters = raw_clusters
        print("Note: Clusters loaded as direct array.")

    # Build valid town names set
    real_town_names = {t["name"].strip() for t in towns if "name" in t}
    valid_name_hints = {f"Near {name}" for name in real_town_names}

    print(f"\nReal towns in towns.json ({len(real_town_names)}):")
    for name in sorted(real_town_names):
        print(f"  - {name}")

    # Validate name_hint for every cluster
    invalid_clusters = []
    empty_candidates_count = 0

    for cl in clusters:
        cid = cl.get("id")
        name_hint = cl.get("name_hint", "")
        cand_ids = cl.get("candidate_ids", [])

        if not isinstance(cand_ids, list) or len(cand_ids) == 0:
            empty_candidates_count += 1

        if name_hint not in valid_name_hints:
            invalid_clusters.append((cid, name_hint))

    print("\n--- Name Hint Validation ---")
    if invalid_clusters:
        print(f"FAILED: Found {len(invalid_clusters)} cluster(s) with invalid name_hint:")
        for cid, hint in invalid_clusters:
            print(f"  Cluster {cid}: '{hint}' (not matching 'Near <town>' from towns.json)")
    else:
        print("PASSED: All clusters have valid name_hint matching 'Near <town>' from towns.json.")

    print("\n--- Summary Statistics ---")
    print(f"Total clusters                    : {len(clusters)}")
    print(f"Clusters with empty candidate_ids : {empty_candidates_count} (needs field survey)")
    print(f"Clusters with candidate_ids       : {len(clusters) - empty_candidates_count}")


if __name__ == "__main__":
    main()
