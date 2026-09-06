"use client";

import { use, useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import MapPanel from "@/components/map/DynamicMapPanel";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse, Candidate } from "@/lib/contracts";

export default function AttributionPage({ params }: { params: Promise<{ caseId: string }> }) {
  const resolvedParams = use(params);
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);

  const [layerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": true,
    "backward-tracks": false,
    "hindcast-corridor": true,
    "forecast-contour": false,
    "candidate-tracks": true,
  });

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const res = await ApiClient.getCaseDashboard(resolvedParams.caseId);
      setData(res);
      if (res.attribution.topCandidates.length > 0) {
        setSelectedCandidate(res.attribution.topCandidates[0]);
      }
      setLoading(false);
    }
    loadData();
  }, [resolvedParams.caseId]);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px] font-mono text-cyan-400">
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mr-3" />
          <span>LOADING PHASE 3 ATTRIBUTION DATA...</span>
        </div>
      </DashboardLayout>
    );
  }

  const { caseSummary, attribution } = data;

  return (
    <DashboardLayout caseSummary={caseSummary}>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 font-mono text-xs">
        {/* LEFT MAP CANVAS (7 COLS) */}
        <div className="lg:col-span-7 flex flex-col space-y-4">
          <div className="relative flex-1 min-h-[520px]">
            <MapPanel
              dashboardData={data}
              activeLayers={layerVisibility}
              selectedCandidateId={selectedCandidate?.candidateId}
              onSelectCandidate={(candId) => {
                const found = attribution.topCandidates.find((c) => c.candidateId === candId);
                if (found) setSelectedCandidate(found);
              }}
            />
          </div>

          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-2 text-[11px] text-slate-300">
            <span className="font-bold text-cyan-400">🔒 PRIVACY & COMPLIANCE:</span>{" "}
            {attribution.privacyDisclaimer}
          </div>
        </div>

        {/* RIGHT TOP-3 CANDIDATES & DRAWER RAIL (5 COLS) */}
        <div className="lg:col-span-5 space-y-4">
          {/* TOP 3 CANDIDATES CARDS */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2">
              TOP-3 RANKED VESSEL CANDIDATES
            </h3>
            <div className="space-y-2.5">
              {attribution.topCandidates.map((cand) => {
                const isSelected = selectedCandidate?.candidateId === cand.candidateId;
                return (
                  <div
                    key={cand.candidateId}
                    onClick={() => setSelectedCandidate(cand)}
                    className={`p-3.5 rounded-xl border transition cursor-pointer flex justify-between items-center ${
                      isSelected
                        ? "bg-cyan-950/80 border-cyan-400 shadow-lg shadow-cyan-500/20"
                        : "bg-[#030d1c] border-cyan-900/40 hover:border-cyan-500/50"
                    }`}
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          cand.rank === 1 ? "bg-cyan-500 text-slate-950" : "bg-slate-800 text-slate-300"
                        }`}>
                          RANK {cand.rank}
                        </span>
                        <span className="font-bold text-white text-sm">{cand.candidateId}</span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {cand.vesselType} • Closest: {cand.closestApproach.distanceKm} km
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-cyan-400 font-extrabold text-base">
                        {cand.investigativeScore}/100
                      </p>
                      <p className="text-[9px] text-slate-500">RELEVANCE SCORE</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* CANDIDATE DETAIL DRAWER */}
          {selectedCandidate && (
            <div className="p-4 bg-[#06152b] border border-cyan-400/60 rounded-xl space-y-4 shadow-2xl animate-in fade-in duration-200">
              <div className="flex justify-between items-center border-b border-cyan-900/40 pb-3">
                <div>
                  <span className="text-[10px] text-cyan-400 font-bold uppercase">
                    CANDIDATE EVIDENCE DRAWER
                  </span>
                  <h4 className="text-lg font-bold text-white">
                    {selectedCandidate.candidateId} ({selectedCandidate.vesselType})
                  </h4>
                </div>
                <span className="px-3 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded font-bold">
                  SCORE: {selectedCandidate.investigativeScore}
                </span>
              </div>

              {/* SCORE BREAKDOWN BARS */}
              <div className="space-y-2">
                <p className="text-[11px] font-bold text-slate-300">SCORE COMPONENT BREAKDOWN</p>
                <div className="space-y-1.5 text-[10px]">
                  <div>
                    <div className="flex justify-between text-slate-400">
                      <span>Proximity Match</span>
                      <span>{selectedCandidate.scoreBreakdown.proximity}/30</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-cyan-400 h-full" style={{ width: `${(selectedCandidate.scoreBreakdown.proximity / 30) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-400">
                      <span>Time Window Overlap</span>
                      <span>{selectedCandidate.scoreBreakdown.timeOverlap}/25</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-teal-400 h-full" style={{ width: `${(selectedCandidate.scoreBreakdown.timeOverlap / 25) * 100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-400">
                      <span>Hindcast Corridor Match</span>
                      <span>{selectedCandidate.scoreBreakdown.corridorMatch}/20</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-purple-400 h-full" style={{ width: `${(selectedCandidate.scoreBreakdown.corridorMatch / 20) * 100}%` }} />
                    </div>
                  </div>
                </div>
              </div>

              {/* SUPPORTING EVIDENCE LIST */}
              <div className="space-y-2">
                <p className="text-[11px] font-bold text-emerald-400">SUPPORTING EVIDENCE</p>
                <ul className="space-y-1 text-[11px] text-slate-300">
                  {selectedCandidate.supportingEvidence.map((ev, idx) => (
                    <li key={idx} className="flex items-start space-x-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* NEGATIVE EVIDENCE */}
              {selectedCandidate.negativeEvidence.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[11px] font-bold text-slate-400">NEGATIVE EVIDENCE / COUNTER-FACTS</p>
                  <ul className="space-y-1 text-[11px] text-slate-400">
                    {selectedCandidate.negativeEvidence.map((ev, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span>•</span>
                        <span>{ev}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* WARNINGS */}
              {selectedCandidate.warnings.length > 0 && (
                <div className="p-2.5 bg-yellow-950/40 border border-yellow-500/40 rounded text-yellow-200 text-[10px]">
                  {selectedCandidate.warnings.join(", ")}
                </div>
              )}
            </div>
          )}

          {/* LEGAL DISCLAIMER FOOTER */}
          <div className="p-3 bg-[#030d1c] border border-cyan-900/40 rounded text-slate-500 text-[10px] italic">
            "{attribution.legalDisclaimer}"
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
