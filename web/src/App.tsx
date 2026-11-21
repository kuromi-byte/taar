import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { CounterPanel } from './components/CounterPanel';
import { ShortlistTable } from './components/ShortlistTable';
import { CoverageMap } from './components/Map';
import { BriefModal } from './components/BriefModal';
import { LimitationsModal } from './components/LimitationsModal';
import { DATA_CONFIG } from './config/data';
import { Candidate, Cluster, RecomputeRequest } from './types/contracts';
import { RequestSequenceGuard } from './utils/requestSequence';
import { isMockSource } from './utils/styleExpressions';
import { validateRecomputeResponse } from './utils/validateRecompute';
import { RecomputeStateMachine, RecomputeStatus } from './utils/recomputeStatus';

export const App: React.FC = () => {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const candidatesRef = useRef<Candidate[]>([]);
  candidatesRef.current = candidates;

  const lastSuccessfulCandidatesRef = useRef<Candidate[]>([]);
  const [initialCandidates, setInitialCandidates] = useState<Candidate[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | number | null>(null);
  const [selectedClusterId, setSelectedClusterId] = useState<string | number | null>(null);
  const [flyToTarget, setFlyToTarget] = useState<{ lat: number; lon: number } | null>(null);

  // Coverage statistics & what-if state
  const [totalUnservedPop, setTotalUnservedPop] = useState<number>(19309);
  const [newlyCoveredPop, setNewlyCoveredPop] = useState<number>(0);
  const [changedCells, setChangedCells] = useState<[number, number][]>([]);
  const [showModeled, setShowModeled] = useState<boolean>(true);
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [isMockData, setIsMockData] = useState<boolean>(false);

  // Status & Error state machine
  const [recomputeStatus, setRecomputeStatus] = useState<RecomputeStatus>('idle');
  const [recomputeError, setRecomputeError] = useState<string | null>(null);
  const [cellsError, setCellsError] = useState<string | null>(null);
  const [shortlistLoading, setShortlistLoading] = useState<boolean>(true);
  const [shortlistError, setShortlistError] = useState<string | null>(null);

  // Modals
  const [activeBriefCluster, setActiveBriefCluster] = useState<Cluster | null>(null);
  const [showLimitationsModal, setShowLimitationsModal] = useState<boolean>(false);

  // Request sequence counter & AbortController ref
  const requestSeqRef = useRef<RequestSequenceGuard>(new RequestSequenceGuard());
  const abortControllerRef = useRef<AbortController | null>(null);
  const recomputeStateMachineRef = useRef<RecomputeStateMachine>(new RecomputeStateMachine());

  // Subscribe to recompute state machine
  useEffect(() => {
    return recomputeStateMachineRef.current.subscribe((status) => {
      setRecomputeStatus(status);
    });
  }, []);

  // 1. Load Cells GeoJSON (with full-panel error fallback)
  const loadCells = useCallback(() => {
    setCellsError(null);
    fetch(DATA_CONFIG.paths.cells)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!data || !Array.isArray(data.features)) {
          throw new Error('Invalid GeoJSON');
        }
        if (isMockSource(data.meta?.source) || isMockSource(data.source)) {
          setIsMockData(true);
        }
      })
      .catch(() => {
        setCellsError('Could not load cell grid data. Please verify data files and retry.');
      });
  }, []);

  // 2. Perform Recompute against FastAPI Backend using EXACT contract shape
  const runRecompute = useCallback(async (currentCandidates: Candidate[]) => {
    // Abort in-flight recompute request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const seq = requestSeqRef.current.next();
    setRecomputeError(null);

    const slowMs = DATA_CONFIG.getSlowMs();
    const timeoutMs = DATA_CONFIG.getTimeoutMs();

    recomputeStateMachineRef.current.start(seq, {
      slowMs,
      timeoutMs,
      onTimeout: () => {
        controller.abort('timeout');
      },
    });

    const requestPayload: RecomputeRequest = {
      towers: currentCandidates.map((c) => ({
        lat: c.lat,
        lon: c.lon,
        height_m: (c as any).height_m || 30.0,
        power_dbm: (c as any).power_dbm || 43.0,
      })),
    };

    try {
      const response = await fetch(`${DATA_CONFIG.apiUrl}/recompute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
        signal: controller.signal,
      });

      if (!response.ok) {
        if (!requestSeqRef.current.isLatest(seq)) return;
        setRecomputeError(`The server returned an error (HTTP ${response.status})`);
        recomputeStateMachineRef.current.error(seq);
        return;
      }

      let resJson: unknown;
      try {
        resJson = await response.json();
      } catch {
        if (!requestSeqRef.current.isLatest(seq)) return;
        setRecomputeError('The server sent an unexpected response');
        recomputeStateMachineRef.current.error(seq);
        return;
      }

      const validation = validateRecomputeResponse(resJson);
      if (!validation.ok) {
        if (!requestSeqRef.current.isLatest(seq)) return;
        setRecomputeError('The server sent an unexpected response');
        recomputeStateMachineRef.current.error(seq);
        return;
      }

      // Guard against out-of-order stale responses
      if (!requestSeqRef.current.isLatest(seq)) {
        return;
      }

      setApiConnected(true);
      setRecomputeError(null);
      lastSuccessfulCandidatesRef.current = JSON.parse(JSON.stringify(currentCandidates));

      const data = validation.data;
      setChangedCells(data.changed);
      setNewlyCoveredPop(data.newly_covered_pop);
      setTotalUnservedPop(data.total_unserved_pop);
      setShowModeled(true);

      recomputeStateMachineRef.current.success(seq, data.changed.length);
    } catch (err: any) {
      if (!requestSeqRef.current.isLatest(seq)) {
        return;
      }

      if (err.name === 'AbortError' || controller.signal.aborted) {
        if (controller.signal.reason === 'timeout' || recomputeStateMachineRef.current.getStatus() === 'error') {
          setRecomputeError('The server took too long to respond');
          recomputeStateMachineRef.current.error(seq);
        }
        return;
      }

      setRecomputeError("Can't reach the server");
      recomputeStateMachineRef.current.error(seq);
    }
  }, []);

  // 3. Load Candidates & Clusters (with loading skeleton and retry)
  const loadCandidatesAndClusters = useCallback(() => {
    setShortlistLoading(true);
    setShortlistError(null);

    Promise.all([
      fetch(DATA_CONFIG.paths.candidates).then((r) => {
        if (!r.ok) throw new Error(`Candidates HTTP ${r.status}`);
        return r.json();
      }),
      fetch(DATA_CONFIG.paths.clusters).then((r) => {
        if (!r.ok) throw new Error(`Clusters HTTP ${r.status}`);
        return r.json();
      }),
    ])
      .then(([cands, cls]) => {
        if (!Array.isArray(cands) || !Array.isArray(cls)) {
          throw new Error('Invalid candidates or clusters format');
        }
        const normalized = cands.map((c: any) => ({
          ...c,
          height_m: c.height_m ?? 30.0,
          power_dbm: c.power_dbm ?? 43.0,
        }));
        setCandidates(normalized);
        candidatesRef.current = normalized;
        setInitialCandidates(JSON.parse(JSON.stringify(normalized)));
        lastSuccessfulCandidatesRef.current = JSON.parse(JSON.stringify(normalized));
        setClusters(cls);
        setSelectedCandidateId(normalized[0]?.id || null);
        setShortlistLoading(false);

        // Initial recompute once candidates land
        runRecompute(normalized);
      })
      .catch(() => {
        setShortlistLoading(false);
        setShortlistError('Could not load candidate sites. Please retry.');
      });
  }, [runRecompute]);

  // Initial Fetch on Mount
  useEffect(() => {
    loadCells();
    loadCandidatesAndClusters();
  }, [loadCells, loadCandidatesAndClusters]);

  // 4. Candidate Drag Handler (Fires strictly on marker DROP)
  const handleCandidateMove = useCallback(
    (id: string | number, newLat: number, newLon: number) => {
      const updatedList = candidatesRef.current.map((c) => {
        if (c.id === id) {
          return {
            ...c,
            lat: Number(newLat.toFixed(6)),
            lon: Number(newLon.toFixed(6)),
          };
        }
        return c;
      });
      candidatesRef.current = updatedList;
      setCandidates(updatedList);

      // Trigger live recompute on drop
      runRecompute(updatedList);
    },
    [runRecompute]
  );

  // 5. Update Candidate Parameters (height_m, power_dbm)
  const handleCandidateParamChange = useCallback(
    (id: string | number, field: 'height_m' | 'power_dbm', value: number) => {
      const updatedList = candidatesRef.current.map((c) => {
        if (c.id === id) {
          return {
            ...c,
            [field]: Number(value),
          };
        }
        return c;
      });
      candidatesRef.current = updatedList;
      setCandidates(updatedList);
      runRecompute(updatedList);
    },
    [runRecompute]
  );

  // 6. Delete Candidate
  const handleDeleteCandidate = useCallback(
    (id: string | number) => {
      const updatedList = candidatesRef.current.filter((c) => c.id !== id);
      candidatesRef.current = updatedList;
      setCandidates(updatedList);
      if (selectedCandidateId === id) {
        setSelectedCandidateId(updatedList[0]?.id || null);
      }
      runRecompute(updatedList);
    },
    [selectedCandidateId, runRecompute]
  );

  // 7. Add Candidate
  const handleAddCandidate = useCallback(() => {
    const newId = `cand-custom-${Date.now().toString().slice(-4)}`;
    const newCand: Candidate = {
      id: newId,
      cluster_id: selectedClusterId || 'custom',
      lat: Number((DATA_CONFIG.pilot.center[1] + (Math.random() - 0.5) * 0.05).toFixed(6)),
      lon: Number((DATA_CONFIG.pilot.center[0] + (Math.random() - 0.5) * 0.05).toFixed(6)),
      added_pop: 0,
      flags: {
        road_km: 0.45,
        slope_deg: 6.2,
        backhaul: 'Fiber feasible',
      },
      why: 'User-placed candidate site for scenario testing',
      height_m: 30.0,
      power_dbm: 43.0,
    } as any;

    const updated = [...candidatesRef.current, newCand];
    candidatesRef.current = updated;
    setCandidates(updated);
    setSelectedCandidateId(newId);
    setFlyToTarget({ lat: newCand.lat, lon: newCand.lon });
    runRecompute(updated);
  }, [selectedClusterId, runRecompute]);

  // 8. Reset Candidates to Initial
  const handleResetCandidates = useCallback(() => {
    const copy = JSON.parse(JSON.stringify(initialCandidates));
    candidatesRef.current = copy;
    setCandidates(copy);
    setRecomputeError(null);
    runRecompute(copy);
  }, [initialCandidates, runRecompute]);

  // 9. Retry Recompute Handler
  const handleRetryRecompute = useCallback(() => {
    runRecompute(candidatesRef.current);
  }, [runRecompute]);

  // 10. Revert Marker Handler
  const handleRevertMarker = useCallback(() => {
    const reverted = JSON.parse(JSON.stringify(lastSuccessfulCandidatesRef.current));
    candidatesRef.current = reverted;
    setCandidates(reverted);
    setRecomputeError(null);
    recomputeStateMachineRef.current.success(requestSeqRef.current.next(), 1);
    setRecomputeStatus('success');
  }, []);

  // 11. Select Candidate
  const handleSelectCandidate = useCallback((candidate: Candidate) => {
    setSelectedCandidateId(candidate.id);
    setSelectedClusterId(candidate.cluster_id);
    setFlyToTarget({ lat: candidate.lat, lon: candidate.lon });
  }, []);

  // 12. Select Cluster
  const handleSelectCluster = useCallback(
    (cluster: Cluster) => {
      setSelectedClusterId(cluster.id);
      const matchCand = candidates.find((c) => c.cluster_id === cluster.id);
      if (matchCand) {
        setSelectedCandidateId(matchCand.id);
        setFlyToTarget({ lat: matchCand.lat, lon: matchCand.lon });
      }
    },
    [candidates]
  );

  // Expose dev helpers for automated tests
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    (window as any).__appState = {
      candidates,
      newlyCoveredPop,
      totalUnservedPop,
      recomputeStatus,
      recomputeError,
      isRecomputing: recomputeStatus === 'loading' || recomputeStatus === 'slow',
      apiConnected,
      handleCandidateMove,
      handleRetryRecompute,
      handleRevertMarker,
      loadCells,
      loadCandidatesAndClusters,
    };
  }

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);

  return (
    <div className="app-container">
      <Header
        onOpenLimitations={() => setShowLimitationsModal(true)}
        apiConnected={apiConnected}
        isMockData={isMockData}
      />

      {/* Error banner with role="alert", Retry and Revert marker buttons */}
      {recomputeError && (
        <div className="recompute-error-banner" role="alert">
          <div className="error-banner-content">
            <span className="error-icon">⚠️</span>
            <span className="error-message">{recomputeError}</span>
          </div>
          <div className="error-banner-actions">
            <button className="btn-error-retry" onClick={handleRetryRecompute}>
              Retry
            </button>
            <button className="btn-error-revert" onClick={handleRevertMarker}>
              Revert marker
            </button>
          </div>
        </div>
      )}

      <div className="main-content-split">
        {/* Left Side: Interactive Map & Counter Panel */}
        <div className="map-panel-wrapper">
          <CounterPanel
            totalUnservedPop={totalUnservedPop}
            newlyCoveredPop={newlyCoveredPop}
            candidateCount={candidates.length}
            showModeled={showModeled}
            onToggleBeforeAfter={() => setShowModeled((prev) => !prev)}
            onResetCandidates={handleResetCandidates}
            recomputeStatus={recomputeStatus}
            recomputeError={recomputeError}
            onManualRecompute={() => runRecompute(candidates)}
          />

          <CoverageMap
            candidates={candidates}
            selectedCandidateId={selectedCandidateId}
            onCandidateMove={handleCandidateMove}
            onSelectCandidate={(id) => {
              const c = candidates.find((cand) => cand.id === id);
              if (c) handleSelectCandidate(c);
            }}
            changedCells={changedCells}
            showModeled={showModeled}
            flyToTarget={flyToTarget}
            cellsError={cellsError}
            onRetryCells={loadCells}
          />
        </div>

        {/* Right Side: Shortlist Table & Gap Clusters */}
        <aside className="sidebar-shortlist">
          {selectedCandidate && (
            <div className="candidate-inspector-card">
              <div className="inspector-header">
                <div>
                  <span className="inspector-tag">Selected Site</span>
                  <strong>{selectedCandidate.id}</strong>
                </div>
                <button
                  className="btn-danger-sm"
                  onClick={() => handleDeleteCandidate(selectedCandidate.id)}
                  title="Remove this candidate tower"
                >
                  Delete Site
                </button>
              </div>

              <div className="inspector-controls-grid">
                <div className="control-group">
                  <label>Height: {(selectedCandidate as any).height_m || 30} m</label>
                  <input
                    type="range"
                    min="15"
                    max="60"
                    step="5"
                    value={(selectedCandidate as any).height_m || 30}
                    onChange={(e) =>
                      handleCandidateParamChange(selectedCandidate.id, 'height_m', Number(e.target.value))
                    }
                  />
                </div>

                <div className="control-group">
                  <label>Power: {(selectedCandidate as any).power_dbm || 43} dBm</label>
                  <input
                    type="range"
                    min="30"
                    max="50"
                    step="1"
                    value={(selectedCandidate as any).power_dbm || 43}
                    onChange={(e) =>
                      handleCandidateParamChange(selectedCandidate.id, 'power_dbm', Number(e.target.value))
                    }
                  />
                </div>
              </div>

              <div className="inspector-coords">
                Lat: {selectedCandidate.lat.toFixed(5)}°N, Lon: {selectedCandidate.lon.toFixed(5)}°E
              </div>
            </div>
          )}

          <div className="sidebar-action-bar">
            <button className="btn-add-cand" onClick={handleAddCandidate} title="Place a new candidate tower">
              + Add Candidate Tower
            </button>
          </div>

          <ShortlistTable
            candidates={candidates}
            clusters={clusters}
            selectedCandidateId={selectedCandidateId}
            selectedClusterId={selectedClusterId}
            onSelectCandidate={handleSelectCandidate}
            onSelectCluster={handleSelectCluster}
            onGenerateBrief={(cluster) => setActiveBriefCluster(cluster)}
            isLoading={shortlistLoading}
            error={shortlistError}
            onRetry={loadCandidatesAndClusters}
          />
        </aside>
      </div>

      {/* Modals */}
      {activeBriefCluster && (
        <BriefModal
          cluster={activeBriefCluster}
          candidates={candidates}
          onClose={() => setActiveBriefCluster(null)}
        />
      )}

      <LimitationsModal
        isOpen={showLimitationsModal}
        onClose={() => setShowLimitationsModal(false)}
      />
    </div>
  );
};

export default App;
