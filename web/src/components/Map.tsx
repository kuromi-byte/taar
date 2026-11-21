import React, { useEffect, useRef } from 'react';
import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';
import { DATA_CONFIG } from '../config/data';

export const Map: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    // Offline blank dark style: zero external network requests
    const offlineDarkStyle: maplibregl.StyleSpecification = {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: {
            'background-color': '#0f172a', // Deep slate dark background
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

      // Pilot bounding box polygon as placeholder rectangle until basemap files exist
      const bboxGeoJSON: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            id: 0,
            properties: {
              name: DATA_CONFIG.pilot.name,
            },
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [minLon, minLat],
                  [maxLon, minLat],
                  [maxLon, maxLat],
                  [minLon, maxLat],
                  [minLon, minLat],
                ],
              ],
            },
          },
        ],
      };

      map.addSource('pilot-bbox', {
        type: 'geojson',
        data: bboxGeoJSON,
      });

      map.addLayer({
        id: 'pilot-bbox-fill',
        type: 'fill',
        source: 'pilot-bbox',
        paint: {
          'fill-color': '#1e293b',
          'fill-opacity': 0.6,
        },
      });

      map.addLayer({
        id: 'pilot-bbox-line',
        type: 'line',
        source: 'pilot-bbox',
        paint: {
          'line-color': '#38bdf8',
          'line-width': 2,
          'line-dasharray': [2, 2],
        },
      });

      map.fitBounds(
        [
          [minLon, minLat],
          [maxLon, maxLat],
        ],
        { padding: 40, duration: 0 }
      );
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="map-viewport">
      <div ref={mapContainer} className="map-container" />
    </div>
  );
};
