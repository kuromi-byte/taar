import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { CounterPanel } from './components/CounterPanel';
import { ShortlistTable } from './components/ShortlistTable';
import { CoverageMap } from './components/Map';
import { BriefModal } from './components/BriefModal';
import { LimitationsModal } from './components/LimitationsModal';
import { DATA_CONFIG } from './config/data';
import { Candidate, Cluster, RecomputeResponse } from './types/contracts';

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
  const [overriddenDbmMap, setOverriddenDbmMap] = useState<globalThis.Map<number, number>>(new globalThis.Map());
  const [showModeled, setShowModeled] = useState<boolean>(true);
  const [isRecomputing, setIsRecomputing] = useState<boolean>(false);
  const [apiConnected, setApiConnected] = useState<boolean>(false);

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

    // Fetch Candidates
    fetch(DATA_CONFIG.paths.candidates)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Candidate[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setCandidates(data);
          setInitialCandidates(JSON.parse(JSON.stringify(data)));
          // Sum initial added population
          const sumAdded = data.reduce((acc, c) => acc + (c.added_pop || 0), 0);
          setNewlyCoveredPop(sumAdded);
          setSelectedCandidateId(data[0].id);
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

  // 2. Perform Recompute against FastAPI Backend
  const runRecompute = useCallback(async (currentCandidates: Candidate[]) => {
    setIsRecomputing(true);

    const payload = currentCandidates.map((c) => ({
      id: c.id,
      lat: c.lat,
      lon: c.lon,
      height: 30.0,
      power: 43.0,
    }));

    try {
      const response = await fetch(`${DATA_CONFIG.apiUrl}/recompute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Recompute HTTP ${response.status}`);
      }

      const resData: RecomputeResponse = await response.json();
      setApiConnected(true);

      // Convert changed [[id, dbm], ...] to Map
      const newMap = new globalThis.Map<number, number>();
      resData.changed.forEach(([id, dbm]) => {
        newMap.set(id, dbm);
      });

      setOverriddenDbmMap(newMap);
      setNewlyCoveredPop(resData.newly_covered_pop);
      setTotalUnservedPop(resData.total_unserved_pop);
      setShowModeled(true);
    } catch (err) {
      console.warn('API recompute unavailable, using client-side calculation fallback:', err);
      setApiConnected(false);
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

  // 3. Candidate Drag Handler
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

  // 4. Reset Candidates to Initial
  const handleResetCandidates = useCallback(() => {
    const copy = JSON.parse(JSON.stringify(initialCandidates));
    setCandidates(copy);
    runRecompute(copy);
  }, [initialCandidates, runRecompute]);

  // 5. Select Candidate
  const handleSelectCandidate = useCallback((candidate: Candidate) => {
    setSelectedCandidateId(candidate.id);
    setSelectedClusterId(candidate.cluster_id);
    setFlyToTarget({ lat: candidate.lat, lon: candidate.lon });
  }, []);

  // 6. Select Cluster
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

  return (
    <div className="app-container">
      <Header
        onOpenLimitations={() => setShowLimitationsModal(true)}
        apiConnected={apiConnected}
      />

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
            overriddenDbmMap={overriddenDbmMap}
            showModeled={showModeled}
            flyToTarget={flyToTarget}
          />
        </div>

        {/* Right Side: Shortlist Table & Gap Clusters */}
        <aside className="sidebar-shortlist">
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
