import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, Marker, Popup } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { DATA_CONFIG } from '../config/data';
import { Candidate, Town } from '../types/contracts';

interface ExistingTower {
  id: number | string;
  name?: string;
  lat: number;
  lon: number;
  height_m?: number;
  power_dbm?: number;
  assumed?: boolean;
  radio?: string;
}

interface MapProps {
  candidates: Candidate[];
  selectedCandidateId: string | number | null;
  onCandidateMove: (id: string | number, lat: number, lon: number) => void;
  onSelectCandidate: (id: string | number) => void;
  overriddenDbmMap: Map<number, number>;
  showModeled: boolean;
  flyToTarget: { lat: number; lon: number } | null;
}

export const CoverageMap: React.FC<MapProps> = ({
  candidates,
  selectedCandidateId,
  onCandidateMove,
  onSelectCandidate,
  overriddenDbmMap,
  showModeled,
  flyToTarget,
}) => {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const candidateMarkersRef = useRef<globalThis.Map<string | number, Marker>>(new globalThis.Map());
  const existingMarkersRef = useRef<Marker[]>([]);
  const townMarkersRef = useRef<Marker[]>([]);
  const previousOverriddenRef = useRef<Set<number>>(new Set());
  const [mapLoaded, setMapLoaded] = useState(false);
  const [webGlSupported, setWebGlSupported] = useState(true);

  // 1. Initialize MapLibre GL
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const isWebGLAvailable = () => {
      try {
        const canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch {
        return false;
      }
    };

    if (!isWebGLAvailable()) {
      console.warn('MapLibre GL is not supported: WebGL is disabled or unavailable.');
      setWebGlSupported(false);
      return;
    }

    try {
      // 100% Offline Blank Dark Style Specification (no external network or font glyphs)
      const offlineDarkStyle: maplibregl.StyleSpecification = {
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: {
              'background-color': '#090d16', // Deep slate dark background
            },
          },
        ],
      };

      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: offlineDarkStyle,
        center: DATA_CONFIG.pilot.center,
        zoom: DATA_CONFIG.pilot.zoom,
        attributionControl: false,
      });

      mapRef.current = map;

      map.on('load', () => {
      const [minLon, minLat, maxLon, maxLat] = DATA_CONFIG.pilot.bbox;

      // 1a. Boundary Layer (Taluk pilot border)
      map.addSource('pilot-boundary', {
        type: 'geojson',
        data: DATA_CONFIG.paths.basemapBoundary,
      });

      map.addLayer({
        id: 'pilot-boundary-fill',
        type: 'fill',
        source: 'pilot-boundary',
        paint: {
          'fill-color': '#111827',
          'fill-opacity': 0.4,
        },
      });

      map.addLayer({
        id: 'pilot-boundary-line',
        type: 'line',
        source: 'pilot-boundary',
        paint: {
          'line-color': '#38bdf8',
          'line-width': 1.5,
          'line-dasharray': [3, 2],
        },
      });

      // 1b. Roads Layer (Simplified OSM roads)
      map.addSource('osm-roads', {
        type: 'geojson',
        data: DATA_CONFIG.paths.basemapRoads,
      });

      map.addLayer({
        id: 'osm-roads-line',
        type: 'line',
        source: 'osm-roads',
        paint: {
          'line-color': '#334155',
          'line-width': 1.2,
          'line-opacity': 0.7,
        },
      });

      // 1c. Cells GeoJSON Layer (300m population cells)
      map.addSource('cells', {
        type: 'geojson',
        data: DATA_CONFIG.paths.cells,
      });

      // Data-driven color expression using feature-state 'dbm' if set, else baseline_dbm
      map.addLayer({
        id: 'cells-fill',
        type: 'fill',
        source: 'cells',
        paint: {
          'fill-color': [
            'case',
            ['>=', ['coalesce', ['feature-state', 'dbm'], ['get', 'baseline_dbm']], -94.0],
            '#10b981', // Emerald green: Likely covered
            ['>=', ['coalesce', ['feature-state', 'dbm'], ['get', 'baseline_dbm']], -106.0],
            '#f59e0b', // Amber: Uncertain band (+/- 6 dB around -100 dBm)
            '#ef4444', // Red: Likely gap
          ],
          'fill-opacity': 0.65,
        },
      });

      map.addLayer({
        id: 'cells-line',
        type: 'line',
        source: 'cells',
        paint: {
          'line-color': '#0f172a',
          'line-width': 0.5,
          'line-opacity': 0.5,
        },
      });

      // Cell click popup
      map.on('click', 'cells-fill', (e) => {
        if (!e.features || e.features.length === 0) return;
        const feat = e.features[0];
        const props = feat.properties || {};
        const cellId = feat.id;
        const pop = props.pop || 'N/A';
        const baseDbm = props.baseline_dbm !== undefined ? `${props.baseline_dbm} dBm` : 'Unknown';
        const state = props.state || 'Unknown';

        new Popup({ closeButton: true, className: 'dark-popup' })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div class="map-popup-card">
              <div class="popup-title">Cell ID: ${cellId}</div>
              <div class="popup-item"><span>Population:</span> <strong>${pop} residents</strong></div>
              <div class="popup-item"><span>Baseline Signal:</span> <strong>${baseDbm}</strong></div>
              <div class="popup-item"><span>Modeled State:</span> <strong class="state-${String(state).toLowerCase().replace(' ', '-')}">${state}</strong></div>
            </div>`
          )
          .addTo(map);
      });

      // Mouse pointer style on hover
      map.on('mouseenter', 'cells-fill', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'cells-fill', () => {
        map.getCanvas().style.cursor = '';
      });

      // Fit to pilot bbox
      map.fitBounds(
        [
          [minLon, minLat],
          [maxLon, maxLat],
        ],
        { padding: 40, duration: 0 }
      );

      setMapLoaded(true);
    });
    } catch (err) {
      console.error('Failed to initialize MapLibre GL:', err);
      setWebGlSupported(false);
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // 2. Load Existing Towers and Towns
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const map = mapRef.current;

    // Load Existing Towers
    fetch(DATA_CONFIG.paths.towers)
      .then((res) => res.json())
      .then((towers: ExistingTower[]) => {
        existingMarkersRef.current.forEach((m) => m.remove());
        existingMarkersRef.current = [];

        towers.forEach((t) => {
          const el = document.createElement('div');
          el.className = 'existing-tower-marker';
          el.innerHTML = `
            <div class="tower-icon-wrapper">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v20M2 20h20M7 8l5-6 5 6M6 14l6-6 6 6M4 20l8-8 8 8"/>
              </svg>
            </div>
          `;

          const popup = new Popup({ offset: 15, className: 'dark-popup' }).setHTML(
            `<div class="map-popup-card">
              <div class="popup-title">Existing Macro Tower</div>
              <div class="popup-item"><span>Site Name:</span> <strong>${t.name || `Tower ${t.id}`}</strong></div>
              <div class="popup-item"><span>Radio/Tech:</span> <strong>${t.radio || 'LTE (Macro)'}</strong></div>
              <div class="popup-item"><span>Height:</span> <strong>${t.height_m || 30.0}m (assumed)</strong></div>
              <div class="popup-item"><span>Power:</span> <strong>${t.power_dbm || 43.0} dBm (20W)</strong></div>
              <div class="popup-item"><span>Location:</span> <strong>${t.lat.toFixed(4)}°N, ${t.lon.toFixed(4)}°E</strong></div>
            </div>`
          );

          const marker = new Marker({ element: el })
            .setLngLat([t.lon, t.lat])
            .setPopup(popup)
            .addTo(map);

          existingMarkersRef.current.push(marker);
        });
      })
      .catch((err) => console.error('Error loading towers:', err));

    // Load Towns for orientation
    fetch(DATA_CONFIG.paths.towns)
      .then((res) => res.json())
      .then((towns: Town[]) => {
        townMarkersRef.current.forEach((m) => m.remove());
        townMarkersRef.current = [];

        towns.forEach((tn) => {
          const el = document.createElement('div');
          el.className = 'town-marker-pill';
          el.innerHTML = `<span class="town-dot"></span><span class="town-name">${tn.name}</span>`;

          const marker = new Marker({ element: el })
            .setLngLat([tn.lon, tn.lat])
            .addTo(map);

          townMarkersRef.current.push(marker);
        });
      })
      .catch((err) => console.error('Error loading towns:', err));
  }, [mapLoaded]);

  // 3. Render Draggable Candidate Markers
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const map = mapRef.current;

    // Remove old candidate markers
    candidateMarkersRef.current.forEach((m) => m.remove());
    candidateMarkersRef.current.clear();

    candidates.forEach((cand, idx) => {
      const isSelected = selectedCandidateId === cand.id;
      const el = document.createElement('div');
      el.className = `candidate-marker-pin ${isSelected ? 'selected' : ''}`;
      el.innerHTML = `
        <div class="cand-pin-body">
          <span class="cand-rank">#${idx + 1}</span>
        </div>
        <div class="cand-pin-point"></div>
      `;

      el.addEventListener('click', (e) => {
        e.stopPropagation();
        onSelectCandidate(cand.id);
      });

      const marker = new Marker({
        element: el,
        draggable: true,
      })
        .setLngLat([cand.lon, cand.lat])
        .addTo(map);

      // On Drag End -> trigger recompute in parent
      marker.on('dragend', () => {
        const lngLat = marker.getLngLat();
        onCandidateMove(cand.id, lngLat.lat, lngLat.lng);
      });

      candidateMarkersRef.current.set(cand.id, marker);
    });
  }, [mapLoaded, candidates, selectedCandidateId, onCandidateMove, onSelectCandidate]);

  // 4. Idempotent Feature-State Updates (setFeatureState & removeFeatureState)
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const map = mapRef.current;
    if (!map.getSource('cells')) return;

    const previousSet = previousOverriddenRef.current;

    if (!showModeled) {
      // Revert completely to baseline
      previousSet.forEach((cellId) => {
        map.removeFeatureState({ source: 'cells', id: cellId });
      });
      previousSet.clear();
      return;
    }

    const currentMap = overriddenDbmMap;
    const currentKeys = new Set(currentMap.keys());

    // Remove feature state for cells no longer changed (cleans stale footprints)
    previousSet.forEach((cellId) => {
      if (!currentKeys.has(cellId)) {
        map.removeFeatureState({ source: 'cells', id: cellId });
      }
    });

    // Apply new feature states
    currentMap.forEach((dbm, cellId) => {
      map.setFeatureState({ source: 'cells', id: cellId }, { dbm });
    });

    previousOverriddenRef.current = currentKeys;
  }, [mapLoaded, overriddenDbmMap, showModeled]);

  // 5. Handle FlyTo target
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !flyToTarget) return;
    mapRef.current.flyTo({
      center: [flyToTarget.lon, flyToTarget.lat],
      zoom: 13.5,
      speed: 1.2,
      curve: 1.4,
    });
  }, [mapLoaded, flyToTarget]);

  return (
    <div className="map-viewport">
      <div ref={mapContainer} className="map-container" />

      {!webGlSupported && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: '#090d16ee',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            textAlign: 'center',
            zIndex: 10,
          }}
        >
          <h3 style={{ color: '#f59e0b', marginBottom: '8px' }}>WebGL Not Detected in Browser</h3>
          <p style={{ color: '#94a3b8', maxWidth: '420px', fontSize: '13px', lineHeight: 1.5 }}>
            MapLibre GL requires WebGL hardware acceleration to render the map tiles.
            Please verify that <strong>Use hardware acceleration when available</strong> is enabled in your browser settings (e.g. <code>chrome://settings/system</code>).
          </p>
        </div>
      )}

      {/* Floating Map Legend */}
      <div className="map-floating-legend">
        <div className="legend-title">Coverage &amp; Siting Legend</div>
        <div className="legend-items">
          <div className="legend-item">
            <span className="color-swatch covered"></span>
            <span>Likely Covered (&ge; -94 dBm)</span>
          </div>
          <div className="legend-item">
            <span className="color-swatch uncertain"></span>
            <span>Uncertain Band (-106 to -94 dBm)</span>
          </div>
          <div className="legend-item">
            <span className="color-swatch gap"></span>
            <span>Likely Gap (&lt; -106 dBm)</span>
          </div>
          <div className="legend-divider"></div>
          <div className="legend-item">
            <span className="marker-legend-icon existing"></span>
            <span>Existing Macro Tower (Fixed)</span>
          </div>
          <div className="legend-item">
            <span className="marker-legend-icon candidate"></span>
            <span>Candidate Site (Draggable)</span>
          </div>
        </div>
        <div className="legend-footer">
          Drag candidate pins to test what-if coverage
        </div>
      </div>
    </div>
  );
};

export const Map = CoverageMap;
