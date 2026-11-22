// /web/src/utils/requestSequence.ts
// Request sequence counter / guard to drop out-of-order stale async API responses

export class RequestSequenceGuard {
  private latestSeq = 0;

  /**
   * Generates a new monotonically increasing request sequence number.
   */
  public next(): number {
    return ++this.latestSeq;
  }

  /**
   * Returns true if the given sequence number is still the latest active request.
   * If a newer request was dispatched in the meantime, returns false.
   */
  public isLatest(seq: number): boolean {
    return seq === this.latestSeq;
  }

  /**
   * Gets the current sequence counter.
   */
  public current(): number {
    return this.latestSeq;
  }

  /**
   * Resets the sequence counter.
   */
  public reset(): void {
    this.latestSeq = 0;
  }
}
