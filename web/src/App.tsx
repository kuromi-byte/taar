import React from 'react';
import { Map } from './components/Map';
import { DATA_CONFIG } from './config/data';
import { params } from './config/params';

export const App: React.FC = () => {
  return (
    <div className="app-container">
      <header
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          zIndex: 10,
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '10px 16px',
          borderRadius: '8px',
          border: '1px solid #334155',
          backdropFilter: 'blur(4px)',
        }}
      >
        <h1 style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
          Gap-to-Brief | {DATA_CONFIG.pilot.name}
        </h1>
        <p style={{ fontSize: '12px', color: '#94a3b8', margin: '4px 0 0 0' }}>
          Threshold: {params.gap_threshold_dbm} dBm (±{params.uncertain_band_db} dB) | Max Radius:{' '}
          {params.max_radius_km} km
        </p>
      </header>
      <Map />
    </div>
  );
};

export default App;
