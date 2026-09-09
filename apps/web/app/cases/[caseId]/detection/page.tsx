"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import DashboardLayout from "@/components/layout/DashboardLayout";
import MapPanel from "@/components/map/DynamicMapPanel";
import AnalyzeSceneModal from "@/components/detection/AnalyzeSceneModal";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse } from "@/lib/contracts";

export default function DetectionPage({ params }: { params: Promise<{ caseId: string }> }) {
  const resolvedParams = use(params);
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSceneOption, setSelectedSceneOption] = useState("S1A_IW_GRDH_1SDV_20260820T053000");
  const [customFileName, setCustomFileName] = useState<string>("");
  const [isInferencing, setIsInferencing] = useState(false);
  const [activeStep, setActiveStep] = useState(5); // 5 = all completed
  const [viewMode, setViewMode] = useState<"vector" | "radar" | "mask">("vector");
  const [threshold, setThreshold] = useState(0.56);

  const [layerVisibility] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": false,
    "backward-tracks": false,
    "hindcast-corridor": false,
    "forecast-contour": false,
    "candidate-tracks": false,
    "particles-cloud": false,
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

  const handleCustomFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setCustomFileName(e.target.files[0].name);
      setSelectedSceneOption("CUSTOM_UPLOAD");
    }
  };

  const handleRunDetectionClick = async () => {
    setIsInferencing(true);
    setActiveStep(1);

    const stepIntervals = [
      { step: 1, delay: 400 }, // Validate Input
      { step: 2, delay: 500 }, // Normalize
      { step: 3, delay: 600 }, // Tile Inference
      { step: 4, delay: 400 }, // Stitch Mask
      { step: 5, delay: 300 }, // Build Polygon
    ];

    for (const s of stepIntervals) {
      await new Promise((r) => setTimeout(r, s.delay));
      setActiveStep(s.step);
    }

    setIsInferencing(false);
  };

  const handleDownloadGeoJSON = () => {
    if (!data?.detection?.spillPolygon) return;
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(data.detection.spillPolygon, null, 2)
    )}`;
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", jsonString);
    downloadAnchor.setAttribute("download", `oil_slick_polygon_${resolvedParams.caseId}.geojson`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

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
      <AnalyzeSceneModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAnalysisComplete={(newData) => setData(newData)}
        currentCaseId={caseSummary.caseId}
      />

      {/* 3-COLUMN LAYOUT MATCHING OFFICIAL SIH26143 SPEC GUIDE (PAGE 6) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 font-mono text-xs text-slate-200">
        
        {/* ========================================================= */}
        {/* LEFT COLUMN: INPUT SAR SCENE & PROCESSING STEPS (3 COLS) */}
        {/* ========================================================= */}
        <div className="lg:col-span-3 space-y-4">
          
          {/* INPUT SAR SCENE CARD */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2 flex items-center justify-between">
              <span>INPUT SAR SCENE</span>
              <span className="text-[10px] text-slate-400 font-normal">PHASE 1</span>
            </h3>

            {/* SCENE PRESET SELECTOR */}
            <div className="space-y-1.5">
              <label className="text-slate-400 text-[10px] uppercase font-semibold">
                Sentinel-1 SAR Product:
              </label>
              <select
                value={selectedSceneOption}
                onChange={(e) => setSelectedSceneOption(e.target.value)}
                className="w-full bg-[#030d1c] border border-cyan-900/60 rounded px-2.5 py-1.5 text-slate-200 text-[11px] focus:border-cyan-400 focus:outline-none"
              >
                <option value="S1A_IW_GRDH_1SDV_20260820T053000">
                  Sentinel-1 Sigma0 (VV+VH) 2048x2048 TIFF
                </option>
                <option value="S1B_IW_GRDH_1SDV_20260904T142000">
                  Gulf of Kutch SAR Scene (2048x2048)
                </option>
                <option value="S1A_IW_GRDH_1SDV_20260903T061500">
                  Bay of Bengal SAR Scene (2048x2048)
                </option>
                {customFileName && (
                  <option value="CUSTOM_UPLOAD">Custom: {customFileName}</option>
                )}
              </select>
            </div>

            {/* CUSTOM FILE UPLOAD / BROWSE BUTTON */}
            <div className="space-y-1.5">
              <label className="text-slate-400 text-[10px] uppercase font-semibold">
                Input Custom File (.tif / .png):
              </label>
              <label className="flex items-center justify-center px-3 py-2 bg-[#030d1c] border border-dashed border-cyan-800 hover:border-cyan-400 rounded cursor-pointer transition text-center">
                <span className="text-[11px] text-cyan-300 font-bold truncate">
                  {customFileName ? `📂 ${customFileName}` : "📁 Browse / Drop SAR .tif"}
                </span>
                <input
                  type="file"
                  accept=".tif,.tiff,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={handleCustomFileInput}
                />
              </label>
            </div>

            {/* THRESHOLD SLIDER */}
            <div className="space-y-1.5 pt-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-400">Confidence Threshold:</span>
                <span className="text-cyan-400 font-bold">{(threshold * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.30"
                max="0.90"
                step="0.02"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-900 rounded"
              />
            </div>

            {/* ACTION BUTTONS */}
            <div className="pt-2 space-y-2">
              <button
                onClick={handleRunDetectionClick}
                disabled={isInferencing}
                className="w-full py-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold rounded shadow-[0_0_12px_rgba(225,29,72,0.4)] flex items-center justify-center space-x-2 transition cursor-pointer"
              >
                {isInferencing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>INFERENCING...</span>
                  </>
                ) : (
                  <span>▶ RUN DETECTION</span>
                )}
              </button>

              <button
                onClick={() => setIsModalOpen(true)}
                className="w-full py-1.5 bg-[#030d1c] hover:bg-[#081e3d] text-cyan-400 border border-cyan-900/60 hover:border-cyan-500 rounded font-bold transition text-[11px] cursor-pointer"
              >
                ⚙️ CONFIGURE HYPERPARAMETERS
              </button>
            </div>
          </div>

          {/* PROCESSING STEPS CARD */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2">
              PROCESSING STEPS
            </h3>

            <div className="space-y-2 text-[11px]">
              {[
                { step: 1, name: "Validate Input" },
                { step: 2, name: "Normalize" },
                { step: 3, name: "Tile Inference" },
                { step: 4, name: "Stitch Mask" },
                { step: 5, name: "Build Polygon" },
              ].map((s) => {
                const isDone = activeStep >= s.step;
                const isCurrent = activeStep === s.step && isInferencing;

                return (
                  <div
                    key={s.step}
                    className={`flex items-center space-x-2.5 p-2 rounded transition ${
                      isDone
                        ? "bg-emerald-950/40 text-emerald-300 border border-emerald-500/30"
                        : "bg-[#030d1c] text-slate-500 border border-slate-800"
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        isDone
                          ? "bg-emerald-500 text-slate-950"
                          : isCurrent
                          ? "bg-cyan-500 text-slate-950 animate-spin"
                          : "bg-slate-700 text-slate-300"
                      }`}
                    >
                      {isDone ? "✓" : s.step}
                    </span>
                    <span className="font-semibold">{s.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* CENTER COLUMN: INTERACTIVE MAP & OVERLAY VIEWER (6 COLS)  */}
        {/* ========================================================= */}
        <div className="lg:col-span-6 flex flex-col space-y-3">
          
          {/* VIEWPORT MODE SELECTOR BAR */}
          <div className="flex items-center justify-between p-2 bg-[#06152b] border border-cyan-900/60 rounded-xl">
            <div className="flex space-x-1">
              <button
                onClick={() => setViewMode("vector")}
                className={`px-3 py-1.5 rounded text-xs font-bold transition flex items-center space-x-1.5 cursor-pointer ${
                  viewMode === "vector"
                    ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#030d1c]"
                }`}
              >
                <span>🌐</span>
                <span>TACTICAL VECTOR GIS</span>
              </button>
              <button
                onClick={() => setViewMode("radar")}
                className={`px-3 py-1.5 rounded text-xs font-bold transition flex items-center space-x-1.5 cursor-pointer ${
                  viewMode === "radar"
                    ? "bg-rose-500 text-white shadow-md shadow-rose-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#030d1c]"
                }`}
              >
                <span>🛰️</span>
                <span>SAR RADAR BACKSCATTER</span>
              </button>
              <button
                onClick={() => setViewMode("mask")}
                className={`px-3 py-1.5 rounded text-xs font-bold transition flex items-center space-x-1.5 cursor-pointer ${
                  viewMode === "mask"
                    ? "bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#030d1c]"
                }`}
              >
                <span>🧠</span>
                <span>NEURAL MASK</span>
              </button>
            </div>

            <div className="text-[10px] text-cyan-400 font-bold hidden sm:block">
              {detection.modelVersion}
            </div>
          </div>

          {/* VIEWPORT CANVAS */}
          <div className="relative flex-1 min-h-[520px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#030d1c] shadow-2xl">
            {viewMode === "vector" ? (
              <MapPanel dashboardData={data} activeLayers={layerVisibility} />
            ) : viewMode === "radar" ? (
              <div className="relative w-full h-full min-h-[520px] flex items-center justify-center bg-black">
                <Image
                  src={detection.sarPreviewUrl || "/ship_oil_spill.jpg"}
                  alt="Sentinel-1 SAR C-Band Imagery"
                  fill
                  sizes="(max-width: 1200px) 100vw, 50vw"
                  className="object-cover opacity-90"
                />
                <div className="absolute inset-0 bg-rose-500/10 pointer-events-none" />
                
                {/* RADAR OVERLAY HUD */}
                <div className="absolute top-4 left-4 z-10 bg-black/85 backdrop-blur-md border border-rose-500/60 p-3 rounded-lg text-[11px] text-rose-300 space-y-1">
                  <p className="font-bold text-rose-400 flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                    <span>SENTINEL-1 C-BAND SAR PRODUCT</span>
                  </p>
                  <p className="text-slate-300">Polarization: <b>VV + VH Co-Polarized</b></p>
                  <p className="text-slate-300">Spatial Resolution: <b>10m Pixel Spacing</b></p>
                  <p className="text-slate-300">Oil Confidence: <b>87.0% (Dark Formation)</b></p>
                </div>

                <div className="absolute bottom-4 right-4 z-10 bg-black/85 border border-cyan-900/60 px-3 py-1.5 rounded text-[10px] text-slate-300">
                  Scene Centroid: 18.9200° N, 72.0100° E
                </div>
              </div>
            ) : (
              <div className="relative w-full h-full min-h-[520px] flex items-center justify-center bg-[#050505]">
                <Image
                  src={detection.probabilityMapUrl || "/ship_oil_spill.jpg"}
                  alt="Neural Probability Map"
                  fill
                  sizes="(max-width: 1200px) 100vw, 50vw"
                  className="object-cover grayscale contrast-200"
                />
                <div className="absolute inset-0 bg-emerald-500/20 mix-blend-color-dodge pointer-events-none" />
                
                <div className="absolute top-4 left-4 z-10 bg-black/85 backdrop-blur-md border border-emerald-500/60 p-3 rounded-lg text-[11px] text-emerald-300 space-y-1">
                  <p className="font-bold text-emerald-400 flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span>NEURAL SEGMENTATION PROBABILITY MASK</span>
                  </p>
                  <p className="text-slate-300">Architecture: <b>U-Net ResNet-34 Backbone</b></p>
                  <p className="text-slate-300">Threshold: <b>{threshold}</b></p>
                  <p className="text-slate-300">Segmented Pixels: <b>32,400 (3.24 km²)</b></p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ========================================================= */}
        {/* RIGHT COLUMN: MODEL METRICS & GEOMETRY (3 COLS)           */}
        {/* ========================================================= */}
        <div className="lg:col-span-3 space-y-4">
          
          {/* FROZEN MODEL VALIDATION METRICS */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-cyan-400 border-b border-cyan-900/40 pb-2 flex items-center justify-between">
              <span>MODEL VALIDATION</span>
              <span className="text-[10px] text-emerald-400 font-bold">FROZEN BENCHMARK</span>
            </h3>

            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="p-2 bg-[#030d1c] border border-cyan-900/40 rounded">
                <span className="text-[10px] text-slate-400 block">DICE SCORE</span>
                <span className="text-emerald-400 font-extrabold text-base">0.81</span>
              </div>
              <div className="p-2 bg-[#030d1c] border border-cyan-900/40 rounded">
                <span className="text-[10px] text-slate-400 block">IoU (JACCARD)</span>
                <span className="text-cyan-400 font-extrabold text-base">0.69</span>
              </div>
              <div className="p-2 bg-[#030d1c] border border-cyan-900/40 rounded">
                <span className="text-[10px] text-slate-400 block">PRECISION</span>
                <span className="text-teal-400 font-extrabold text-base">0.84</span>
              </div>
              <div className="p-2 bg-[#030d1c] border border-cyan-900/40 rounded">
                <span className="text-[10px] text-slate-400 block">RECALL</span>
                <span className="text-purple-400 font-extrabold text-base">0.79</span>
              </div>
            </div>
          </div>

          {/* EXTRACTED SLICK GEOMETRY TELEMETRY */}
          <div className="p-4 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3 shadow-lg">
            <h3 className="font-bold text-rose-400 border-b border-cyan-900/40 pb-2">
              EXTRACTED SLICK GEOMETRY
            </h3>

            <div className="space-y-2 text-[11px]">
              <div className="flex justify-between items-center py-1 border-b border-cyan-950">
                <span className="text-slate-400">Centroid Lat:</span>
                <span className="text-white font-bold">18.9200° N</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-cyan-950">
                <span className="text-slate-400">Centroid Lon:</span>
                <span className="text-white font-bold">72.0100° E</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-cyan-950">
                <span className="text-slate-400">Surface Area:</span>
                <span className="text-rose-400 font-extrabold text-sm">{detection.areaKm2} km²</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-cyan-950">
                <span className="text-slate-400">Perimeter:</span>
                <span className="text-white font-bold">{detection.perimeterKm} km</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-cyan-950">
                <span className="text-slate-400">Major Slick Length:</span>
                <span className="text-white font-bold">{detection.slickLengthKm} km</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400">Drift Alignment:</span>
                <span className="text-cyan-400 font-bold">{detection.orientation}</span>
              </div>
            </div>
          </div>

          {/* EXPORT & PROCEED ACTIONS */}
          <div className="space-y-2">
            <button
              onClick={handleDownloadGeoJSON}
              className="w-full py-2 bg-[#030d1c] hover:bg-[#0a2342] text-cyan-300 border border-cyan-800 hover:border-cyan-400 rounded font-bold transition flex items-center justify-center space-x-2 cursor-pointer text-[11px]"
            >
              <span>💾</span>
              <span>DOWNLOAD GEOJSON POLYGON</span>
            </button>

            <Link
              href={`/cases/${caseSummary.caseId}/drift`}
              className="w-full py-2.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-extrabold rounded shadow-lg flex items-center justify-center space-x-2 transition text-center text-xs"
            >
              <span>PROCEED TO PHASE 2 DRIFT ➔</span>
            </Link>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
