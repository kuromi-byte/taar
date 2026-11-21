// /web/src/config/params.ts
// Loads thresholds and pilot bbox from /contracts/config.json.
// Adapts to real schema keys (where thresholds are inside "propagation").
// Never hard-code them. Derived map center and fitBounds are calculated dynamically.

import rawConfig from './contracts-fallback.json';
import { ContractConfig } from '../types/contracts';

// In the real /contracts/config.json, tunables are nested under "propagation"
const propagation = (rawConfig as any).propagation || {};

export const params: ContractConfig = {
  gap_threshold_dbm: propagation.gap_threshold_dbm ?? (rawConfig as any).gap_threshold_dbm ?? -100.0,
  uncertain_band_db: propagation.uncertain_band_db ?? (rawConfig as any).uncertain_band_db ?? 6.0,
  max_radius_km: propagation.max_radius_km ?? (rawConfig as any).max_radius_km ?? 10.0,
  propagation: (rawConfig as any).propagation,
  pilot: (rawConfig as any).pilot,
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
  name: rawConfig.pilot?.name
    ? `${rawConfig.pilot.name} Taluk (${rawConfig.pilot.district ? rawConfig.pilot.district + ', ' : ''}${rawConfig.pilot.state || 'Karnataka'})`
    : 'Sakleshpur Taluk (Karnataka)',
  // Bounding box: [minLon, minLat, maxLon, maxLat]
  bbox: [bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat] as [number, number, number, number],
  // Center derived as midpoint of bbox: [lon, lat]
  center: [(bbox.min_lon + bbox.max_lon) / 2, (bbox.min_lat + bbox.max_lat) / 2] as [number, number],
  zoom: 11,
};
