import React from 'react';
import { Candidate, Cluster } from '../types/contracts';
import { DATA_CONFIG } from '../config/data';
import { params } from '../config/params';

interface BriefModalProps {
  cluster: Cluster | null;
  candidates: Candidate[];
  onClose: () => void;
}

export const BriefModal: React.FC<BriefModalProps> = ({ cluster, candidates, onClose }) => {
  if (!cluster) return null;

  const clusterCandidates = candidates.filter((c) => c.cluster_id === cluster.id);
  const needsSurvey = !cluster.candidate_ids || cluster.candidate_ids.length === 0;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="brief-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="brief-actions-bar no-print">
          <div className="brief-action-hint">One-Page Executive Briefing Document</div>
          <div className="brief-action-buttons">
            <button onClick={handlePrint} className="btn-primary">
              Print / Save as PDF
            </button>
            <button onClick={onClose} className="btn-secondary">
              Close
            </button>
          </div>
        </div>

        {/* Printable Document Sheet */}
        <div className="brief-sheet printable-area">
          <div className="brief-header">
            <div className="brief-header-meta">
              <span className="gov-seal">DIGITAL BHARAT NIDHI / STATE IT SCREENING BRIEF</span>
              <span className="brief-date">{new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}</span>
            </div>
            <h2 className="brief-title">Rural Mobile Network Coverage Gap &amp; Tower Recommendation Brief</h2>
            <div className="brief-subheading">
              <strong>Pilot Taluk:</strong> {DATA_CONFIG.pilot.name} | <strong>District:</strong> Hassan, Karnataka | <strong>CRS:</strong> EPSG:32643
            </div>
          </div>

          <div className="brief-section">
            <h3 className="section-title">1. Cluster Profile &amp; Population Gap</h3>
            <div className="profile-grid">
              <div className="profile-card">
                <span className="label">Cluster Reference</span>
                <span className="val">{cluster.id}: {cluster.name_hint || 'Rural Settlement Cluster'}</span>
              </div>
              <div className="profile-card">
                <span className="label">Unserved Gap Population</span>
                <span className="val highlight-danger">{cluster.pop_in_gap.toLocaleString()} people</span>
              </div>
              <div className="profile-card">
                <span className="label">Analyzed 300m Cells</span>
                <span className="val">{cluster.cell_ids.length} cells (&lt; {params.gap_threshold_dbm} dBm)</span>
              </div>
              <div className="profile-card">
                <span className="label">Target Hamlets</span>
                <span className="val">{cluster.villages ? cluster.villages.join(', ') : 'Sakleshpur rural fringe'}</span>
              </div>
            </div>
            {cluster.terrain_summary && (
              <p className="terrain-note">
                <strong>Terrain Context:</strong> {cluster.terrain_summary}
              </p>
            )}
          </div>

          <div className="brief-section">
            <h3 className="section-title">2. Prioritized Site Recommendations &amp; Feasibility Flags</h3>
            {needsSurvey ? (
              <div className="brief-warning-box">
                <h4>Recommendation: Field Survey Required (No Viable Automated Siting)</h4>
                <p>
                  This cluster is situated in steep Western Ghats terrain where slope exceeds 15° and distance to
                  the nearest motorable road exceeds 1.5 km. None of the automated candidate points satisfied the mandatory
                  feasibility screening criteria.
                </p>
                <p>
                  <strong>Next Action:</strong> Dispatch a field survey team to evaluate decentralized small-cell options,
                  solar micro-power backup, or ridge-line relay masts not accessible via standard vehicular roads.
                </p>
              </div>
            ) : (
              <>
                <table className="brief-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Site ID</th>
                      <th>Coordinates (WGS84)</th>
                      <th>Added Pop</th>
                      <th>Road Dist (km)</th>
                      <th>Slope (deg)</th>
                      <th>Backhaul Feasibility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clusterCandidates.map((c, idx) => (
                      <tr key={c.id}>
                        <td><strong>#{idx + 1}</strong></td>
                        <td className="font-semibold">{c.id}</td>
                        <td className="text-mono">{c.lat.toFixed(5)}°N, {c.lon.toFixed(5)}°E</td>
                        <td className="font-bold text-success">+{c.added_pop.toLocaleString()}</td>
                        <td>{c.flags.road_km.toFixed(2)} km</td>
                        <td>{c.flags.slope_deg.toFixed(1)}°</td>
                        <td>{c.flags.backhaul}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="justification-list">
                  <h4>Site Justifications:</h4>
                  {clusterCandidates.map((c) => (
                    <div key={c.id} className="justification-item">
                      <strong>{c.id}:</strong> {c.why}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="brief-section">
            <h3 className="section-title">3. Model Configuration &amp; Baseline Assumptions</h3>
            <div className="assumptions-table">
              <div className="assumption-row">
                <span>Propagation Model:</span>
                <span>Okumura / COST-231 Hata (900 MHz baseline) with 30m Polar Sweep Raycasting</span>
              </div>
              <div className="assumption-row">
                <span>Assumed Macrocell Specs:</span>
                <span>Tower Height 30.0m (assumed) | EIRP 43.0 dBm (20W) | Rx Height 1.5m</span>
              </div>
              <div className="assumption-row">
                <span>Terrain Obstruction Penalty:</span>
                <span>15.0 dB flat shadow diffraction penalty applied to line-of-sight obstructed cells</span>
              </div>
              <div className="assumption-row">
                <span>Threshold &amp; Uncertainty:</span>
                <span>Gap threshold -100.0 dBm | Uncertainty margin &plusmn;6.0 dB</span>
              </div>
            </div>
          </div>

          <div className="brief-section limitations-box">
            <h3 className="section-title text-danger">4. Transparent Methodological Boundaries &amp; Limitations</h3>
            <ul className="limits-list">
              <li>
                <strong>Modeled, Not Measured:</strong> Signal power is mathematically estimated using standard propagation models
                and 30m Copernicus/SRTM DEM elevation data. It does not replace real-world RF drive testing.
              </li>
              <li>
                <strong>OpenCellID Baseline as Lower Bound:</strong> Existing tower evidence is sourced from OpenCellID crowd-sourced logs.
                Uncovered cells with missing nearby tower records are treated as Unknown/Uncertain, not confirmed dead zones.
              </li>
              <li>
                <strong>Expected Model Error Band:</strong> Published literature across similar hilly terrains indicates empirical error
                bands between 5 to 11 dB. Field validation in Hassan district has not yet been conducted.
              </li>
              <li>
                <strong>Triage Screening Only:</strong> Land tenure, power grid stability, and fiber rights-of-way cannot be determined from
                open geospatial data. This report serves solely as a screening triage shortlist for dispatching field survey personnel.
              </li>
            </ul>
          </div>

          <div className="brief-footer">
            <span>Rural Coverage Gap Mapper (Gap-to-Brief) | Hackathon Submission 2026</span>
            <span>Page 1 of 1</span>
          </div>
        </div>
      </div>
    </div>
  );
};
