"use client";

import dynamic from "next/dynamic";

const MapPanel = dynamic(() => import("./MapPanel"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[460px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#061427] flex items-center justify-center font-mono text-cyan-400">
      <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mr-3" />
      <span>INITIALIZING MAPLIBRE GL CANVAS...</span>
    </div>
  ),
});

export default MapPanel;
