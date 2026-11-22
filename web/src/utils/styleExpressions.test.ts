import { describe, it, expect } from 'vitest';
import {
  buildCellColorExpression,
  evaluateCellColor,
  CELL_COLORS,
  isMockSource,
} from './styleExpressions';
import { STATE_COLORS } from '../config/stateColors';

describe('styleExpressions and cell color resolution', () => {
  const thresholds = {
    coveredThreshold: -94.0,
    gapThreshold: -106.0,
  };

  it('shares identical color constants with STATE_COLORS', () => {
    expect(CELL_COLORS).toBe(STATE_COLORS);
    expect(CELL_COLORS.covered).toBe('#10b981');
    expect(CELL_COLORS.uncertain).toBe('#f59e0b');
    expect(CELL_COLORS.gap).toBe('#ef4444');
    expect(CELL_COLORS.unknown).toBe('#6b7280');
  });

  it('builds a valid MapLibre case expression with unknown check first', () => {
    const expr = buildCellColorExpression(thresholds.coveredThreshold, thresholds.gapThreshold);
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe('case');
    // First branch checks unknown
    expect(expr[1]).toEqual([
      'any',
      ['==', ['get', 'state'], 'unknown'],
      ['==', ['get', 'state'], 'Unknown'],
    ]);
    expect(expr[2]).toBe(CELL_COLORS.unknown);
  });

  describe('Boundary tests with real params (gap threshold -100, band 6)', () => {
    // Boundary rule:
    // covered:   dbm >= -94.0 dBm (inclusive)
    // uncertain: -106.0 dBm <= dbm < -94.0 dBm (inclusive of -106.0, exclusive of -94.0)
    // gap:       dbm < -106.0 dBm (exclusive)

    it('asserts the boundary rule for covered threshold (-94.0 dBm)', () => {
      // dbm = -93.9 (covered)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -93.9 }, null, thresholds)).toBe(
        CELL_COLORS.covered
      );
      // dbm = -94.0 (covered, inclusive boundary)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -94.0 }, null, thresholds)).toBe(
        CELL_COLORS.covered
      );
      // dbm = -94.1 (uncertain, just below covered boundary)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -94.1 }, null, thresholds)).toBe(
        CELL_COLORS.uncertain
      );
    });

    it('asserts the boundary rule for gap threshold (-106.0 dBm)', () => {
      // dbm = -105.9 (uncertain, inside band)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -105.9 }, null, thresholds)).toBe(
        CELL_COLORS.uncertain
      );
      // dbm = -106.0 (uncertain, inclusive lower boundary of band)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -106.0 }, null, thresholds)).toBe(
        CELL_COLORS.uncertain
      );
      // dbm = -106.1 (gap, below lower band boundary)
      expect(evaluateCellColor({ state: 'gap', baseline_dbm: -106.1 }, null, thresholds)).toBe(
        CELL_COLORS.gap
      );
    });
  });

  describe('Param-driven test: arbitrary threshold and band', () => {
    it('builds the expression with custom threshold and band and asserts stops change', () => {
      const customCovered = -90.0;
      const customGap = -110.0;
      const expr = buildCellColorExpression(customCovered, customGap);

      // Branch 2: active signal >= customCovered
      const coveredBranch = expr[3] as any[];
      expect(coveredBranch[0]).toBe('>=');
      expect(coveredBranch[2]).toBe(-90.0);
      expect(expr[4]).toBe(CELL_COLORS.covered);

      // Branch 3: active signal >= customGap
      const uncertainBranch = expr[5] as any[];
      expect(uncertainBranch[0]).toBe('>=');
      expect(uncertainBranch[2]).toBe(-110.0);
      expect(expr[6]).toBe(CELL_COLORS.uncertain);
    });
  });

  describe('Unknown-as-grey invariant under all dBm conditions', () => {
    it('remains grey with very low baseline dBm (-120.0 dBm)', () => {
      expect(
        evaluateCellColor({ state: 'unknown', baseline_dbm: -120.0 }, null, thresholds)
      ).toBe(CELL_COLORS.unknown);
    });

    it('remains grey with high baseline dBm (-80.0 dBm)', () => {
      expect(
        evaluateCellColor({ state: 'unknown', baseline_dbm: -80.0 }, null, thresholds)
      ).toBe(CELL_COLORS.unknown);
    });

    it('remains grey when feature-state dbm is set to covered-level (-75.0 dBm)', () => {
      expect(
        evaluateCellColor({ state: 'unknown', baseline_dbm: null }, -75.0, thresholds)
      ).toBe(CELL_COLORS.unknown);
    });

    it('remains grey with capitalized Unknown and feature-state set (-60.0 dBm)', () => {
      expect(
        evaluateCellColor({ state: 'Unknown', baseline_dbm: -110.0 }, -60.0, thresholds)
      ).toBe(CELL_COLORS.unknown);
    });
  });

  describe('MOCK banner logic (pure condition)', () => {
    it('returns true when meta.source is "mock"', () => {
      expect(isMockSource('mock')).toBe(true);
    });

    it('returns false when meta.source is "worldpop"', () => {
      expect(isMockSource('worldpop')).toBe(false);
    });

    it('returns false when meta.source is null, undefined, or other string', () => {
      expect(isMockSource(null)).toBe(false);
      expect(isMockSource(undefined)).toBe(false);
      expect(isMockSource('')).toBe(false);
      expect(isMockSource('real')).toBe(false);
    });
  });

  describe('evaluateCellColor with null baseline and no feature-state', () => {
    it('colors unknown cells as grey (#6b7280)', () => {
      const color = evaluateCellColor(
        { state: 'unknown', baseline_dbm: null },
        null,
        thresholds
      );
      expect(color).toBe(CELL_COLORS.unknown);
    });

    it('colors covered cells as green (#10b981) instead of defaulting to gap', () => {
      const color = evaluateCellColor(
        { state: 'covered', baseline_dbm: null },
        null,
        thresholds
      );
      expect(color).toBe(CELL_COLORS.covered);
    });

    it('colors uncertain cells as amber (#f59e0b) instead of defaulting to gap', () => {
      const color = evaluateCellColor(
        { state: 'uncertain', baseline_dbm: null },
        null,
        thresholds
      );
      expect(color).toBe(CELL_COLORS.uncertain);
    });

    it('colors gap cells as red (#ef4444)', () => {
      const color = evaluateCellColor(
        { state: 'gap', baseline_dbm: null },
        null,
        thresholds
      );
      expect(color).toBe(CELL_COLORS.gap);
    });
  });

  describe('evaluateCellColor with active signals', () => {
    it('applies baseline_dbm thresholds when present', () => {
      expect(
        evaluateCellColor({ state: 'gap', baseline_dbm: -80.0 }, null, thresholds)
      ).toBe(CELL_COLORS.covered);

      expect(
        evaluateCellColor({ state: 'gap', baseline_dbm: -100.0 }, null, thresholds)
      ).toBe(CELL_COLORS.uncertain);

      expect(
        evaluateCellColor({ state: 'covered', baseline_dbm: -115.0 }, null, thresholds)
      ).toBe(CELL_COLORS.gap);
    });

    it('overrides null baseline when feature-state dbm is provided (tower placement)', () => {
      // Cell started with null baseline and state gap
      expect(
        evaluateCellColor({ state: 'gap', baseline_dbm: null }, -85.0, thresholds)
      ).toBe(CELL_COLORS.covered);

      expect(
        evaluateCellColor({ state: 'gap', baseline_dbm: null }, -102.0, thresholds)
      ).toBe(CELL_COLORS.uncertain);

      expect(
        evaluateCellColor({ state: 'gap', baseline_dbm: null }, -110.0, thresholds)
      ).toBe(CELL_COLORS.gap);
    });
  });
});
