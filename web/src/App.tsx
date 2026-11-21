import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { CounterPanel } from './components/CounterPanel';
import { ShortlistTable } from './components/ShortlistTable';
import { CoverageMap } from './components/Map';
import { BriefModal } from './components/BriefModal';
import { LimitationsModal } from './components/LimitationsModal';
import { DATA_CONFIG } from './config/data';
import { Candidate, Cluster, RecomputeRequest, RecomputeResponse } from './types/contracts';

export const App: React.FC = () => {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
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
  const [isRecomputing, setIsRecomputing] = useState<boolean>(false);
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isMockData, setIsMockData] = useState<boolean>(false);

  // Modals
  const [activeBriefCluster, setActiveBriefCluster] = useState<Cluster | null>(null);
  const [showLimitationsModal, setShowLimitationsModal] = useState<boolean>(false);

  // 1. Initial Data Fetch
  useEffect(() => {
    // Check API health
    fetch(`${DATA_CONFIG.apiUrl}/health`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status === 'ok') setApiConnected(true);
      })
      .catch(() => setApiConnected(false));

    // Audit cells.geojson for meta.source == "mock"
    fetch(DATA_CONFIG.paths.cells)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && (data.meta?.source === 'mock' || data.source === 'mock')) {
          setIsMockData(true);
        }
      })
      .catch((err) => console.warn('Could not inspect cells metadata:', err));

    // Fetch Candidates
    fetch(DATA_CONFIG.paths.candidates)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Candidate[]) => {
        if (Array.isArray(data) && data.length > 0) {
          // Normalize height_m and power_dbm defaults if missing
          const normalized = data.map((c) => ({
            ...c,
            height_m: (c as any).height_m ?? 30.0,
            power_dbm: (c as any).power_dbm ?? 43.0,
          }));
          setCandidates(normalized);
          setInitialCandidates(JSON.parse(JSON.stringify(normalized)));
          const sumAdded = normalized.reduce((acc, c) => acc + (c.added_pop || 0), 0);
          setNewlyCoveredPop(sumAdded);
          setSelectedCandidateId(normalized[0].id);
        }
      })
      .catch((err) => console.error('Failed to load candidates:', err));

    // Fetch Clusters
    fetch(DATA_CONFIG.paths.clusters)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Cluster[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setClusters(data);
          const sumUnserved = data.reduce((acc, cl) => acc + (cl.pop_in_gap || 0), 0);
          if (sumUnserved > 0) setTotalUnservedPop(sumUnserved);
        }
      })
      .catch((err) => console.error('Failed to load clusters:', err));
  }, []);

  // 2. Perform Recompute against FastAPI Backend using EXACT contract shape
  const runRecompute = useCallback(async (currentCandidates: Candidate[]) => {
    setIsRecomputing(true);
    setApiError(null);

    // Contract: {"towers":[{"lat": number, "lon": number, "height_m": number, "power_dbm": number}]}
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
      });

      if (!response.ok) {
        throw new Error(`Recompute HTTP ${response.status}: ${response.statusText}`);
      }

      const resData: RecomputeResponse = await response.json();
      setApiConnected(true);

      // Contract response: {"changed": [[cell_id, dbm], ...], "newly_covered_pop": N, "total_unserved_pop": M}
      setChangedCells(resData.changed);
      setNewlyCoveredPop(resData.newly_covered_pop);
      setTotalUnservedPop(resData.total_unserved_pop);
      setShowModeled(true);
    } catch (err: any) {
      // Contract rule: "If the API call fails, show a clear error and keep the previous map state."
      console.warn('API recompute failed; preserving previous map state:', err);
      setApiConnected(false);
      setApiError(`Recompute failed: ${err.message || 'API endpoint unavailable'}. Preserving previous map state.`);
    } finally {
      setIsRecomputing(false);
    }
  }, []);

  // Initial recompute once candidates land
  useEffect(() => {
    if (initialCandidates.length > 0) {
      runRecompute(initialCandidates);
    }
  }, [initialCandidates, runRecompute]);

  // 3. Candidate Drag Handler (Fires strictly on marker DROP)
  const handleCandidateMove = useCallback(
    (id: string | number, newLat: number, newLon: number) => {
      setCandidates((prev) => {
        const updated = prev.map((c) => {
          if (c.id === id) {
            return {
              ...c,
              lat: Number(newLat.toFixed(6)),
              lon: Number(newLon.toFixed(6)),
            };
          }
          return c;
        });

        // Trigger live recompute on drop
        runRecompute(updated);
        return updated;
      });
    },
    [runRecompute]
  );

  // 4. Update Candidate Parameters (height_m, power_dbm)
  const handleCandidateParamChange = useCallback(
    (id: string | number, field: 'height_m' | 'power_dbm', value: number) => {
      setCandidates((prev) => {
        const updated = prev.map((c) => {
          if (c.id === id) {
            return {
              ...c,
              [field]: value,
            };
          }
          return c;
        });
        runRecompute(updated);
        return updated;
      });
    },
    [runRecompute]
  );

  // 5. Delete Candidate
  const handleDeleteCandidate = useCallback(
    (id: string | number) => {
      setCandidates((prev) => {
        const updated = prev.filter((c) => c.id !== id);
        if (selectedCandidateId === id) {
          setSelectedCandidateId(updated.length > 0 ? updated[0].id : null);
        }
        runRecompute(updated);
        return updated;
      });
    },
    [selectedCandidateId, runRecompute]
  );

  // 6. Add Candidate
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

    setCandidates((prev) => {
      const updated = [...prev, newCand];
      setSelectedCandidateId(newId);
      setFlyToTarget({ lat: newCand.lat, lon: newCand.lon });
      runRecompute(updated);
      return updated;
    });
  }, [selectedClusterId, runRecompute]);

  // 7. Reset Candidates to Initial
  const handleResetCandidates = useCallback(() => {
    const copy = JSON.parse(JSON.stringify(initialCandidates));
    setCandidates(copy);
    runRecompute(copy);
  }, [initialCandidates, runRecompute]);

  // 8. Select Candidate
  const handleSelectCandidate = useCallback((candidate: Candidate) => {
    setSelectedCandidateId(candidate.id);
    setSelectedClusterId(candidate.cluster_id);
    setFlyToTarget({ lat: candidate.lat, lon: candidate.lon });
  }, []);

  // 9. Select Cluster
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

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);

  return (
    <div className="app-container">
      <Header
        onOpenLimitations={() => setShowLimitationsModal(true)}
        apiConnected={apiConnected}
        isMockData={isMockData}
      />

      {apiError && (
        <div className="api-error-banner" role="alert">
          <span>⚠️ {apiError}</span>
          <button className="error-close-btn" onClick={() => setApiError(null)}>
            &times;
          </button>
        </div>
      )}

      <div className="main-content-split">
        {/* Left Side: Interactive Map */}
        <div className="map-panel-wrapper">
          <CounterPanel
            totalUnservedPop={totalUnservedPop}
            newlyCoveredPop={newlyCoveredPop}
            candidateCount={candidates.length}
            showModeled={showModeled}
            onToggleBeforeAfter={() => setShowModeled((prev) => !prev)}
            onResetCandidates={handleResetCandidates}
            isRecomputing={isRecomputing}
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
          />
        </div>

        {/* Right Side: Shortlist Table & Gap Clusters */}
        <aside className="sidebar-shortlist">
          {/* Candidate parameter editor card */}
          {selectedCandidate && (
            <div className="candidate-inspector-card">
              <div className="inspector-header">
                <div>
                  <span className="inspector-tag">Selected Site</span>
                  <strong>{selectedCandidate.id}</strong>
                </div>
                <button
                  className="btn-delete-cand"
                  onClick={() => handleDeleteCandidate(selectedCandidate.id)}
                  title="Remove candidate site"
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
          />
        </aside>
      </div>

      {/* Brief Modal */}
      <BriefModal
        cluster={activeBriefCluster}
        candidates={candidates}
        onClose={() => setActiveBriefCluster(null)}
      />

      {/* Limitations & Methodology Modal */}
      <LimitationsModal
        isOpen={showLimitationsModal}
        onClose={() => setShowLimitationsModal(false)}
      />
    </div>
  );
};

export default App;
