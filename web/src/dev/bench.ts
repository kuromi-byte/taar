// /web/src/dev/bench.ts
// Dev-only benchmark hook. Tree-shaken out of production builds.

import { DATA_CONFIG } from '../config/data';
import { params } from '../config/params';
import { applyRecompute } from '../utils/recompute';

interface BenchmarkMetrics {
  dataMode: 'SYNTHETIC' | 'REAL';
  cellCount: number;
  nCellsInRadius: number;
  radiusKm: number;
  load: {
    fetchParseMs: number;
    drawToIdleMs: number;
    totalLoadMs: number;
  };
  render: {
    durationMs: number;
    totalFrames: number;
    avgFps: number;
    minFps: number;
    avgFrameMs: number;
    worstFrameMs: number;
  };
  featureStateSet: {
    loopMedianMs: number;
    loopP95Ms: number;
    idleMedianMs: number;
    idleP95Ms: number;
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

export async function runBenchmark(): Promise<BenchmarkMetrics> {
  console.log('🚀 [Gap-to-Brief Bench] Starting performance benchmark...');
  const map = (window as any).__map;
  if (!map) {
    throw new Error('Map instance not available on window.__map. Ensure map has mounted.');
  }

  // 1. Data Check & Load Measurement (4a)
  const tFetchStart = performance.now();
  const res = await fetch(DATA_CONFIG.paths.cells);
  const cellsGeoJson = await res.json();
  const fetchParseMs = performance.now() - tFetchStart;

  const features = cellsGeoJson.features || [];
  const cellCount = features.length;
  const isSynthetic = cellsGeoJson.meta?.source === 'mock' || cellCount <= 900;
  const dataMode: 'SYNTHETIC' | 'REAL' = isSynthetic ? 'SYNTHETIC' : 'REAL';

  console.log(`[Bench] Loaded ${cellCount} cells (${dataMode}). Fetch + JSON parse: ${fetchParseMs.toFixed(2)} ms`);

  // Measure setData to idle
  const tDrawStart = performance.now();
  if (map.getSource('cells')) {
    map.getSource('cells').setData(cellsGeoJson);
    await waitForMapIdle(map);
  }
  const drawToIdleMs = performance.now() - tDrawStart;

  // 2. Render Benchmark (4b): 3 seconds of programmatic pan & zoom
  console.log('[Bench] Measuring 3s programmatic render frame times...');
  const frameTimes: number[] = [];
  const renderStartTime = performance.now();
  let lastFrameTime = renderStartTime;
  const center = DATA_CONFIG.pilot.center;

  await new Promise<void>((resolve) => {
    let angle = 0;
    const animate = (time: number) => {
      const delta = time - lastFrameTime;
      lastFrameTime = time;
      if (delta > 0 && delta < 500) {
        frameTimes.push(delta);
      }

      angle += 0.08;
      const panOffsetLon = Math.sin(angle) * 0.015;
      const panOffsetLat = Math.cos(angle) * 0.015;
      const zoomPulse = 11.0 + Math.sin(angle * 0.5) * 0.6;

      map.easeTo({
        center: [center[0] + panOffsetLon, center[1] + panOffsetLat],
        zoom: zoomPulse,
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

  console.log(`[Bench] Render test finished: ${frameTimes.length} frames, avg ${avgFps.toFixed(1)} fps (worst frame ${worstFrameMs.toFixed(2)} ms)`);

  // 3. Feature-state on N cells within 10 km (4c)
  // Fetch candidates to pick the first candidate location
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
    // fallback to center
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
  console.log(`[Bench] Selected tower at (${candLat}, ${candLon}). Found ${nCells} cells within ${radiusKm} km radius.`);

  // 30 iterations of setFeatureState
  const setLoopTimes: number[] = [];
  const setIdleTimes: number[] = [];

  for (let i = 0; i < 30; i++) {
    const t0 = performance.now();
    for (const id of cellsInRadius) {
      map.setFeatureState({ source: 'cells', id }, { dbm: -75.0 - (i % 15) });
    }
    const tLoop = performance.now() - t0;
    setLoopTimes.push(tLoop);

    await waitForMapIdle(map);
    const tIdle = performance.now() - t0;
    setIdleTimes.push(tIdle);
  }

  setLoopTimes.sort((a, b) => a - b);
  setIdleTimes.sort((a, b) => a - b);

  // 4. 30 iterations of removeFeatureState (4d)
  const removeLoopTimes: number[] = [];
  const removeIdleTimes: number[] = [];

  for (let i = 0; i < 30; i++) {
    // Prime with state first
    for (const id of cellsInRadius) {
      map.setFeatureState({ source: 'cells', id }, { dbm: -80 });
    }
    await waitForMapIdle(map);

    const t0 = performance.now();
    for (const id of cellsInRadius) {
      map.removeFeatureState({ source: 'cells', id });
    }
    const tLoop = performance.now() - t0;
    removeLoopTimes.push(tLoop);

    await waitForMapIdle(map);
    const tIdle = performance.now() - t0;
    removeIdleTimes.push(tIdle);
  }

  removeLoopTimes.sort((a, b) => a - b);
  removeIdleTimes.sort((a, b) => a - b);

  // 5. applyRecompute end-to-end benchmark & shrinking response (4e)
  const applyLoopTimes: number[] = [];
  const applyIdleTimes: number[] = [];
  let prevSet = new Set<number>();
  const fakeChangedFull: [number, number][] = cellsInRadius.map((id, idx) => [id, -70.0 - (idx % 25)]);

  for (let i = 0; i < 30; i++) {
    const t0 = performance.now();
    prevSet = applyRecompute(map, prevSet, fakeChangedFull, 'cells');
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

  const shrinkingSet = applyRecompute(map, prevSet, fakeChangedHalf, 'cells');
  await waitForMapIdle(map);

  const shrinkingConfirmed =
    shrinkingSet.size === halfCount &&
    droppedIds.every((id) => !shrinkingSet.has(id));

  // Reset map view and state cleanly
  map.easeTo({ center: DATA_CONFIG.pilot.center, zoom: DATA_CONFIG.pilot.zoom, duration: 0 });

  const metrics: BenchmarkMetrics = {
    dataMode,
    cellCount,
    nCellsInRadius: nCells,
    radiusKm,
    load: {
      fetchParseMs: Number(fetchParseMs.toFixed(2)),
      drawToIdleMs: Number(drawToIdleMs.toFixed(2)),
      totalLoadMs: Number((fetchParseMs + drawToIdleMs).toFixed(2)),
    },
    render: {
      durationMs: 3000,
      totalFrames: frameTimes.length,
      avgFps: Number(avgFps.toFixed(1)),
      minFps: Number(minFps.toFixed(1)),
      avgFrameMs: Number(avgFrameMs.toFixed(2)),
      worstFrameMs: Number(worstFrameMs.toFixed(2)),
    },
    featureStateSet: {
      loopMedianMs: Number(quantile(setLoopTimes, 0.5).toFixed(2)),
      loopP95Ms: Number(quantile(setLoopTimes, 0.95).toFixed(2)),
      idleMedianMs: Number(quantile(setIdleTimes, 0.5).toFixed(2)),
      idleP95Ms: Number(quantile(setIdleTimes, 0.95).toFixed(2)),
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
  };

  console.log(`\n=================== BENCHMARK REPORT [${dataMode}] ===================`);
  console.table({
    'Fetch + Parse (ms)': metrics.load.fetchParseMs,
    'Draw to Idle (ms)': metrics.load.drawToIdleMs,
    'Render Avg FPS': metrics.render.avgFps,
    'Render Min FPS': metrics.render.minFps,
    'Worst Frame (ms)': metrics.render.worstFrameMs,
    [`setFeatureState Loop (${nCells} cells) Median (ms)`]: metrics.featureStateSet.loopMedianMs,
    [`setFeatureState Loop (${nCells} cells) p95 (ms)`]: metrics.featureStateSet.loopP95Ms,
    [`setFeatureState + Idle Median (ms)`]: metrics.featureStateSet.idleMedianMs,
    [`setFeatureState + Idle p95 (ms)`]: metrics.featureStateSet.idleP95Ms,
    [`removeFeatureState Loop Median (ms)`]: metrics.featureStateRemove.loopMedianMs,
    [`removeFeatureState Loop p95 (ms)`]: metrics.featureStateRemove.loopP95Ms,
    [`applyRecompute (${nCells} cells) Loop Median (ms)`]: metrics.applyRecomputeEndToEnd.loopMedianMs,
    [`applyRecompute (${nCells} cells) Loop p95 (ms)`]: metrics.applyRecomputeEndToEnd.loopP95Ms,
    'Shrinking Footprint Stale Clear': metrics.applyRecomputeEndToEnd.shrinkingConfirmed ? 'CONFIRMED' : 'FAILED',
  });

  return metrics;
}

// Expose globally
if (typeof window !== 'undefined') {
  (window as any).__bench = runBenchmark;
  console.log('✅ [Gap-to-Brief Bench] Hook window.__bench() registered successfully.');
}
