import type * as GeoJSON from "geojson";

export type PipelineStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

export interface CaseSummary {
  caseId: string;
  title: string;
  region: string;
  detectionTimestamp: string; // ISO 8601 UTC
  overallStatus: PipelineStatus;
  phase1Status: PipelineStatus;
  phase2Status: PipelineStatus;
  phase3Status: PipelineStatus;
  lastUpdated: string;
  offlineReplayAvailable: boolean;
  warnings: string[];
}

export interface DetectionData {
  sarPreviewUrl: string;
  probabilityMapUrl?: string;
  binaryMaskUrl?: string;
  spillPolygon: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>;
  centroid: GeoJSON.Feature<GeoJSON.Point>;
  areaKm2: number;
  perimeterKm: number;
  slickLengthKm: number;
  orientation: string;
  detectionThreshold: number;
  modelVersion: string;
  detectionTimestamp: string;
  warnings: string[];
}

export interface DriftData {
  hindcastCorridor: GeoJSON.Feature<GeoJSON.Polygon>;
  originDensityContours: GeoJSON.FeatureCollection<GeoJSON.Polygon>;
  backwardParticleTracks: GeoJSON.FeatureCollection<GeoJSON.MultiLineString | GeoJSON.LineString>;
  forwardForecast: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.LineString>;
  statedReleaseRadiusKm?: number;
  currentWindQuality: {
    windDataset: string;
    currentDataset: string;
    qualityScore: number;
    coverageGapWarning?: string;
  };
  timeSteps: Array<{
    hourOffset: number; // e.g. -48, -24, 0, +24, +48
    label: string;
    timestampUTC: string;
  }>;
  scientificWarning: string;
}

export interface CandidateScoreBreakdown {
  proximity: number;      // max 30
  timeOverlap: number;     // max 25
  corridorMatch: number;   // max 20
  behaviour: number;       // max 10
  aisGap: number;          // max 5
  dataQuality: number;     // max 10
  negativePenalty: number; // e.g. -4
  totalScore: number;      // sum of above
}

export interface ReasonCodeItem {
  code: string;       // e.g. RC-01
  label: string;      // e.g. Spatial Proximity to Release Zone
  description: string;// e.g. Closest Point of Approach within 0.6 km of Release Zone A
  impact: string;     // e.g. HIGH (+29.5 pts)
  type: "CRITICAL" | "HIGH" | "MEDIUM" | "NEUTRAL";
}

export interface Candidate {
  candidateId: string; // Strictly anonymized (e.g. CAND-003)
  rank: number;
  vesselType: string;
  investigativeScore: number; // Out of 100
  scoreBreakdown: CandidateScoreBreakdown;
  reasonCodes: ReasonCodeItem[];
  closestApproach: {
    distanceKm: number;
    timestampUTC: string;
    coordinates?: [number, number];
  };
  vesselTrack: GeoJSON.Feature<GeoJSON.LineString | GeoJSON.MultiLineString>;
  supportingEvidence: string[];
  negativeEvidence: string[];
  warnings: string[];
}

export interface AttributionData {
  topCandidates: Candidate[];
  privacyDisclaimer: string;
  legalDisclaimer: string;
}

export interface TimelineEvent {
  id: string;
  timestampUTC: string;
  hourOffset: number;
  label: string;
  eventType: "RELEASE" | "DETECTION" | "CLOSEST_APPROACH" | "FORECAST";
  description: string;
  associatedCandidateId?: string;
}

export interface MapLayerManifestItem {
  id: string;
  label: string;
  type: "fill" | "line" | "circle" | "raster";
  category: "DETECTION" | "HINDCAST" | "FORECAST" | "ATTRIBUTION";
  artifactUrl?: string;
  defaultVisible: boolean;
  color: string;
  opacity?: number;
}

export interface CompleteDashboardResponse {
  caseSummary: CaseSummary;
  runs: Record<string, { runId: string; phase: string; status: PipelineStatus; message: string }>;
  detection: DetectionData;
  drift: DriftData;
  attribution: AttributionData;
  timeline: TimelineEvent[];
  layers: MapLayerManifestItem[];
  warnings: string[];
}

export interface RunStatusResponse {
  runId: string;
  phase: string;
  status: PipelineStatus;
  progressPercentage: number;
  message: string;
  error?: {
    code: string;
    message: string;
    retryable: boolean;
  };
}
