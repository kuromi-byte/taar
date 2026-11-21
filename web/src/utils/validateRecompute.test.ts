import { describe, it, expect } from 'vitest';
import { validateRecomputeResponse } from './validateRecompute';

describe('validateRecomputeResponse', () => {
  it('accepts valid contract response', () => {
    const res = validateRecomputeResponse({
      changed: [
        [1, -85.5],
        [2, -102.0],
      ],
      newly_covered_pop: 500,
      total_unserved_pop: 350000,
    });
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.data.changed.length).toBe(2);
      expect(res.data.newly_covered_pop).toBe(500);
      expect(res.data.total_unserved_pop).toBe(350000);
    }
  });

  it('accepts empty changed array (valid empty footprint)', () => {
    const res = validateRecomputeResponse({
      changed: [],
      newly_covered_pop: 0,
      total_unserved_pop: 364978,
    });
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.data.changed).toEqual([]);
      expect(res.data.newly_covered_pop).toBe(0);
    }
  });

  it('ignores extra/unknown fields', () => {
    const res = validateRecomputeResponse({
      changed: [[100, -94.0]],
      newly_covered_pop: 10,
      total_unserved_pop: 1000,
      extra_field: 'ignored',
      computation_time_ms: 45.2,
    });
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect((res.data as any).extra_field).toBeUndefined();
    }
  });

  it('rejects non-object inputs', () => {
    expect(validateRecomputeResponse(null).ok).toBe(false);
    expect(validateRecomputeResponse(undefined).ok).toBe(false);
    expect(validateRecomputeResponse('string').ok).toBe(false);
    expect(validateRecomputeResponse(123).ok).toBe(false);
    expect(validateRecomputeResponse([]).ok).toBe(false);
  });

  it('rejects missing fields', () => {
    expect(
      validateRecomputeResponse({
        newly_covered_pop: 10,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    expect(
      validateRecomputeResponse({
        changed: [],
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    expect(
      validateRecomputeResponse({
        changed: [],
        newly_covered_pop: 10,
      }).ok
    ).toBe(false);
  });

  it('rejects invalid changed pairs', () => {
    // Float ID
    expect(
      validateRecomputeResponse({
        changed: [[1.5, -90.0]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    // String ID
    expect(
      validateRecomputeResponse({
        changed: [['1', -90.0]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    // Wrong tuple length
    expect(
      validateRecomputeResponse({
        changed: [[1]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    expect(
      validateRecomputeResponse({
        changed: [[1, -90.0, 45]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    // Non-finite dBm
    expect(
      validateRecomputeResponse({
        changed: [[1, NaN]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    expect(
      validateRecomputeResponse({
        changed: [[1, Infinity]],
        newly_covered_pop: 0,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);
  });

  it('rejects invalid population numbers', () => {
    // Negative population
    expect(
      validateRecomputeResponse({
        changed: [],
        newly_covered_pop: -1,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    expect(
      validateRecomputeResponse({
        changed: [],
        newly_covered_pop: 0,
        total_unserved_pop: -5,
      }).ok
    ).toBe(false);

    // Float population
    expect(
      validateRecomputeResponse({
        changed: [],
        newly_covered_pop: 12.5,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);

    // NaN population
    expect(
      validateRecomputeResponse({
        changed: [],
        newly_covered_pop: NaN,
        total_unserved_pop: 100,
      }).ok
    ).toBe(false);
  });
});
