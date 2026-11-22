// /web/src/config/data.ts
// The ONLY place that holds data paths and API URL (mock vs real).
// Switching to real data must be a change here or in env var VITE_API_URL.

import { pilotConfig } from './params';

export const DATA_CONFIG = {
  // Use real backend API running on port 8000 (FastAPI), with fallback capability
  apiUrl: (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000',

  // Static file paths (served from /web/public)
  paths: {
    cells: '/data/cells.geojson',
    candidates: '/data/candidates.json',
    clusters: '/data/clusters.json',
    towns: '/data/towns.json',
    towers: '/data/towers.json',
    basemapBoundary: '/data/basemap/boundary.geojson',
    basemapRoads: '/data/basemap/roads.geojson',
  },

  // Taluk Pilot metadata derived dynamically from /contracts/config.json via params.ts
  pilot: pilotConfig,

  // Recompute timing thresholds
  SLOW_MS: 1500,
  TIMEOUT_MS: 15000,

  getSlowMs(): number {
    if (import.meta.env.DEV && typeof window !== 'undefined' && (window as any).__DEV_SLOW_MS != null) {
      return (window as any).__DEV_SLOW_MS;
    }
    return this.SLOW_MS;
  },

  getTimeoutMs(): number {
    if (import.meta.env.DEV && typeof window !== 'undefined' && (window as any).__DEV_TIMEOUT_MS != null) {
      return (window as any).__DEV_TIMEOUT_MS;
    }
    return this.TIMEOUT_MS;
  },
};

export const SLOW_MS = DATA_CONFIG.SLOW_MS;
export const TIMEOUT_MS = DATA_CONFIG.TIMEOUT_MS;
