// /web/src/config/stateColors.ts
// Single source of truth for cell state colors across the map expression and legend

export const STATE_COLORS = {
  covered: '#10b981',
  uncertain: '#f59e0b',
  gap: '#ef4444',
  unknown: '#6b7280',
} as const;

export type CellStateColorKey = keyof typeof STATE_COLORS;
