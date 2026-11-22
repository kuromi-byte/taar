// /web/src/utils/recomputeStatus.ts
// Recompute status state machine: idle -> loading -> slow -> success | error | empty

import { DATA_CONFIG } from '../config/data';

export type RecomputeStatus =
  | 'idle'
  | 'loading'
  | 'slow'
  | 'success'
  | 'error'
  | 'empty';

export type StatusListener = (status: RecomputeStatus) => void;

export interface StateMachineOptions {
  slowMs?: number;
  timeoutMs?: number;
  onTimeout?: (seq: number) => void;
}

export class RecomputeStateMachine {
  private status: RecomputeStatus = 'idle';
  private currentSeq = 0;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;
  private timeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private listeners: Set<StatusListener> = new Set();

  constructor(private defaultSlowMs = DATA_CONFIG.SLOW_MS, private defaultTimeoutMs = DATA_CONFIG.TIMEOUT_MS) {}

  public getStatus(): RecomputeStatus {
    return this.status;
  }

  public getSeq(): number {
    return this.currentSeq;
  }

  public subscribe(listener: StatusListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private setStatus(newStatus: RecomputeStatus): void {
    this.status = newStatus;
    this.listeners.forEach((fn) => fn(newStatus));
  }

  public clearTimers(): void {
    if (this.slowTimer) {
      clearTimeout(this.slowTimer);
      this.slowTimer = null;
    }
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }
  }

  /**
   * Starts a new recompute request sequence.
   * Cancels in-flight timers from any previous sequence.
   */
  public start(seq: number, options?: StateMachineOptions): void {
    this.clearTimers();
    this.currentSeq = seq;
    this.setStatus('loading');

    const slowMs = options?.slowMs ?? this.defaultSlowMs;
    const timeoutMs = options?.timeoutMs ?? this.defaultTimeoutMs;

    this.slowTimer = setTimeout(() => {
      if (this.currentSeq === seq && this.status === 'loading') {
        this.setStatus('slow');
      }
    }, slowMs);

    this.timeoutTimer = setTimeout(() => {
      if (this.currentSeq === seq && (this.status === 'loading' || this.status === 'slow')) {
        this.setStatus('error');
        if (options?.onTimeout) {
          options.onTimeout(seq);
        }
      }
    }, timeoutMs);
  }

  /**
   * Handles successful response for a given sequence.
   * Empty footprint (changedCount === 0) transitions to 'empty'.
   * Otherwise transitions to 'success'.
   */
  public success(seq: number, changedCount: number): boolean {
    if (seq !== this.currentSeq) {
      return false; // Stale sequence ignored
    }
    this.clearTimers();
    if (changedCount === 0) {
      this.setStatus('empty');
    } else {
      this.setStatus('success');
    }
    return true;
  }

  /**
   * Handles an error for a given sequence.
   */
  public error(seq: number): boolean {
    if (seq !== this.currentSeq) {
      return false; // Stale sequence ignored
    }
    this.clearTimers();
    this.setStatus('error');
    return true;
  }

  /**
   * Resets the machine to idle.
   */
  public reset(): void {
    this.clearTimers();
    this.setStatus('idle');
  }
}
