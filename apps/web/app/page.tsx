"use client";

import { useState, useRef } from "react";
import Link from "next/link";

export default function LandingPage() {
  const [isScanning, setIsScanning] = useState(false);
  const [isDetected, setIsDetected] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [activeFeatureTab, setActiveFeatureTab] = useState<"all" | "phase1" | "phase2" | "phase3" | "gis">("all");
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Web Audio Siren Synthesizer
  const playSirenSound = () => {
    if (!soundEnabled) return;
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(440, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.8);
      osc.frequency.linearRampToValueAtTime(440, ctx.currentTime + 1.6);
      osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 2.4);

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 3.0);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 3.0);
    } catch {
      // Audio context fallback
    }
  };

  const triggerScanSequence = () => {
    setIsScanning(true);
    setIsDetected(false);
    setScanProgress(0);
    playSirenSound();

    const interval = setInterval(() => {
      setScanProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsDetected(true);
          return 100;
        }
        return prev + 10;
      });
    }, 180);
  };

  const allFeatures = [
    // Phase 1 Features
    {
      category: "phase1",
      badge: "PHASE 1 • SAR AI",
      icon: "🛰️",
      title: "Sentinel-1 Dual-Pol SAR",
      description: "Processes Sentinel-1 Synthetic Aperture Radar VV+VH dual-polarization satellite tiles. Operating at 5.405 GHz C-band, it penetrates cloud cover and darkness for 24/7 slick detection.",
      borderColor: "border-cyan-400",
      bgColor: "bg-[#0a2342]",
      badgeColor: "bg-cyan-400 text-slate-950 font-black",
    },
    {
      category: "phase1",
      badge: "PHASE 1 • NEURAL MASK",
      icon: "🧠",
      title: "U-Net Neural Segmentation",
      description: "Deep U-Net convolutional neural network isolates true oil slick candidates from look-alikes such as low wind areas, biogenic sheens, and ocean internal waves.",
      borderColor: "border-cyan-400",
      bgColor: "bg-[#0a2342]",
      badgeColor: "bg-cyan-400 text-slate-950 font-black",
    },
    {
      category: "phase1",
      badge: "PHASE 1 • METRICS",
      icon: "📐",
      title: "Automated Geometry Extraction",
      description: "Calculates exact slick surface area (km²), perimeter (km), major/minor axis length, orientation angle (deg), and centroid coordinates automatically.",
      borderColor: "border-cyan-400",
      bgColor: "bg-[#0a2342]",
      badgeColor: "bg-cyan-400 text-slate-950 font-black",
    },
    // Phase 2 Features
    {
      category: "phase2",
      badge: "PHASE 2 • HINDCAST",
      icon: "⏪",
      title: "-48h Backward Hindcast Simulation",
      description: "Simulates thousands of Lagrangian oil particles backwards in time using OpenOil physics engines to pinpoint the exact probable discharge origin zone.",
      borderColor: "border-teal-400",
      bgColor: "bg-[#082a3d]",
      badgeColor: "bg-teal-400 text-slate-950 font-black",
    },
    {
      category: "phase2",
      badge: "PHASE 2 • FORECAST",
      icon: "⏩",
      title: "+48h Forward Risk Forecast",
      description: "Projects future slick dispersion, weathering, and coastal landing trajectories up to +48 hours ahead for rapid coastal defense deployment.",
      borderColor: "border-teal-400",
      bgColor: "bg-[#082a3d]",
      badgeColor: "bg-teal-400 text-slate-950 font-black",
    },
    {
      category: "phase2",
      badge: "PHASE 2 • PHYSICS",
      icon: "💨",
      title: "Meteo-Oceanic Forcing Engine",
      description: "Dynamically ingests NCAR GFS 0.25° atmospheric wind vectors and HYCOM 1/12° ocean surface currents for realistic hydrodynamic forcing.",
      borderColor: "border-teal-400",
      bgColor: "bg-[#082a3d]",
      badgeColor: "bg-teal-400 text-slate-950 font-black",
    },
    // Phase 3 Features
    {
      category: "phase3",
      badge: "PHASE 3 • ATTRIBUTION",
      icon: "🚢",
      title: "Top-3 Candidate Vessel Ranking",
      description: "Correlates historical PostGIS AIS vessel trajectories against origin density contours to isolate top suspect vessels during the estimated discharge window.",
      borderColor: "border-purple-400",
      bgColor: "bg-[#1d1238]",
      badgeColor: "bg-purple-400 text-slate-950 font-black",
    },
    {
      category: "phase3",
      badge: "PHASE 3 • EXPLAINABLE AI",
      icon: "📊",
      title: "Multi-Component Score Breakdown",
      description: "Provides transparent, judge-friendly component breakdown covering spatial proximity, temporal overlap, corridor match, vessel speed behavior, and AIS gaps.",
      borderColor: "border-purple-400",
      bgColor: "bg-[#1d1238]",
      badgeColor: "bg-purple-400 text-slate-950 font-black",
    },
    {
      category: "phase3",
      badge: "PHASE 3 • PRIVACY",
      icon: "🔒",
      title: "Privacy & Legal Protection Engine",
      description: "Strictly enforces anonymized candidate IDs (e.g. CAND-003), masking raw MMSI and using non-prejudicial investigative relevance scoring terminology.",
      borderColor: "border-purple-400",
      bgColor: "bg-[#1d1238]",
      badgeColor: "bg-purple-400 text-slate-950 font-black",
    },
    // GIS Features
    {
      category: "gis",
      badge: "DASHBOARD • GIS",
      icon: "🗺️",
      title: "Interactive MapLibre Engine",
      description: "High-performance vector WebGL map engine with layer toggles for slick fill, origin contours, particle tracks, forecast risk, and vessel trajectories.",
      borderColor: "border-emerald-400",
      bgColor: "bg-[#082d27]",
      badgeColor: "bg-emerald-400 text-slate-950 font-black",
    },
    {
      category: "gis",
      badge: "DASHBOARD • TIMELINE",
      icon: "🎛️",
      title: "Unified Temporal Scrubber",
      description: "Step-by-step interactive timeline scrubber enabling judges to inspect trajectory evolution from -48h past release to +48h future forecast risk.",
      borderColor: "border-emerald-400",
      bgColor: "bg-[#082d27]",
      badgeColor: "bg-emerald-400 text-slate-950 font-black",
    },
    {
      category: "gis",
      badge: "DASHBOARD • OFFLINE",
      icon: "💾",
      title: "Offline Replay Fallback Mode",
      description: "Pre-packaged verified offline replay datasets ensure 100% demonstration stability even during internet-disconnected hackathon judging environments.",
      borderColor: "border-emerald-400",
      bgColor: "bg-[#082d27]",
      badgeColor: "bg-emerald-400 text-slate-950 font-black",
    },
  ];

  const filteredFeatures =
    activeFeatureTab === "all"
      ? allFeatures
      : allFeatures.filter((f) => f.category === activeFeatureTab);

  return (
    <div className="relative min-h-screen bg-[#020712] text-slate-100 font-sans selection:bg-cyan-500 selection:text-slate-950 overflow-x-hidden">
      {/* BACKGROUND OCEAN GRADIENT & TACTICAL GRID */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-radial from-[#0c2240] via-[#051124] to-[#020611] opacity-90" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0284c70f_1px,transparent_1px),linear-gradient(to_bottom,#0284c70f_1px,transparent_1px)] bg-[size:4rem_4rem]" />
      </div>

      {/* TOP NAVIGATION BAR */}
      <header className="relative z-30 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto w-full border-b border-cyan-400/80 bg-[#061224]/95 backdrop-blur-md sticky top-0 shadow-lg">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-cyan-400/20 border-2 border-cyan-400 text-cyan-300 font-black shadow-md shadow-cyan-400/30">
            <span className="font-mono text-base">VA</span>
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-xl font-black tracking-wider text-white">
              VARUN-ASTRA
            </span>
            <span className="text-[10px] font-mono text-cyan-300 tracking-tight font-bold">
              Marine Oil Spill Intelligence Platform
            </span>
          </div>
          <span className="hidden md:inline-block px-3 py-0.5 text-[11px] font-mono bg-cyan-400 text-slate-950 border border-cyan-300 rounded-full ml-2 font-black">
            SIH-26143
          </span>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="flex items-center space-x-2 px-3.5 py-1.5 text-xs font-mono rounded-lg bg-[#0a1b33] border-2 border-cyan-400 hover:border-cyan-300 transition text-white cursor-pointer font-bold"
            title="Toggle Emergency Audio Alert"
          >
            <span>{soundEnabled ? "🔊 SIREN ON" : "🔇 SIREN MUTED"}</span>
          </button>

          <Link
            href="/cases"
            className="px-5 py-2.5 text-xs font-mono font-black rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 shadow-xl shadow-cyan-400/40 transition transform hover:-translate-y-0.5"
          >
            LAUNCH DASHBOARD ➔
          </Link>
        </div>
      </header>

      {/* HERO SECTION */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-8 pb-16 lg:pt-12 lg:pb-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* HERO LEFT COLUMN */}
        <div className="lg:col-span-6 space-y-6 text-left">
          <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-cyan-950 border-2 border-cyan-400 text-cyan-300 text-xs font-mono font-bold shadow-md shadow-cyan-400/20">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <span>Autonomous Marine Oil Slick Intelligence System</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-tight">
            VARUN-ASTRA <br />
            <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-300 bg-clip-text text-transparent">
              Real-Time Marine Oil Spill Intelligence
            </span>
          </h1>

          <p className="text-slate-100 text-base sm:text-lg font-semibold leading-relaxed">
            Autonomous end-to-end platform integrating Sentinel-1 SAR U-Net neural segmentation, OpenOil hydrodynamic drift simulation, and PostGIS AIS vessel attribution.
          </p>

          {/* ACTION BUTTONS */}
          <div className="flex flex-wrap items-center gap-4 pt-2">
            {!isScanning ? (
              <button
                onClick={triggerScanSequence}
                className="px-6 py-3.5 bg-gradient-to-r from-cyan-400 to-teal-400 hover:from-cyan-300 hover:to-teal-300 text-slate-950 font-black rounded-xl shadow-xl shadow-cyan-400/40 transition transform hover:-translate-y-0.5 active:translate-y-0 flex items-center space-x-2 cursor-pointer text-sm"
              >
                <span>🔍 TRIGGER INCIDENT SCAN</span>
              </button>
            ) : (
              <div className="flex items-center space-x-3">
                {isDetected && (
                  <Link
                    href="/cases/CASE-S1-DEMO-001/detection"
                    className="px-6 py-3.5 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl shadow-lg shadow-red-600/40 transition transform hover:-translate-y-0.5 flex items-center space-x-2"
                  >
                    <span>GO TO PHASE 1 DETECTION ➔</span>
                  </Link>
                )}
                <button
                  onClick={triggerScanSequence}
                  className="px-4 py-3.5 bg-[#0e213c] hover:bg-[#142d52] text-cyan-300 text-xs font-mono rounded-xl border-2 border-cyan-400 font-bold transition"
                >
                  RE-SCAN
                </button>
              </div>
            )}

            <Link
              href="/cases"
              className="px-6 py-3.5 bg-[#0a182e] hover:bg-[#0f2445] text-white font-bold rounded-xl border-2 border-cyan-400 hover:border-cyan-300 transition"
            >
              Overview Screen
            </Link>
          </div>

          {/* SYSTEM STATS FOOTPRINT */}
          <div className="grid grid-cols-3 gap-4 pt-4 border-t-2 border-cyan-400/40 font-mono text-xs">
            <div>
              <p className="text-slate-300 font-semibold">SAR SATELLITE</p>
              <p className="text-cyan-300 font-extrabold text-sm">Sentinel-1A VV+VH</p>
            </div>
            <div>
              <p className="text-slate-300 font-semibold">DRIFT MODEL</p>
              <p className="text-cyan-300 font-extrabold text-sm">OpenOil 48h</p>
            </div>
            <div>
              <p className="text-slate-300 font-semibold">VESSEL ETL</p>
              <p className="text-cyan-300 font-extrabold text-sm">PostGIS AIS</p>
            </div>
          </div>
        </div>

        {/* HERO RIGHT COLUMN */}
        <div className="lg:col-span-6 relative">
          <div className="relative rounded-2xl overflow-hidden border-2 border-cyan-400 shadow-2xl shadow-cyan-950 bg-[#071529]">
            <img
              src="/ship_oil_spill.jpg"
              alt="VARUN-ASTRA Ship Oil Spill Incident Telemetry"
              className="w-full h-[420px] sm:h-[480px] object-cover object-center filter brightness-95 contrast-105"
            />

            <div className="absolute inset-0 bg-gradient-to-t from-[#030914] via-transparent to-transparent opacity-80" />

            <div className="absolute top-4 left-4 right-4 flex justify-between items-center z-10 font-mono text-xs">
              <div className="px-3.5 py-1.5 rounded-md bg-[#030914]/95 backdrop-blur-md border-2 border-cyan-400 text-cyan-300 font-black flex items-center space-x-2 shadow-lg">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                <span>FEED: ARABIAN SEA SECTOR 4</span>
              </div>

              <div className="px-3.5 py-1.5 rounded-md bg-[#030914]/95 backdrop-blur-md border-2 border-cyan-400 text-white font-black shadow-lg">
                18.9214° N, 72.8347° E
              </div>
            </div>

            {isScanning && (
              <div className="absolute inset-4 rounded-xl z-20 bg-[#030914]/95 backdrop-blur-md border-2 border-cyan-400 p-6 flex flex-col justify-between animate-in fade-in zoom-in-95 duration-300 shadow-2xl">
                <div className="flex items-center justify-between border-b-2 border-cyan-400 pb-3">
                  <div className="flex items-center space-x-2 font-mono text-xs text-cyan-300 font-black">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
                    <span>U-NET SAR SCANNER V2.4 ACTIVE</span>
                  </div>
                  <span className="font-mono text-xs text-white font-black">
                    {scanProgress}% COMPLETE
                  </span>
                </div>

                <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-cyan-400 my-2">
                  <div
                    className="bg-gradient-to-r from-cyan-400 to-emerald-400 h-full transition-all duration-200 shadow-md shadow-cyan-400/50"
                    style={{ width: `${scanProgress}%` }}
                  />
                </div>

                {isDetected ? (
                  <div className="space-y-3 py-2 animate-in fade-in duration-300">
                    <div className="inline-flex items-center space-x-2 px-3 py-1 bg-red-500/30 border-2 border-red-500 text-red-300 text-xs font-mono font-black rounded-md">
                      <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
                      <span>CRITICAL DETECTED: OIL SPILL SLICK</span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                      <div className="p-2.5 rounded-lg bg-[#071830] border-2 border-cyan-400">
                        <p className="text-slate-200 text-[10px] font-bold">CONFIDENCE SCORE</p>
                        <p className="text-cyan-300 text-base font-black">98.4% MATCH</p>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#071830] border-2 border-cyan-400">
                        <p className="text-slate-200 text-[10px] font-bold">ESTIMATED AREA</p>
                        <p className="text-emerald-300 text-base font-black">3.24 km²</p>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#071830] border-2 border-cyan-400">
                        <p className="text-slate-200 text-[10px] font-bold">TARGET CANDIDATE</p>
                        <p className="text-cyan-300 text-sm font-black">CAND-003</p>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#071830] border-2 border-cyan-400">
                        <p className="text-slate-200 text-[10px] font-bold">DRIFT MODEL</p>
                        <p className="text-cyan-300 text-sm font-black">OpenOil Ready</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-3">
                    <div className="w-10 h-10 border-3 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto" />
                    <p className="font-mono text-cyan-300 text-xs font-black tracking-wider animate-pulse">
                      PROCESSING SYNTHETIC APERTURE RADAR (SAR) TILES...
                    </p>
                  </div>
                )}

                <div className="pt-2 flex justify-end">
                  {isDetected && (
                    <Link
                      href="/cases/CASE-S1-DEMO-001/detection"
                      className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-black font-mono text-xs rounded-lg transition shadow-lg shadow-emerald-400/30"
                    >
                      INSPECT PHASE 1 RESULTS ➔
                    </Link>
                  )}
                </div>
              </div>
            )}

            <div className="absolute bottom-4 left-4 right-4 z-10 bg-[#030914]/90 backdrop-blur-md p-3 rounded-lg border-2 border-cyan-400 flex items-center justify-between text-xs font-mono shadow-lg">
              <span className="text-white font-black">INCIDENT #2026-089 // BOMBAY HIGH</span>
              <span className="text-cyan-300 font-black">LIVE TELEMETRY</span>
            </div>
          </div>
        </div>
      </section>

      {/* HIGH-CONTRAST VIBRANT FEATURES MATRIX SECTION */}
      <section className="py-20 px-6 max-w-7xl mx-auto border-2 border-cyan-400 bg-[#06152b] rounded-3xl my-10 shadow-2xl relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-14 space-y-4">
          <span className="px-4 py-1.5 rounded-full bg-cyan-400 text-slate-950 text-xs font-mono font-black border border-cyan-300 shadow-md shadow-cyan-400/20 uppercase tracking-wider">
            SYSTEM CAPABILITIES & ARCHITECTURE
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            VARUN-ASTRA Complete Feature Matrix
          </h2>
          <p className="text-slate-100 text-base font-semibold leading-relaxed">
            Engineered for Smart India Hackathon (SIH-26143) to provide transparent, judge-friendly oil slick detection, drift forecasting, and vessel attribution.
          </p>

          {/* FEATURE CATEGORY FILTER TABS */}
          <div className="flex flex-wrap justify-center gap-3 pt-4 font-mono text-xs font-black">
            <button
              onClick={() => setActiveFeatureTab("all")}
              className={`px-5 py-2.5 rounded-xl transition border-2 cursor-pointer ${
                activeFeatureTab === "all"
                  ? "bg-cyan-400 text-slate-950 border-cyan-300 shadow-lg shadow-cyan-400/40"
                  : "bg-[#0b2447] text-white border-cyan-400/80 hover:bg-[#10305c]"
              }`}
            >
              ALL 12 FEATURES
            </button>

            <button
              onClick={() => setActiveFeatureTab("phase1")}
              className={`px-5 py-2.5 rounded-xl transition border-2 cursor-pointer ${
                activeFeatureTab === "phase1"
                  ? "bg-cyan-400 text-slate-950 border-cyan-300 shadow-lg shadow-cyan-400/40"
                  : "bg-[#0b2447] text-white border-cyan-400/80 hover:bg-[#10305c]"
              }`}
            >
              1. SAR Neural Detection
            </button>

            <button
              onClick={() => setActiveFeatureTab("phase2")}
              className={`px-5 py-2.5 rounded-xl transition border-2 cursor-pointer ${
                activeFeatureTab === "phase2"
                  ? "bg-teal-400 text-slate-950 border-teal-300 shadow-lg shadow-teal-400/40"
                  : "bg-[#0b2447] text-white border-teal-400/80 hover:bg-[#10305c]"
              }`}
            >
              2. OpenOil Particle Drift
            </button>

            <button
              onClick={() => setActiveFeatureTab("phase3")}
              className={`px-5 py-2.5 rounded-xl transition border-2 cursor-pointer ${
                activeFeatureTab === "phase3"
                  ? "bg-purple-400 text-slate-950 border-purple-300 shadow-lg shadow-purple-400/40"
                  : "bg-[#0b2447] text-white border-purple-400/80 hover:bg-[#10305c]"
              }`}
            >
              3. AIS Vessel Attribution
            </button>

            <button
              onClick={() => setActiveFeatureTab("gis")}
              className={`px-5 py-2.5 rounded-xl transition border-2 cursor-pointer ${
                activeFeatureTab === "gis"
                  ? "bg-emerald-400 text-slate-950 border-emerald-300 shadow-lg shadow-emerald-400/40"
                  : "bg-[#0b2447] text-white border-emerald-400/80 hover:bg-[#10305c]"
              }`}
            >
              4. MapLibre GIS & Replay
            </button>
          </div>
        </div>

        {/* HIGH CONTRAST FEATURE CARDS GRID */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 font-mono">
          {filteredFeatures.map((feat, idx) => (
            <div
              key={idx}
              className={`p-6 ${feat.bgColor} border-2 ${feat.borderColor} rounded-2xl space-y-4 shadow-2xl transform transition hover:-translate-y-1`}
            >
              <div className="flex justify-between items-center">
                <div className="w-12 h-12 rounded-xl bg-slate-950 border-2 border-white/40 flex items-center justify-center text-2xl shadow-md">
                  {feat.icon}
                </div>
                <span className={`px-3 py-1.5 rounded-md text-[11px] font-black uppercase shadow-sm ${feat.badgeColor}`}>
                  {feat.badge}
                </span>
              </div>

              <h3 className="text-xl font-black text-white tracking-tight">
                {feat.title}
              </h3>

              <p className="text-slate-100 text-xs leading-relaxed font-bold">
                {feat.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* HIGH-CONTRAST BOLD FOUR-SCREEN DASHBOARD ARCHITECTURE SECTION */}
      <section className="py-20 px-6 max-w-7xl mx-auto border-2 border-cyan-400 bg-[#061833] rounded-3xl my-10 shadow-2xl relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-14 space-y-4">
          <span className="px-4 py-1.5 rounded-full bg-cyan-400 text-slate-950 text-xs font-mono font-black border border-cyan-300 shadow-md shadow-cyan-400/20 uppercase tracking-wider">
            FOUR-SCREEN DASHBOARD ARCHITECTURE
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Inspect VARUN-ASTRA Dashboard Screens
          </h2>
          <p className="text-slate-100 text-base font-semibold leading-relaxed">
            Click any screen below to enter the interactive judge-ready dashboard routes.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 font-mono">
          {/* Screen 1 */}
          <div className="p-6 rounded-2xl bg-[#0a274c] border-2 border-cyan-400 hover:border-cyan-300 transition space-y-4 flex flex-col justify-between shadow-2xl">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="px-3 py-1 rounded bg-cyan-400 text-slate-950 text-xs font-black">
                  SCREEN 1
                </span>
                <span className="text-xs font-black text-cyan-300">
                  OVERVIEW
                </span>
              </div>
              <h4 className="text-2xl font-black text-white">
                Case Overview
              </h4>
              <p className="text-slate-100 text-xs font-bold leading-relaxed">
                Summary of all active incidents, phase pipeline run statuses, system warnings, and offline replay badges.
              </p>
            </div>
            <Link
              href="/cases"
              className="w-full py-2.5 bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-xs rounded-lg text-center transition shadow-md shadow-cyan-400/30 inline-block"
            >
              OPEN CASE OVERVIEW ➔
            </Link>
          </div>

          {/* Screen 2 */}
          <div className="p-6 rounded-2xl bg-[#0a274c] border-2 border-cyan-400 hover:border-cyan-300 transition space-y-4 flex flex-col justify-between shadow-2xl">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="px-3 py-1 rounded bg-cyan-400 text-slate-950 text-xs font-black">
                  SCREEN 2
                </span>
                <span className="text-xs font-black text-cyan-300">
                  PHASE 1
                </span>
              </div>
              <h4 className="text-2xl font-black text-white">
                Phase 1 Detection
              </h4>
              <p className="text-slate-100 text-xs font-bold leading-relaxed">
                SAR satellite image preview overlay, oil slick polygon, centroid marker, area (km²), perimeter, and threshold cards.
              </p>
            </div>
            <Link
              href="/cases/CASE-S1-DEMO-001/detection"
              className="w-full py-2.5 bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-xs rounded-lg text-center transition shadow-md shadow-cyan-400/30 inline-block"
            >
              INSPECT DETECTION ➔
            </Link>
          </div>

          {/* Screen 3 */}
          <div className="p-6 rounded-2xl bg-[#073042] border-2 border-teal-400 hover:border-teal-300 transition space-y-4 flex flex-col justify-between shadow-2xl">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="px-3 py-1 rounded bg-teal-400 text-slate-950 text-xs font-black">
                  SCREEN 3
                </span>
                <span className="text-xs font-black text-teal-300">
                  PHASE 2
                </span>
              </div>
              <h4 className="text-2xl font-black text-white">
                Phase 2 Drift
              </h4>
              <p className="text-slate-100 text-xs font-bold leading-relaxed">
                Origin-density contours, backward particle tracks, forecast risk contours, and time slider scrubber (-48h to +48h).
              </p>
            </div>
            <Link
              href="/cases/CASE-S1-DEMO-001/drift"
              className="w-full py-2.5 bg-teal-400 hover:bg-teal-300 text-slate-950 font-black text-xs rounded-lg text-center transition shadow-md shadow-teal-400/30 inline-block"
            >
              INSPECT DRIFT ➔
            </Link>
          </div>

          {/* Screen 4 */}
          <div className="p-6 rounded-2xl bg-[#1e123b] border-2 border-purple-400 hover:border-purple-300 transition space-y-4 flex flex-col justify-between shadow-2xl">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="px-3 py-1 rounded bg-purple-400 text-slate-950 text-xs font-black">
                  SCREEN 4
                </span>
                <span className="text-xs font-black text-purple-300">
                  PHASE 3
                </span>
              </div>
              <h4 className="text-2xl font-black text-white">
                Phase 3 Attribution
              </h4>
              <p className="text-slate-100 text-xs font-bold leading-relaxed">
                Top-3 privacy-safe candidate cards (`CAND-003`), Candidate Evidence Drawer, component score breakdown, and legal disclaimer.
              </p>
            </div>
            <Link
              href="/cases/CASE-S1-DEMO-001/attribution"
              className="w-full py-2.5 bg-purple-400 hover:bg-purple-300 text-slate-950 font-black text-xs rounded-lg text-center transition shadow-md shadow-purple-400/30 inline-block"
            >
              INSPECT ATTRIBUTION ➔
            </Link>
          </div>
        </div>
      </section>

      {/* SLEEK MODERN HIGH-CONTRAST FOOTER */}
      <footer className="py-8 px-6 border-t border-cyan-500/30 bg-[#030914] relative z-20">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 font-mono text-xs">
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-white text-sm tracking-wider">VARUN-ASTRA</span>
            <span className="text-cyan-400 font-bold">•</span>
            <span className="text-slate-200 font-bold">Smart India Hackathon (SIH-26143)</span>
          </div>

          <div className="flex items-center space-x-6 text-sm font-bold">
            <Link
              href="/cases"
              className="text-cyan-300 hover:text-cyan-100 transition border-b-2 border-cyan-400/50 pb-0.5 hover:border-cyan-300"
            >
              Case Overview
            </Link>
            <Link
              href="/cases/CASE-S1-DEMO-001/detection"
              className="text-cyan-300 hover:text-cyan-100 transition border-b-2 border-cyan-400/50 pb-0.5 hover:border-cyan-300"
            >
              Detection
            </Link>
            <Link
              href="/cases/CASE-S1-DEMO-001/drift"
              className="text-teal-300 hover:text-teal-100 transition border-b-2 border-teal-400/50 pb-0.5 hover:border-teal-300"
            >
              Drift
            </Link>
            <Link
              href="/cases/CASE-S1-DEMO-001/attribution"
              className="text-purple-300 hover:text-purple-100 transition border-b-2 border-purple-400/50 pb-0.5 hover:border-purple-300"
            >
              Attribution
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
