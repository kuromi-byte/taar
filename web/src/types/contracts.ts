// /web/src/types/contracts.ts
// Shared contract interfaces for Gap-to-Brief (Dev C frontend)

export type CellState = 'covered' | 'gap' | 'uncertain' | 'unknown';

export interface CellProperties {
  pop: number;
  baseline_dbm: number | null;
  state: CellState;
}

export interface CellFeature {
  type: 'Feature';
  id: number; // Integer ID 0..N
  geometry: {
    type: 'Polygon';
    coordinates: number[][][];
  };
  properties: CellProperties;
}

export interface CellsGeoJSON {
  type: 'FeatureCollection';
  features: CellFeature[];
}

export interface CandidateFlags {
  road_km: number;
  slope_deg: number;
  backhaul: string;
}

export interface Candidate {
  id: string | number;
  cluster_id: string | number;
  lat: number;
  lon: number;
  added_pop: number;
  flags: CandidateFlags;
  why: string;
}

export interface Cluster {
  id: string | number;
  cell_ids: number[];
  pop_in_gap: number;
  candidate_ids: (string | number)[]; // Empty array means "needs field survey"
  name_hint?: string;
}

export interface Town {
  name: string;
  lat: number;
  lon: number;
}

export interface TowerInput {
  lat: number;
  lon: number;
  height_m: number;
  power_dbm: number;
}

export interface RecomputeRequest {
  towers: TowerInput[];
}

export interface RecomputeResponse {
  changed: [number, number][]; // [cell_id, dbm]
  newly_covered_pop: number;
  total_unserved_pop: number;
}

export interface ConfigBboxWGS84 {
  min_lon: number;
  max_lon: number;
  min_lat: number;
  max_lat: number;
}

export interface ContractConfig {
  gap_threshold_dbm: number;
  uncertain_band_db: number;
  max_radius_km: number;
  pilot?: {
    name?: string;
    bbox_wgs84: ConfigBboxWGS84;
  };
}
