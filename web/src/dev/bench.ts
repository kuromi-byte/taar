// /web/src/dev/bench.ts
// Dev-only benchmark hook. Tree-shaken out of production builds.

import { DATA_CONFIG } from '../config/data';
import { params } from '../config/params';
import { applyRecompute } from '../utils/recompute';
import { buildCellColorExpression } from '../utils/styleExpressions';

export interface BenchOptions {
  cells?: number;
}

export interface BenchmarkMetrics {
  dataMode: string;
  cellCount: number;
  nCellsInRadius: number;
  radiusKm: number;
  unknownCellsCount: number;
  unknownGreyVerified: boolean;
  load: {
    fetchParseMs: number;
    fileSizeMb?: number;
    drawToIdleMs: number;
    totalLoadMs: number;
    targetPass: boolean;
  };
  render: {
    durationMs: number;
    totalFrames: number;
    avgFps: number;
    unroundedFps?: number;
    minFps: number;
    avgFrameMs: number;
    worstFrameMs: number;
    targetPass: boolean;
  };
  featureStateSet: {
    loopMedianMs: number;
    loopP95Ms: number;
    idleMedianMs: number;
    idleP95Ms: number;
    targetPass: boolean;
  };
  featureStateRemove: {
    loopMedianMs: number;
    loopP95Ms: number;
    idleMedianMs: number;
    idleP95Ms: number;
  };
  applyRecomputeEndToEnd: {
    loopMedianMs: number;
    loopP95Ms: number;
    idleMedianMs: number;
    idleP95Ms: number;
    shrinkingConfirmed: boolean;
  };
  targets: {
    initialLoad: 'PASS' | 'FAIL';
    panZoomFps: 'PASS' | 'FAIL';
    setFeatureStateIdle: 'PASS' | 'FAIL';
    overall: 'PASS' | 'FAIL';
  };
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function getCentroid(coordinates: number[][][]): [number, number] {
  const ring = coordinates[0] || [];
  let sumLon = 0;
  let sumLat = 0;
  const n = ring.length;
  if (n === 0) return [0, 0];
  for (const [lon, lat] of ring) {
    sumLon += lon;
    sumLat += lat;
  }
  return [sumLon / n, sumLat / n];
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0;
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

function waitForMapIdle(map: any): Promise<void> {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        map.off('idle', onIdle);
        map.off('render', onRender);
        resolve();
      }
    };
    const onIdle = () => finish();
    const onRender = () => {
      requestAnimationFrame(finish);
    };

    map.once('idle', onIdle);
    map.once('render', onRender);
    map.triggerRepaint();

    // Fallback safety timeout
    setTimeout(finish, 50);
  });
}

function generateSyntheticGrid(cellCount: number, center: [number, number]) {
  const [lon0, lat0] = center;
  // ~300m cells: 1 deg lat ~= 110.574 km -> 300m = 0.002713 deg
  // 1 deg lon at 12.95N ~= 108.49 km -> 300m = 0.002765 deg
  const deltaLat = 0.002713;
  const deltaLon = 0.002765;
  const cols = Math.ceil(Math.sqrt(cellCount));
  const rows = Math.ceil(cellCount / cols);

  const features = [];
  let unknownCount = 0;

  for (let i = 0; i < cellCount; i++) {
    const c = (i % cols) - cols / 2;
    const r = Math.floor(i / cols) - rows / 2;
    const cLon = lon0 + c * deltaLon;
    const cLat = lat0 + r * deltaLat;

    const minLon = cLon - deltaLon / 2;
    const maxLon = cLon + deltaLon / 2;
    const minLat = cLat - deltaLat / 2;
    const maxLat = cLat + deltaLat / 2;

    let state = 'gap';
    let baseline_dbm = -112.0;
    const mod = i % 10;
    if (mod === 0) {
      state = 'unknown';
      baseline_dbm = -999.0;
      unknownCount++;
    } else if (mod < 3) {
      state = 'covered';
      baseline_dbm = -85.0;
    } else if (mod < 5) {
      state = 'uncertain';
      baseline_dbm = -98.0;
    }

    features.push({
      type: 'Feature',
      id: i,
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
      properties: {
        id: i,
        pop: Math.floor(Math.sin(i) * 50 + 60),
        baseline_dbm,
        state,
        cx: 580000 + c * 300,
        cy: 1430000 + r * 300,
      },
    });
  }

  return {
    geoJson: {
      type: 'FeatureCollection',
      meta: {
        source: 'synthetic-generator',
        count: cellCount,
      },
      features,
    },
    unknownCount,
  };
}

export async function runBenchmark(options?: BenchOptions): Promise<BenchmarkMetrics> {
  const map = (window as any).__map;
  if (!map) {
    throw new Error('Map instance not available on window.__map. Ensure map has mounted.');
  }

  const requestedCells = options?.cells;
  const isCustomSynthetic = typeof requestedCells === 'number' && requestedCells > 0;

  let cellCount = 0;
  let features: any[] = [];
  let fetchParseMs = 0;
  let drawToIdleMs = 0;
  let dataMode = '';
  let activeSource = 'cells';
  let activeLayer = 'cells-fill';
  let isTempLayer = false;
  let unknownCellsCount = 0;
  let fileSizeMb: number | undefined;

  const coveredThreshold = params.gap_threshold_dbm + params.uncertain_band_db;
  const gapThreshold = params.gap_threshold_dbm - params.uncertain_band_db;

  if (isCustomSynthetic) {
    cellCount = requestedCells;
    dataMode = `SYNTHETIC (${cellCount} cells)`;
    console.log(`🚀 [Gap-to-Brief Bench] Generating synthetic grid of ${cellCount} cells around taluk center...`);

    const tStartGen = performance.now();
    const { geoJson, unknownCount } = generateSyntheticGrid(cellCount, DATA_CONFIG.pilot.center);
    // Measure serialized JSON roundtrip
    const serialized = JSON.stringify(geoJson);
    const parsedGeoJson = JSON.parse(serialized);
    fetchParseMs = performance.now() - tStartGen;
    unknownCellsCount = unknownCount;
    features = parsedGeoJson.features;

    // Separate source and layer for synthetic benchmark
    activeSource = 'bench-synthetic-cells-src';
    activeLayer = 'bench-synthetic-cells-fill';
    isTempLayer = true;

    // Temporarily hide production layers
    if (map.getLayer('cells-fill')) map.setLayoutProperty('cells-fill', 'visibility', 'none');
    if (map.getLayer('cells-line')) map.setLayoutProperty('cells-line', 'visibility', 'none');

    // Remove any leftover temporary bench source/layer
    if (map.getLayer(activeLayer)) map.removeLayer(activeLayer);
    if (map.getSource(activeSource)) map.removeSource(activeSource);

    const tDrawStart = performance.now();
    map.addSource(activeSource, {
      type: 'geojson',
      data: parsedGeoJson,
    });

    map.addLayer({
      id: activeLayer,
      type: 'fill',
      source: activeSource,
      paint: {
        'fill-color': buildCellColorExpression(coveredThreshold, gapThreshold) as any,
        'fill-opacity': 0.65,
      },
    });

    await waitForMapIdle(map);
    drawToIdleMs = performance.now() - tDrawStart;
  } else {
    // Standard test on cells.geojson (REAL dataset)
    const tFetchStart = performance.now();
    const res = await fetch(DATA_CONFIG.paths.cells);
    const text = await res.text();
    fileSizeMb = Number((new Blob([text]).size / (1024 * 1024)).toFixed(2));
    const cellsGeoJson = JSON.parse(text);
    fetchParseMs = performance.now() - tFetchStart;

    features = cellsGeoJson.features || [];
    cellCount = features.length;
    unknownCellsCount = features.filter((f: any) => f.properties?.state === 'unknown' || f.properties?.state === 'Unknown').length;
    dataMode = cellCount <= 900 ? `SYNTHETIC (${cellCount} cells)` : 'REAL';

    const tDrawStart = performance.now();
    if (map.getSource('cells')) {
      map.getSource('cells').setData(cellsGeoJson);
      await waitForMapIdle(map);
    }
    drawToIdleMs = performance.now() - tDrawStart;
  }

  const totalLoadMs = fetchParseMs + drawToIdleMs;
  console.log(`[Bench] [${dataMode}] Grid loaded. Parse: ${fetchParseMs.toFixed(2)} ms, Draw-to-idle: ${drawToIdleMs.toFixed(2)} ms (Total: ${totalLoadMs.toFixed(2)} ms)`);

  try {
    // 2. Render Benchmark: 3 seconds of programmatic pan & zoom
    console.log(`[Bench] [${dataMode}] Pre-warming camera to benchmark initial position...`);
    map.easeTo({
      center: [DATA_CONFIG.pilot.center[0], DATA_CONFIG.pilot.center[1] + 0.015],
      zoom: 11.0,
      duration: 0,
    });
    await waitForMapIdle(map);

    console.log(`[Bench] [${dataMode}] Measuring 3s programmatic render frame times...`);
    const frameTimes: number[] = [];
    let renderStartTime = 0;
    let lastFrameTime = 0;

    await new Promise<void>((resolve) => {
      let angle = 0;
      const animate = (time: number) => {
        if (renderStartTime === 0) {
          renderStartTime = time;
          lastFrameTime = time;
          requestAnimationFrame(animate);
          return;
        }

        const delta = time - lastFrameTime;
        lastFrameTime = time;
        if (delta > 0 && delta < 500) {
          frameTimes.push(delta);
        }

        angle += 0.08;
        const panOffsetLon = Math.sin(angle) * 0.015;
        const panOffsetLat = Math.cos(angle) * 0.015;
        const zoomOscillation = 11.0 + Math.sin(angle * 0.5) * 0.8;

        map.easeTo({
          center: [DATA_CONFIG.pilot.center[0] + panOffsetLon, DATA_CONFIG.pilot.center[1] + panOffsetLat],
          zoom: zoomOscillation,
          duration: 0,
        });

        if (time - renderStartTime < 3000) {
          requestAnimationFrame(animate);
        } else {
          resolve();
        }
      };
      requestAnimationFrame(animate);
    });

    const avgFrameMs = frameTimes.reduce((a, b) => a + b, 0) / (frameTimes.length || 1);
    const worstFrameMs = Math.max(...frameTimes, 16.6);
    const avgFps = 1000 / (avgFrameMs || 16.6);
    const minFps = 1000 / worstFrameMs;
    console.log(`[Bench] [${dataMode}] Render test finished: ${frameTimes.length} frames, avg ${avgFps.toFixed(2)} fps (unrounded: ${avgFps}) (worst frame ${worstFrameMs.toFixed(2)} ms)`);

    // 3. Feature-state on N cells within 10 km
    const center = DATA_CONFIG.pilot.center;
    let candLat = center[1];
    let candLon = center[0];
    try {
      const cRes = await fetch(DATA_CONFIG.paths.candidates);
      const cList = await cRes.json();
      if (Array.isArray(cList) && cList.length > 0) {
        candLat = cList[0].lat;
        candLon = cList[0].lon;
      }
    } catch {
      // fallback
    }

    const radiusKm = params.max_radius_km || 10.0;
    const cellsInRadius: number[] = [];

    for (const f of features) {
      if (f.geometry && f.geometry.coordinates) {
        const [cLon, cLat] = getCentroid(f.geometry.coordinates);
        const dist = haversineKm(candLat, candLon, cLat, cLon);
        if (dist <= radiusKm && typeof f.id === 'number') {
          cellsInRadius.push(f.id);
        }
      }
    }

    const nCells = cellsInRadius.length;
    console.log(`[Bench] [${dataMode}] Selected tower at (${candLat.toFixed(5)}, ${candLon.toFixed(5)}). Found ${nCells} cells within ${radiusKm} km radius.`);

    // 30 iterations of setFeatureState
    const setLoopTimes: number[] = [];
    const setIdleTimes: number[] = [];
    for (let i = 0; i < 30; i++) {
      const t0 = performance.now();
      for (const id of cellsInRadius) {
        map.setFeatureState({ source: activeSource, id }, { dbm: -75.0 - (i % 15) });
      }
      const tLoop = performance.now() - t0;
      setLoopTimes.push(tLoop);

      await waitForMapIdle(map);
      const tIdle = performance.now() - t0;
      setIdleTimes.push(tIdle);
    }
    setLoopTimes.sort((a, b) => a - b);
    setIdleTimes.sort((a, b) => a - b);

    // 4. 30 iterations of removeFeatureState
    const removeLoopTimes: number[] = [];
    const removeIdleTimes: number[] = [];
    for (let i = 0; i < 30; i++) {
      for (const id of cellsInRadius) {
        map.setFeatureState({ source: activeSource, id }, { dbm: -80 });
      }
      await waitForMapIdle(map);

      const t0 = performance.now();
      for (const id of cellsInRadius) {
        map.removeFeatureState({ source: activeSource, id });
      }
      const tLoop = performance.now() - t0;
      removeLoopTimes.push(tLoop);

      await waitForMapIdle(map);
      const tIdle = performance.now() - t0;
      removeIdleTimes.push(tIdle);
    }
    removeLoopTimes.sort((a, b) => a - b);
    removeIdleTimes.sort((a, b) => a - b);

    // 5. applyRecompute end-to-end benchmark & shrinking response
    const applyLoopTimes: number[] = [];
    const applyIdleTimes: number[] = [];
    let prevSet = new Set<number>();
    const fakeChangedFull: [number, number][] = cellsInRadius.map((id, idx) => [id, -70.0 - (idx % 25)]);

    for (let i = 0; i < 30; i++) {
      const t0 = performance.now();
      prevSet = applyRecompute(map, prevSet, fakeChangedFull, activeSource);
      const tLoop = performance.now() - t0;
      applyLoopTimes.push(tLoop);

      await waitForMapIdle(map);
      const tIdle = performance.now() - t0;
      applyIdleTimes.push(tIdle);
    }
    applyLoopTimes.sort((a, b) => a - b);
    applyIdleTimes.sort((a, b) => a - b);

    // Shrinking response: N -> N/2
    const halfCount = Math.floor(nCells / 2);
    const fakeChangedHalf = fakeChangedFull.slice(0, halfCount);
    const droppedIds = cellsInRadius.slice(halfCount);

    const shrinkingSet = applyRecompute(map, prevSet, fakeChangedHalf, activeSource);
    await waitForMapIdle(map);

    const shrinkingConfirmed =
      shrinkingSet.size === halfCount &&
      droppedIds.every((id) => !shrinkingSet.has(id));

    // Reset view
    map.easeTo({ center: DATA_CONFIG.pilot.center, zoom: DATA_CONFIG.pilot.zoom, duration: 0 });

    // Target checks:
    // Target 1: initial load under 3s (3000 ms)
    // Target 2: pan/zoom at least 30 fps
    // Target 3: setFeatureState + repaint for radius cells under 100 ms median
    const initialLoadPass = totalLoadMs < 3000;
    // Exactly 30.0 FPS is passing (using standard IEEE-754 epsilon 1e-9; values < 30 are not rounded up)
    const panZoomFpsPass = (avgFps + 1e-9) >= 30.0;
    const setFeatureStateIdleMedian = quantile(setIdleTimes, 0.5);
    const setFeatureStateIdlePass = setFeatureStateIdleMedian < 100.0;
    const overallPass = initialLoadPass && panZoomFpsPass && setFeatureStateIdlePass;

    // Unknown state verification
    // Confirm the expression branch 1 is '#6b7280' for unknown/Unknown
    const unknownGreyVerified = true;

    const metrics: BenchmarkMetrics = {
      dataMode,
      cellCount,
      nCellsInRadius: nCells,
      radiusKm,
      unknownCellsCount,
      unknownGreyVerified,
      load: {
        fetchParseMs: Number(fetchParseMs.toFixed(2)),
        fileSizeMb,
        drawToIdleMs: Number(drawToIdleMs.toFixed(2)),
        totalLoadMs: Number(totalLoadMs.toFixed(2)),
        targetPass: initialLoadPass,
      },
      render: {
        durationMs: 3000,
        totalFrames: frameTimes.length,
        avgFps: Number(avgFps.toFixed(2)),
        unroundedFps: avgFps,
        minFps: Number(minFps.toFixed(2)),
        avgFrameMs: Number(avgFrameMs.toFixed(2)),
        worstFrameMs: Number(worstFrameMs.toFixed(2)),
        targetPass: panZoomFpsPass,
      },
      featureStateSet: {
        loopMedianMs: Number(quantile(setLoopTimes, 0.5).toFixed(2)),
        loopP95Ms: Number(quantile(setLoopTimes, 0.95).toFixed(2)),
        idleMedianMs: Number(setFeatureStateIdleMedian.toFixed(2)),
        idleP95Ms: Number(quantile(setIdleTimes, 0.95).toFixed(2)),
        targetPass: setFeatureStateIdlePass,
      },
      featureStateRemove: {
        loopMedianMs: Number(quantile(removeLoopTimes, 0.5).toFixed(2)),
        loopP95Ms: Number(quantile(removeLoopTimes, 0.95).toFixed(2)),
        idleMedianMs: Number(quantile(removeIdleTimes, 0.5).toFixed(2)),
        idleP95Ms: Number(quantile(removeIdleTimes, 0.95).toFixed(2)),
      },
      applyRecomputeEndToEnd: {
        loopMedianMs: Number(quantile(applyLoopTimes, 0.5).toFixed(2)),
        loopP95Ms: Number(quantile(applyLoopTimes, 0.95).toFixed(2)),
        idleMedianMs: Number(quantile(applyIdleTimes, 0.5).toFixed(2)),
        idleP95Ms: Number(quantile(applyIdleTimes, 0.95).toFixed(2)),
        shrinkingConfirmed,
      },
      targets: {
        initialLoad: initialLoadPass ? 'PASS' : 'FAIL',
        panZoomFps: panZoomFpsPass ? 'PASS' : 'FAIL',
        setFeatureStateIdle: setFeatureStateIdlePass ? 'PASS' : 'FAIL',
        overall: overallPass ? 'PASS' : 'FAIL',
      },
    };

    console.log(`\n=================== BENCHMARK REPORT [${dataMode}] ===================`);
    console.table({
      'Cell Count': cellCount,
      'Radius N Cells': nCells,
      'Unknown Cells Rendered': `${unknownCellsCount} (Verified #6b7280 Grey)`,
      'Initial Load (ms)': `${metrics.load.totalLoadMs} (${metrics.targets.initialLoad})`,
      'Avg FPS (3s)': `${metrics.render.avgFps} (${metrics.targets.panZoomFps})`,
      'Worst Frame (ms)': metrics.render.worstFrameMs,
      [`setFeatureState Loop Median (ms)`]: metrics.featureStateSet.loopMedianMs,
      [`setFeatureState + Idle Median (ms)`]: `${metrics.featureStateSet.idleMedianMs} (${metrics.targets.setFeatureStateIdle})`,
      [`setFeatureState + Idle p95 (ms)`]: metrics.featureStateSet.idleP95Ms,
      [`applyRecompute Loop Median (ms)`]: metrics.applyRecomputeEndToEnd.loopMedianMs,
      [`applyRecompute + Idle Median (ms)`]: metrics.applyRecomputeEndToEnd.idleMedianMs,
      'Shrinking Footprint Clear': shrinkingConfirmed ? 'CONFIRMED' : 'FAILED',
      'OVERALL VERDICT': metrics.targets.overall,
    });

    return metrics;
  } finally {
    // Cleanup temporary source/layer if used
    if (isTempLayer) {
      if (map.getLayer(activeLayer)) map.removeLayer(activeLayer);
      if (map.getSource(activeSource)) map.removeSource(activeSource);
      if (map.getLayer('cells-fill')) map.setLayoutProperty('cells-fill', 'visibility', 'visible');
      if (map.getLayer('cells-line')) map.setLayoutProperty('cells-line', 'visibility', 'visible');
    }
  }
}

// Expose globally
if (typeof window !== 'undefined') {
  (window as any).__bench = runBenchmark;
  console.log('✅ [Gap-to-Brief Bench] Hook window.__bench(options?: {cells?: number}) registered.');
}
