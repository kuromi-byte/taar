import { describe, it, expect } from 'vitest';
import candidatesData from '../../public/data/candidates.json';
import clustersData from '../../public/data/clusters.json';
import townsData from '../../public/data/towns.json';
import towersData from '../../public/data/towers.json';

describe('Contracts and Static Data Integrity', () => {
  it('validates candidate site schema and feasibility flags', () => {
    expect(candidatesData.length).toBeGreaterThan(0);
    for (const c of candidatesData) {
      expect(c.id).toBeDefined();
      expect(c.cluster_id).toBeDefined();
      expect(c.lat).toBeGreaterThanOrEqual(12.8);
      expect(c.lat).toBeLessThanOrEqual(13.1);
      expect(c.lon).toBeGreaterThanOrEqual(75.6);
      expect(c.lon).toBeLessThanOrEqual(75.95);
      expect(c.added_pop).toBeGreaterThan(0);
      expect(c.flags).toBeDefined();
      expect(c.flags.road_km).toBeLessThanOrEqual(1.0);
      expect(c.flags.slope_deg).toBeLessThan(15.0);
      expect(c.why).toContain('residents');
    }
  });

  it('validates clusters and checks for at least one needs-field-survey outcome', () => {
    expect(clustersData.length).toBeGreaterThan(0);
    let foundNeedsSurvey = false;

    for (const cl of clustersData) {
      expect(cl.id).toBeDefined();
      expect(cl.cell_ids.length).toBeGreaterThan(0);
      expect(cl.pop_in_gap).toBeGreaterThan(0);
      if (!cl.candidate_ids || cl.candidate_ids.length === 0) {
        foundNeedsSurvey = true;
        expect(cl.needs_field_survey).toBe(true);
      }
    }

    expect(foundNeedsSurvey).toBe(true);
  });

  it('validates towns list for anchor orientation', () => {
    expect(townsData.length).toBeGreaterThanOrEqual(6);
    const sakleshpur = townsData.find((t) => t.name.toLowerCase().includes('sakleshpur'));
    expect(sakleshpur).toBeDefined();
    expect(sakleshpur?.lat).toBeCloseTo(12.972, 2);
    expect(sakleshpur?.lon).toBeCloseTo(75.785, 2);
  });

  it('validates existing macro towers', () => {
    expect(towersData.length).toBeGreaterThan(0);
    for (const t of towersData) {
      expect(t.lat).toBeGreaterThanOrEqual(12.8);
      expect(t.lon).toBeGreaterThanOrEqual(75.6);
      expect(t.assumed).toBe(true);
    }
  });
});
