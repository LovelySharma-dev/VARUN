"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CompleteDashboardResponse, Candidate } from "@/lib/contracts";

interface MapPanelProps {
  dashboardData: CompleteDashboardResponse;
  activeLayers?: Record<string, boolean>;
  onSelectCandidate?: (candidateId: string) => void;
  selectedCandidateId?: string;
  currentTimeStepIndex?: number;
}

// Dark Tactical Nautical Basemap
const DARK_BASEMAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "esri-dark-base": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "&copy; Esri, DeLorme, NAVTEQ",
      maxzoom: 16,
    },
    "esri-dark-labels": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 16,
    },
  },
  layers: [
    {
      id: "background",
      type: "background",
      paint: {
        "background-color": "#020813",
      },
    },
    {
      id: "esri-dark-tiles",
      type: "raster",
      source: "esri-dark-base",
      minzoom: 0,
      maxzoom: 16,
      paint: {
        "raster-opacity": 0.88,
      },
    },
    {
      id: "esri-labels-tiles",
      type: "raster",
      source: "esri-dark-labels",
      minzoom: 0,
      maxzoom: 16,
      paint: {
        "raster-opacity": 0.65,
      },
    },
  ],
};

export default function MapPanel({
  dashboardData,
  activeLayers: externalActiveLayers,
  onSelectCandidate,
  selectedCandidateId,
  currentTimeStepIndex = 3,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mouseCoords, setMouseCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [currentZoom, setCurrentZoom] = useState<number>(12);
  const [, setRenderTrigger] = useState(0);

  // Internal layer toggle state
  const [localLayers, setLocalLayers] = useState<Record<string, boolean>>({
    "spill-polygon": true,
    "origin-density": true,
    "backward-tracks": true,
    "hindcast-corridor": true,
    "forecast-contour": true,
    "candidate-tracks": true,
    "particles-cloud": true,
    "range-rings": true,
  });

  useEffect(() => {
    if (externalActiveLayers) {
      setLocalLayers((prev) => ({
        ...prev,
        ...externalActiveLayers,
      }));
    }
  }, [externalActiveLayers]);

  const centroidCoords: [number, number] =
    (dashboardData.detection?.centroid?.geometry?.coordinates as [number, number]) || [72.0100, 18.9200];

  // Helper: Convert geographic [lng, lat] to SVG screen [x, y]
  const projectPoint = useCallback((coord: [number, number]): [number, number] => {
    if (!mapRef.current) return [0, 0];
    const p = mapRef.current.project(coord);
    return [p.x, p.y];
  }, []);

  // Helper: Convert GeoJSON Polygon coordinates to SVG path `M x y L x y ... Z`
  const polygonToSvgPath = useCallback(
    (coords: [number, number][][]): string => {
      if (!coords || !coords[0] || coords[0].length === 0) return "";
      return coords[0]
        .map((c, i) => {
          const [x, y] = projectPoint(c);
          return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ") + " Z";
    },
    [projectPoint]
  );

  // Helper: Convert GeoJSON LineString coordinates to SVG path `M x y L x y ...`
  const lineToSvgPath = useCallback(
    (coords: [number, number][]): string => {
      if (!coords || coords.length === 0) return "";
      return coords
        .map((c, i) => {
          const [x, y] = projectPoint(c);
          return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ");
    },
    [projectPoint]
  );

  // Helper: Compute interpolated vessel position along track based on timeline step
  const getInterpolatedVesselPosition = useCallback(
    (trackCoords: [number, number][], stepIdx: number): [number, number] => {
      if (!trackCoords || trackCoords.length === 0) return [0, 0];
      const maxSteps = dashboardData.drift?.timeSteps?.length || 6;
      const ratio = Math.max(0, Math.min(1, stepIdx / (maxSteps - 1)));
      const indexFloat = ratio * (trackCoords.length - 1);
      const idxFloor = Math.floor(indexFloat);
      const idxCeil = Math.min(trackCoords.length - 1, Math.ceil(indexFloat));
      const frac = indexFloat - idxFloor;

      const p1 = trackCoords[idxFloor];
      const p2 = trackCoords[idxCeil];
      const lng = p1[0] + (p2[0] - p1[0]) * frac;
      const lat = p1[1] + (p2[1] - p1[1]) * frac;
      return [lng, lat];
    },
    [dashboardData]
  );

  // Helper: Lagrangian particle cloud positions based on timeline step
  const getParticlePositions = useCallback(
    (center: [number, number], stepIdx: number) => {
      const particles: Array<{ lng: number; lat: number; size: number; opacity: number }> = [];
      const numParticles = 45;
      const maxSteps = dashboardData.drift?.timeSteps?.length || 6;
      const tRatio = stepIdx / (maxSteps - 1); // 0.0 (origin -48h) to 1.0 (forecast +48h)

      for (let i = 0; i < numParticles; i++) {
        const spread = 0.012 + tRatio * 0.022;
        const jitterX = Math.sin(i * 3.7 + stepIdx * 1.5) * spread;
        const jitterY = Math.cos(i * 2.3 + stepIdx * 1.2) * spread;

        // Drift vector from South-West (71.55, 18.45) through Centroid (72.01, 18.92) to North-East (72.18, 19.10)
        const driftOffsetX = (tRatio - 0.5) * 0.92;
        const driftOffsetY = (tRatio - 0.5) * 0.88;

        const lng = center[0] + driftOffsetX + jitterX;
        const lat = center[1] + driftOffsetY + jitterY;

        particles.push({
          lng,
          lat,
          size: 4 + (i % 3) * 1.5,
          opacity: 0.85 - Math.abs(tRatio - 0.5) * 0.25,
        });
      }
      return particles;
    },
    [dashboardData]
  );

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_BASEMAP_STYLE,
      center: centroidCoords,
      zoom: 12,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    map.on("mousemove", (e) => {
      setMouseCoords({
        lat: parseFloat(e.lngLat.lat.toFixed(4)),
        lng: parseFloat(e.lngLat.lng.toFixed(4)),
      });
    });

    map.on("zoom", () => {
      setCurrentZoom(parseFloat(map.getZoom().toFixed(1)));
    });

    // Re-render SVG overlay on map movements
    const triggerUpdate = () => {
      setRenderTrigger((prev) => prev + 1);
    };

    map.on("move", triggerUpdate);
    map.on("zoom", triggerUpdate);
    map.on("resize", triggerUpdate);
    map.on("render", triggerUpdate);

    map.on("load", () => {
      setMapLoaded(true);
      map.resize();
    });

    mapRef.current = map;

    return () => {
      map.remove();
    };
  }, [centroidCoords]);

  const toggleLayer = (layerKey: string) => {
    setLocalLayers((prev) => ({
      ...prev,
      [layerKey]: !prev[layerKey],
    }));
  };

  const focusSlickCentroid = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: centroidCoords,
        zoom: 12.8,
        essential: true,
      });
    }
  };

  const focusDriftCorridor = () => {
    if (mapRef.current) {
      const bounds = new maplibregl.LngLatBounds();
      bounds.extend(centroidCoords);

      if (dashboardData.drift?.originDensityContours?.features?.[0]?.geometry?.coordinates?.[0]) {
        dashboardData.drift.originDensityContours.features[0].geometry.coordinates[0].forEach((pt) => {
          bounds.extend(pt as [number, number]);
        });
      }

      mapRef.current.fitBounds(bounds, { padding: 90, maxZoom: 13 });
    }
  };

  const focusVesselTracks = () => {
    if (mapRef.current && dashboardData.attribution?.topCandidates?.[0]) {
      const bounds = new maplibregl.LngLatBounds();
      bounds.extend(centroidCoords);

      const trackGeom = dashboardData.attribution.topCandidates[0].vesselTrack.geometry as GeoJSON.LineString;
      if (trackGeom?.coordinates) {
        trackGeom.coordinates.forEach((pt) => bounds.extend(pt as [number, number]));
      }

      mapRef.current.fitBounds(bounds, { padding: 90, maxZoom: 12.5 });
    }
  };

  const resetRegionalOverview = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: centroidCoords,
        zoom: 10.5,
        essential: true,
      });
    }
  };

  // Pre-calculate SVG coordinates
  const centroidScreen = projectPoint(centroidCoords);

  // 1. Oil Slick Polygon
  const slickGeom = dashboardData.detection?.spillPolygon?.geometry as GeoJSON.Polygon;
  const slickSvgPath = slickGeom?.coordinates ? polygonToSvgPath(slickGeom.coordinates as [number, number][][]) : "";

  // 2. Hindcast Corridor
  const hindcastGeom = dashboardData.drift?.hindcastCorridor?.geometry as GeoJSON.Polygon;
  const hindcastSvgPath = hindcastGeom?.coordinates ? polygonToSvgPath(hindcastGeom.coordinates as [number, number][][]) : "";

  // 3. Origin Density Contours
  const originZones = dashboardData.drift?.originDensityContours?.features || [];
  const originZoneA = originZones[0]?.geometry as GeoJSON.Polygon;
  const originZoneB = originZones[1]?.geometry as GeoJSON.Polygon;
  const originZoneASvg = originZoneA?.coordinates ? polygonToSvgPath(originZoneA.coordinates as [number, number][][]) : "";
  const originZoneBSvg = originZoneB?.coordinates ? polygonToSvgPath(originZoneB.coordinates as [number, number][][]) : "";

  // Origin Zone A Center for Stated Radius Callout
  const originCenterCoords: [number, number] = originZoneA?.coordinates?.[0]?.[0]
    ? (originZoneA.coordinates[0][0] as [number, number])
    : [71.5600, 18.4500];
  const originCenterScreen = projectPoint(originCenterCoords);

  // 4. Backward Streamlines / Particle Tracks
  const backtrackFeatures = dashboardData.drift?.backwardParticleTracks?.features || [];

  // 5. Forward Forecast
  const forecastGeom = dashboardData.drift?.forwardForecast?.features?.[0]?.geometry as GeoJSON.Polygon;
  const forecastSvgPath = forecastGeom?.coordinates ? polygonToSvgPath(forecastGeom.coordinates as [number, number][][]) : "";

  // 6. Lagrangian Particles
  const particles = getParticlePositions(centroidCoords, currentTimeStepIndex);

  // 7. AIS Vessel Candidate Tracks
  const candidates: Candidate[] = dashboardData.attribution?.topCandidates || [];

  // 8. Range Rings (5km, 10km, 20km)
  const rangeRings = [5, 10, 20].map((radiusKm) => {
    const edgeCoords: [number, number] = [
      centroidCoords[0] + radiusKm / (111.32 * Math.cos((centroidCoords[1] * Math.PI) / 180)),
      centroidCoords[1],
    ];
    const edgeScreen = projectPoint(edgeCoords);
    const radiusPx = Math.abs(edgeScreen[0] - centroidScreen[0]);
    return { radiusKm, radiusPx };
  });

  return (
    <div className="relative w-full h-full min-h-[560px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#020813] shadow-2xl font-mono select-none">
      {/* MAPLIBRE GL CANVAS */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[560px]" />

      {/* ========================================================= */}
      {/* HIGH-PRECISION HARDWARE-ACCELERATED SVG TACTICAL OVERLAY  */}
      {/* ========================================================= */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-20">
        <defs>
          {/* Neon Glow Filters */}
          <filter id="glow-rose" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-orange" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Diagonal Hatch Pattern for Hindcast Corridor */}
          <pattern id="hatch-amber" width="12" height="12" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="12" stroke="#f59e0b" strokeWidth="1.5" strokeOpacity="0.4" />
          </pattern>

          {/* Diagonal Hatch Pattern for Forecast Cone */}
          <pattern id="hatch-cyan" width="12" height="12" patternTransform="rotate(-45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="12" stroke="#06b6d4" strokeWidth="1.5" strokeOpacity="0.3" />
          </pattern>
        </defs>

        {/* 1. TACTICAL RANGE RINGS (5km, 10km, 20km) */}
        {localLayers["range-rings"] &&
          rangeRings.map((ring) => (
            <g key={ring.radiusKm}>
              <circle
                cx={centroidScreen[0]}
                cy={centroidScreen[1]}
                r={ring.radiusPx}
                fill="none"
                stroke="#38bdf8"
                strokeWidth="1.5"
                strokeDasharray="5,5"
                strokeOpacity="0.4"
              />
              <text
                x={centroidScreen[0] + ring.radiusPx + 4}
                y={centroidScreen[1] - 4}
                fill="#38bdf8"
                fontSize="10"
                fontWeight="bold"
                fontFamily="monospace"
                opacity="0.85"
              >
                {ring.radiusKm} KM
              </text>
            </g>
          ))}

        {/* 2. HINDCAST CORRIDOR (-48h to 0h) */}
        {localLayers["hindcast-corridor"] && hindcastSvgPath && (
          <g>
            <path d={hindcastSvgPath} fill="url(#hatch-amber)" opacity="0.8" />
            <path
              d={hindcastSvgPath}
              fill="#f59e0b"
              fillOpacity="0.22"
              stroke="#fbbf24"
              strokeWidth="2.5"
              strokeDasharray="6,4"
              strokeOpacity="0.95"
            />
          </g>
        )}

        {/* 3. FUTURE FORECAST RISK CONE (+24h / +48h) */}
        {localLayers["forecast-contour"] && forecastSvgPath && (
          <g>
            <path d={forecastSvgPath} fill="url(#hatch-cyan)" opacity="0.8" />
            <path
              d={forecastSvgPath}
              fill="#06b6d4"
              fillOpacity="0.28"
              stroke="#22d3ee"
              strokeWidth="2.5"
              strokeDasharray="5,4"
              strokeOpacity="0.95"
            />
          </g>
        )}

        {/* 4. ORIGIN DENSITY ZONES (ORANGE POLYGONS WITH STATED RADIUS) */}
        {localLayers["origin-density"] && (
          <g>
            {/* Origin Zone B (75% CI) */}
            {originZoneBSvg && (
              <path
                d={originZoneBSvg}
                fill="#9333ea"
                fillOpacity="0.40"
                stroke="#c084fc"
                strokeWidth="2"
                strokeOpacity="0.85"
              />
            )}

            {/* Origin Zone A (90% CI) - High Probability Release Zone */}
            {originZoneASvg && (
              <g filter="url(#glow-orange)">
                <path
                  d={originZoneASvg}
                  fill="#ea580c"
                  fillOpacity="0.65"
                  stroke="#ffedd5"
                  strokeWidth="3.5"
                  strokeOpacity="1.0"
                />
              </g>
            )}

            {/* Stated Radius Callout Badge */}
            {originCenterScreen[0] > 0 && originCenterScreen[1] > 0 && (
              <g transform={`translate(${originCenterScreen[0] - 80}, ${originCenterScreen[1] - 40})`}>
                <rect
                  x="0"
                  y="0"
                  width="180"
                  height="28"
                  rx="6"
                  fill="#030d1c"
                  fillOpacity="0.92"
                  stroke="#ea580c"
                  strokeWidth="1.5"
                />
                <text x="8" y="14" fill="#fb923c" fontSize="9" fontWeight="bold" fontFamily="monospace">
                  🎯 RELEASE ZONE A (90% CI)
                </text>
                <text x="8" y="24" fill="#ffedd5" fontSize="9" fontWeight="bold" fontFamily="monospace">
                  STATED RADIUS: {dashboardData.drift?.statedReleaseRadiusKm || 8.5} KM
                </text>
              </g>
            )}
          </g>
        )}

        {/* 5. BACKWARD STREAMLINES / PARTICLE DRIFT PATH */}
        {localLayers["backward-tracks"] &&
          backtrackFeatures.map((feat, idx) => {
            const lineGeom = feat.geometry as GeoJSON.LineString;
            const linePath = lineGeom?.coordinates ? lineToSvgPath(lineGeom.coordinates as [number, number][]) : "";
            return (
              <path
                key={idx}
                d={linePath}
                fill="none"
                stroke="#38bdf8"
                strokeWidth={idx === 0 ? "3.5" : "2"}
                strokeDasharray="6,4"
                strokeOpacity="0.95"
                filter="url(#glow-cyan)"
              />
            );
          })}

        {/* 6. LAGRANGIAN PARTICLE CLOUD (Animated ensemble) */}
        {localLayers["particles-cloud"] &&
          particles.map((p, idx) => {
            const screen = projectPoint([p.lng, p.lat]);
            const isOrigin = currentTimeStepIndex < 2;
            const isForecast = currentTimeStepIndex > 3;
            const pColor = isOrigin ? "#c084fc" : isForecast ? "#22d3ee" : "#fb923c";

            return (
              <g key={idx}>
                <circle cx={screen[0]} cy={screen[1]} r={p.size * 1.6} fill={pColor} opacity="0.35" />
                <circle
                  cx={screen[0]}
                  cy={screen[1]}
                  r={p.size}
                  fill={pColor}
                  stroke="#ffffff"
                  strokeWidth="1.2"
                  opacity={p.opacity}
                />
              </g>
            );
          })}

        {/* 7. AIS VESSEL CANDIDATE TRACKS & TIME-SCRUBBABLE MARKERS */}
        {localLayers["candidate-tracks"] &&
          candidates.map((cand) => {
            const trackGeom = cand.vesselTrack.geometry as GeoJSON.LineString;
            const trackPath = trackGeom?.coordinates ? lineToSvgPath(trackGeom.coordinates as [number, number][]) : "";
            const isSelected = selectedCandidateId === cand.candidateId;
            const color = cand.rank === 1 ? "#06b6d4" : cand.rank === 2 ? "#38bdf8" : "#94a3b8";

            // Scrubbable Vessel Position along track
            const currentVesselCoords = getInterpolatedVesselPosition(
              trackGeom.coordinates as [number, number][],
              currentTimeStepIndex
            );
            const currentVesselScreen = projectPoint(currentVesselCoords);

            // CPA Position
            const cpaCoords = cand.closestApproach.coordinates || trackGeom.coordinates[1] as [number, number];
            const cpaScreen = projectPoint(cpaCoords);

            return (
              <g key={cand.candidateId} className="pointer-events-auto cursor-pointer" onClick={() => onSelectCandidate?.(cand.candidateId)}>
                {/* Track Halo */}
                <path
                  d={trackPath}
                  fill="none"
                  stroke={color}
                  strokeWidth={isSelected ? "9" : cand.rank === 1 ? "6" : "4"}
                  strokeOpacity={isSelected ? "0.6" : cand.rank === 1 ? "0.35" : "0.2"}
                />

                {/* Track Core Line */}
                <path
                  d={trackPath}
                  fill="none"
                  stroke={cand.rank === 1 ? "#22d3ee" : cand.rank === 2 ? "#7dd3fc" : "#cbd5e1"}
                  strokeWidth={isSelected ? "4.5" : cand.rank === 1 ? "3.5" : "2.5"}
                  strokeOpacity="0.95"
                />

                {/* CPA Marker Reticle */}
                {cpaScreen[0] > 0 && (
                  <g transform={`translate(${cpaScreen[0]}, ${cpaScreen[1]})`}>
                    <circle r="7" fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="3,2" />
                    <circle r="3" fill={color} />
                    <text x="10" y="4" fill={color} fontSize="9" fontWeight="bold" fontFamily="monospace">
                      CPA: {cand.closestApproach.distanceKm} km (RANK {cand.rank})
                    </text>
                  </g>
                )}

                {/* TIME-SCRUBBABLE LIVE VESSEL MARKER */}
                {currentVesselScreen[0] > 0 && (
                  <g transform={`translate(${currentVesselScreen[0]}, ${currentVesselScreen[1]})`}>
                    <circle r="12" fill={color} opacity="0.25" className="animate-ping" />
                    <circle r="6" fill={color} stroke="#ffffff" strokeWidth="2" />
                    <text x="9" y="-8" fill="#ffffff" fontSize="10" fontWeight="bold" fontFamily="monospace">
                      🚢 {cand.candidateId} ({cand.investigativeScore}%)
                    </text>
                  </g>
                )}
              </g>
            );
          })}

        {/* 8. DETECTED OIL SLICK POLYGON WITH MEASURED SPAN */}
        {localLayers["spill-polygon"] && slickSvgPath && (
          <g filter="url(#glow-rose)" className="pointer-events-auto cursor-pointer" onClick={focusSlickCentroid}>
            {/* Ambient Glow */}
            <path d={slickSvgPath} fill="#e11d48" fillOpacity="0.30" />

            {/* Core Neon Rose Fill */}
            <path
              d={slickSvgPath}
              fill="#f43f5e"
              fillOpacity="0.75"
              stroke="#fb7185"
              strokeWidth="4"
              strokeOpacity="1.0"
            />

            {/* MEASURED SPAN DIMENSION RULER & ANNOTATION */}
            {centroidScreen[0] > 0 && (
              <g transform={`translate(${centroidScreen[0] - 110}, ${centroidScreen[1] + 30})`}>
                <rect
                  x="0"
                  y="0"
                  width="220"
                  height="34"
                  rx="6"
                  fill="#020813"
                  fillOpacity="0.94"
                  stroke="#fb7185"
                  strokeWidth="1.5"
                />
                <text x="8" y="14" fill="#fb7185" fontSize="10" fontWeight="bold" fontFamily="monospace">
                  📐 MEASURED SPAN: {dashboardData.detection?.areaKm2 || 3.24} km²
                </text>
                <text x="8" y="26" fill="#cbd5e1" fontSize="9" fontFamily="monospace">
                  LENGTH: {dashboardData.detection?.slickLengthKm || 6.7} km | PERIMETER: {dashboardData.detection?.perimeterKm || 11.8} km
                </text>
              </g>
            )}
          </g>
        )}

        {/* 9. CENTROID RETICLE */}
        {centroidScreen[0] > 0 && (
          <g transform={`translate(${centroidScreen[0]}, ${centroidScreen[1]})`}>
            {/* Crosshair Lines */}
            <line x1="-14" y1="0" x2="14" y2="0" stroke="#f43f5e" strokeWidth="1.5" strokeOpacity="0.8" />
            <line x1="0" y1="-14" x2="0" y2="14" stroke="#f43f5e" strokeWidth="1.5" strokeOpacity="0.8" />
            <circle r="8" fill="none" stroke="#fb7185" strokeWidth="2" strokeDasharray="4,2" />
            <circle r="3" fill="#f43f5e" />
          </g>
        )}
      </svg>

      {/* ========================================================= */}
      {/* UNIFIED SCI-FI FLOATING LAYERS CONTROL HUD (TOP LEFT)     */}
      {/* ========================================================= */}
      <div className="absolute top-3 left-3 z-30 w-56 bg-[#030d1c]/92 backdrop-blur-md border border-cyan-500/40 rounded-xl shadow-2xl overflow-hidden text-slate-200">
        <div className="px-3 py-2 bg-[#020914] border-b border-cyan-900/60 flex items-center justify-between text-[11px] font-bold text-cyan-400">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>TACTICAL LAYERS</span>
          </div>
          <span className="text-[9px] text-slate-500">HUD v3.0</span>
        </div>

        <div className="p-2 space-y-1 text-[11px]">
          {/* 1. Oil Slick Polygons */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["spill-polygon"] !== false}
                onChange={() => toggleLayer("spill-polygon")}
                className="accent-rose-500 rounded cursor-pointer"
              />
              <span className="text-rose-300 font-semibold">Oil Slick (Span)</span>
            </div>
            <span className="w-3 h-2 rounded-sm bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.9)]" />
          </label>

          {/* 2. Lagrangian Particle Cloud */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["particles-cloud"] !== false}
                onChange={() => toggleLayer("particles-cloud")}
                className="accent-orange-500 rounded cursor-pointer"
              />
              <span className="text-orange-300 font-semibold">Particle Cloud</span>
            </div>
            <span className="w-2.5 h-2.5 rounded-full bg-orange-400 shadow-[0_0_6px_rgba(251,146,60,0.8)]" />
          </label>

          {/* 3. Hindcast Release Cone */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["hindcast-corridor"] !== false}
                onChange={() => toggleLayer("hindcast-corridor")}
                className="accent-amber-500 rounded cursor-pointer"
              />
              <span className="text-amber-300 font-semibold">Hindcast Corridor</span>
            </div>
            <span className="w-3 h-1.5 border border-amber-400 bg-amber-500/30" />
          </label>

          {/* 4. Origin Density Zones */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["origin-density"] !== false}
                onChange={() => toggleLayer("origin-density")}
                className="accent-orange-600 rounded cursor-pointer"
              />
              <span className="text-orange-400 font-semibold">Release Zone (8.5km)</span>
            </div>
            <span className="w-3 h-2 rounded-sm bg-orange-600" />
          </label>

          {/* 5. Backtrack Drift Streamlines */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["backward-tracks"] !== false}
                onChange={() => toggleLayer("backward-tracks")}
                className="accent-cyan-400 rounded cursor-pointer"
              />
              <span className="text-cyan-300 font-semibold">Backtrack Path</span>
            </div>
            <span className="w-3 h-0.5 bg-cyan-400" />
          </label>

          {/* 6. Forecast Trajectory */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["forecast-contour"] !== false}
                onChange={() => toggleLayer("forecast-contour")}
                className="accent-teal-400 rounded cursor-pointer"
              />
              <span className="text-teal-300 font-semibold">Forecast Cone (+48h)</span>
            </div>
            <span className="w-3 h-1 border border-teal-400 border-dashed" />
          </label>

          {/* 7. AIS Vessel Tracks */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["candidate-tracks"] !== false}
                onChange={() => toggleLayer("candidate-tracks")}
                className="accent-blue-400 rounded cursor-pointer"
              />
              <span className="text-blue-300 font-semibold">AIS Vessel Tracks</span>
            </div>
            <span className="w-3 h-0.5 bg-blue-400" />
          </label>

          {/* 8. Tactical Range Rings */}
          <label className="flex items-center justify-between cursor-pointer py-1 px-1.5 rounded hover:bg-cyan-950/40 transition border-t border-cyan-900/40 pt-1">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={localLayers["range-rings"] !== false}
                onChange={() => toggleLayer("range-rings")}
                className="accent-sky-400 rounded cursor-pointer"
              />
              <span className="text-sky-300 font-semibold text-[10px]">Range Rings (5-20km)</span>
            </div>
            <span className="w-2.5 h-2.5 rounded-full border border-sky-400 border-dashed" />
          </label>
        </div>
      </div>

      {/* ========================================================= */}
      {/* TACTICAL MAP CAMERA SHORTCUTS (TOP RIGHT)                 */}
      {/* ========================================================= */}
      <div className="absolute top-3 right-12 z-30 flex space-x-1.5">
        <button
          onClick={focusSlickCentroid}
          className="px-2.5 py-1.5 bg-[#030d1c]/90 backdrop-blur-md border border-rose-500/50 hover:border-rose-400 text-rose-300 hover:text-white rounded-lg shadow-lg text-[10px] font-bold flex items-center space-x-1.5 transition cursor-pointer"
          title="Zoom directly to Detected Spill & Span"
        >
          <span>🎯</span>
          <span>FOCUS SLICK</span>
        </button>
        <button
          onClick={focusDriftCorridor}
          className="px-2.5 py-1.5 bg-[#030d1c]/90 backdrop-blur-md border border-amber-500/50 hover:border-amber-400 text-amber-300 hover:text-white rounded-lg shadow-lg text-[10px] font-bold flex items-center space-x-1.5 transition cursor-pointer"
          title="Frame Backtrack Path and 8.5km Release Zone"
        >
          <span>🌊</span>
          <span>RELEASE ZONE</span>
        </button>
        <button
          onClick={focusVesselTracks}
          className="px-2.5 py-1.5 bg-[#030d1c]/90 backdrop-blur-md border border-cyan-500/50 hover:border-cyan-400 text-cyan-300 hover:text-white rounded-lg shadow-lg text-[10px] font-bold flex items-center space-x-1.5 transition cursor-pointer"
          title="Frame Suspect Vessel Tracks and CPA"
        >
          <span>🚢</span>
          <span>VESSEL TRACKS</span>
        </button>
        <button
          onClick={resetRegionalOverview}
          className="px-2.5 py-1.5 bg-[#030d1c]/90 backdrop-blur-md border border-cyan-900/60 hover:border-cyan-400 text-slate-300 hover:text-white rounded-lg shadow-lg text-[10px] font-bold flex items-center space-x-1.5 transition cursor-pointer"
          title="Reset Camera to Regional Overview"
        >
          <span>🌐</span>
          <span>OVERVIEW</span>
        </button>
      </div>

      {/* ========================================================= */}
      {/* BOTTOM TELEMETRY FOOTER HUD (COORDINATES & FORCING)       */}
      {/* ========================================================= */}
      <div className="absolute bottom-2.5 left-2.5 right-2.5 z-30 flex flex-wrap justify-between items-center pointer-events-none gap-2">
        {/* LIVE MOUSE COORDINATES READOUT */}
        <div className="px-3 py-1 bg-[#020914]/92 backdrop-blur-md border border-cyan-500/40 rounded-lg text-[10px] text-slate-300 font-mono flex items-center space-x-3 pointer-events-auto shadow-xl">
          <div className="flex items-center space-x-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-400">CURSOR:</span>
            <span className="text-cyan-300 font-bold">
              {mouseCoords ? `${mouseCoords.lat}° N, ${mouseCoords.lng}° E` : `${centroidCoords[1].toFixed(4)}° N, ${centroidCoords[0].toFixed(4)}° E`}
            </span>
          </div>
          <span className="text-slate-600">|</span>
          <div>
            <span className="text-slate-400">CURRENT:</span>{" "}
            <span className="text-emerald-400 font-bold">0.85 m/s (210° SSW)</span>
          </div>
          <span className="text-slate-600">|</span>
          <div>
            <span className="text-slate-400">WIND:</span>{" "}
            <span className="text-cyan-400 font-bold">14.2 kts (225° SW)</span>
          </div>
          <span className="text-slate-600">|</span>
          <div>
            <span className="text-slate-400">ZOOM:</span>{" "}
            <span className="text-slate-200 font-bold">{currentZoom}x</span>
          </div>
        </div>

        {/* SENSOR BADGE */}
        <div className="px-2.5 py-1 bg-[#020914]/85 backdrop-blur-sm border border-cyan-900/60 rounded text-[9px] text-slate-400 pointer-events-auto">
          VARUN-ASTRA GIS Engine • Sentinel-1 SAR C-Band
        </div>
      </div>
    </div>
  );
}
