import { describe, it, expect } from 'vitest';
import { RequestSequenceGuard } from './requestSequence';

describe('RequestSequenceGuard', () => {
  it('increments sequence numbers monotonically', () => {
    const guard = new RequestSequenceGuard();
    expect(guard.current()).toBe(0);
    expect(guard.next()).toBe(1);
    expect(guard.next()).toBe(2);
    expect(guard.next()).toBe(3);
    expect(guard.current()).toBe(3);
  });

  it('correctly identifies whether a sequence number is still the latest', () => {
    const guard = new RequestSequenceGuard();
    const req1 = guard.next();
    expect(guard.isLatest(req1)).toBe(true);

    const req2 = guard.next();
    // req1 is now stale
    expect(guard.isLatest(req1)).toBe(false);
    expect(guard.isLatest(req2)).toBe(true);
  });

  it('drops out-of-order responses in simulated rapid double-drop scenario', async () => {
    const guard = new RequestSequenceGuard();
    let appliedData: string | null = null;

    // Simulate Drop 1 (takes 100ms)
    const seq1 = guard.next();
    const drop1Promise = new Promise<void>((resolve) => {
      setTimeout(() => {
        if (guard.isLatest(seq1)) {
          appliedData = 'drop1-data';
        }
        resolve();
      }, 100);
    });

    // Simulate Drop 2 dispatched 20ms later (takes only 30ms)
    await new Promise((r) => setTimeout(r, 20));
    const seq2 = guard.next();
    const drop2Promise = new Promise<void>((resolve) => {
      setTimeout(() => {
        if (guard.isLatest(seq2)) {
          appliedData = 'drop2-data';
        }
        resolve();
      }, 30);
    });

    await Promise.all([drop1Promise, drop2Promise]);

    // Drop 2 must be the final applied state, drop 1 must be ignored
    expect(appliedData).toBe('drop2-data');
  });

  it('resets cleanly', () => {
    const guard = new RequestSequenceGuard();
    guard.next();
    guard.next();
    guard.reset();
    expect(guard.current()).toBe(0);
  });
});
