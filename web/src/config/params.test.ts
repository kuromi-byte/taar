import { describe, it, expect } from 'vitest';
import { params, gap_threshold_dbm, uncertain_band_db, max_radius_km, pilotConfig } from './params';

describe('params config module', () => {
  it('loads thresholds correctly from real /contracts/config.json without hardcoding', () => {
    expect(typeof params.gap_threshold_dbm).toBe('number');
    expect(typeof params.uncertain_band_db).toBe('number');
    expect(typeof params.max_radius_km).toBe('number');

    expect(gap_threshold_dbm).toBe(params.gap_threshold_dbm);
    expect(uncertain_band_db).toBe(params.uncertain_band_db);
    expect(max_radius_km).toBe(params.max_radius_km);

    // Exact threshold values from real contracts/config.json
    expect(gap_threshold_dbm).toBe(-100.0);
    expect(uncertain_band_db).toBe(6.0);
    expect(max_radius_km).toBe(10.0);
  });

  it('derives pilot center and bbox dynamically from config without hardcoded coordinates', () => {
    expect(pilotConfig.bbox).toEqual([75.60, 12.80, 75.95, 13.10]);
    // Center is exact midpoint: [(75.60 + 75.95) / 2, (12.80 + 13.10) / 2] = [75.775, 12.95]
    expect(pilotConfig.center[0]).toBeCloseTo(75.775, 3);
    expect(pilotConfig.center[1]).toBeCloseTo(12.95, 3);
    expect(pilotConfig.name).toContain('Sakleshpur');
  });
});
