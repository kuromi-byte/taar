import { describe, it, expect, vi } from 'vitest';
import { applyRecompute, MapFeatureStateManager } from './recompute';

function createMockMap(): MapFeatureStateManager & {
  setCalls: { target: { source: string; id: number | string }; state: Record<string, unknown> }[];
  removeCalls: { target: { source: string; id: number | string }; key?: string }[];
} {
  const setCalls: { target: { source: string; id: number | string }; state: Record<string, unknown> }[] = [];
  const removeCalls: { target: { source: string; id: number | string }; key?: string }[] = [];

  return {
    setCalls,
    removeCalls,
    setFeatureState: vi.fn((target, state) => {
      setCalls.push({ target, state });
    }),
    removeFeatureState: vi.fn((target, key) => {
      removeCalls.push({ target, key });
    }),
  };
}

describe('applyRecompute pure function', () => {
  it('applies changed cell dBm values and returns a Set of overridden IDs', () => {
    const map = createMockMap();
    const prevSet = new Set<number>();
    const changed: [number, number][] = [
      [10, -92.5],
      [20, -88.0],
    ];

    const result = applyRecompute(map, prevSet, changed, 'cells');

    expect(result).toBeInstanceOf(Set);
    expect(result.size).toBe(2);
    expect(result.has(10)).toBe(true);
    expect(result.has(20)).toBe(true);

    expect(map.setFeatureState).toHaveBeenCalledTimes(2);
    expect(map.setCalls).toEqual([
      { target: { source: 'cells', id: 10 }, state: { dbm: -92.5 } },
      { target: { source: 'cells', id: 20 }, state: { dbm: -88.0 } },
    ]);
    expect(map.removeFeatureState).not.toHaveBeenCalled();
  });

  it('clears dropped cells when response shrinks (idempotency check)', () => {
    const map = createMockMap();
    // Previous call had cells 10, 20, 30
    const prevSet = new Set<number>([10, 20, 30]);
    // New response only has cell 20 (cells 10 and 30 dropped out)
    const changed: [number, number][] = [[20, -85.0]];

    const result = applyRecompute(map, prevSet, changed, 'cells');

    expect(result.size).toBe(1);
    expect(result.has(20)).toBe(true);
    expect(result.has(10)).toBe(false);
    expect(result.has(30)).toBe(false);

    // removeFeatureState must have been called for cells 10 and 30
    expect(map.removeFeatureState).toHaveBeenCalledTimes(2);
    expect(map.removeCalls).toEqual([
      { target: { source: 'cells', id: 10 } },
      { target: { source: 'cells', id: 30 } },
    ]);

    // setFeatureState called for cell 20
    expect(map.setFeatureState).toHaveBeenCalledWith(
      { source: 'cells', id: 20 },
      { dbm: -85.0 }
    );
  });

  it('clears everything when response is empty', () => {
    const map = createMockMap();
    const prevSet = new Set<number>([1, 2, 3, 4]);
    const changed: [number, number][] = [];

    const result = applyRecompute(map, prevSet, changed, 'cells');

    expect(result.size).toBe(0);
    expect(map.removeFeatureState).toHaveBeenCalledTimes(4);
    expect(map.setFeatureState).not.toHaveBeenCalled();
  });

  it('safely ignores unknown, non-integer, or malformed cell IDs', () => {
    const map = createMockMap();
    const prevSet = new Set<number>();
    const malformedChanged: any = [
      ['unknown-string-id', -90.0],
      [null, -95.0],
      [undefined, -100.0],
      [NaN, -80.0],
      [15, NaN], // invalid dbm
      [42, -75.4], // valid
      'not-an-array',
      [],
    ];

    const result = applyRecompute(map, prevSet, malformedChanged, 'cells');

    expect(result.size).toBe(1);
    expect(result.has(42)).toBe(true);
    expect(map.setFeatureState).toHaveBeenCalledTimes(1);
    expect(map.setFeatureState).toHaveBeenCalledWith(
      { source: 'cells', id: 42 },
      { dbm: -75.4 }
    );
  });

  it('verifies dragging the same tower twice cleanly removes stale footprint', () => {
    const map = createMockMap();
    let prevSet = new Set<number>();

    // Drag 1: Tower placed at location A covers cells 100..120
    const drag1Changed: [number, number][] = Array.from({ length: 20 }, (_, i) => [100 + i, -80 - i]);
    prevSet = applyRecompute(map, prevSet, drag1Changed, 'cells');

    expect(prevSet.size).toBe(20);
    expect(map.setFeatureState).toHaveBeenCalledTimes(20);
    expect(map.removeFeatureState).not.toHaveBeenCalled();

    // Drag 2: Tower moved to location B covering cells 115..135 (cells 100..114 must be removed!)
    const drag2Changed: [number, number][] = Array.from({ length: 20 }, (_, i) => [115 + i, -82 - i]);
    prevSet = applyRecompute(map, prevSet, drag2Changed, 'cells');

    expect(prevSet.size).toBe(20);
    // Cells 100..114 (15 cells) dropped out of the coverage footprint and must have been removed
    expect(map.removeFeatureState).toHaveBeenCalledTimes(15);
    for (let i = 100; i < 115; i++) {
      expect(map.removeCalls).toContainEqual({ target: { source: 'cells', id: i } });
    }
    // New footprint cells 115..134 are updated
    expect(prevSet.has(100)).toBe(false);
    expect(prevSet.has(134)).toBe(true);
  });

  it('benchmarks setFeatureState timing for real cell count (900 cells)', () => {
    const map = createMockMap();
    const prevSet = new Set<number>();
    const allCellsChanged: [number, number][] = Array.from({ length: 900 }, (_, i) => [i, -75 - (i % 30)]);

    const start = performance.now();
    const result = applyRecompute(map, prevSet, allCellsChanged, 'cells');
    const elapsed = performance.now() - start;

    expect(result.size).toBe(900);
    expect(map.setFeatureState).toHaveBeenCalledTimes(900);
    // 900 setFeatureState calls in JS must execute in well under 10ms
    expect(elapsed).toBeLessThan(50);
  });

  it('correctly handles 1-based indexing for real full dataset (ids 1..11394)', () => {
    const map = createMockMap();
    const prevSet = new Set<number>();
    const changed1Based: [number, number][] = [
      [1, -85.0],
      [500, -90.0],
      [11394, -72.5],
    ];

    const result = applyRecompute(map, prevSet, changed1Based, 'cells');

    expect(result.size).toBe(3);
    expect(result.has(1)).toBe(true);
    expect(result.has(500)).toBe(true);
    expect(result.has(11394)).toBe(true);
    expect(result.has(0)).toBe(false);

    expect(map.setCalls).toEqual([
      { target: { source: 'cells', id: 1 }, state: { dbm: -85.0 } },
      { target: { source: 'cells', id: 500 }, state: { dbm: -90.0 } },
      { target: { source: 'cells', id: 11394 }, state: { dbm: -72.5 } },
    ]);
  });
});
