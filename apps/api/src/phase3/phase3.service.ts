import { Prisma } from '@prisma/client';
import { Injectable, Logger, NotFoundException, BadRequestException } from '@nestjs/common';
import { createHash, randomUUID, createHash as sha256Hash } from 'crypto';
import { PgBoss } from 'pg-boss';
import { promises as fs } from 'fs';
import path from 'path';
import { PrismaService } from '../database/prisma.service';
import { Phase3EngineClient, Phase3EngineResponse, Phase3RunRequest } from './phase3-engine.client';

export interface Phase3RunInput {
  phase2RunId: string;
  phase2Folder: string;
  aisCsvPath: string;
  outputDirectory: string;
  windowStride?: number;
  batchSize?: number;
  topCandidates?: number;
}

interface Phase3Job {
  runId: string;
  caseId: string;
  phase2RunId: string;
  correlationId: string;
  request: Phase3RunRequest;
}

const LEGAL_DISCLAIMER =
  'Candidate ranking supports investigation and does not constitute legal attribution or proof of responsibility.';

const SCORE_SEMANTICS =
  'INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY';

@Injectable()
export class Phase3Service {
  private readonly logger = new Logger(Phase3Service.name);
  private boss: PgBoss | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly engine: Phase3EngineClient,
  ) {}

  async onModuleInit() {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      this.logger.warn('DATABASE_URL is missing. Phase-3 queue disabled.');
      return;
    }

    try {
      this.boss = new PgBoss(connectionString);
      await this.boss.start();
      await this.boss.createQueue('phase3.attribution');
      await this.boss.work<Phase3Job>('phase3.attribution', async (jobs) => {
        const job = jobs[0];
        if (job) await this.execute(job.data);
      });
      this.logger.log('Phase-3 pg-boss queue initialized.');
    } catch (error) {
      this.logger.warn('Phase-3 queue unavailable; Phase-3 creation disabled.');
      this.boss = null;
    }
  }

  async onModuleDestroy() {
    if (this.boss) {
      await this.boss.stop();
      this.boss = null;
    }
  }

  private stableError(error: unknown) {
    const text = error instanceof Error ? error.message : String(error);
    if (text.includes('NO_CANDIDATES')) {
      return {
        code: 'PHASE3_NO_CANDIDATES',
        userMessage: 'No AIS candidates matched the Phase 2 time and space gate.',
        retryable: false,
      };
    }
    if (text.includes('LOW_AIS') || text.includes('QUALITY')) {
      return {
        code: 'PHASE3_LOW_AIS_QUALITY',
        userMessage: 'AIS data quality was insufficient for Phase 3 attribution.',
        retryable: false,
      };
    }
    if (text.includes('HTTP_404') || text.includes('FileNotFound')) {
      return {
        code: 'PHASE3_INPUT_NOT_FOUND',
        userMessage: 'A required Phase 3 input was not found.',
        retryable: false,
      };
    }
    return {
      code: 'PHASE3_ENGINE_FAILED',
      userMessage: 'Phase 3 attribution could not be completed.',
      retryable: true,
    };
  }

  private async event(
    runId: string,
    status: any,
    stage: string,
    progressPercent: number,
    safeMessage: string,
    correlationId: string,
    extra: Record<string, unknown> = {},
    errorCode?: string,
    retryable?: boolean,
  ) {
    await this.prisma.runEvent.create({
      data: {
        analysisRunId: runId,
        status,
        stage,
        progressPercent,
        safeMessage,
        correlationId,
        errorCode,
        retryable,
        details: JSON.parse(JSON.stringify(extra)) as Prisma.InputJsonValue,
      },
    });
  }

  async createRun(caseId: string, input: Phase3RunInput) {
    if (!caseId || !input.phase2RunId || !input.phase2Folder || !input.aisCsvPath || !input.outputDirectory) {
      throw new BadRequestException({
        error: {
          code: 'INVALID_PHASE3_REQUEST',
          message: 'caseId, phase2RunId, phase2Folder, aisCsvPath and outputDirectory are required.',
          retryable: false,
        },
      });
    }

    const phase2 = await this.prisma.analysisRun.findUnique({
      where: { id: input.phase2RunId },
    });

    if (!phase2) {
      throw new NotFoundException({
        error: { code: 'PHASE2_RUN_NOT_FOUND', message: 'The supplied Phase-2 run does not exist.', retryable: false },
      });
    }

    if (phase2.caseId !== caseId) {
      throw new BadRequestException({
        error: { code: 'PHASE2_CASE_MISMATCH', message: 'Phase-2 run does not belong to the requested case.', retryable: false },
      });
    }

    if (phase2.phase !== 'PHASE2') {
      throw new BadRequestException({
        error: { code: 'INVALID_PHASE2_RUN', message: 'The supplied run is not a Phase-2 run.', retryable: false },
      });
    }

    if (!['COMPLETED', 'COMPLETED_WITH_WARNINGS'].includes(phase2.status)) {
      throw new BadRequestException({
        error: { code: 'PHASE2_RESULT_NOT_READY', message: 'Phase 3 requires a completed Phase 2 result.', retryable: false },
      });
    }

    if (!this.boss) {
      throw new BadRequestException({
        error: { code: 'JOB_QUEUE_UNAVAILABLE', message: 'Phase-3 job queue is unavailable.', retryable: true },
      });
    }

    const request: Phase3RunRequest = {
      phase2Folder: input.phase2Folder,
      aisCsvPath: input.aisCsvPath,
      outputDirectory: input.outputDirectory,
      windowStride: input.windowStride ?? 2,
      batchSize: input.batchSize ?? 1024,
      topCandidates: input.topCandidates ?? 3,
    };

    const snapshot = {
      phase2RunId: input.phase2RunId,
      contractVersion: 'phase2-to-phase3-v1',
      request,
    };

    const configHash = createHash('sha256')
      .update(JSON.stringify(snapshot))
      .digest('hex');

    const idempotencyKey = `phase3-${caseId}-${input.phase2RunId}-${createHash('sha256').update(JSON.stringify(request)).digest('hex').slice(0, 16)}`;

    const existing = await this.prisma.analysisRun.findFirst({
      where: { idempotencyKey, phase: 'PHASE3' },
    });

    if (existing) {
      return {
        runId: existing.id,
        caseId: existing.caseId,
        phase: 'PHASE3',
        status: existing.status,
        progressPercentage: existing.status === 'COMPLETED' ? 100 : 0,
      };
    }

    const runId = randomUUID();
    const correlationId = randomUUID();

    await this.prisma.analysisRun.create({
      data: {
        id: runId,
        caseId,
        sceneId: phase2.sceneId,
        phase: 'PHASE3',
        status: 'QUEUED',
        dataOrigin: phase2.dataOrigin,
        idempotencyKey,
        inputContractVersion: 'phase2-to-phase3-v1',
        outputContractVersion: 'phase3-run-v1',
        configHash,
        codeVersion: 'VARUN-PHASE3-NESTJS-V1',
        requestedBy: 'AKHILESH',
        inputSnapshot: JSON.parse(JSON.stringify(snapshot)) as Prisma.InputJsonValue,
        provenance: {
          source: 'phase2',
          phase2RunId: input.phase2RunId,
          scoreSemantics: SCORE_SEMANTICS,
        },
      },
    });

    await this.event(
      runId,
      'QUEUED',
      'PHASE3_QUEUED',
      0,
      'Phase-3 AIS attribution queued.',
      correlationId,
      { phase2RunId: input.phase2RunId },
    );

    const jobExecutionId = randomUUID();
    await this.prisma.jobExecution.create({
      data: {
        id: jobExecutionId,
        analysisRunId: runId,
        queueName: 'phase3.attribution',
        idempotencyKey: `phase3-job-${runId}`,
        attemptNo: 1,
        status: 'QUEUED',
        correlationId,
      },
    });

    const bossJobId = await this.boss.send('phase3.attribution', {
      runId,
      caseId,
      phase2RunId: input.phase2RunId,
      correlationId,
      request,
    });

    if (bossJobId) {
      await this.prisma.jobExecution.update({
        where: { id: jobExecutionId },
        data: { bossJobId: bossJobId as string },
      });
    }

    return {
      runId,
      caseId,
      phase: 'PHASE3',
      status: 'QUEUED',
      progressPercentage: 0,
    };
  }

  private async persistArtifacts(
    runId: string,
    result: Phase3EngineResponse,
  ) {
    const root = path.resolve(process.cwd());
    const outputDirectory = path.resolve(root, result.outputDirectory);
    const allowedRoot = path.resolve(root, 'artifacts');

    if (
      outputDirectory !== allowedRoot &&
      !outputDirectory.startsWith(`${allowedRoot}${path.sep}`)
    ) {
      throw new Error('PHASE3_ARTIFACT_PATH_INVALID');
    }

    const files = Array.isArray(result.files) ? result.files : [];

    for (const logicalName of files) {
      if (
        typeof logicalName !== 'string' ||
        logicalName.includes('..') ||
        path.isAbsolute(logicalName) ||
        !/^[A-Za-z0-9._-]+$/.test(logicalName)
      ) {
        throw new Error('PHASE3_ARTIFACT_NAME_INVALID');
      }

      const fullPath = path.join(outputDirectory, logicalName);
      const bytes = await fs.readFile(fullPath);
      const stat = await fs.stat(fullPath);
      const checksum =
        result.artifactSha256?.[logicalName] ??
        createHash('sha256').update(Buffer.from(bytes)).digest('hex');

      const mediaType = logicalName.endsWith('.geojson')
        ? 'application/geo+json'
        : logicalName.endsWith('.json')
          ? 'application/json'
          : logicalName.endsWith('.csv')
            ? 'text/csv'
            : 'application/octet-stream';

      const uri = path
        .relative(root, fullPath)
        .split(path.sep)
        .join('/');

      await this.prisma.$executeRawUnsafe(
        `INSERT INTO artifacts
          (artifact_id, analysis_run_id, role, logical_name, artifact_version, uri,
           media_type, checksum_sha256, size_bytes, metadata)
         VALUES
          (gen_random_uuid(), $1::uuid, 'SCIENTIFIC'::artifact_role, $2, '1.0.0', $3,
           $4, $5, $6, $7::jsonb)
         ON CONFLICT (analysis_run_id, logical_name, artifact_version)
         DO UPDATE SET
           uri=EXCLUDED.uri,
           media_type=EXCLUDED.media_type,
           checksum_sha256=EXCLUDED.checksum_sha256,
           size_bytes=EXCLUDED.size_bytes,
           metadata=EXCLUDED.metadata`,
        runId,
        logicalName,
        uri,
        mediaType,
        checksum,
        stat.size,
        JSON.stringify({
          phase: 'PHASE3',
          source: 'services/ais-engine',
          outputDirectory: result.outputDirectory,
        }),
      );
    }
  }

  private async execute(job: Phase3Job) {
    const startedAt = new Date();

    await this.prisma.analysisRun.update({
      where: { id: job.runId },
      data: { status: 'PROCESSING', startedAt },
    });

    await this.prisma.jobExecution.updateMany({
      where: { analysisRunId: job.runId, status: 'QUEUED' },
      data: { status: 'RUNNING', startedAt },
    });

    await this.event(
      job.runId,
      'PROCESSING',
      'PHASE3_RUNNING',
      20,
      'Phase-3 AIS attribution is running.',
      job.correlationId,
    );

    try {
      await this.event(
        job.runId,
        'PROCESSING',
        'PHASE3_ENGINE_CALL',
        40,
        'Phase-3 AIS engine accepted the request.',
        job.correlationId,
      );

      const result = await this.engine.run(job.request);

      if (!result || result.status !== 'completed') {
        throw new Error('PHASE3_ENGINE_INVALID_RESPONSE');
      }

      const warnings = Array.isArray(result.warnings) ? result.warnings : [];
      const candidateCount = Number(result.candidateCount ?? 0);

      await this.persistArtifacts(job.runId, result);

      const provenance = {
        source: 'phase3-ais-engine',
        phase2RunId: result.phase2RunId,
        caseId: result.caseId,
        modelVersion: result.modelVersion,
        candidateCount,
        scoredWindows: Number(result.scoredWindows ?? 0),
        scoreSemantics: result.scoreSemantics ?? SCORE_SEMANTICS,
        calibrationStatus: result.calibrationStatus ?? null,
        artifactSha256: result.artifactSha256 ?? null,
        outputDirectory: result.outputDirectory,
        files: result.files ?? [],
        topCandidates: result.topCandidates ?? [],
        warnings,
        legalDisclaimer: LEGAL_DISCLAIMER,
      };

      await this.prisma.analysisRun.update({
        where: { id: job.runId },
        data: {
          status: warnings.length ? 'COMPLETED_WITH_WARNINGS' : 'COMPLETED',
          finishedAt: new Date(),
          provenance: JSON.parse(JSON.stringify(provenance)) as Prisma.InputJsonValue,
        },
      });

      await this.event(
        job.runId,
        warnings.length ? 'COMPLETED_WITH_WARNINGS' : 'COMPLETED',
        'PHASE3_COMPLETED',
        100,
        warnings.length
          ? 'Phase-3 completed with warnings.'
          : 'Phase-3 AIS attribution completed.',
        job.correlationId,
        { candidateCount, scoredWindows: Number(result.scoredWindows ?? 0) },
      );

      await this.prisma.jobExecution.updateMany({
        where: { analysisRunId: job.runId },
        data: { status: 'COMPLETED', completedAt: new Date() },
      });

      for (const warning of warnings) {
        await this.prisma.runWarning.create({
          data: {
            analysisRunId: job.runId,
            code: typeof warning === 'string' ? 'PHASE3_WARNING' : 'PHASE3_ENGINE_WARNING',
            severity: 'WARN',
            message: typeof warning === 'string' ? warning : JSON.stringify(warning),
            stage: 'PHASE3',
            details: {},
          },
        });
      }
    } catch (error) {
      const safe = this.stableError(error);

      await this.prisma.analysisRun.update({
        where: { id: job.runId },
        data: {
          status: 'FAILED',
          finishedAt: new Date(),
          provenance: JSON.parse(JSON.stringify({
            source: 'phase3-ais-engine',
            error: safe,
            phase2RunId: job.phase2RunId,
          })) as Prisma.InputJsonValue,
        },
      });

      await this.prisma.jobExecution.updateMany({
        where: { analysisRunId: job.runId },
        data: {
          status: 'FAILED',
          completedAt: new Date(),
          safeError: safe,
        },
      });

      await this.event(
        job.runId,
        'FAILED',
        'PHASE3_FAILED',
        100,
        safe.userMessage,
        job.correlationId,
        {},
        safe.code,
        safe.retryable,
      );

      this.logger.error(`Phase-3 ${job.runId} failed: ${safe.code}`);
    }
  }

  private publicCandidate(candidate: any, index: number) {
    const metadata =
      candidate && typeof candidate.publicMetadata === 'object' && !Array.isArray(candidate.publicMetadata)
        ? candidate.publicMetadata
        : {};

    return {
      ...candidate,
      candidateId: String(candidate.candidateId ?? candidate.id ?? ''),
      rankLabel: candidate.rankLabel ?? `CAND-${String(index + 1).padStart(3, '0')}`,
      investigativeScore: Number(candidate.investigativeScore ?? candidate.score?.investigativeScore ?? 0),
      scoreBreakdownPoints: candidate.scoreBreakdownPoints ?? {},
      closestApproach: candidate.closestApproach ?? null,
      candidateTrackRef: candidate.candidateTrackRef
        ? {
            ...candidate.candidateTrackRef,
            publicUrl: `/api/v1/artifacts/by-run/${encodeURIComponent(candidate.candidateTrackRef.artifactFile)}`,
          }
        : null,
      dataQuality: candidate.dataQuality ?? {
        status: 'MODEL_ELIGIBLE',
        observationCount: 0,
        eligibleWindowCount: 0,
        anomalyWindowCount: 0,
        includedInScoreV1: false,
      },
      supportingEvidence: Array.isArray(candidate.supportingEvidence) ? candidate.supportingEvidence : [],
      negativeEvidence: Array.isArray(candidate.negativeEvidence) ? candidate.negativeEvidence : [],
      warnings: Array.isArray(candidate.warnings) ? candidate.warnings : [],
      legalDisclaimer: LEGAL_DISCLAIMER,
      publicMetadata: {
        candidateLabel:
          typeof (metadata as any).candidateLabel === 'string'
            ? (metadata as any).candidateLabel
            : `Candidate ${index + 1}`,
        source:
          typeof (metadata as any).source === 'string'
            ? (metadata as any).source
            : 'AIS_FILTER',
        dataOrigin:
          typeof (metadata as any).dataOrigin === 'string'
            ? (metadata as any).dataOrigin
            : 'UNKNOWN',
      },
    };
  }

  async getAttribution(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
    });

    if (!run) {
      throw new NotFoundException({
        error: { code: 'RUN_NOT_FOUND', message: 'Analysis run not found.', retryable: false },
      });
    }

    if (run.phase !== 'PHASE3') {
      throw new BadRequestException({
        error: { code: 'INVALID_PHASE3_RUN', message: 'The supplied run is not a Phase-3 run.', retryable: false },
      });
    }

    const provenance: any = run.provenance ?? {};
    const rawCandidates = Array.isArray(provenance.topCandidates)
      ? provenance.topCandidates
      : [];
    const artifacts = await this.prisma.artifact.findMany({
      where: { analysisRunId: runId },
      select: { id: true, logicalName: true },
    });
    const artifactIds = new Map(artifacts.map((artifact) => [artifact.logicalName, artifact.id]));

    const candidates = rawCandidates.map((candidate: any, index: number) => {
      const mapped = this.publicCandidate(candidate, index);
      if (mapped.candidateTrackRef?.artifactFile) {
        const artifactId = artifactIds.get(mapped.candidateTrackRef.artifactFile);
        mapped.candidateTrackRef = artifactId
          ? { ...mapped.candidateTrackRef, publicUrl: `/api/v1/artifacts/${artifactId}` }
          : mapped.candidateTrackRef;
      }
      return mapped;
    });

    return {
      runId: run.id,
      caseId: run.caseId,
      phase: 'PHASE3',
      status: run.status,
      dataOrigin: run.dataOrigin,
      modelVersion: provenance.modelVersion ?? null,
      candidateCount: Number(provenance.candidateCount ?? candidates.length),
      scoredWindows: Number(provenance.scoredWindows ?? 0),
      scoreSemantics: provenance.scoreSemantics ?? SCORE_SEMANTICS,
      calibrationStatus: provenance.calibrationStatus ?? null,
      artifactSha256: provenance.artifactSha256 ?? null,
      candidates,
      warnings: provenance.warnings ?? [],
      disclaimer: LEGAL_DISCLAIMER,
    };
  }

  async getAttributionByCase(caseId: string) {
    const run = await this.prisma.analysisRun.findFirst({
      where: { caseId, phase: 'PHASE3' },
      orderBy: { createdAt: 'desc' },
    });

    if (!run) {
      throw new NotFoundException({
        error: { code: 'PHASE3_RUN_NOT_FOUND', message: 'No Phase-3 attribution run exists for this case.', retryable: false },
      });
    }

    return this.getAttribution(run.id);
  }

  async getStatus(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
    });

    if (!run) {
      throw new NotFoundException({
        error: { code: 'RUN_NOT_FOUND', message: 'Analysis run not found.', retryable: false },
      });
    }

    const latest = await this.prisma.runEvent.findFirst({
      where: { analysisRunId: runId },
      orderBy: { occurredAt: 'desc' },
    });

    const provenance: any = run.provenance ?? {};
    const failure = provenance.error ?? null;

    return {
      runId,
      phase: run.phase,
      status: run.status,
      progressPercentage: Number(latest?.progressPercent ?? (run.status === 'COMPLETED' ? 100 : 0)),
      message:
        latest?.safeMessage ??
        (run.status === 'QUEUED'
          ? 'Phase-3 AIS attribution queued.'
          : run.status === 'PROCESSING'
            ? 'Phase-3 AIS attribution running.'
            : run.status === 'COMPLETED'
              ? 'Phase-3 AIS attribution completed.'
              : 'Phase-3 AIS attribution failed.'),
      error: failure
        ? {
            code: failure.code,
            userMessage: failure.userMessage,
            retryable: Boolean(failure.retryable),
          }
        : null,
    };
  }

  async getCaseDashboard(caseId: string) {
    const run = await this.prisma.analysisRun.findFirst({
      where: { caseId, phase: 'PHASE3' },
      orderBy: { createdAt: 'desc' },
    });

    if (!run) {
      throw new NotFoundException({
        error: {
          code: 'PHASE3_RUN_NOT_FOUND',
          message: 'No Phase-3 attribution run exists for this case.',
          retryable: false,
        },
      });
    }

    const attribution = await this.getAttribution(run.id);
    const artifacts = await this.prisma.artifact.findMany({
      where: { analysisRunId: run.id },
      orderBy: { createdAt: 'asc' },
    });

    return {
      runId: run.id,
      caseId: run.caseId,
      sceneId: run.sceneId,
      phase: run.phase,
      status: run.status,
      dataOrigin: run.dataOrigin,
      createdAt: run.createdAt.toISOString(),
      startedAt: run.startedAt?.toISOString() ?? null,
      finishedAt: run.finishedAt?.toISOString() ?? null,
      phase3: attribution,
      artifacts: artifacts.map((artifact) => ({
        artifactId: artifact.id,
        logicalName: artifact.logicalName,
        artifactVersion: artifact.artifactVersion,
        mediaType: artifact.mediaType,
        checksumSha256: artifact.checksumSha256,
        sizeBytes: artifact.sizeBytes?.toString() ?? null,
        publicUrl: `/api/v1/artifacts/${artifact.id}`,
        metadata: artifact.metadata,
        createdAt: artifact.createdAt.toISOString(),
      })),
    };
  }

  // Legacy DB-backed readers retained for compatibility with the existing dashboard.
  async getCandidates(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({ where: { id: runId } });
    if (!run) {
      throw new NotFoundException({
        error: { code: 'RUN_NOT_FOUND', message: 'Analysis run not found.', retryable: false },
      });
    }

    const candidates = await this.prisma.phase3Candidate.findMany({
      where: { analysisRunId: runId },
      include: {
        scores: { orderBy: { rank: 'asc' }, include: { components: true } },
        features: true,
        evidenceEvents: true,
      },
      orderBy: { createdAt: 'asc' },
    });

    return {
      runId,
      phase: 'PHASE3',
      status: run.status,
      dataOrigin: run.dataOrigin,
      candidates: candidates.map((candidate: any) => ({
        candidateId: candidate.id,
        publicMetadata: this.sanitizePublicValue(candidate.publicMetadata),
        score: candidate.scores?.[0]
          ? {
              scoreVersion: candidate.scores[0].scoreVersion,
              investigativeScore: Number(candidate.scores[0].investigativeScore),
              rank: candidate.scores[0].rank,
              confidence: null,
              positiveTotal: Number(candidate.scores[0].positiveTotal),
              negativeTotal: Number(candidate.scores[0].negativeTotal),
              confidenceCap: candidate.scores[0].confidenceCap == null ? null : Number(candidate.scores[0].confidenceCap),
              explanation: candidate.scores[0].explanation,
              components: (candidate.scores[0].components ?? []).map((component: any) => ({
                componentName: component.componentName,
                rawValue: component.rawValue == null ? null : Number(component.rawValue),
                normalizedValue: component.normalizedValue == null ? null : Number(component.normalizedValue),
                weight: Number(component.weight),
                contribution: Number(component.contribution),
                isDeduction: component.isDeduction,
                capApplied: component.capApplied == null ? null : Number(component.capApplied),
                reason: component.reason,
              })),
            }
          : null,
        features: (candidate.features ?? []).map((feature: any) => ({
          featureName: feature.featureName,
          featureVersion: feature.featureVersion,
          rawValue: feature.rawValue == null ? null : Number(feature.rawValue),
          normalizedValue: feature.normalizedValue == null ? null : Number(feature.normalizedValue),
          unit: feature.unit,
          availability: feature.availability,
          confidenceCap: feature.confidenceCap == null ? null : Number(feature.confidenceCap),
          reason: feature.reason,
          provenance: feature.provenance,
        })),
        evidence: (candidate.evidenceEvents ?? []).map((event: any) => ({
          evidenceEventId: event.id,
          kind: event.kind,
          eventCode: event.eventCode,
          eventTimeUtc: event.eventTimeUtc?.toISOString?.() ?? event.eventTimeUtc ?? null,
          timeEndUtc: event.timeEndUtc?.toISOString?.() ?? event.timeEndUtc ?? null,
          rawValue: event.rawValue == null ? null : Number(event.rawValue),
          unit: event.unit,
          explanation: event.explanation,
          details: this.sanitizePublicValue(event.details),
        })),
      })),
      disclaimer: LEGAL_DISCLAIMER,
    };
  }

  async getCandidate(runId: string, candidateId: string) {
    const result = await this.getCandidates(runId);
    const candidate = result.candidates.find((item: any) => item.candidateId === candidateId);
    if (!candidate) {
      throw new NotFoundException({
        error: { code: 'CANDIDATE_NOT_FOUND', message: 'Phase-3 candidate not found.', retryable: false },
      });
    }
    return candidate;
  }

  private sanitizePublicValue(value: unknown): unknown {
    if (Array.isArray(value)) return value.map((item) => this.sanitizePublicValue(item));
    if (value === null || typeof value !== 'object') return value;
    const blocked = new Set([
      'mmsi', 'MMSI', 'imo', 'IMO', 'identityId', 'identity_id',
      'restrictedVesselId', 'restricted_vessel_id',
      'restrictedMetadata', 'restricted_metadata',
      'providerVesselId', 'provider_vessel_id',
      'groundTruth', 'ground_truth', 'shipName', 'ship_name',
    ]);
    const safe: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (!blocked.has(key)) safe[key] = this.sanitizePublicValue(child);
    }
    return safe;
  }
}




