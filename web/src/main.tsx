import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import './index.css';
import 'maplibre-gl/dist/maplibre-gl.css';

// Dev-only benchmark hook: tree-shaken from production build
if (import.meta.env.DEV && typeof window !== 'undefined' && window.location.search.includes('bench=1')) {
  import('./dev/bench');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
