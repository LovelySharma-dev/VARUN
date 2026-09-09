import { Injectable } from '@nestjs/common';

export interface Phase3RunRequest {
  phase2Folder: string;
  aisCsvPath: string;
  outputDirectory: string;
  windowStride?: number;
  batchSize?: number;
  topCandidates?: number;
}

export interface Phase3CandidateTrackRef {
  artifactFile: 'candidate_tracks.geojson';
  candidateId: string;
}

export interface Phase3Candidate {
  rank: number;
  candidateId: string;
  investigativePriorityScore: number;
  originProximityScore: number;
  originDwellScore: number;
  releaseTimeAlignmentScore: number;
  corridorAlignmentScore: number;
  behaviourRuleScore: number;
  lstmContinuousScore: number;
  darkGapScore: number;
  enteredOrigin50: boolean;
  enteredOrigin75: boolean;
  enteredOrigin90: boolean;
  minimumOriginCenterDistanceM: number;
  minimumCorridorDistanceM: number;
  closestOriginMidpointOffsetMin: number;
  scoreSemantics: string;
  calibrationStatus: string;
  rankLabel: string;
  investigativeScore: number;
  scoreBreakdownPoints: Record<string, number>;
  closestApproach: { distanceKm: number; timestampUtc: string };
  candidateTrackRef: Phase3CandidateTrackRef;
  dataQuality: {
    status: 'MODEL_ELIGIBLE';
    observationCount: number;
    eligibleWindowCount: number;
    anomalyWindowCount: number;
    includedInScoreV1: false;
  };
  supportingEvidence: string[];
  negativeEvidence: string[];
  warnings: string[];
  legalDisclaimer: string;
  [key: string]: unknown;
}

export interface Phase3EngineResponse {
  status: 'completed';
  caseId: string;
  phase2RunId: string;
  modelVersion: string;
  outputDirectory: string;
  files: string[];
  artifactSha256: Record<string, string>;
  candidateCount: number;
  scoredWindows: number;
  scoreSemantics: string;
  calibrationStatus: string;
  topCandidates: Phase3Candidate[];
  warnings: unknown[];
}

@Injectable()
export class Phase3EngineClient {
  private readonly baseUrl =
    process.env.PHASE3_ENGINE_URL ??
    'http://127.0.0.1:8103';

  async run(input: Phase3RunRequest): Promise<Phase3EngineResponse> {
    const response = await fetch(`${this.baseUrl}/v1/phase3/run`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        phase2Folder: input.phase2Folder,
        aisCsvPath: input.aisCsvPath,
        outputDirectory: input.outputDirectory,
        windowStride: input.windowStride ?? 2,
        batchSize: input.batchSize ?? 1024,
        topCandidates: input.topCandidates ?? 3,
      }),
    });

    const text = await response.text();

    if (!response.ok) {
      let detail = '';
      try {
        const parsed = JSON.parse(text);
        detail = typeof parsed?.detail === 'string' ? parsed.detail : '';
      } catch {}
      throw new Error(`PHASE3_ENGINE_HTTP_${response.status}${detail ? `: ${detail}` : ''}`);
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error('PHASE3_ENGINE_INVALID_JSON');
    }

    const result = parsed as Phase3EngineResponse;
    if (
      result.status !== 'completed' ||
      typeof result.caseId !== 'string' ||
      typeof result.phase2RunId !== 'string' ||
      !Array.isArray(result.topCandidates)
    ) {
      throw new Error('PHASE3_ENGINE_INVALID_RESPONSE');
    }

    return result;
  }

  async health(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}
