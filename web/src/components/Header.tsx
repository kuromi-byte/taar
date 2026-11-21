import React from 'react';
import { DATA_CONFIG } from '../config/data';
import { params } from '../config/params';

interface HeaderProps {
  onOpenLimitations: () => void;
  apiConnected: boolean;
  isMockData?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onOpenLimitations, apiConnected, isMockData }) => {
  return (
    <>
      {isMockData && (
        <div className="mock-data-banner" role="alert">
          <span className="mock-badge-tag">MOCK DATA</span>
          <span>Synthetic mock cells loaded (meta.source == "mock"). Results do not represent real terrain/RF propagation.</span>
        </div>
      )}

      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo-badge">GB</div>
          <div>
            <div className="brand-title-row">
              <h1 className="brand-title">Gap-to-Brief</h1>
              <span className="pilot-tag">{DATA_CONFIG.pilot.name}</span>
              <button
                onClick={onOpenLimitations}
                className="modeled-badge-btn"
                title="Click to view modeling methodology and limitations"
              >
                <span className="modeled-badge-dot"></span>
                Modeled, not measured
              </button>
            </div>
            <p className="brand-subtitle">
              Rural Coverage Screening &amp; Siting Tool | Center: 12.95°N, 75.775°E | EPSG:32643
            </p>
          </div>
        </div>

        <div className="header-actions">
          <div className="threshold-pill">
            <span className="pill-label">Threshold:</span>
            <span className="pill-value">{params.gap_threshold_dbm} dBm</span>
            <span className="pill-sub">(&plusmn;{params.uncertain_band_db} dB uncertain band)</span>
          </div>

          <div
            className={`api-status-badge ${apiConnected ? 'online' : 'offline'}`}
            title={apiConnected ? 'API Connected (FastAPI @ localhost:8000)' : 'API Disconnected (Offline / Local Mode)'}
          >
            <span className="status-dot"></span>
            <span>{apiConnected ? 'API Online' : 'Offline Mode'}</span>
          </div>

          <button onClick={onOpenLimitations} className="btn-secondary" title="View Methods and Honest Limitations">
            Methodology &amp; Limits
          </button>
        </div>
      </header>
    </>
  );
};
