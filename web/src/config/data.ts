// /web/src/config/data.ts
// The ONLY place that holds data paths and API URL (mock vs real).
// Switching to real data must be a change here or in env var VITE_API_URL.

import { pilotConfig } from './params';

export const DATA_CONFIG = {
  // Use mock or real API URL. Override via env var VITE_API_URL when real API is running
  apiUrl: (import.meta.env.VITE_API_URL as string) || 'mock',

  // Static file paths (served from /web/public)
  paths: {
    cells: '/data/cells.geojson',
    candidates: '/data/candidates.json',
    clusters: '/data/clusters.json',
    towns: '/data/towns.json',
    basemapBoundary: '/data/basemap/boundary.geojson',
    basemapRoads: '/data/basemap/roads.geojson',
  },

  // Taluk Pilot metadata derived dynamically from /contracts/config.json via params.ts
  pilot: pilotConfig,
};
