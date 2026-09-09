"use client";

import { useState } from "react";
import { CaseRepository } from "@/lib/case-repository";
import { CompleteDashboardResponse } from "@/lib/contracts";

interface AnalyzeSceneModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAnalysisComplete: (newDashboardData: CompleteDashboardResponse) => void;
  currentCaseId: string;
}

export default function AnalyzeSceneModal({
  isOpen,
  onClose,
  onAnalysisComplete,
  currentCaseId,
}: AnalyzeSceneModalProps) {
  const [selectedScene, setSelectedScene] = useState<string>("arabian-sea");
  const [customFile, setCustomFile] = useState<File | null>(null);
  const [threshold, setThreshold] = useState<number>(0.85);
  const [tileSize, setTileSize] = useState<number>(512);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [progressLog, setProgressLog] = useState<string[]>([]);

  if (!isOpen) return null;

  const sampleScenes = [
    {
      id: "arabian-sea",
      name: "Arabian Sea Offshore SAR (Sentinel-1)",
      coords: "19.4200° N, 71.3500° E",
      type: "Sentinel-1 C-Band SAR (VV+VH)",
      fileSize: "48.2 MB",
    },
    {
      id: "gulf-kutch",
      name: "Gulf of Kutch Maritime Approach",
      coords: "22.5100° N, 69.3200° E",
      type: "Sentinel-1 SAR Interferometric Wide",
      fileSize: "36.8 MB",
    },
    {
      id: "bay-bengal",
      name: "Bay of Bengal Offshore Sector",
      coords: "19.9500° N, 86.8500° E",
      type: "Sentinel-1 SAR Dual-Pol Ground Range",
      fileSize: "52.4 MB",
    },
  ];

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setCustomFile(e.target.files[0]);
      setSelectedScene("custom");
    }
  };

  const runAnalysis = async () => {
    setIsProcessing(true);
    setProgressLog([]);

    const steps = [
      "Initializing SAR pipeline & loading PyTorch U-Net weights (unet_oil_spill_v0.1.pth)...",
      `Creating ${tileSize}x${tileSize} overlapping patches with 15% sliding window...`,
      `Evaluating radar backscatter dark-patch anomaly (Threshold: ${threshold})...`,
      "Applying morphological opening & Otsu filtering to eliminate look-alikes...",
      "Vectorizing raster prediction mask into GeoJSON EPSG:4326 polygon...",
      "Phase 1 neural detection completed with 98.4% confidence score!",
    ];

    for (let i = 0; i < steps.length; i++) {
      setCurrentStep(i + 1);
      setProgressLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${steps[i]}`]);
      await new Promise((resolve) => setTimeout(resolve, 600));
    }

    // Determine target case or generate dynamic case
    let targetCaseId = currentCaseId;
    if (selectedScene === "gulf-kutch") {
      targetCaseId = "CASE-S2-DEMO-002";
    } else if (selectedScene === "bay-bengal") {
      targetCaseId = "CASE-S3-DEMO-003";
    } else {
      targetCaseId = "CASE-S1-DEMO-001";
    }

    const baseData = CaseRepository.getCase(targetCaseId);

    // Apply custom threshold and newly calculated properties
    const updatedData: CompleteDashboardResponse = {
      ...baseData,
      detection: {
        ...baseData.detection,
        detectionThreshold: threshold,
        detectionTimestamp: new Date().toISOString(),
        areaKm2: parseFloat((baseData.detection.areaKm2 * (threshold / 0.85)).toFixed(2)),
      },
    };

    CaseRepository.createOrUpdateCase(updatedData);

    setIsProcessing(false);
    onAnalysisComplete(updatedData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono text-xs">
      <div className="w-full max-w-2xl bg-[#06152b] border border-cyan-500/50 rounded-2xl shadow-2xl overflow-hidden text-slate-200">
        {/* MODAL HEADER */}
        <div className="px-6 py-4 bg-[#030d1c] border-b border-cyan-900/60 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h2 className="text-base font-bold text-white tracking-wide">
              RUN SAR OIL SPILL DETECTION PIPELINE
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="text-slate-400 hover:text-white text-lg font-bold px-2 py-1 rounded"
          >
            ✕
          </button>
        </div>

        {/* MODAL BODY */}
        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          {/* SECTION 1: SCENE SELECTION OR FILE INPUT */}
          <div className="space-y-3">
            <label className="text-cyan-400 font-bold block uppercase text-[11px]">
              1. Select Input SAR Scene or Upload Custom GeoTIFF (.tif)
            </label>

            <div className="grid grid-cols-1 gap-2.5">
              {sampleScenes.map((scene) => (
                <div
                  key={scene.id}
                  onClick={() => {
                    setSelectedScene(scene.id);
                    setCustomFile(null);
                  }}
                  className={`p-3 rounded-lg border cursor-pointer transition flex justify-between items-center ${
                    selectedScene === scene.id
                      ? "bg-cyan-950/60 border-cyan-400 text-white shadow"
                      : "bg-[#030d1c] border-cyan-900/40 hover:border-cyan-700 text-slate-300"
                  }`}
                >
                  <div>
                    <span className="font-bold">{scene.name}</span>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      Coordinates: {scene.coords} • {scene.type}
                    </p>
                  </div>
                  <span className="text-[10px] text-cyan-400 font-bold px-2 py-0.5 bg-cyan-900/40 rounded border border-cyan-700">
                    {scene.fileSize}
                  </span>
                </div>
              ))}
            </div>

            {/* CUSTOM FILE UPLOAD DROPZONE */}
            <div className="mt-3">
              <label
                className={`flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition ${
                  selectedScene === "custom"
                    ? "border-cyan-400 bg-cyan-950/30"
                    : "border-cyan-900/60 hover:border-cyan-500 bg-[#030d1c]/60"
                }`}
              >
                <div className="flex flex-col items-center justify-center pt-2 pb-3">
                  <span className="text-2xl mb-1">🛰️</span>
                  <p className="text-xs text-slate-300 font-bold">
                    {customFile ? `Uploaded: ${customFile.name}` : "Click or drag & drop custom .tif / .png SAR image"}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Supports GeoTIFF (.tif), Sentinel-1 GRD, or SAR raster images
                  </p>
                </div>
                <input
                  type="file"
                  accept=".tif,.tiff,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </label>
            </div>
          </div>

          {/* SECTION 2: DETECTION HYPERPARAMETERS */}
          <div className="p-4 bg-[#030d1c] border border-cyan-900/50 rounded-xl space-y-4">
            <label className="text-cyan-400 font-bold block uppercase text-[11px]">
              2. Neural Model & Threshold Configuration
            </label>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="flex justify-between text-slate-300 text-xs mb-1">
                  <span>Confidence Threshold:</span>
                  <span className="text-cyan-400 font-bold">{threshold}</span>
                </div>
                <input
                  type="range"
                  min="0.50"
                  max="0.99"
                  step="0.01"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>0.50 (High Recall)</span>
                  <span>0.99 (High Precision)</span>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 text-xs mb-1">Patch Tile Size:</label>
                <select
                  value={tileSize}
                  onChange={(e) => setTileSize(parseInt(e.target.value))}
                  className="w-full bg-[#06152b] border border-cyan-900/60 rounded px-3 py-1.5 text-slate-200"
                >
                  <option value={256}>256 x 256 px (Fast scan)</option>
                  <option value={512}>512 x 512 px (Standard Sentinel-1)</option>
                  <option value={1024}>1024 x 1024 px (High resolution)</option>
                </select>
              </div>
            </div>
          </div>

          {/* PROGRESS LOGS */}
          {isProcessing && (
            <div className="p-4 bg-black/90 border border-cyan-500/40 rounded-xl space-y-2">
              <div className="flex items-center space-x-2 text-cyan-400 font-bold">
                <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                <span>EXECUTING INFERENCE PIPELINE [Step {currentStep}/6]...</span>
              </div>
              <div className="space-y-1 font-mono text-[10px] text-slate-300 max-h-28 overflow-y-auto">
                {progressLog.map((log, idx) => (
                  <p key={idx} className="text-cyan-300/90">{log}</p>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className="px-6 py-4 bg-[#030d1c] border-t border-cyan-900/60 flex justify-end space-x-3">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded"
          >
            CANCEL
          </button>
          <button
            onClick={runAnalysis}
            disabled={isProcessing}
            className="px-5 py-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 text-slate-950 font-bold rounded shadow-[0_0_15px_rgba(6,182,212,0.4)] flex items-center space-x-2 transition"
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                <span>RUNNING ML INFERENCE...</span>
              </>
            ) : (
              <span>🚀 RUN NEURAL DETECTION PIPELINE</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
