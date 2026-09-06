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

export default function MapPanel({
  dashboardData,
  activeLayers,
  onSelectCandidate,
  selectedCandidateId,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const centroidCoords = dashboardData.detection.centroid.geometry.coordinates as [number, number];

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Dark high-tech basemap style
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: centroidCoords, // [lng, lat]
      zoom: 10,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      setMapLoaded(true);

      // Add Detection Spill Polygon Source & Layer
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
          "fill-opacity": activeLayers["spill-polygon"] !== false ? 0.45 : 0,
        },
      });

      map.addLayer({
        id: "spill-polygon-outline",
        type: "line",
        source: "spill-source",
        paint: {
          "line-color": "#dc2626",
          "line-width": 2.5,
          "line-opacity": activeLayers["spill-polygon"] !== false ? 1 : 0,
        },
      });

      // Centroid Marker
      const el = document.createElement("div");
      el.className = "w-4 h-4 rounded-full bg-red-500 border-2 border-white animate-ping";
      new maplibregl.Marker({ element: el })
        .setLngLat(centroidCoords)
        .setPopup(
          new maplibregl.Popup({ offset: 10 }).setHTML(
            `<div class="p-2 font-mono text-xs text-slate-900">
              <strong class="text-red-600">OIL SLICK CENTROID</strong><br/>
              Area: ${dashboardData.detection.areaKm2} km²<br/>
              Coords: ${centroidCoords[1].toFixed(4)}° N, ${centroidCoords[0].toFixed(4)}° E
            </div>`
          )
        )
        .addTo(map);

      // Origin Density Contours
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
          "fill-opacity": activeLayers["origin-density"] !== false ? 0.35 : 0,
        },
      });

      // Backward Particle Tracks
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

      // Hindcast Corridor
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
          "fill-opacity": activeLayers["hindcast-corridor"] ? 0.2 : 0,
        },
      });

      // Forecast Contour
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
          "fill-opacity": activeLayers["forecast-contour"] !== false ? 0.3 : 0,
        },
      });

      // Top Candidates Vessel Tracks
      dashboardData.attribution.topCandidates.forEach((candidate) => {
        const sourceId = `candidate-track-${candidate.candidateId}`;
        const isSelected = selectedCandidateId === candidate.candidateId;

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
            "line-width": isSelected ? 4 : candidate.rank === 1 ? 3 : 2,
            "line-opacity": activeLayers["candidate-tracks"] !== false ? 1 : 0,
          },
        });

        // Click track to select candidate
        map.on("click", `${sourceId}-line`, () => {
          if (onSelectCandidate) {
            onSelectCandidate(candidate.candidateId);
          }
        });
      });

      // Automatically fit map bounds around spill
      const bounds = new maplibregl.LngLatBounds();
      const polygonGeom = dashboardData.detection.spillPolygon.geometry as GeoJSON.Polygon;
      const coords = polygonGeom.coordinates[0];
      coords.forEach((coord: number[]) => bounds.extend(coord as [number, number]));
      map.fitBounds(bounds, { padding: 80, maxZoom: 12 });
    });

    mapRef.current = map;

    return () => {
      map.remove();
    };
  }, [dashboardData]);

  // Update layer visibility dynamically
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const setVisibility = (layerId: string, isVisible: boolean, targetOpacity = 0.4) => {
      if (map.getLayer(layerId)) {
        map.setPaintProperty(layerId, layerId.includes("fill") ? "fill-opacity" : "line-opacity", isVisible ? targetOpacity : 0);
      }
    };

    setVisibility("spill-polygon-fill", activeLayers["spill-polygon"] !== false, 0.45);
    setVisibility("spill-polygon-outline", activeLayers["spill-polygon"] !== false, 1);
    setVisibility("origin-density-fill", activeLayers["origin-density"] !== false, 0.35);
    setVisibility("backward-tracks-line", activeLayers["backward-tracks"] !== false, 0.9);
    setVisibility("hindcast-corridor-fill", activeLayers["hindcast-corridor"] === true, 0.2);
    setVisibility("forecast-fill", activeLayers["forecast-contour"] !== false, 0.3);

    dashboardData.attribution.topCandidates.forEach((candidate) => {
      const layerId = `candidate-track-${candidate.candidateId}-line`;
      if (map.getLayer(layerId)) {
        map.setPaintProperty(layerId, "line-opacity", activeLayers["candidate-tracks"] !== false ? 1 : 0);
      }
    });
  }, [activeLayers, mapLoaded, dashboardData]);

  return (
    <div className="relative w-full h-full min-h-[460px] rounded-xl overflow-hidden border border-cyan-900/60 bg-[#061427]">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
}
