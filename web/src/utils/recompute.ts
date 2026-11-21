// /web/src/utils/recompute.ts
// Pure idempotent feature-state applicator for MapLibre GL cell layers

export interface FeatureStateTarget {
  source: string;
  sourceLayer?: string;
  id: number | string;
}

export interface MapFeatureStateManager {
  setFeatureState: (target: FeatureStateTarget, state: Record<string, unknown>) => void;
  removeFeatureState: (target: FeatureStateTarget, key?: string) => void;
}

/**
 * Idempotently applies changed cell dBm values to MapLibre feature-state.
 *
 * @param map MapLibre map or mock with setFeatureState & removeFeatureState
 * @param prevIdSet Set of cell IDs overridden in the previous recompute cycle
 * @param changed Array of [cell_id, dbm] tuples from server response
 * @param source Source id in MapLibre (defaults to 'cells')
 * @returns The new Set of overridden cell IDs
 */
export function applyRecompute(
  map: MapFeatureStateManager | null | undefined,
  prevIdSet: Set<number>,
  changed: [number, number][] | null | undefined,
  source = 'cells'
): Set<number> {
  const currentIdSet = new Set<number>();
  if (!map || typeof map.setFeatureState !== 'function' || typeof map.removeFeatureState !== 'function') {
    return currentIdSet;
  }

  const safeChanged = Array.isArray(changed) ? changed : [];

  // 1. Collect valid cell IDs from changed response
  for (const item of safeChanged) {
    if (!Array.isArray(item) || item.length < 2) continue;
    const [cellId, dbm] = item;
    if (typeof cellId === 'number' && Number.isInteger(cellId) && typeof dbm === 'number' && Number.isFinite(dbm)) {
      currentIdSet.add(cellId);
    }
  }

  // 2. Remove feature state for cells that dropped out of the response (prevents stale footprints)
  if (prevIdSet && typeof prevIdSet.forEach === 'function') {
    prevIdSet.forEach((oldId) => {
      if (!currentIdSet.has(oldId)) {
        try {
          map.removeFeatureState({ source, id: oldId });
        } catch {
          // Graceful ignore if feature doesn't exist
        }
      }
    });
  }

  // 3. Set new feature state for all cells in current response
  for (const item of safeChanged) {
    if (!Array.isArray(item) || item.length < 2) continue;
    const [cellId, dbm] = item;
    if (typeof cellId === 'number' && Number.isInteger(cellId) && typeof dbm === 'number' && Number.isFinite(dbm)) {
      try {
        map.setFeatureState({ source, id: cellId }, { dbm });
      } catch {
        // Graceful ignore
      }
    }
  }

  return currentIdSet;
}
