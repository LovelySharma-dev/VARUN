"use client";

import { use, useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import MapPanel from "@/components/map/DynamicMapPanel";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse } from "@/lib/contracts";

export default function DetectionPage({ params }: { params: Promise<{ caseId: string }> }) {
  const resolvedParams = use(params);
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": false,
    "backward-tracks": false,
    "hindcast-corridor": false,
    "forecast-contour": false,
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

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px] font-mono text-cyan-400">
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mr-3" />
          <span>LOADING PHASE 1 DETECTION DATA...</span>
        </div>
      </DashboardLayout>
    );
  }

  const { caseSummary, detection } = data;

  return (
    <DashboardLayout caseSummary={caseSummary}>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 font-mono text-xs">
        {/* LEFT INTERACTIVE MAP (8 COLS) */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          <div className="relative flex-1 min-h-[500px]">
            <MapPanel dashboardData={data} activeLayers={layerVisibility} />

            {/* MAP HUD OVERLAY CONTROLS */}
            <div className="absolute top-4 right-4 z-20 bg-[#030914]/90 backdrop-blur-md border border-cyan-900/60 p-3 rounded-xl space-y-2 text-xs font-mono shadow-xl">
              <p className="text-[11px] font-bold text-cyan-400 uppercase border-b border-cyan-900/40 pb-1">
                DETECTION LAYERS
              </p>
              <label className="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-white">
                <input
                  type="checkbox"
                  checked={layerVisibility["spill-polygon"]}
                  onChange={(e) =>
                    setLayerVisibility((prev) => ({
                      ...prev,
                      "spill-polygon": e.target.checked,
                    }))
                  }
                  className="accent-red-500 rounded"
                />
                <span>Slick Boundary Polygon</span>
              </label>
            </div>
          </div>

          {/* SCIENTIFIC LIMITATION WARNING BANNER */}
          <div className="p-4 bg-yellow-950/30 border border-yellow-500/40 rounded-xl text-yellow-200">
            <span className="font-bold">⚠️ SCIENTIFIC NOTICE:</span> Detection mask is neural model-derived (U-Net SAR). Values represent radar backscatter oil-likelihood region, not chemical verification.
          </div>
        </div>

        {/* RIGHT MEASUREMENTS & TELEMETRY RAIL (4 COLS) */}
        <div className="lg:col-span-4 space-y-4">
          {/* SAR PREVIEW IMAGE CARD */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2">
              SAR SATELLITE IMAGE PREVIEW
            </h3>
            <div className="relative rounded-lg overflow-hidden border border-cyan-500/40 h-48">
              <img
                src={detection.sarPreviewUrl}
                alt="SAR Image Preview"
                className="w-full h-full object-cover filter brightness-95 contrast-110"
              />
              <div className="absolute top-2 left-2 px-2 py-0.5 bg-[#030914]/80 text-cyan-300 text-[10px] rounded border border-cyan-500/40">
                SENTINEL-1 SAR VV+VH
              </div>
            </div>
          </div>

          {/* SPILL MEASUREMENTS CARD */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2">
              SLICK MEASUREMENTS & PARAMETERS
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-[#030d1c] rounded border border-cyan-900/40">
                <p className="text-slate-400 text-[10px]">TOTAL AREA</p>
                <p className="text-red-400 text-lg font-bold">{detection.areaKm2} km²</p>
              </div>
              <div className="p-3 bg-[#030d1c] rounded border border-cyan-900/40">
                <p className="text-slate-400 text-[10px]">PERIMETER</p>
                <p className="text-white text-lg font-bold">{detection.perimeterKm} km</p>
              </div>
              <div className="p-3 bg-[#030d1c] rounded border border-cyan-900/40">
                <p className="text-slate-400 text-[10px]">SLICK LENGTH</p>
                <p className="text-white text-base font-bold">{detection.slickLengthKm} km</p>
              </div>
              <div className="p-3 bg-[#030d1c] rounded border border-cyan-900/40">
                <p className="text-slate-400 text-[10px]">ORIENTATION</p>
                <p className="text-white text-base font-bold">{detection.orientation}</p>
              </div>
            </div>

            <div className="pt-2 border-t border-cyan-900/40 space-y-1.5 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">DETECTION THRESHOLD:</span>
                <span className="text-cyan-300 font-bold">{detection.detectionThreshold}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">MODEL VERSION:</span>
                <span className="text-slate-200">{detection.modelVersion}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">DETECTION TIMESTAMP:</span>
                <span className="text-slate-200">{new Date(detection.detectionTimestamp).toUTCString()}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
