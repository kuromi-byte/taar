"""Fetch real OSM communication towers/masts in the pilot bounding box and buffer via Overpass."""
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from pyproj import Transformer

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "contracts" / "config.json"

ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def fetch_osm_towers():
    cfg = json.loads(CONFIG_PATH.read_text())
    bbox = cfg["pilot"]["bbox_wgs84"]
    buf_km = cfg["pilot"]["terrain_buffer_km"]
    deg_per_km = 1.0 / 111.0
    buf_deg = buf_km * deg_per_km

    # Core box
    c_min_lat, c_max_lat = bbox["min_lat"], bbox["max_lat"]
    c_min_lon, c_max_lon = bbox["min_lon"], bbox["max_lon"]

    # Buffered box
    b_min_lat, b_max_lat = c_min_lat - buf_deg, c_max_lat + buf_deg
    b_min_lon, b_max_lon = c_min_lon - buf_deg, c_max_lon + buf_deg

    print(f"Core Box:     Lat [{c_min_lat}, {c_max_lat}], Lon [{c_min_lon}, {c_max_lon}]")
    print(f"Buffered Box: Lat [{b_min_lat:.3f}, {b_max_lat:.3f}], Lon [{b_min_lon:.3f}, {b_max_lon:.3f}]")

    query = f"""[out:json][timeout:35];
(
  node["man_made"="mast"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
  node["tower:type"="communication"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
  node["telecom"="antenna"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
  node["communication:mobile_phone"="yes"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
  way["man_made"="mast"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
  way["tower:type"="communication"]({b_min_lat:.4f},{b_min_lon:.4f},{b_max_lat:.4f},{b_max_lon:.4f});
);
out center tags;
"""

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    headers = {"User-Agent": "GapToBrief-DevA/1.0 (hackathon tool; contact: dev-a@taar.local)"}

    elements = []
    for ep in ENDPOINTS:
        print(f"Attempting query on {ep} ...")
        try:
            req = urllib.request.Request(ep, data=data, headers=headers)
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=40, context=ctx) as resp:
                text = resp.read().decode("utf-8")
                res = json.loads(text)
                elements = res.get("elements", [])
                print(f"Success from {ep}: retrieved {len(elements)} elements.")
                # Save raw response
                (REPO_ROOT / "data" / "raw" / "osm_towers_raw.json").write_text(text, encoding="utf-8")
                break
        except Exception as e:
            print(f"  Failed {ep}: {e}")

    # Process elements into structured records
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)

    towers = []
    core_count = 0
    buffer_only_count = 0
    radio_counts = {}

    for elem in elements:
        tags = elem.get("tags", {})
        # Coordinate
        if elem.get("type") == "node":
            lat = elem.get("lat")
            lon = elem.get("lon")
        else:
            center = elem.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        in_core = (c_min_lat <= lat <= c_max_lat) and (c_min_lon <= lon <= c_max_lon)
        if in_core:
            core_count += 1
        else:
            buffer_only_count += 1

        # Identify radio or tech if specified, else generic/unknown
        radio = tags.get("communication:mobile_phone") or tags.get("radio") or tags.get("tower:type") or "telecom"
        radio_counts[radio] = radio_counts.get(radio, 0) + 1

        # Height
        h_str = tags.get("height", "30.0")
        try:
            height_m = float(str(h_str).replace("m", "").strip())
        except ValueError:
            height_m = 30.0

        x_utm, y_utm = transformer.transform(lon, lat)

        towers.append({
            "id": elem.get("id"),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "x": round(x_utm, 1),
            "y": round(y_utm, 1),
            "height_m": height_m,
            "power_dbm": 43.0,
            "assumed": True,
            "in_core_bbox": in_core,
            "radio": radio,
            "tags": tags,
            "source": "OpenStreetMap Overpass (sparse fallback)",
        })

    print("\n--- TOWER REPORT ---")
    print(f"Total Towers Found:           {len(towers)}")
    print(f"Towers Inside Core Bbox:      {core_count}")
    print(f"Towers in 10 km Buffer Only:  {buffer_only_count}")
    print(f"Total in Buffered Area:       {core_count + buffer_only_count}")
    print(f"Radio/Type Breakdown:         {radio_counts}")

    if core_count < 10:
        print("WARNING: Tower count inside pilot box is VERY LOW. Labeling clearly as sparse fallback!")

    # Save to data/raw/osm_towers_processed.json
    out_file = REPO_ROOT / "data" / "raw" / "osm_towers_processed.json"
    out_file.write_text(json.dumps(towers, indent=2), encoding="utf-8")
    print(f"Saved processed towers to {out_file}")

    return towers, core_count, buffer_only_count, radio_counts


if __name__ == "__main__":
    fetch_osm_towers()
