"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import MapPanel from "@/components/map/DynamicMapPanel";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse } from "@/lib/contracts";

export default function DriftPage({ params }: { params: Promise<{ caseId: string }> }) {
  const resolvedParams = use(params);
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [timelineIndex, setTimelineIndex] = useState(3); // Default to T=0h
  const [isPlaying, setIsPlaying] = useState(false);

  const [layerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": true,
    "backward-tracks": true,
    "hindcast-corridor": true,
    "forecast-contour": true,
    "candidate-tracks": false,
    "particles-cloud": true,
    "range-rings": true,
  });

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const res = await ApiClient.getCaseDashboard(resolvedParams.caseId);
      setData(res);
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

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px] font-mono text-cyan-400">
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mr-3" />
          <span>LOADING PHASE 2 DRIFT SIMULATION TELEMETRY...</span>
        </div>
      </DashboardLayout>
    );
  }

  const { caseSummary, drift } = data;
  const currentStep = drift.timeSteps[timelineIndex] || drift.timeSteps[0];

  return (
    <DashboardLayout caseSummary={caseSummary}>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 font-mono text-xs text-slate-200">
        
        {/* ========================================================= */}
        {/* LEFT COLUMN: INTERACTIVE DRIFT MAP & TIMELINE (8 COLS)   */}
        {/* ========================================================= */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          
          {/* MAP CANVAS */}
          <div className="relative flex-1 min-h-[520px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#030d1c] shadow-2xl">
            <MapPanel
              dashboardData={data}
              activeLayers={layerVisibility}
              currentTimeStepIndex={timelineIndex}
            />
          </div>

          {/* TIMELINE SCRUBBER CONTROLS */}
          <div className="bg-[#06152b] border border-cyan-900/60 rounded-xl p-4 space-y-3 shadow-xl">
            <div className="flex flex-wrap justify-between items-center gap-3">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className={`px-3.5 py-1.5 rounded font-extrabold flex items-center space-x-2 transition cursor-pointer ${
                    isPlaying
                      ? "bg-amber-400 text-slate-950 shadow-md shadow-amber-400/30"
                      : "bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/30"
                  }`}
                >
                  <span>{isPlaying ? "⏸" : "▶"}</span>
                  <span>{isPlaying ? "PAUSE SIMULATION" : "PLAY TRAJECTORY"}</span>
                </button>
                <span className="text-cyan-400 font-bold text-sm">
                  {currentStep.label}
                </span>
              </div>

              <div className="flex items-center space-x-2 text-slate-400 text-[11px]">
                <span>TIMESTEP UTC:</span>
                <span className="text-white font-bold bg-[#030d1c] px-2 py-0.5 rounded border border-cyan-900/40">
                  {new Date(currentStep.timestampUTC).toUTCString()}
                </span>
              </div>
            </div>

            {/* RANGE SLIDER */}
            <div className="relative pt-1">
              <input
                type="range"
                min="0"
                max={drift.timeSteps.length - 1}
                value={timelineIndex}
                onChange={(e) => setTimelineIndex(Number(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer h-2.5 bg-slate-900 rounded-lg shadow-inner"
              />
            </div>

            {/* TIMELINE STEPS MARKERS */}
            <div className="flex justify-between text-[10px] text-slate-400 pt-1">
              {drift.timeSteps.map((step, idx) => {
                const isSelected = idx === timelineIndex;
                const isOrigin = step.hourOffset < 0;
                const isNow = step.hourOffset === 0;

                return (
                  <button
                    key={step.hourOffset}
                    onClick={() => setTimelineIndex(idx)}
                    className={`cursor-pointer px-2 py-1 rounded transition text-center flex flex-col items-center ${
                      isSelected
                        ? "bg-cyan-500 text-slate-950 font-extrabold shadow-md shadow-cyan-500/30"
                        : isOrigin
                        ? "text-purple-300 hover:bg-purple-950/40"
                        : isNow
                        ? "text-rose-300 hover:bg-rose-950/40 font-bold"
                        : "text-teal-300 hover:bg-teal-950/40"
                    }`}
                  >
                    <span className="font-bold">
                      {step.hourOffset < 0 ? `${step.hourOffset}h` : step.hourOffset === 0 ? "0h (NOW)" : `+${step.hourOffset}h`}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* RIGHT COLUMN: ENVIRONMENTAL FORCING & LEGEND (4 COLS)     */}
        {/* ========================================================= */}
        <div className="lg:col-span-4 space-y-4">
          
          {/* ENVIRONMENTAL FORCING METRICS */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-teal-400 border-b border-cyan-900/40 pb-2 flex items-center justify-between">
              <span>ENVIRONMENTAL FORCING</span>
              <span className="text-[10px] text-emerald-400 font-bold">LIVE TELEMETRY</span>
            </h3>

            <div className="space-y-2.5 text-[11px]">
              <div>
                <p className="text-slate-400 text-[10px] uppercase">Atmospheric Wind Model:</p>
                <p className="text-white font-bold">{drift.currentWindQuality.windDataset}</p>
              </div>

              <div>
                <p className="text-slate-400 text-[10px] uppercase">Ocean Hydrodynamic Currents:</p>
                <p className="text-white font-bold">{drift.currentWindQuality.currentDataset}</p>
              </div>

              <div className="p-2.5 bg-[#030d1c] rounded border border-cyan-900/40 flex justify-between items-center">
                <span className="text-slate-300">FORCING QUALITY SCORE:</span>
                <span className="text-emerald-400 font-extrabold text-base">
                  {drift.currentWindQuality.qualityScore}%
                </span>
              </div>

              {drift.currentWindQuality.coverageGapWarning && (
                <p className="text-[10px] text-slate-400 italic">
                  {drift.currentWindQuality.coverageGapWarning}
                </p>
              )}
            </div>
          </div>

          {/* HINDCAST VS FORECAST LEGEND */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-purple-400 border-b border-cyan-900/40 pb-2">
              SIMULATION PHASES & LEGEND
            </h3>

            <div className="space-y-2 text-[11px]">
              <div className="flex items-center space-x-2.5 p-1.5 bg-[#030d1c] rounded">
                <div className="w-3.5 h-3.5 bg-orange-600 rounded border border-orange-400" />
                <div>
                  <span className="text-orange-300 font-bold block">Origin Zone A (90% CI)</span>
                  <span className="text-[10px] text-slate-400">High-confidence release origin probability</span>
                </div>
              </div>

              <div className="flex items-center space-x-2.5 p-1.5 bg-[#030d1c] rounded">
                <div className="w-3.5 h-3.5 bg-amber-500/40 border border-amber-400 rounded" />
                <div>
                  <span className="text-amber-300 font-bold block">-48h Hindcast Corridor</span>
                  <span className="text-[10px] text-slate-400">Lagrangian backtrack dispersion cone</span>
                </div>
              </div>

              <div className="flex items-center space-x-2.5 p-1.5 bg-[#030d1c] rounded">
                <div className="w-3.5 h-3.5 bg-teal-500/40 border border-teal-400 border-dashed rounded" />
                <div>
                  <span className="text-teal-300 font-bold block">+48h Future Risk Forecast</span>
                  <span className="text-[10px] text-slate-400">Projected coastal landing & dispersion vector</span>
                </div>
              </div>

              <div className="flex items-center space-x-2.5 p-1.5 bg-[#030d1c] rounded">
                <div className="w-3 h-3 rounded-full bg-orange-400 border border-white" />
                <div>
                  <span className="text-slate-200 font-bold block">Lagrangian Particle Cloud</span>
                  <span className="text-[10px] text-slate-400">48-particle ensemble tracking</span>
                </div>
              </div>
            </div>
          </div>

          {/* SCIENTIFIC METHODOLOGY WARNING */}
          <div className="p-3.5 bg-purple-950/30 border border-purple-500/40 rounded-xl text-purple-200 text-[11px] leading-relaxed shadow-lg">
            <span className="font-bold text-purple-400">⚠️ SCIENTIFIC NOTICE:</span> {drift.scientificWarning}
          </div>

          {/* PROCEED ACTION */}
          <Link
            href={`/cases/${caseSummary.caseId}/attribution`}
            className="w-full py-2.5 bg-gradient-to-r from-purple-500 to-cyan-500 hover:from-purple-400 hover:to-cyan-400 text-slate-950 font-extrabold rounded shadow-lg flex items-center justify-center space-x-2 transition text-center text-xs"
          >
            <span>PROCEED TO PHASE 3 ATTRIBUTION ➔</span>
          </Link>
        </div>
      </div>
    </DashboardLayout>
  );
}
