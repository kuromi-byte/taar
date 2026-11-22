"""DEM loading, resampling, and spatial indexing in UTM Zone 43N."""
from typing import Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.transform import Affine


class DEMGrid:
    """In-memory 2D Digital Elevation Model raster in UTM coordinates."""

    def __init__(
        self,
        data: np.ndarray,
        transform: Affine,
        crs: str = "EPSG:32643",
        nodata: float = -9999.0,
    ):
        """Initialize DEMGrid.

        Args:
            data: 2D numpy array of elevations (height x width).
            transform: Affine transform mapping pixel (col, row) to UTM (x, y).
            crs: Coordinate reference system (default EPSG:32643).
            nodata: Sentinel value for missing data.
        """
        self.data = data.astype(np.float32)
        self.transform = transform
        self.inv_transform = ~transform
        self.crs = crs
        self.nodata = nodata
        self.height, self.width = data.shape

        # Cell size (assuming square pixels in UTM)
        self.res_x = float(transform.a)
        self.res_y = float(-transform.e)

        # Bounding box in UTM coordinates
        self.left = float(transform.c)
        self.top = float(transform.f)
        self.right = self.left + self.width * self.res_x
        self.bottom = self.top - self.height * self.res_y

    @classmethod
    def from_file(
        cls,
        filepath: str,
        crop_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> "DEMGrid":
        """Load DEM from a GeoTIFF raster file, optionally cropped to (min_x, min_y, max_x, max_y)."""
        with rasterio.open(filepath) as src:
            if crop_bounds is not None:
                min_x, min_y, max_x, max_y = crop_bounds
                # Window from bounds
                window = rasterio.windows.from_bounds(min_x, min_y, max_x, max_y, src.transform)
                window = window.round_offsets().round_lengths()
                data = src.read(1, window=window)
                transform = rasterio.windows.transform(window, src.transform)
            else:
                data = src.read(1)
                transform = src.transform

            nodata = src.nodata if src.nodata is not None else -9999.0
            return cls(data, transform, str(src.crs), nodata)

    @classmethod
    def create_synthetic(
        cls,
        center_x: float = 580000.0,
        center_y: float = 1430000.0,
        width_m: float = 24000.0,
        height_m: float = 24000.0,
        resolution_m: float = 30.0,
        base_elevation_m: float = 900.0,
        ridge_distance_m: Optional[float] = None,
        ridge_height_m: float = 100.0,
        ridge_width_m: float = 150.0,
    ) -> "DEMGrid":
        """Create a synthetic DEM grid for testing and benchmarking.
        
        If ridge_distance_m is specified, places a North-South ridge at center_x + ridge_distance_m.
        """
        cols = int(np.ceil(width_m / resolution_m))
        rows = int(np.ceil(height_m / resolution_m))

        left = center_x - (cols * resolution_m) / 2.0
        top = center_y + (rows * resolution_m) / 2.0

        transform = Affine(resolution_m, 0.0, left, 0.0, -resolution_m, top)
        data = np.full((rows, cols), base_elevation_m, dtype=np.float32)

        if ridge_distance_m is not None:
            ridge_center_x = center_x + ridge_distance_m
            x_coords = left + (np.arange(cols) + 0.5) * resolution_m
            # Gaussian or box ridge shape
            dist_from_ridge = np.abs(x_coords - ridge_center_x)
            ridge_profile = np.maximum(0.0, ridge_height_m * (1.0 - dist_from_ridge / (ridge_width_m / 2.0)))
            data += ridge_profile[None, :]

        return cls(data, transform, "EPSG:32643")

    def sample_points(
        self,
        x: Union[float, np.ndarray],
        y: Union[float, np.ndarray],
        default_val: float = 0.0,
    ) -> np.ndarray:
        """Sample elevations at arbitrary UTM points using fast vectorized nearest neighbor / clamping."""
        x_arr = np.atleast_1d(x)
        y_arr = np.atleast_1d(y)

        cols = np.floor((x_arr - self.left) / self.res_x).astype(np.int64)
        rows = np.floor((self.top - y_arr) / self.res_y).astype(np.int64)

        # Check in-bounds
        valid = (cols >= 0) & (cols < self.width) & (rows >= 0) & (rows < self.height)
        safe_cols = np.clip(cols, 0, self.width - 1)
        safe_rows = np.clip(rows, 0, self.height - 1)

        elev = self.data[safe_rows, safe_cols].copy()
        elev[~valid] = default_val
        is_nodata = (elev == self.nodata) | np.isnan(elev)
        if np.any(is_nodata):
            valid_pts = self.data[(self.data != self.nodata) & (~np.isnan(self.data))]
            elev[is_nodata] = float(np.median(valid_pts)) if len(valid_pts) > 0 else default_val

        return elev if isinstance(x, np.ndarray) else elev[0]

    def sample_grid(self, x_grid: np.ndarray, y_grid: np.ndarray, default_val: float = 0.0) -> np.ndarray:
        """Sample elevations on a 2D array of UTM points (e.g., polar sweep rays)."""
        cols = np.floor((x_grid - self.left) / self.res_x).astype(np.int64)
        rows = np.floor((self.top - y_grid) / self.res_y).astype(np.int64)

        valid = (cols >= 0) & (cols < self.width) & (rows >= 0) & (rows < self.height)
        safe_cols = np.clip(cols, 0, self.width - 1)
        safe_rows = np.clip(rows, 0, self.height - 1)

        elev = self.data[safe_rows, safe_cols].copy()
        elev[~valid] = default_val
        elev[np.isnan(elev)] = self.nodata
        return elev
