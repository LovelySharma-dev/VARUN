"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CompleteDashboardResponse } from "@/lib/contracts";

interface MapPanelProps {
  dashboardData: CompleteDashboardResponse;
  activeLayers: Record<string, boolean>;
  onSelectCandidate?: (candidateId: string) => void;
  selectedCandidateId?: string;
}

// Clean, watermark-free dark maritime basemap style (100% free, no API key required)
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
        "background-color": "#030d1c",
      },
    },
    {
      id: "esri-dark-tiles",
      type: "raster",
      source: "esri-dark-base",
      minzoom: 0,
      maxzoom: 16,
      paint: {
        "raster-opacity": 0.9,
      },
    },
    {
      id: "esri-labels-tiles",
      type: "raster",
      source: "esri-dark-labels",
      minzoom: 0,
      maxzoom: 16,
      paint: {
        "raster-opacity": 0.75,
      },
    },
  ],
};

export default function MapPanel({
  dashboardData,
  activeLayers,
  onSelectCandidate,
  selectedCandidateId,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const centroidCoords =
    (dashboardData.detection?.centroid?.geometry?.coordinates as [number, number]) || [72.8347, 18.9214];

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Initialize MapLibre GL
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_BASEMAP_STYLE,
      center: centroidCoords,
      zoom: 10,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const setupLayers = () => {
      setMapLoaded(true);

      // 1. Detection Spill Polygon
      if (dashboardData.detection?.spillPolygon) {
        if (!map.getSource("spill-source")) {
          map.addSource("spill-source", {
            type: "geojson",
            data: dashboardData.detection.spillPolygon,
          });

          map.addLayer({
            id: "spill-polygon-fill",
            type: "fill",
            source: "spill-source",
            paint: {
              "fill-color": "#ef4444",
              "fill-opacity": activeLayers["spill-polygon"] !== false ? 0.55 : 0,
            },
          });

          map.addLayer({
            id: "spill-polygon-outline",
            type: "line",
            source: "spill-source",
            paint: {
              "line-color": "#f87171",
              "line-width": 2.5,
              "line-opacity": activeLayers["spill-polygon"] !== false ? 1 : 0,
            },
          });
        }
      }

      // 2. Centroid Marker
      const el = document.createElement("div");
      el.className = "w-5 h-5 rounded-full bg-red-500 border-2 border-white shadow-lg animate-pulse cursor-pointer";
      new maplibregl.Marker({ element: el })
        .setLngLat(centroidCoords)
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="color:#0f172a;font-family:monospace;padding:4px;font-size:11px;">
              <strong style="color:#dc2626;">OIL SLICK CENTROID</strong><br/>
              Area: ${dashboardData.detection?.areaKm2 ?? 3.24} km²<br/>
              Lat: ${centroidCoords[1].toFixed(4)}° N, Lng: ${centroidCoords[0].toFixed(4)}° E
            </div>`
          )
        )
        .addTo(map);

      // 3. Origin Density Contours
      if (dashboardData.drift?.originDensityContours) {
        if (!map.getSource("origin-density-source")) {
          map.addSource("origin-density-source", {
            type: "geojson",
            data: dashboardData.drift.originDensityContours,
          });

          map.addLayer({
            id: "origin-density-fill",
            type: "fill",
            source: "origin-density-source",
            paint: {
              "fill-color": "#a855f7",
              "fill-opacity": activeLayers["origin-density"] !== false ? 0.4 : 0,
            },
          });
        }
      }

      // 4. Backward Particle Tracks
      if (dashboardData.drift?.backwardParticleTracks) {
        if (!map.getSource("backward-tracks-source")) {
          map.addSource("backward-tracks-source", {
            type: "geojson",
            data: dashboardData.drift.backwardParticleTracks,
          });

          map.addLayer({
            id: "backward-tracks-line",
            type: "line",
            source: "backward-tracks-source",
            paint: {
              "line-color": "#c084fc",
              "line-width": 2,
              "line-dasharray": [2, 2],
              "line-opacity": activeLayers["backward-tracks"] !== false ? 0.9 : 0,
            },
          });
        }
      }

      // 5. Hindcast Corridor
      if (dashboardData.drift?.hindcastCorridor) {
        if (!map.getSource("hindcast-corridor-source")) {
          map.addSource("hindcast-corridor-source", {
            type: "geojson",
            data: dashboardData.drift.hindcastCorridor,
          });

          map.addLayer({
            id: "hindcast-corridor-fill",
            type: "fill",
            source: "hindcast-corridor-source",
            paint: {
              "fill-color": "#9333ea",
              "fill-opacity": activeLayers["hindcast-corridor"] ? 0.25 : 0,
            },
          });
        }
      }

      // 6. Forecast Contour
      if (dashboardData.drift?.forwardForecast) {
        if (!map.getSource("forecast-source")) {
          map.addSource("forecast-source", {
            type: "geojson",
            data: dashboardData.drift.forwardForecast,
          });

          map.addLayer({
            id: "forecast-fill",
            type: "fill",
            source: "forecast-source",
            paint: {
              "fill-color": "#f97316",
              "fill-opacity": activeLayers["forecast-contour"] !== false ? 0.35 : 0,
            },
          });
        }
      }

      // 7. Top Candidates Vessel Tracks
      if (dashboardData.attribution?.topCandidates) {
        dashboardData.attribution.topCandidates.forEach((candidate) => {
          const sourceId = `candidate-track-${candidate.candidateId}`;
          const isSelected = selectedCandidateId === candidate.candidateId;

          if (!map.getSource(sourceId)) {
            map.addSource(sourceId, {
              type: "geojson",
              data: candidate.vesselTrack,
            });

            map.addLayer({
              id: `${sourceId}-line`,
              type: "line",
              source: sourceId,
              paint: {
                "line-color": candidate.rank === 1 ? "#06b6d4" : candidate.rank === 2 ? "#38bdf8" : "#94a3b8",
                "line-width": isSelected ? 4.5 : candidate.rank === 1 ? 3 : 2,
                "line-opacity": activeLayers["candidate-tracks"] !== false ? 1 : 0,
              },
            });

            map.on("click", `${sourceId}-line`, () => {
              if (onSelectCandidate) {
                onSelectCandidate(candidate.candidateId);
              }
            });
          }
        });
      }

      // Fit map bounds around spill
      try {
        const polygonGeom = dashboardData.detection?.spillPolygon?.geometry as GeoJSON.Polygon;
        if (polygonGeom?.coordinates?.[0]) {
          const bounds = new maplibregl.LngLatBounds();
          polygonGeom.coordinates[0].forEach((coord: number[]) => bounds.extend(coord as [number, number]));
          map.fitBounds(bounds, { padding: 60, maxZoom: 12 });
        }
      } catch {
        // Fallback zoom
      }
    };

    map.on("load", setupLayers);

    mapRef.current = map;

    // Force map container resize
    const resizeTimer = setTimeout(() => {
      map.resize();
    }, 200);

    return () => {
      clearTimeout(resizeTimer);
      map.remove();
    };
  }, [dashboardData]);

  // Update layer visibility dynamically
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const setVisibility = (layerId: string, isVisible: boolean, targetOpacity = 0.4) => {
      if (map.getLayer(layerId)) {
        map.setPaintProperty(
          layerId,
          layerId.includes("fill") ? "fill-opacity" : "line-opacity",
          isVisible ? targetOpacity : 0
        );
      }
    };

    setVisibility("spill-polygon-fill", activeLayers["spill-polygon"] !== false, 0.55);
    setVisibility("spill-polygon-outline", activeLayers["spill-polygon"] !== false, 1);
    setVisibility("origin-density-fill", activeLayers["origin-density"] !== false, 0.4);
    setVisibility("backward-tracks-line", activeLayers["backward-tracks"] !== false, 0.9);
    setVisibility("hindcast-corridor-fill", activeLayers["hindcast-corridor"] === true, 0.25);
    setVisibility("forecast-fill", activeLayers["forecast-contour"] !== false, 0.35);

    if (dashboardData.attribution?.topCandidates) {
      dashboardData.attribution.topCandidates.forEach((candidate) => {
        const layerId = `candidate-track-${candidate.candidateId}-line`;
        if (map.getLayer(layerId)) {
          map.setPaintProperty(layerId, "line-opacity", activeLayers["candidate-tracks"] !== false ? 1 : 0);
          map.setPaintProperty(layerId, "line-width", selectedCandidateId === candidate.candidateId ? 4.5 : 2.5);
        }
      });
    }
  }, [activeLayers, mapLoaded, dashboardData, selectedCandidateId]);

  return (
    <div className="relative w-full h-full min-h-[520px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#030d1c] shadow-2xl">
      <div ref={mapContainerRef} className="w-full h-full min-h-[520px]" />
    </div>
  );
}
