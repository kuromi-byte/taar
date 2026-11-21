import React from 'react';

interface LimitationsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LimitationsModal: React.FC<LimitationsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <span className="badge-caution">HONEST BOUNDARIES</span>
            <h2 className="modal-title">Methodology &amp; Engineering Limitations</h2>
          </div>
          <button onClick={onClose} className="modal-close-btn">&times;</button>
        </div>

        <div className="modal-body">
          <p className="modal-intro">
            The <strong>Rural Coverage Gap Mapper (Gap-to-Brief)</strong> is designed as a rapid screening and triage tool
            for state planners and policy analysts. It is <strong>NOT</strong> an RF drive-test system or an authoritative tower siting decider.
          </p>

          <div className="limitations-grid">
            <div className="limit-card">
              <h4>1. Modeled Signal, Not Physical Measurement</h4>
              <p>
                Signal strength is calculated using standard Okumura/COST-231 Hata empirical path loss combined with a
                720-ray polar sweep elevation analysis over 30m DEM terrain. Actual local clutter (dense foliage, plantation canopy,
                concrete structures) is not captured in open DEM data.
              </p>
            </div>

            <div className="limit-card">
              <h4>2. OpenCellID is a Lower Bound</h4>
              <p>
                Towers are sourced from crowd-sourced OpenCellID datasets, which tend to be concentrated along highways and urban centers.
                Areas without recorded towers are conservatively labeled <em>Unknown</em> or treated as potential gaps, not definitive dead zones.
              </p>
            </div>

            <div className="limit-card">
              <h4>3. Empirical Error Band (&plusmn;5 to 11 dB)</h4>
              <p>
                Published academic studies evaluating Hata and knife-edge diffraction in complex topography document standard errors
                ranging from 5 to 11 dB. To reflect this honestly, cells within &plusmn;6 dB of the threshold (-100 dBm) are explicitly colored
                as <strong>Uncertain</strong> rather than false green or red.
              </p>
            </div>

            <div className="limit-card">
              <h4>4. Siting Decisions Require Ground Truth</h4>
              <p>
                Real telecommunication tower placement depends on physical land acquisition, reliable 3-phase grid power or solar feasibility,
                and fiber/microwave backhaul rights-of-way. This tool produces a <strong>prioritized shortlist for field survey dispatch</strong>.
              </p>
            </div>
          </div>

          <div className="modal-callout">
            <strong>Key takeaway for reviewers &amp; judges:</strong>
            <br />
            Our goal is not to pretend open data replaces telco RF engineering suites. Our goal is to solve the
            <em>"Where do we send the survey team first and how do we justify the budget?"</em> problem with complete mathematical transparency.
          </div>
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn-primary">
            Acknowledge &amp; Return to Map
          </button>
        </div>
      </div>
    </div>
  );
};
