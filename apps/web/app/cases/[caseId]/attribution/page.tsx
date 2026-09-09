"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import MapPanel from "@/components/map/DynamicMapPanel";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse, Candidate } from "@/lib/contracts";

export default function AttributionPage({ params }: { params: Promise<{ caseId: string }> }) {
  const resolvedParams = use(params);
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [timelineIndex, setTimelineIndex] = useState(1); // Default to T-24h (Suspected release & approach)
  const [isPlaying, setIsPlaying] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  const [layerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": true,
    "backward-tracks": true,
    "hindcast-corridor": true,
    "forecast-contour": false,
    "candidate-tracks": true,
    "particles-cloud": true,
    "range-rings": true,
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

  // Timeline Scrubber Auto-play animation
  useEffect(() => {
    if (!isPlaying || !data) return;
    const interval = setInterval(() => {
      setTimelineIndex((prev) => (prev + 1) % (data.drift.timeSteps.length || 6));
    }, 1400);
    return () => clearInterval(interval);
  }, [isPlaying, data]);

  const handleExportDossier = async () => {
    setIsExporting(true);
    await new Promise((r) => setTimeout(r, 1200));
    setIsExporting(false);
    setExportSuccess(true);
    setTimeout(() => setExportSuccess(false), 4000);
  };

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

  const { caseSummary, attribution, drift } = data;
  const currentStep = drift.timeSteps[timelineIndex] || drift.timeSteps[0];

  return (
    <DashboardLayout caseSummary={caseSummary}>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 font-mono text-xs text-slate-200">
        
        {/* ========================================================= */}
        {/* LEFT COLUMN: AIS MAP CANVAS & TIMELINE SCRUBBER (7 COLS)  */}
        {/* ========================================================= */}
        <div className="lg:col-span-7 flex flex-col space-y-4">
          
          {/* MAP CANVAS */}
          <div className="relative flex-1 min-h-[520px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#030d1c] shadow-2xl">
            <MapPanel
              dashboardData={data}
              activeLayers={layerVisibility}
              selectedCandidateId={selectedCandidate?.candidateId}
              currentTimeStepIndex={timelineIndex}
              onSelectCandidate={(candId) => {
                const found = attribution.topCandidates.find((c) => c.candidateId === candId);
                if (found) setSelectedCandidate(found);
              }}
            />
          </div>

          {/* TIME AXIS SCRUBBER FOR VESSEL TRAJECTORIES */}
          <div className="bg-[#06152b] border border-cyan-900/60 rounded-xl p-3.5 space-y-2.5 shadow-xl">
            <div className="flex flex-wrap justify-between items-center gap-2">
              <div className="flex items-center space-x-2.5">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className={`px-3 py-1 rounded font-extrabold flex items-center space-x-1.5 transition cursor-pointer text-[11px] ${
                    isPlaying
                      ? "bg-amber-400 text-slate-950 shadow-md shadow-amber-400/30"
                      : "bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/30"
                  }`}
                >
                  <span>{isPlaying ? "⏸" : "▶"}</span>
                  <span>{isPlaying ? "PAUSE" : "SCRUB TIME"}</span>
                </button>
                <span className="text-cyan-400 font-bold text-xs">
                  {currentStep.label}
                </span>
              </div>

              <div className="text-[10px] text-slate-400">
                <span>APPROACH UTC: </span>
                <span className="text-white font-bold bg-[#030d1c] px-2 py-0.5 rounded border border-cyan-900/40">
                  {new Date(currentStep.timestampUTC).toUTCString()}
                </span>
              </div>
            </div>

            {/* SLIDER */}
            <input
              type="range"
              min="0"
              max={drift.timeSteps.length - 1}
              value={timelineIndex}
              onChange={(e) => setTimelineIndex(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer h-2 bg-slate-900 rounded-lg shadow-inner"
            />

            <div className="flex justify-between text-[10px] text-slate-500">
              {drift.timeSteps.map((step, idx) => (
                <span
                  key={step.hourOffset}
                  onClick={() => setTimelineIndex(idx)}
                  className={`cursor-pointer ${
                    idx === timelineIndex ? "text-cyan-400 font-bold underline" : "hover:text-slate-300"
                  }`}
                >
                  {step.hourOffset < 0 ? `${step.hourOffset}h` : step.hourOffset === 0 ? "0h" : `+${step.hourOffset}h`}
                </span>
              ))}
            </div>
          </div>

          {/* PRIVACY & COMPLIANCE FOOTER NOTICE */}
          <div className="p-3 bg-[#06152b] border border-cyan-900/60 rounded-xl flex items-center justify-between text-[11px] text-slate-300">
            <div className="flex items-center space-x-2">
              <span className="text-cyan-400 font-bold">🔒 PRIVACY & COMPLIANCE:</span>
              <span>{attribution.privacyDisclaimer}</span>
            </div>
            <span className="px-2 py-0.5 bg-cyan-950 text-cyan-400 border border-cyan-800 rounded text-[10px] font-bold">
              IMO MARPOL COMPLIANT
            </span>
          </div>
        </div>

        {/* ========================================================= */}
        {/* RIGHT COLUMN: LEADERBOARD & REASON CODES (5 COLS)        */}
        {/* ========================================================= */}
        <div className="lg:col-span-5 space-y-4">
          
          {/* TOP 3 CANDIDATES LEADERBOARD WITH REASON CODES */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2 flex items-center justify-between">
              <span>SUSPECT VESSEL LEADERBOARD</span>
              <span className="text-[10px] text-slate-400 font-normal">ATTRIBUTION SCORE</span>
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
                        ? "bg-cyan-950/90 border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)] ring-1 ring-cyan-400"
                        : "bg-[#030d1c] border-cyan-900/40 hover:border-cyan-500/50"
                    }`}
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            cand.rank === 1
                              ? "bg-gradient-to-r from-cyan-400 to-teal-400 text-slate-950"
                              : cand.rank === 2
                              ? "bg-slate-700 text-slate-200"
                              : "bg-slate-800 text-slate-400"
                          }`}
                        >
                          RANK {cand.rank}
                        </span>
                        <span className="font-bold text-white text-sm">{cand.candidateId}</span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {cand.vesselType} • CPA: <b className="text-white">{cand.closestApproach.distanceKm} km</b>
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-cyan-400 font-extrabold text-lg">
                        {cand.investigativeScore}%
                      </p>
                      <p className="text-[9px] text-slate-500">CORRELATION</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* CANDIDATE EVIDENCE DOSSIER & REASON CODES */}
          {selectedCandidate && (
            <div className="p-4 bg-[#06152b] border border-cyan-400/50 rounded-xl space-y-3.5 shadow-2xl">
              <div className="flex justify-between items-center border-b border-cyan-900/40 pb-2.5">
                <div>
                  <span className="text-[10px] text-cyan-400 font-bold uppercase">
                    EVIDENCE DOSSIER & REASON CODES
                  </span>
                  <h4 className="text-base font-bold text-white">
                    {selectedCandidate.candidateId} — {selectedCandidate.vesselType}
                  </h4>
                </div>
                <span className="px-2.5 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded font-bold text-xs">
                  SCORE: {selectedCandidate.investigativeScore}/100
                </span>
              </div>

              {/* REASON CODES TABLE */}
              <div className="space-y-2">
                <p className="text-[10px] font-bold text-amber-400 uppercase flex items-center justify-between">
                  <span>ATTRIBUTION REASON CODES</span>
                  <span className="text-slate-500 font-normal">IMO MARPOL PROTOCOL</span>
                </p>

                <div className="space-y-1.5">
                  {(selectedCandidate.reasonCodes || []).map((rc) => (
                    <div
                      key={rc.code}
                      className="p-2 bg-[#030d1c] border border-cyan-900/50 rounded flex items-start justify-between gap-2 text-[11px]"
                    >
                      <div>
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                              rc.type === "CRITICAL"
                                ? "bg-rose-500 text-white"
                                : rc.type === "HIGH"
                                ? "bg-amber-500 text-slate-950"
                                : "bg-cyan-900 text-cyan-200"
                            }`}
                          >
                            {rc.code}
                          </span>
                          <span className="font-bold text-white">{rc.label}</span>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1">{rc.description}</p>
                      </div>

                      <span className="text-[10px] font-bold text-cyan-400 whitespace-nowrap">
                        {rc.impact}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* SCORE BREAKDOWN COMPONENT BARS */}
              <div className="space-y-2 pt-1">
                <p className="text-[10px] font-bold text-slate-400 uppercase">
                  SCORE COMPONENT BREAKDOWN
                </p>
                <div className="space-y-1.5 text-[10px]">
                  <div>
                    <div className="flex justify-between text-slate-300 mb-0.5">
                      <span>Proximity to Release Zone:</span>
                      <span className="text-cyan-400 font-bold">{selectedCandidate.scoreBreakdown.proximity}/30</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-cyan-400 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(selectedCandidate.scoreBreakdown.proximity / 30) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300 mb-0.5">
                      <span>Time Window Overlap:</span>
                      <span className="text-teal-400 font-bold">{selectedCandidate.scoreBreakdown.timeOverlap}/25</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-teal-400 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(selectedCandidate.scoreBreakdown.timeOverlap / 25) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300 mb-0.5">
                      <span>Hindcast Corridor Intersection:</span>
                      <span className="text-purple-400 font-bold">{selectedCandidate.scoreBreakdown.corridorMatch}/20</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-purple-400 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(selectedCandidate.scoreBreakdown.corridorMatch / 20) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* ACTION: GENERATE DIGITAL DOSSIER */}
              <div className="pt-2">
                <button
                  onClick={handleExportDossier}
                  disabled={isExporting}
                  className="w-full py-2.5 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 text-slate-950 font-extrabold rounded shadow-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
                >
                  {isExporting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                      <span>GENERATING IMO MARPOL DOSSIER...</span>
                    </>
                  ) : exportSuccess ? (
                    <>
                      <span>✓</span>
                      <span>DOSSIER EXPORTED (PDF + JSON)</span>
                    </>
                  ) : (
                    <>
                      <span>📄</span>
                      <span>GENERATE COURT-READY DIGITAL DOSSIER</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* LEGAL DISCLAIMER */}
          <div className="p-3 bg-[#030d1c] border border-cyan-900/40 rounded-xl text-slate-400 text-[10px] italic leading-relaxed">
            &quot;{attribution.legalDisclaimer}&quot;
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
