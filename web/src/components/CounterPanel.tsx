import React from 'react';

interface CounterPanelProps {
  totalUnservedPop: number;
  newlyCoveredPop: number;
  candidateCount: number;
  showModeled: boolean;
  onToggleBeforeAfter: () => void;
  onResetCandidates: () => void;
  isRecomputing: boolean;
  onManualRecompute: () => void;
}

export const CounterPanel: React.FC<CounterPanelProps> = ({
  totalUnservedPop,
  newlyCoveredPop,
  candidateCount,
  showModeled,
  onToggleBeforeAfter,
  onResetCandidates,
  isRecomputing,
  onManualRecompute,
}) => {
  return (
    <div className="counter-panel">
      <div className="metric-box">
        <div className="metric-label">Unserved Population</div>
        <div className="metric-value-row">
          <span className="metric-number unserved">
            {totalUnservedPop.toLocaleString()}
          </span>
          <span className="metric-sublabel">residents in gap</span>
        </div>
      </div>

      <div className="metric-box highlight">
        <div className="metric-label">Newly Covered (Modeled)</div>
        <div className="metric-value-row">
          <span className="metric-number covered">
            +{newlyCoveredPop.toLocaleString()}
          </span>
          {newlyCoveredPop > 0 && (
            <span className="badge-positive">
              {((newlyCoveredPop / (totalUnservedPop + newlyCoveredPop)) * 100).toFixed(1)}% gap reduction
            </span>
          )}
        </div>
      </div>

      <div className="metric-box">
        <div className="metric-label">Active Candidate Sites</div>
        <div className="metric-value-row">
          <span className="metric-number candidates">{candidateCount}</span>
          <span className="metric-sublabel">towers evaluated</span>
        </div>
      </div>

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
          disabled={isRecomputing}
          className="btn-primary"
          title="Recalculate signal across pilot cells"
        >
          {isRecomputing ? 'Computing...' : 'Recalculate'}
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
