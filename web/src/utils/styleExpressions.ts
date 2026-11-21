// /web/src/utils/styleExpressions.ts
// Pure style expression helpers for MapLibre GL cell layers

export const CELL_COLORS = {
  unknown: '#6b7280',
  covered: '#10b981',
  uncertain: '#f59e0b',
  gap: '#ef4444',
} as const;

/**
 * Builds the data-driven fill-color expression for the cells layer.
 *
 * Rules:
 * 1. Unknown cells (state === 'unknown' or 'Unknown') are always grey (#6b7280), never gap.
 * 2. If a valid signal level exists (from feature-state dbm or baseline_dbm >= coveredThreshold): green (#10b981).
 * 3. If signal in uncertain band [gapThreshold, coveredThreshold): amber (#f59e0b).
 * 4. If signal is present but < gapThreshold: red (#ef4444).
 * 5. If BOTH feature-state dbm and baseline_dbm are null/missing: color by the cell's 'state' property:
 *    - 'covered' / 'Likely covered' -> green (#10b981)
 *    - 'uncertain' / 'Uncertain' -> amber (#f59e0b)
 *    - 'gap' / 'Likely gap' -> red (#ef4444)
 *    - default -> red (#ef4444)
 */
export function buildCellColorExpression(
  coveredThreshold: number,
  gapThreshold: number
): unknown[] {
  return [
    'case',
    // 1. Unknown check first: always grey, never gap
    [
      'any',
      ['==', ['get', 'state'], 'unknown'],
      ['==', ['get', 'state'], 'Unknown'],
    ],
    CELL_COLORS.unknown,

    // 2. Active signal >= coveredThreshold
    [
      '>=',
      ['coalesce', ['feature-state', 'dbm'], ['get', 'baseline_dbm'], -9999.0],
      coveredThreshold,
    ],
    CELL_COLORS.covered,

    // 3. Active signal in uncertain band [gapThreshold, coveredThreshold)
    [
      '>=',
      ['coalesce', ['feature-state', 'dbm'], ['get', 'baseline_dbm'], -9999.0],
      gapThreshold,
    ],
    CELL_COLORS.uncertain,

    // 4. Active signal present and < gapThreshold (coalesce > -999.0)
    [
      '>',
      ['coalesce', ['feature-state', 'dbm'], ['get', 'baseline_dbm'], -9999.0],
      -999.0,
    ],
    CELL_COLORS.gap,

    // 5. Fallback when BOTH feature-state dbm AND baseline_dbm are null:
    // Color strictly by the cell's state property (never default to gap if state is covered/uncertain)
    [
      'any',
      ['==', ['get', 'state'], 'covered'],
      ['==', ['get', 'state'], 'Likely covered'],
    ],
    CELL_COLORS.covered,

    [
      'any',
      ['==', ['get', 'state'], 'uncertain'],
      ['==', ['get', 'state'], 'Uncertain'],
    ],
    CELL_COLORS.uncertain,

    // Default for gap or unrecognized state
    CELL_COLORS.gap,
  ];
}

/**
 * Pure evaluation helper modeling the exact MapLibre expression logic for unit testing.
 */
export function evaluateCellColor(
  props: { state?: string | null; baseline_dbm?: number | null },
  featureStateDbm: number | null | undefined,
  thresholds: { coveredThreshold: number; gapThreshold: number }
): string {
  const stateStr = props.state != null ? String(props.state) : '';

  // 1. Unknown check first
  if (stateStr === 'unknown' || stateStr === 'Unknown') {
    return CELL_COLORS.unknown;
  }

  // Determine active dBm
  const activeDbm =
    featureStateDbm !== null && featureStateDbm !== undefined
      ? featureStateDbm
      : props.baseline_dbm !== null && props.baseline_dbm !== undefined
        ? props.baseline_dbm
        : null;

  if (activeDbm !== null) {
    if (activeDbm >= thresholds.coveredThreshold) {
      return CELL_COLORS.covered;
    }
    if (activeDbm >= thresholds.gapThreshold) {
      return CELL_COLORS.uncertain;
    }
    return CELL_COLORS.gap;
  }

  // 2. Both null -> fallback to state property
  if (stateStr === 'covered' || stateStr === 'Likely covered') {
    return CELL_COLORS.covered;
  }
  if (stateStr === 'uncertain' || stateStr === 'Uncertain') {
    return CELL_COLORS.uncertain;
  }
  return CELL_COLORS.gap;
}
