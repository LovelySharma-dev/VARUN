"use client";

import { use, useEffect, useState } from "react";
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

  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": true,
    "backward-tracks": true,
    "hindcast-corridor": true,
    "forecast-contour": true,
    "candidate-tracks": false,
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
      setTimelineIndex((prev) => (prev + 1) % data.drift.timeSteps.length);
    }, 1500);
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
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 font-mono text-xs">
        {/* LEFT MAP CANVAS & TIMELINE SCRUBBER (8 COLS) */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          <div className="relative flex-1 min-h-[500px]">
            <MapPanel dashboardData={data} activeLayers={layerVisibility} />

            {/* LAYER CONTROL TOGGLES */}
            <div className="absolute top-4 right-4 z-20 bg-[#030914]/90 backdrop-blur-md border border-cyan-900/60 p-3 rounded-xl space-y-2 text-xs font-mono shadow-xl">
              <p className="text-[11px] font-bold text-cyan-400 uppercase border-b border-cyan-900/40 pb-1">
                DRIFT LAYERS
              </p>
              <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-white">
                <input
                  type="checkbox"
                  checked={layerVisibility["origin-density"]}
                  onChange={(e) =>
                    setLayerVisibility((prev) => ({ ...prev, "origin-density": e.target.checked }))
                  }
                  className="accent-purple-500 rounded"
                />
                <span>Origin-Density Contours</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-white">
                <input
                  type="checkbox"
                  checked={layerVisibility["backward-tracks"]}
                  onChange={(e) =>
                    setLayerVisibility((prev) => ({ ...prev, "backward-tracks": e.target.checked }))
                  }
                  className="accent-purple-400 rounded"
                />
                <span>Backward Particle Tracks</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-white">
                <input
                  type="checkbox"
                  checked={layerVisibility["hindcast-corridor"]}
                  onChange={(e) =>
                    setLayerVisibility((prev) => ({ ...prev, "hindcast-corridor": e.target.checked }))
                  }
                  className="accent-purple-600 rounded"
                />
                <span>Hindcast Corridor</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-white">
                <input
                  type="checkbox"
                  checked={layerVisibility["forecast-contour"]}
                  onChange={(e) =>
                    setLayerVisibility((prev) => ({ ...prev, "forecast-contour": e.target.checked }))
                  }
                  className="accent-orange-500 rounded"
                />
                <span>Future Risk Forecast</span>
              </label>
            </div>
          </div>

          {/* TIMELINE SCRUBBER CONTROLS */}
          <div className="bg-[#06152b] border border-cyan-900/60 rounded-xl p-4 space-y-3">
            <div className="flex justify-between items-center text-xs">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded cursor-pointer transition"
                >
                  {isPlaying ? "⏸ PAUSE SIMULATION" : "▶ PLAY TRAJECTORY"}
                </button>
                <span className="text-cyan-400 font-bold">
                  STEP: {currentStep.label}
                </span>
              </div>
              <span className="text-slate-400 text-[11px]">
                UTC: {new Date(currentStep.timestampUTC).toUTCString()}
              </span>
            </div>

            <input
              type="range"
              min="0"
              max={drift.timeSteps.length - 1}
              value={timelineIndex}
              onChange={(e) => setTimelineIndex(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer h-2 bg-slate-900 rounded-lg"
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
        </div>

        {/* RIGHT ENVIRONMENTAL & SCIENTIFIC METRICS RAIL (4 COLS) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="font-bold text-teal-400 border-b border-cyan-900/40 pb-2">
              ENVIRONMENTAL FORCING METRICS
            </h3>
            <div className="space-y-2 text-[11px]">
              <div>
                <p className="text-slate-400">ATMOSPHERIC WIND DATASET</p>
                <p className="text-white font-bold">{drift.currentWindQuality.windDataset}</p>
              </div>
              <div>
                <p className="text-slate-400">OCEAN CURRENTS DATASET</p>
                <p className="text-white font-bold">{drift.currentWindQuality.currentDataset}</p>
              </div>
              <div className="p-2.5 bg-[#030d1c] rounded border border-cyan-900/40 flex justify-between items-center">
                <span className="text-slate-300">DATASET QUALITY SCORE:</span>
                <span className="text-emerald-400 font-bold text-sm">
                  {drift.currentWindQuality.qualityScore}%
                </span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="font-bold text-purple-400 border-b border-cyan-900/40 pb-2">
              HINDCAST VS FORECAST LEGEND
            </h3>
            <div className="space-y-2 text-[11px]">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-purple-500 rounded" />
                <span className="text-slate-200">Purple: Possible Origin Density Region</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-purple-400 rounded" />
                <span className="text-slate-200">Light Purple: Backward Particle Tracks</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-orange-500 rounded" />
                <span className="text-slate-200">Orange: Future Risk Forecast Contours</span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-purple-950/30 border border-purple-500/40 rounded-xl text-purple-200 text-[11px] leading-relaxed">
            <span className="font-bold">⚠️ SCIENTIFIC WARNING:</span> {drift.scientificWarning}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
