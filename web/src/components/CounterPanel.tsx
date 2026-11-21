import React from 'react';
import { RecomputeStatus } from '../utils/recomputeStatus';

interface CounterPanelProps {
  totalUnservedPop: number;
  newlyCoveredPop: number;
  candidateCount: number;
  showModeled: boolean;
  onToggleBeforeAfter: () => void;
  onResetCandidates: () => void;
  recomputeStatus: RecomputeStatus;
  recomputeError: string | null;
  onManualRecompute: () => void;
}

export const CounterPanel: React.FC<CounterPanelProps> = ({
  totalUnservedPop,
  newlyCoveredPop,
  candidateCount,
  showModeled,
  onToggleBeforeAfter,
  onResetCandidates,
  recomputeStatus,
  recomputeError,
  onManualRecompute,
}) => {
  const isLoading = recomputeStatus === 'loading' || recomputeStatus === 'slow';
  const isSlow = recomputeStatus === 'slow';
  const isEmpty = recomputeStatus === 'empty';
  const hasError = !!recomputeError;

  return (
    <div className="counter-panel">
      <div className="metric-box">
        <div className="metric-label">Unserved Population</div>
        <div className="metric-value-row">
          <span className={`metric-number unserved ${isLoading ? 'dimmed' : ''}`}>
            {totalUnservedPop.toLocaleString()}
          </span>
          <span className="metric-sublabel">residents in gap</span>
          {hasError && <span className="metric-stale-tag">from previous result</span>}
        </div>
      </div>

      <div className="metric-box highlight">
        <div className="metric-label">Newly Covered (Modeled)</div>
        <div className="metric-value-row">
          <span className={`metric-number covered ${isLoading ? 'dimmed' : ''}`}>
            +{newlyCoveredPop.toLocaleString()}
          </span>
          {hasError && <span className="metric-stale-tag">from previous result</span>}
          {!hasError && newlyCoveredPop > 0 && (
            <span className="badge-positive">
              {((newlyCoveredPop / (totalUnservedPop + newlyCoveredPop)) * 100).toFixed(1)}% gap reduction
            </span>
          )}
        </div>
      </div>

      <div className="metric-box">
        <div className="metric-label">Active Candidate Sites</div>
        <div className="metric-value-row">
          <span className={`metric-number candidates ${isLoading ? 'dimmed' : ''}`}>{candidateCount}</span>
          <span className="metric-sublabel">towers evaluated</span>
        </div>
      </div>

      {isLoading && (
        <div className="counter-loading-pill" role="status">
          <span className="loading-spinner-small"></span>
          <span>{isSlow ? 'Still computing, this is taking longer than usual...' : 'Recomputing...'}</span>
        </div>
      )}

      {isEmpty && !isLoading && !hasError && (
        <div className="empty-coverage-note" role="note">
          This position adds no new coverage.
        </div>
      )}

      <div className="panel-actions">
        <button
          onClick={onToggleBeforeAfter}
          className={`btn-toggle ${showModeled ? 'active-after' : 'active-before'}`}
          title="Toggle between pristine baseline and modeled candidate footprint"
        >
          {showModeled ? 'Viewing: After (What-If)' : 'Viewing: Before (Baseline)'}
        </button>

        <button
          onClick={onManualRecompute}
          disabled={isLoading}
          className="btn-primary"
          title="Recalculate signal across pilot cells"
        >
          {isLoading ? 'Computing...' : 'Recalculate'}
        </button>

        <button
          onClick={onResetCandidates}
          className="btn-icon"
          title="Reset candidate towers to recommended positions"
        >
          Reset Sites
        </button>
      </div>
    </div>
  );
};
