import { describe, it, expect } from 'vitest';
import {
  buildCellColorExpression,
  evaluateCellColor,
  CELL_COLORS,
} from './styleExpressions';

describe('styleExpressions and cell color resolution', () => {
  const thresholds = {
    coveredThreshold: -94.0,
    gapThreshold: -106.0,
  };

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

    it('preserves grey for unknown cells even if feature-state dbm is set', () => {
      expect(
        evaluateCellColor({ state: 'unknown', baseline_dbm: null }, -75.0, thresholds)
      ).toBe(CELL_COLORS.unknown);
    });
  });
});
