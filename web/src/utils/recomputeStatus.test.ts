import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RecomputeStateMachine } from './recomputeStatus';

describe('RecomputeStateMachine', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts in idle status', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    expect(sm.getStatus()).toBe('idle');
  });

  it('transitions to loading on start', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    sm.start(1);
    expect(sm.getStatus()).toBe('loading');
  });

  it('transitions to slow after SLOW_MS (1500 ms)', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    sm.start(1);
    expect(sm.getStatus()).toBe('loading');

    vi.advanceTimersByTime(1499);
    expect(sm.getStatus()).toBe('loading');

    vi.advanceTimersByTime(2);
    expect(sm.getStatus()).toBe('slow');
  });

  it('transitions to error after TIMEOUT_MS (15000 ms) and calls onTimeout', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    const onTimeout = vi.fn();
    sm.start(1, { onTimeout });

    vi.advanceTimersByTime(1500);
    expect(sm.getStatus()).toBe('slow');

    vi.advanceTimersByTime(13500);
    expect(sm.getStatus()).toBe('error');
    expect(onTimeout).toHaveBeenCalledWith(1);
  });

  it('transitions to success on successful response with non-empty changed', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    sm.start(1);
    vi.advanceTimersByTime(500);

    const handled = sm.success(1, 45);
    expect(handled).toBe(true);
    expect(sm.getStatus()).toBe('success');

    // Ensure timers are cancelled
    vi.advanceTimersByTime(20000);
    expect(sm.getStatus()).toBe('success');
  });

  it('transitions to empty when changedCount is 0', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    sm.start(1);

    const handled = sm.success(1, 0);
    expect(handled).toBe(true);
    expect(sm.getStatus()).toBe('empty');

    vi.advanceTimersByTime(20000);
    expect(sm.getStatus()).toBe('empty');
  });

  it('transitions to error on explicit error()', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    sm.start(1);

    const handled = sm.error(1);
    expect(handled).toBe(true);
    expect(sm.getStatus()).toBe('error');

    vi.advanceTimersByTime(20000);
    expect(sm.getStatus()).toBe('error');
  });

  it('cancels older request timers when a newer request starts', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    const onTimeout1 = vi.fn();
    const onTimeout2 = vi.fn();

    // Start request 1
    sm.start(1, { onTimeout: onTimeout1 });
    vi.advanceTimersByTime(1000);
    expect(sm.getStatus()).toBe('loading');

    // Start request 2 before request 1 completes
    sm.start(2, { onTimeout: onTimeout2 });
    expect(sm.getStatus()).toBe('loading');

    // Stale response from request 1 is rejected and ignored
    const staleResult = sm.success(1, 10);
    expect(staleResult).toBe(false);
    expect(sm.getStatus()).toBe('loading'); // Stays loading for request 2

    // Advance 600 ms (request 1 would have been 1600ms, but request 2 is only at 600ms)
    vi.advanceTimersByTime(600);
    expect(sm.getStatus()).toBe('loading'); // Not slow yet for request 2

    // Advance another 950 ms (request 2 reaches 1550ms -> slow)
    vi.advanceTimersByTime(950);
    expect(sm.getStatus()).toBe('slow');

    // Request 2 completes successfully
    sm.success(2, 5);
    expect(sm.getStatus()).toBe('success');

    // Advance past timeout: neither onTimeout should be called
    vi.advanceTimersByTime(20000);
    expect(onTimeout1).not.toHaveBeenCalled();
    expect(onTimeout2).not.toHaveBeenCalled();
  });

  it('notifies subscribers on status change', () => {
    const sm = new RecomputeStateMachine(1500, 15000);
    const history: string[] = [];
    sm.subscribe((st) => history.push(st));

    sm.start(1);
    vi.advanceTimersByTime(1500);
    sm.success(1, 10);

    expect(history).toEqual(['loading', 'slow', 'success']);
  });
});
