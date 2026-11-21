"""Task 0 — DEM coverage check, download missing tiles, merge, reproject, clip.

Reads pilot bbox exclusively from contracts/config.json.
Never hard-codes coordinates or tile names.
Run from repo root:  python -m pipeline.model.task0_dem_build
"""
from __future__ import annotations
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio import windows as rio_windows
from pyproj import Transformer

REPO_ROOT = Path(__file__).resolve().parents[2]  # d:/taar
CONFIG_PATH = REPO_ROOT / "contracts" / "config.json"

# Copernicus GLO-30 public S3 URL template
COPERNICUS_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{lat_tag}_00_{lon_tag}_00_DEM/"
    "Copernicus_DSM_COG_10_{lat_tag}_00_{lon_tag}_00_DEM.tif"
)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"STOP: {CONFIG_PATH} not found — cannot derive pilot area.")
    return json.loads(CONFIG_PATH.read_text())


def required_tiles(bbox: dict, buffer_km: float) -> list[tuple[int, int]]:
    """Return list of (lat_floor, lon_floor) for all 1°x1° tiles needed."""
    DEG_PER_KM = 1.0 / 111.0
    buf_deg = buffer_km * DEG_PER_KM
    min_lat = bbox["min_lat"] - buf_deg
    max_lat = bbox["max_lat"] + buf_deg
    min_lon = bbox["min_lon"] - buf_deg
    max_lon = bbox["max_lon"] + buf_deg

    tiles = []
    lat = int(np.floor(min_lat))
    while lat < int(np.ceil(max_lat)):
        lon = int(np.floor(min_lon))
        while lon < int(np.ceil(max_lon)):
            tiles.append((lat, lon))
            lon += 1
        lat += 1
    return tiles


def tile_url(lat: int, lon: int) -> str:
    lat_tag = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
    lon_tag = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
    return COPERNICUS_URL.format(lat_tag=lat_tag, lon_tag=lon_tag)


def tile_path(raw_dir: Path, lat: int, lon: int) -> Path:
    lat_tag = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
    lon_tag = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
    return raw_dir / f"copernicus_{lat_tag}{lon_tag}.tif"


def download_tile(url: str, dest: Path) -> None:
    """Download tile using curl (subprocess) since urllib SSL may be blocked."""
    import subprocess
    print(f"  Downloading {dest.name} ...")
    result = subprocess.run(
        ["curl.exe", "-L", "-s", "-o", str(dest), url],
        capture_output=True,
    )
    if result.returncode != 0:
        sys.exit(f"STOP: curl failed for {url}: {result.stderr.decode()}")
    print(f"  → {dest.name}  {dest.stat().st_size // 1024} KB")


def build_dem(cfg: dict) -> None:
    bbox = cfg["pilot"]["bbox_wgs84"]
    buf_km = cfg["pilot"]["terrain_buffer_km"]
    dst_crs = cfg["pilot"]["crs_internal"]
    raw_dir = REPO_ROOT / cfg["paths"]["dem_raw_dir"]
    out_path = REPO_ROOT / cfg["paths"]["dem_processed"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1 — Identify required tiles
    tiles = required_tiles(bbox, buf_km)
    print(f"\n[Task 0] Pilot bbox: {bbox}")
    print(f"Buffer: {buf_km} km → extended box needs tiles: {tiles}")

    # 2 — Download missing tiles
    tile_files = []
    for lat, lon in tiles:
        path = tile_path(raw_dir, lat, lon)
        if path.exists():
            print(f"  {path.name}  already present ({path.stat().st_size // 1024} KB)")
        else:
            url = tile_url(lat, lon)
            print(f"  {path.name} missing → {url}")
            download_tile(url, path)
        tile_files.append(path)

    # 3 — Merge all tiles in WGS84, then reproject to UTM43N
    print("\n[Task 0] Merging tiles ...")
    src_datasets = [rasterio.open(p) for p in tile_files]
    merged, merge_transform = merge(src_datasets)
    src_crs = src_datasets[0].crs
    src_nodata = src_datasets[0].nodata
    for ds in src_datasets:
        ds.close()

    print(f"  Merged shape: {merged.shape}  (1, rows, cols)")

    # 4 — Reproject merged raster to UTM43N at 30 m resolution (bilinear)
    DEG_PER_KM = 1.0 / 111.0
    buf_deg = buf_km * DEG_PER_KM
    clip_min_lon = bbox["min_lon"] - buf_deg
    clip_max_lon = bbox["max_lon"] + buf_deg
    clip_min_lat = bbox["min_lat"] - buf_deg
    clip_max_lat = bbox["max_lat"] + buf_deg

    # Compute UTM extent from lat/lon clip box (never typed by hand)
    transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
    corners_lon = [clip_min_lon, clip_max_lon, clip_min_lon, clip_max_lon]
    corners_lat = [clip_min_lat, clip_min_lat, clip_max_lat, clip_max_lat]
    corners_x, corners_y = transformer.transform(corners_lon, corners_lat)
    utm_min_x, utm_max_x = min(corners_x), max(corners_x)
    utm_min_y, utm_max_y = min(corners_y), max(corners_y)

    print(f"  UTM clip box (derived): X [{utm_min_x:.0f}, {utm_max_x:.0f}]  Y [{utm_min_y:.0f}, {utm_max_y:.0f}]")

    # Write merged WGS84 raster to temp mem-file, then reproject
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds as tfm_from_bounds

    merged_meta = {
        "driver": "GTiff",
        "height": merged.shape[1],
        "width": merged.shape[2],
        "count": 1,
        "dtype": "float32",
        "crs": src_crs,
        "transform": merge_transform,
        "nodata": src_nodata if src_nodata is not None else -9999.0,
    }

    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs, dst_crs,
        merged.shape[2], merged.shape[1],
        left=clip_min_lon, bottom=clip_min_lat,
        right=clip_max_lon, top=clip_max_lat,
        resolution=30.0,
    )

    dst_meta = {
        "driver": "GTiff",
        "height": dst_height,
        "width": dst_width,
        "count": 1,
        "dtype": "float32",
        "crs": dst_crs,
        "transform": dst_transform,
        "nodata": -9999.0,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    print(f"\n[Task 0] Reprojecting to {dst_crs} @ 30 m ...")
    with MemoryFile() as mem:
        with mem.open(**merged_meta) as src:
            src.write(merged[0].astype("float32"), 1)
            with rasterio.open(out_path, "w", **dst_meta) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=merge_transform,
                    src_crs=src_crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=src_nodata if src_nodata is not None else -9999.0,
                    dst_nodata=-9999.0,
                )

    # 5 — Verify: nodata inside pilot bbox (not buffer)
    print(f"\n[Task 0] Verifying output ...")
    with rasterio.open(out_path) as ds:
        print(f"  Output path : {out_path}")
        print(f"  Shape       : {ds.shape}  (rows, cols)")
        print(f"  Bounds(UTM) : {ds.bounds}")
        print(f"  Resolution  : {ds.res}")
        print(f"  CRS         : {ds.crs}")

        data = ds.read(1)
        total_nodata = int(np.sum(data == ds.nodata))

        # Pilot bbox (without buffer) window
        pilot_corners_x, pilot_corners_y = transformer.transform(
            [bbox["min_lon"], bbox["max_lon"], bbox["min_lon"], bbox["max_lon"]],
            [bbox["min_lat"], bbox["min_lat"], bbox["max_lat"], bbox["max_lat"]],
        )
        pilot_win = rio_windows.from_bounds(
            min(pilot_corners_x), min(pilot_corners_y),
            max(pilot_corners_x), max(pilot_corners_y),
            ds.transform,
        )
        pilot_win = pilot_win.round_offsets().round_lengths()
        pilot_data = ds.read(1, window=pilot_win)
        pilot_nodata = int(np.sum(pilot_data == ds.nodata))

        print(f"\n  Total nodata in full raster : {total_nodata}")
        print(f"  Nodata INSIDE pilot bbox    : {pilot_nodata}")

        if pilot_nodata > 0:
            print("  ⚠️  WARNING: nodata pixels inside pilot bbox — check tile coverage!")
        else:
            print("  ✅  No nodata inside pilot bbox.")

        print(f"\n  Elevation min: {data[data != ds.nodata].min():.1f} m")
        print(f"  Elevation max: {data[data != ds.nodata].max():.1f} m")

    print("\n[Task 0] DONE ✅")


if __name__ == "__main__":
    cfg = load_config()
    build_dem(cfg)
