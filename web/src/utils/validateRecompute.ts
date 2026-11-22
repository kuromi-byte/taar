// /web/src/utils/validateRecompute.ts
// Pure validation for FastAPI /recompute response shapes per Contract 3

import { RecomputeResponse } from '../types/contracts';

export type ValidationResult =
  | { ok: true; data: RecomputeResponse }
  | { ok: false; reason: string };

/**
 * Validates that an arbitrary payload adheres strictly to the contract for RecomputeResponse.
 *
 * Rules:
 * - Must be an object (non-null, not an array)
 * - 'changed' must be an array of [integer id, finite number dbm] pairs
 * - 'newly_covered_pop' must be a non-negative integer (>= 0)
 * - 'total_unserved_pop' must be a non-negative integer (>= 0)
 * - Extra or unknown fields are ignored
 * - Empty 'changed: []' is valid
 */
export function validateRecomputeResponse(x: unknown): ValidationResult {
  if (x === null || typeof x !== 'object' || Array.isArray(x)) {
    return { ok: false, reason: 'Response must be a non-null object' };
  }

  const obj = x as Record<string, unknown>;

  // Check changed
  if (!('changed' in obj) || !Array.isArray(obj.changed)) {
    return { ok: false, reason: "'changed' must be an array" };
  }

  for (let i = 0; i < obj.changed.length; i++) {
    const item = obj.changed[i];
    if (!Array.isArray(item) || item.length !== 2) {
      return {
        ok: false,
        reason: `Item at changed[${i}] must be a 2-element tuple [id, dbm]`,
      };
    }
    const [id, dbm] = item;
    if (typeof id !== 'number' || !Number.isInteger(id)) {
      return {
        ok: false,
        reason: `Item at changed[${i}][0] must be an integer cell ID, received ${typeof id === 'number' ? id : typeof id}`,
      };
    }
    if (typeof dbm !== 'number' || !Number.isFinite(dbm)) {
      return {
        ok: false,
        reason: `Item at changed[${i}][1] must be a finite number dBm, received ${dbm}`,
      };
    }
  }

  // Check newly_covered_pop
  if (
    typeof obj.newly_covered_pop !== 'number' ||
    !Number.isInteger(obj.newly_covered_pop) ||
    obj.newly_covered_pop < 0
  ) {
    return {
      ok: false,
      reason: `'newly_covered_pop' must be a non-negative integer, received ${obj.newly_covered_pop}`,
    };
  }

  // Check total_unserved_pop
  if (
    typeof obj.total_unserved_pop !== 'number' ||
    !Number.isInteger(obj.total_unserved_pop) ||
    obj.total_unserved_pop < 0
  ) {
    return {
      ok: false,
      reason: `'total_unserved_pop' must be a non-negative integer, received ${obj.total_unserved_pop}`,
    };
  }

  return {
    ok: true,
    data: {
      changed: obj.changed as [number, number][],
      newly_covered_pop: obj.newly_covered_pop,
      total_unserved_pop: obj.total_unserved_pop,
    },
  };
}
