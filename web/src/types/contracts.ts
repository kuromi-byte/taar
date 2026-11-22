// /web/src/types/contracts.ts
// Shared contract interfaces for Gap-to-Brief (Dev C frontend)

export type CellState = 'covered' | 'gap' | 'uncertain' | 'unknown' | 'Likely covered' | 'Likely gap' | 'Uncertain' | 'Unknown';

export interface CellProperties {
  id?: number;
  pop: number;
  baseline_dbm: number | null;
  state: CellState;
  [key: string]: unknown;
}

export interface CellFeature {
  type: 'Feature';
  id: number; // Integer ID (supports 1..N or 0..N)
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
  villages?: string[];
  terrain_summary?: string;
  needs_field_survey?: boolean;
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

export interface PilotConfig {
  name: string;
  district?: string;
  state?: string;
  bbox_wgs84: ConfigBboxWGS84;
  terrain_buffer_km?: number;
  crs_internal?: string;
  crs_exchange?: string;
}

export interface PropagationConfig {
  frequency_mhz: number;
  tower_height_m: number;
  rx_height_m: number;
  shadow_penalty_db: number;
  gap_threshold_dbm: number;
  uncertain_band_db: number;
  max_radius_km: number;
  ray_step_m: number;
  n_rays: number;
  eirp_dbm: number;
}

export interface ContractConfig {
  gap_threshold_dbm: number;
  uncertain_band_db: number;
  max_radius_km: number;
  propagation?: Partial<PropagationConfig>;
  pilot?: Partial<PilotConfig>;
  paths?: Record<string, string>;
  _notes?: Record<string, string>;
}
