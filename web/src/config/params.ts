// /web/src/config/params.ts
// Loads thresholds and pilot bbox from /contracts/config.json.
// Never hard-code them. Derived map center and fitBounds are calculated dynamically.

import rawConfig from '/contracts/config.json';
import { ContractConfig } from '../types/contracts';

export const params: ContractConfig = {
  gap_threshold_dbm: rawConfig.gap_threshold_dbm,
  uncertain_band_db: rawConfig.uncertain_band_db,
  max_radius_km: rawConfig.max_radius_km,
  pilot: rawConfig.pilot,
};

export const { gap_threshold_dbm, uncertain_band_db, max_radius_km } = params;

// Derived pilot spatial configuration directly from config.json bbox
const bbox = rawConfig.pilot?.bbox_wgs84 ?? {
  min_lon: 75.60,
  max_lon: 75.95,
  min_lat: 12.80,
  max_lat: 13.10,
};

export const pilotConfig = {
  name: rawConfig.pilot?.name || 'Sakleshpur Taluk (Karnataka)',
  // Bounding box: [minLon, minLat, maxLon, maxLat]
  bbox: [bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat] as [number, number, number, number],
  // Center derived as midpoint of bbox: [lon, lat]
  center: [(bbox.min_lon + bbox.max_lon) / 2, (bbox.min_lat + bbox.max_lat) / 2] as [number, number],
  zoom: 11,
};
