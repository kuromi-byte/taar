import React, { useState } from 'react';
import { Candidate, Cluster } from '../types/contracts';

interface ShortlistTableProps {
  candidates: Candidate[];
  clusters: Cluster[];
  selectedCandidateId: string | number | null;
  selectedClusterId: string | number | null;
  onSelectCandidate: (candidate: Candidate) => void;
  onSelectCluster: (cluster: Cluster) => void;
  onGenerateBrief: (cluster: Cluster) => void;
}

export const ShortlistTable: React.FC<ShortlistTableProps> = ({
  candidates,
  clusters,
  selectedCandidateId,
  selectedClusterId,
  onSelectCandidate,
  onSelectCluster,
  onGenerateBrief,
}) => {
  const [activeTab, setActiveTab] = useState<'candidates' | 'clusters'>('candidates');

  return (
    <div className="shortlist-container">
      <div className="shortlist-tabs">
        <button
          className={`tab-btn ${activeTab === 'candidates' ? 'active' : ''}`}
          onClick={() => setActiveTab('candidates')}
        >
          Ranked Sites ({candidates.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'clusters' ? 'active' : ''}`}
          onClick={() => setActiveTab('clusters')}
        >
          Gap Clusters ({clusters.length})
        </button>
      </div>

      <div className="shortlist-content">
        {activeTab === 'candidates' ? (
          <div className="table-responsive">
            <table className="shortlist-table">
              <thead>
                <tr>
                  <th style={{ width: '45px' }}>Rank</th>
                  <th>Site ID</th>
                  <th>Target Cluster</th>
                  <th>+Added Pop</th>
                  <th>Road (km)</th>
                  <th>Slope (°)</th>
                  <th>Backhaul</th>
                  <th>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c, idx) => {
                  const isSelected = selectedCandidateId === c.id;
                  const roadFlag = c.flags.road_km > 0.7;
                  const slopeFlag = c.flags.slope_deg > 10.0;

                  return (
                    <tr
                      key={c.id}
                      className={`candidate-row ${isSelected ? 'selected' : ''}`}
                      onClick={() => onSelectCandidate(c)}
                      title="Click to zoom to site on map"
                    >
                      <td className="rank-cell">#{idx + 1}</td>
                      <td className="font-semibold text-accent">{c.id}</td>
                      <td>
                        <span className="cluster-tag">
                          {c.cluster_id}
                        </span>
                      </td>
                      <td className="pop-cell font-bold text-success">
                        +{c.added_pop.toLocaleString()}
                      </td>
                      <td>
                        <span className={`flag-badge ${roadFlag ? 'warning' : 'good'}`}>
                          {c.flags.road_km.toFixed(2)} km
                        </span>
                      </td>
                      <td>
                        <span className={`flag-badge ${slopeFlag ? 'warning' : 'good'}`}>
                          {c.flags.slope_deg.toFixed(1)}°
                        </span>
                      </td>
                      <td className="text-muted text-xs">{c.flags.backhaul}</td>
                      <td className="why-cell text-xs text-muted" title={c.why}>
                        {c.why}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="clusters-list">
            {clusters.map((cl) => {
              const isSelected = selectedClusterId === cl.id;
              const needsSurvey = !cl.candidate_ids || cl.candidate_ids.length === 0;

              return (
                <div
                  key={cl.id}
                  className={`cluster-card ${isSelected ? 'selected' : ''} ${needsSurvey ? 'needs-survey' : ''}`}
                  onClick={() => onSelectCluster(cl)}
                >
                  <div className="cluster-header">
                    <div>
                      <span className="cluster-id-badge">{cl.id}</span>
                      <strong className="cluster-name">{cl.name_hint || `Cluster ${cl.id}`}</strong>
                    </div>
                    {needsSurvey ? (
                      <span className="badge-survey-required">Needs Field Survey</span>
                    ) : (
                      <span className="badge-viable">
                        {cl.candidate_ids.length} Site{cl.candidate_ids.length > 1 ? 's' : ''} Recommended
                      </span>
                    )}
                  </div>

                  <div className="cluster-details">
                    <div className="detail-item">
                      <span className="label">Unserved Gap Population:</span>
                      <span className="value font-bold text-danger">{cl.pop_in_gap.toLocaleString()}</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">Cells:</span>
                      <span className="value">{cl.cell_ids.length} (300m cells)</span>
                    </div>
                    {cl.villages && (
                      <div className="detail-item">
                        <span className="label">Hamlets:</span>
                        <span className="value text-muted">{cl.villages.join(', ')}</span>
                      </div>
                    )}
                  </div>

                  {needsSurvey && (
                    <div className="survey-warning-box">
                      <strong>Survey Justification:</strong> Slopes exceed 15° and nearest road is &gt;1.5 km.
                      No standard macrocell passed automated feasibility filters. Requires physical site survey team for small-cell / solar mast scouting.
                    </div>
                  )}

                  <div className="cluster-actions">
                    <button
                      className="btn-brief"
                      onClick={(e) => {
                        e.stopPropagation();
                        onGenerateBrief(cl);
                      }}
                      title="Generate official one-page briefing document"
                    >
                      Generate Cluster Brief
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
