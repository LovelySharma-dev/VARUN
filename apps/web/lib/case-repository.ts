import { CompleteDashboardResponse } from "./contracts";
import baseFixture from "../fixtures/complete-dashboard.fixture.json";

// --- CASE 1: Arabian Sea Offshore (Bombay High Sector) ---
const CASE_1_DASHBOARD: CompleteDashboardResponse = {
  ...(baseFixture as unknown as CompleteDashboardResponse),
};

// --- CASE 2: Gulf of Kutch Shipping Channel ---
const CASE_2_DASHBOARD: CompleteDashboardResponse = {
  ...(baseFixture as unknown as CompleteDashboardResponse),
  caseSummary: {
    caseId: "CASE-S2-DEMO-002",
    title: "Gulf of Kutch Channel Spillage",
    region: "Kandla Approach Channel (22.5100° N, 69.3200° E)",
    detectionTimestamp: "2026-09-04T14:20:00Z",
    overallStatus: "COMPLETED",
    phase1Status: "COMPLETED",
    phase2Status: "COMPLETED",
    phase3Status: "COMPLETED",
    lastUpdated: "2026-09-05T09:40:00Z",
    offlineReplayAvailable: true,
    warnings: [
      "Strong tidal current oscillation (1.4 m/s)",
      "High coastal sensitivity zone within 12 km"
    ]
  },
  detection: {
    sarPreviewUrl: "/ship_oil_spill.jpg",
    probabilityMapUrl: "/ship_oil_spill.jpg",
    binaryMaskUrl: "/ship_oil_spill.jpg",
    spillPolygon: {
      type: "Feature",
      properties: { name: "Gulf of Kutch Slick", confidence: 0.962 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [69.2900, 22.4850],
            [69.3350, 22.5020],
            [69.3550, 22.5280],
            [69.3250, 22.5350],
            [69.2850, 22.5120],
            [69.2900, 22.4850]
          ]
        ]
      }
    },
    centroid: {
      type: "Feature",
      properties: { name: "Spill Centroid" },
      geometry: {
        type: "Point",
        coordinates: [69.3200, 22.5100]
      }
    },
    areaKm2: 2.75,
    perimeterKm: 8.9,
    slickLengthKm: 4.8,
    orientation: "75° ENE",
    detectionThreshold: 0.82,
    modelVersion: "U-Net-SAR-v2.4-Sentinel1",
    detectionTimestamp: "2026-09-04T14:20:00Z",
    warnings: [
      "Narrow channel slick detection; tidal flow influence modeled."
    ]
  },
  drift: {
    statedReleaseRadiusKm: 6.2,
    hindcastCorridor: {
      type: "Feature",
      properties: { name: "Gulf of Kutch Tidal Hindcast" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [69.3200, 22.5100],
            [69.2100, 22.4600],
            [69.1000, 22.4200],
            [69.0200, 22.3800],
            [69.0600, 22.3400],
            [69.1800, 22.3900],
            [69.3200, 22.5100]
          ]
        ]
      }
    },
    originDensityContours: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "Origin Probability Zone A (90%)", density: 0.90, radiusKm: 6.2 },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [69.0400, 22.3900],
                [69.1100, 22.4200],
                [69.1400, 22.3700],
                [69.0700, 22.3500],
                [69.0400, 22.3900]
              ]
            ]
          }
        },
        {
          type: "Feature",
          properties: { name: "Origin Probability Zone B (75%)", density: 0.75, radiusKm: 12.5 },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [69.0000, 22.3600],
                [69.1500, 22.4400],
                [69.1900, 22.3900],
                [69.0500, 22.3200],
                [69.0000, 22.3600]
              ]
            ]
          }
        }
      ]
    },
    backwardParticleTracks: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { trackId: "PT-KUTCH-01", weight: 0.91 },
          geometry: {
            type: "LineString",
            coordinates: [
              [69.3200, 22.5100],
              [69.2300, 22.4700],
              [69.1400, 22.4300],
              [69.0600, 22.3800]
            ]
          }
        }
      ]
    },
    forwardForecast: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "+24h Tidal Dispersion Risk", risk: "HIGH" },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [69.3200, 22.5100],
                [69.3700, 22.5400],
                [69.4300, 22.5700],
                [69.4600, 22.5500],
                [69.4000, 22.5100],
                [69.3200, 22.5100]
              ]
            ]
          }
        }
      ]
    },
    currentWindQuality: {
      windDataset: "INCOIS Coastal Wind Model (11.4 kts 190° S)",
      currentDataset: "INCOIS High-Resolution Coastal Current Model (1.4 m/s)",
      qualityScore: 91,
      coverageGapWarning: "Strong tidal oscillation with rapid current reversals."
    },
    timeSteps: [
      { hourOffset: -48, label: "T - 48h (Origin Start)", timestampUTC: "2026-09-02T14:20:00Z" },
      { hourOffset: -24, label: "T - 24h (Tidal Corridor)", timestampUTC: "2026-09-03T14:20:00Z" },
      { hourOffset: 0, label: "T = 0h (Detection Time)", timestampUTC: "2026-09-04T14:20:00Z" },
      { hourOffset: 24, label: "T + 24h (Channel Risk)", timestampUTC: "2026-09-05T14:20:00Z" }
    ],
    scientificWarning: "Tidal oscillation hydrodynamics simulated across Kandla deepwater channel."
  },
  attribution: {
    topCandidates: [
      {
        candidateId: "CAND-008",
        rank: 1,
        vesselType: "Chemical Tanker",
        investigativeScore: 88.7,
        scoreBreakdown: {
          proximity: 28.0,
          timeOverlap: 23.5,
          corridorMatch: 18.0,
          behaviour: 8.5,
          aisGap: 3.5,
          dataQuality: 8.8,
          negativePenalty: -1.6,
          totalScore: 88.7
        },
        reasonCodes: [
          {
            code: "RC-01",
            label: "Critical Channel Proximity",
            description: "Passed within 0.4 km of release zone during slack tide.",
            impact: "+28.0 pts",
            type: "CRITICAL"
          },
          {
            "code": "RC-03",
            "label": "Tidal Speed Anomaly",
            "description": "Speed dropped significantly to 5.4 kts inside corridor.",
            "impact": "+8.5 pts",
            "type": "HIGH"
          }
        ],
        closestApproach: {
          distanceKm: 0.4,
          timestampUTC: "2026-09-04T11:30:00Z",
          coordinates: [69.0800, 22.3900]
        },
        supportingEvidence: [
          "Passed directly through high origin probability zone during tidal turn (CPA = 0.4 km)",
          "Engine load and sudden speed reduction from 12.8 kts to 5.4 kts",
          "AIS position report dropped for 45 minutes in origin corridor"
        ],
        negativeEvidence: [],
        warnings: [],
        vesselTrack: {
          type: "Feature",
          properties: { name: "GULF TRADER Track" },
          geometry: {
            type: "LineString",
            coordinates: [
              [68.9000, 22.3000],
              [69.0800, 22.3900],
              [69.2500, 22.4800],
              [69.4200, 22.5700]
            ]
          }
        }
      }
    ],
    privacyDisclaimer: "Vessel ranking is probabilistic investigative intelligence; not a formal legal accusation.",
    legalDisclaimer: "Court-admissible digital dossier formatted under IMO MARPOL Annex I protocol."
  }
};

// --- CASE 3: Bay of Bengal (Paradip Offshore Sector) ---
const CASE_3_DASHBOARD: CompleteDashboardResponse = {
  ...(baseFixture as unknown as CompleteDashboardResponse),
  caseSummary: {
    caseId: "CASE-S3-DEMO-003",
    title: "Bay of Bengal Bulk Carrier Discharge",
    region: "Paradip Offshore Sector (19.9500° N, 86.8500° E)",
    detectionTimestamp: "2026-09-03T06:15:00Z",
    overallStatus: "COMPLETED",
    phase1Status: "COMPLETED",
    phase2Status: "COMPLETED",
    phase3Status: "COMPLETED",
    lastUpdated: "2026-09-04T18:00:00Z",
    offlineReplayAvailable: true,
    warnings: [
      "Monsoon wind field (18.5 knots SSE)",
      "High open ocean dispersion rate"
    ]
  },
  detection: {
    sarPreviewUrl: "/ship_oil_spill.jpg",
    probabilityMapUrl: "/ship_oil_spill.jpg",
    binaryMaskUrl: "/ship_oil_spill.jpg",
    spillPolygon: {
      type: "Feature",
      properties: { name: "Bay of Bengal Slick", confidence: 0.978 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [86.8100, 19.9200],
            [86.8650, 19.9400],
            [86.8900, 19.9750],
            [86.8550, 19.9850],
            [86.8050, 19.9550],
            [86.8100, 19.9200]
          ]
        ]
      }
    },
    centroid: {
      type: "Feature",
      properties: { name: "Spill Centroid" },
      geometry: {
        type: "Point",
        coordinates: [86.8500, 19.9500]
      }
    },
    areaKm2: 5.64,
    perimeterKm: 16.1,
    slickLengthKm: 8.4,
    orientation: "42° NE",
    detectionThreshold: 0.85,
    modelVersion: "U-Net-SAR-v2.4-Sentinel1",
    detectionTimestamp: "2026-09-03T06:15:00Z",
    warnings: [
      "Extensive diffuse sheen detected offshore Odisha coast."
    ]
  },
  drift: {
    statedReleaseRadiusKm: 11.2,
    hindcastCorridor: {
      type: "Feature",
      properties: { name: "Bay of Bengal Monsoon Drift" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [86.8500, 19.9500],
            [86.7200, 19.8200],
            [86.6000, 19.6800],
            [86.4800, 19.5200],
            [86.5400, 19.4800],
            [86.6800, 19.6400],
            [86.8500, 19.9500]
          ]
        ]
      }
    },
    originDensityContours: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "Origin Probability Zone A (90%)", density: 0.90, radiusKm: 11.2 },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [86.5000, 19.5400],
                [86.5800, 19.5800],
                [86.6100, 19.5200],
                [86.5300, 19.4900],
                [86.5000, 19.5400]
              ]
            ]
          }
        },
        {
          type: "Feature",
          properties: { name: "Origin Probability Zone B (75%)", density: 0.75, radiusKm: 22.0 },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [86.4500, 19.5000],
                [86.6300, 19.6200],
                [86.6700, 19.5500],
                [86.5000, 19.4500],
                [86.4500, 19.5000]
              ]
            ]
          }
        }
      ]
    },
    backwardParticleTracks: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { trackId: "PT-BOB-01", weight: 0.94 },
          geometry: {
            type: "LineString",
            coordinates: [
              [86.8500, 19.9500],
              [86.7400, 19.8300],
              [86.6200, 19.6900],
              [86.5200, 19.5300]
            ]
          }
        }
      ]
    },
    forwardForecast: {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "+24h Monsoon Dispersion Risk", risk: "MEDIUM" },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [86.8500, 19.9500],
                [86.9100, 20.0100],
                [86.9800, 20.0800],
                [87.0300, 20.0500],
                [86.9500, 19.9600],
                [86.8500, 19.9500]
              ]
            ]
          }
        }
      ]
    },
    currentWindQuality: {
      windDataset: "INCOIS BoB High-Resolution Wind (18.5 kts SSE)",
      currentDataset: "INCOIS BoB Hydrodynamic Current Model",
      qualityScore: 96,
      coverageGapWarning: "Monsoon oceanic forcing modeled cleanly."
    },
    timeSteps: [
      { hourOffset: -48, label: "T - 48h (Origin Estimated)", timestampUTC: "2026-09-01T06:15:00Z" },
      { hourOffset: -24, label: "T - 24h (Monsoon Corridor)", timestampUTC: "2026-09-02T06:15:00Z" },
      { hourOffset: 0, label: "T = 0h (Detection Time)", timestampUTC: "2026-09-03T06:15:00Z" },
      { hourOffset: 48, label: "T + 48h (Maximum Drift)", timestampUTC: "2026-09-05T06:15:00Z" }
    ],
    scientificWarning: "Open ocean monsoon hydrodynamic dispersion trajectory."
  },
  attribution: {
    topCandidates: [
      {
        candidateId: "CAND-014",
        rank: 1,
        vesselType: "Bulk Cargo Carrier",
        investigativeScore: 90.1,
        scoreBreakdown: {
          proximity: 28.5,
          timeOverlap: 24.0,
          corridorMatch: 18.5,
          behaviour: 9.0,
          aisGap: 3.8,
          dataQuality: 9.1,
          negativePenalty: -2.8,
          totalScore: 90.1
        },
        reasonCodes: [
          {
            code: "RC-01",
            label: "Open Ocean Proximity Match",
            description: "CPA = 0.5 km at suspected release origin point.",
            impact: "+28.5 pts",
            type: "CRITICAL"
          },
          {
            code: "RC-02",
            label: "AIS Transponder Signal Gap",
            description: "58-minute reporting gap during corridor transit.",
            impact: "+13.8 pts",
            type: "HIGH"
          }
        ],
        closestApproach: {
          distanceKm: 0.5,
          timestampUTC: "2026-09-02T23:45:00Z",
          coordinates: [86.5300, 19.5300]
        },
        supportingEvidence: [
          "AIS track directly aligns with -36h origin trajectory in BoB corridor (CPA = 0.5 km)",
          "Speed drops from 14.2 kts to 6.8 kts during passage near origin point",
          "AIS gap of 58 minutes recorded"
        ],
        negativeEvidence: [],
        warnings: [],
        vesselTrack: {
          type: "Feature",
          properties: { name: "ODISHA PROMOTER Track" },
          geometry: {
            type: "LineString",
            coordinates: [
              [86.3500, 19.3500],
              [86.5300, 19.5300],
              [86.7200, 19.8000],
              [86.9500, 20.1000]
            ]
          }
        }
      }
    ],
    privacyDisclaimer: "Vessel ranking is probabilistic investigative intelligence; not a formal legal accusation.",
    legalDisclaimer: "Court-admissible digital dossier formatted under IMO MARPOL Annex I protocol."
  }
};

export class CaseRepository {
  private static dynamicCases: Record<string, CompleteDashboardResponse> = {
    "CASE-S1-DEMO-001": CASE_1_DASHBOARD,
    "CASE-S2-DEMO-002": CASE_2_DASHBOARD,
    "CASE-S3-DEMO-003": CASE_3_DASHBOARD,
  };

  static getCase(caseId: string): CompleteDashboardResponse {
    if (this.dynamicCases[caseId]) {
      return this.dynamicCases[caseId];
    }
    // Fallback to Case 1 if unknown
    return this.dynamicCases["CASE-S1-DEMO-001"];
  }

  static createOrUpdateCase(dashboard: CompleteDashboardResponse): void {
    this.dynamicCases[dashboard.caseSummary.caseId] = dashboard;
  }
}
