"""Polar sweep terrain shadowing model.

Casts 720 rays outward at 30 m steps up to 10 km.
Samples DEM, computes ground elevation angles, calculates running maximum via
np.maximum.accumulate, and maps cells to ray/distance bins to detect shadowing.
"""
from typing import Optional, Tuple
import numpy as np
from .config import PropagationConfig
from .dem import DEMGrid


class PolarSweepEngine:
    """Precomputed polar sweep engine for fast ray casting and shadow determination."""

    def __init__(self, cfg: Optional[PropagationConfig] = None):
        self.cfg = cfg or PropagationConfig()

        self.num_rays = self.cfg.num_rays
        self.ray_step_m = self.cfg.ray_step_m
        self.max_radius_m = self.cfg.max_radius_km * 1000.0

        # Number of radial steps
        self.num_steps = int(np.floor(self.max_radius_m / self.ray_step_m))
        self.distances = (np.arange(1, self.num_steps + 1) * self.ray_step_m).astype(np.float32)

        # Precompute ray angles (0 to 360 deg, 0.5 deg step for 720 rays)
        self.ray_angles_deg = np.linspace(0.0, 360.0, self.num_rays, endpoint=False, dtype=np.float32)
        angles_rad = np.radians(self.ray_angles_deg)

        # Navigation coordinates: 0 deg = North (+Y), 90 deg = East (+X)
        self.dx = np.sin(angles_rad).astype(np.float32)  # shape (720,)
        self.dy = np.cos(angles_rad).astype(np.float32)  # shape (720,)

        # Relative coordinates along all rays: shape (720, num_steps)
        self.rel_x = self.dx[:, None] * self.distances[None, :]
        self.rel_y = self.dy[:, None] * self.distances[None, :]

        # Precomputed angular resolution
        self.deg_per_ray = 360.0 / self.num_rays

    def compute_tower_sweep(
        self,
        tower_x: float,
        tower_y: float,
        tower_height: float,
        dem: DEMGrid,
    ) -> Tuple[np.ndarray, float]:
        """Compute running maximum obstruction angles along 720 rays for a tower.

        Returns:
            Tuple of:
              - running_max_angle: shape (720, num_steps)
              - z_antenna: absolute elevation of the tower antenna (m)
        """
        # Ground elevation at tower base
        z_tower_ground = float(dem.sample_points(tower_x, tower_y))
        z_antenna = z_tower_ground + tower_height

        # Absolute UTM coordinates for all samples along all 720 rays
        sample_x = tower_x + self.rel_x
        sample_y = tower_y + self.rel_y

        # Sample DEM at native resolution along all rays: shape (720, num_steps)
        z_samples = dem.sample_grid(sample_x, sample_y, default_val=z_tower_ground)

        # Elevation angle from antenna to each ground point: (z_ground - z_antenna) / d
        angles = (z_samples - z_antenna) / self.distances[None, :]

        # Vectorized running maximum along each ray
        running_max_angle = np.maximum.accumulate(angles, axis=1)

        return running_max_angle, z_antenna

    def evaluate_shadows(
        self,
        tower_x: float,
        tower_y: float,
        running_max_angle: np.ndarray,
        z_antenna: float,
        cell_x: np.ndarray,
        cell_y: np.ndarray,
        cell_elev: np.ndarray,
        receiver_height_m: float = 1.5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Map cells to nearest ray and distance bin and evaluate if they are shadowed.

        Args:
            tower_x, tower_y: Tower UTM coordinates.
            running_max_angle: Precomputed running max angles from compute_tower_sweep.
            z_antenna: Antenna absolute elevation.
            cell_x, cell_y: 1D arrays of cell UTM coordinates.
            cell_elev: 1D array of cell ground elevations.
            receiver_height_m: Mobile antenna height above ground.

        Returns:
            Tuple of:
              - is_shadowed: boolean array of shape (N,) indicating terrain obstruction.
              - distances: float32 array of shape (N,) distances to tower.
        """
        dx = cell_x - tower_x
        dy = cell_y - tower_y
        dist = np.sqrt(dx * dx + dy * dy).astype(np.float32)

        # Cell azimuth angle in degrees [0, 360)
        azimuth_deg = np.degrees(np.arctan2(dx, dy)) % 360.0

        # Map to nearest ray index (0 to num_rays - 1)
        ray_idx = (np.round(azimuth_deg / self.deg_per_ray).astype(np.int64)) % self.num_rays

        # Map distance to radial bin index (0 to num_steps - 1)
        step_idx = np.clip(np.round(dist / self.ray_step_m).astype(np.int64), 1, self.num_steps) - 1

        # Mobile receiver absolute elevation
        z_rx = cell_elev + receiver_height_m

        # Line-of-sight elevation angle from antenna to receiver
        cell_los_angle = (z_rx - z_antenna) / np.maximum(dist, 1.0)

        # Obstruction angle from running maximum
        obstruction_angle = running_max_angle[ray_idx, step_idx]

        # Cell is shadowed if its receiver angle is below the horizon obstruction
        # Small tolerance (1e-5) prevents numerical noise on flat ground
        is_shadowed = (cell_los_angle < obstruction_angle - 1e-5) & (dist <= self.max_radius_m)

        return is_shadowed, dist
