import {
  Injectable,
  Logger,
  OnModuleDestroy,
  OnModuleInit,
} from '@nestjs/common';
import { createHash, randomUUID } from 'crypto';
import { PgBoss } from 'pg-boss';
import { PrismaService } from '../database/prisma.service';
import { Phase1EngineClient } from './phase1-engine.client';

export type TestRunStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED';

export interface TestRun {
  runId: string;
  status: TestRunStatus;
  progress: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
}

interface TestJobData {
  runId: string;
  jobExecutionId: string;
  correlationId: string;
}

@Injectable()
export class RunsService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RunsService.name);

  private boss: PgBoss | null = null;

  private readonly runs = new Map<string, TestRun>();

  constructor(
    private readonly prisma: PrismaService,
    private readonly phase1Engine: Phase1EngineClient,
  ) {}
  // =========================================================
  // PUBLIC ATTRIBUTION PRIVACY BOUNDARY
  // Explicit allow-list only. Never return restricted identity.
  // =========================================================

  private sanitizeAttributionMetadata(metadata: unknown) {
    const source =
      metadata &&
      typeof metadata === 'object' &&
      !Array.isArray(metadata)
        ? metadata as Record<string, unknown>
        : {};

    return {
      candidateLabel:
        typeof source.candidateLabel === 'string'
          ? source.candidateLabel
          : 'Candidate',

      source:
        typeof source.source === 'string'
          ? source.source
          : 'AIS_FILTER',

      dataOrigin:
        typeof source.dataOrigin === 'string'
          ? source.dataOrigin
          : 'UNKNOWN',
    };
  }


  async onModuleInit(): Promise<void> {
    const connectionString = process.env.DATABASE_URL;

    if (!connectionString) {
      this.logger.warn(
        'DATABASE_URL is not configured. Queue is disabled.',
      );
      return;
    }

    try {
      this.boss = new PgBoss(connectionString);

      await this.boss.start();

      await this.boss.createQueue('test-run');

      await this.boss.work<TestJobData>(
        'test-run',
        async (jobs) => {
          const job = jobs[0];

          if (!job) {
            return;
          }

          const {
            runId,
            jobExecutionId,
            correlationId,
          } = job.data;

          const run = this.runs.get(runId);

          /*
           * A process restart can clear the in-memory map.
           * In that case the database remains the source of truth.
           */
          if (!run) {
            const dbRun =
              await this.prisma.analysisRun.findUnique({
                where: {
                  id: runId,
                },
              });

            if (!dbRun) {
              this.logger.warn(
                `Run ${runId} not found`,
              );
              return;
            }

            this.runs.set(runId, {
              runId: dbRun.id,
              status: dbRun.status as TestRunStatus,
              progress:
                dbRun.status === 'COMPLETED'
                  ? 100
                  : dbRun.status === 'PROCESSING'
                    ? 50
                    : 0,
              createdAt:
                dbRun.createdAt.toISOString(),
              startedAt:
                dbRun.startedAt?.toISOString(),
              completedAt:
                dbRun.finishedAt?.toISOString(),
            });
          }

          const currentRun = this.runs.get(runId);

          if (!currentRun) {
            return;
          }

          // ---------------------------------
          // RUNNING
          // ---------------------------------

          const startedAt = new Date();

          currentRun.status = 'RUNNING';
          currentRun.progress = 50;
          currentRun.startedAt =
            startedAt.toISOString();

          await this.prisma.jobExecution.update({
            where: {
              id: jobExecutionId,
            },
            data: {
              status: 'RUNNING',
              startedAt,
              correlationId,
            },
          });

          await this.prisma.analysisRun.update({
            where: {
              id: runId,
            },
            data: {
              status: 'PROCESSING',
              startedAt,
            },
          });

          await this.prisma.runEvent.create({
            data: {
              analysisRunId: runId,
              status: 'PROCESSING',
              stage: 'TEST_PROCESSING',
              progressPercent: 50,
              safeMessage:
                'Test run processing started.',
              correlationId,
              details: {},
            },
          });

          // ---------------------------------
          // SIMULATE PROCESSING
          // ---------------------------------

         // ---------------------------------
// LOAD RUN INPUT
// ---------------------------------

const dbRun =
  await this.prisma.analysisRun.findUnique({
    where: {
      id: runId,
    },
  });

if (!dbRun) {
  throw new Error(`Run ${runId} not found`);
}

const snapshot =
  dbRun.inputSnapshot &&
  typeof dbRun.inputSnapshot === 'object' &&
  !Array.isArray(dbRun.inputSnapshot)
    ? dbRun.inputSnapshot as Record<string, unknown>
    : {};

const input = {
  imagePath:
    typeof snapshot.imagePath === 'string'
      ? snapshot.imagePath
      : undefined,

  imageWidth:
    typeof snapshot.imageWidth === 'number'
      ? snapshot.imageWidth
      : undefined,

  imageHeight:
    typeof snapshot.imageHeight === 'number'
      ? snapshot.imageHeight
      : undefined,

  tileSize:
    typeof snapshot.tileSize === 'number'
      ? snapshot.tileSize
      : 512,

  overlap:
    typeof snapshot.overlap === 'number'
      ? snapshot.overlap
      : 64,

  confidenceThreshold:
    typeof snapshot.confidenceThreshold === 'number'
      ? snapshot.confidenceThreshold
      : 0.5,

  iouThreshold:
    typeof snapshot.iouThreshold === 'number'
      ? snapshot.iouThreshold
      : 0.5,
};

if (
  !input.imagePath ||
  !input.imageWidth ||
  !input.imageHeight
) {
  throw new Error(
    'Run inputSnapshot does not contain valid imagePath, imageWidth and imageHeight',
  );
}

// ---------------------------------
// PHASE-1 DETECTION ENGINE
// ---------------------------------

const engineResult =
  await this.phase1Engine.infer({
    imagePath: input.imagePath,
    imageWidth: input.imageWidth,
    imageHeight: input.imageHeight,
    tileSize: input.tileSize,
    overlap: input.overlap,
    confidenceThreshold:
      input.confidenceThreshold,
    iouThreshold:
      input.iouThreshold,
  });
          // ---------------------------------
          // COMPLETED
          // ---------------------------------

          const completedAt = new Date();

          currentRun.status = 'COMPLETED';
          currentRun.progress = 100;
          currentRun.completedAt =
            completedAt.toISOString();

          await this.prisma.jobExecution.update({
            where: {
              id: jobExecutionId,
            },
            data: {
              status: 'COMPLETED',
              completedAt,
            },
          });

          await this.prisma.analysisRun.update({
            where: {
              id: runId,
            },
            data: {
              status: 'COMPLETED',
              finishedAt: completedAt,
            },
          });

          await this.prisma.runEvent.create({
            data: {
              analysisRunId: runId,
              status: 'COMPLETED',
              stage: 'TEST_COMPLETED',
              progressPercent: 100,
              safeMessage:
                'Test run completed successfully.',
              correlationId,
              details: {},
            },
          });

          this.logger.log(
            `Test run ${runId} completed`,
          );
        },
      );

      this.logger.log(
        'pg-boss queue initialized successfully.',
      );
    } catch (error) {
      this.logger.warn(
        'PostgreSQL/pg-boss is unavailable. Queue is disabled for this session.',
      );

      this.boss = null;
    }
  }

  async onModuleDestroy(): Promise<void> {
    if (this.boss) {
      await this.boss.stop();
      this.boss = null;
    }
  }

  // =========================================
  // CREATE TEST RUN
  // =========================================

  async createTestRun(): Promise<TestRun> {
    if (!this.boss) {
      throw new Error(
        'JOB_QUEUE_UNAVAILABLE: PostgreSQL/pg-boss is not available.',
      );
    }

    const runId = randomUUID();

    const caseId =
      '00000000-0000-4000-8000-000000000001';

    const sceneId =
      '00000000-0000-4000-8000-000000000002';

    const inputSnapshot = {
  type: 'TEST_RUN',
  caseId,
  sceneId,

  imagePath: 'C:/Users/akhil/projects/VARUN/data/fixtures/images/00168.tif',
  imageWidth: 2048,
  imageHeight: 2048,

  tileSize: 512,
  overlap: 64,

  confidenceThreshold: 0.5,
  iouThreshold: 0.5,
};

    const configHash = createHash('sha256')
      .update(JSON.stringify(inputSnapshot))
      .digest('hex');

    const idempotencyKey =
      `test-run-${runId}`;

    const correlationId = randomUUID();

    // ---------------------------------
    // ANALYSIS RUN
    // ---------------------------------

    await this.prisma.analysisRun.create({
      data: {
        id: runId,
        caseId,
        sceneId,

        phase: 'PHASE1',
        status: 'QUEUED',
        dataOrigin: 'SYNTHETIC',

        idempotencyKey,

        inputContractVersion: 'v1',
        outputContractVersion: 'v1',

        configHash,
        codeVersion: 'dev',

        requestedBy: 'test',

        inputSnapshot,
        provenance: {
          source: 'api-test',
        },
      },
    });

    const run: TestRun = {
      runId,
      status: 'QUEUED',
      progress: 0,
      createdAt: new Date().toISOString(),
    };

    this.runs.set(runId, run);

    // ---------------------------------
    // QUEUED EVENT
    // ---------------------------------

    await this.prisma.runEvent.create({
      data: {
        analysisRunId: runId,
        status: 'QUEUED',
        stage: 'QUEUED',
        progressPercent: 0,
        safeMessage: 'Test run queued.',
        correlationId,
        details: {},
      },
    });

    // ---------------------------------
    // JOB EXECUTION
    // ---------------------------------

    const jobExecutionId = randomUUID();

    await this.prisma.jobExecution.create({
      data: {
        id: jobExecutionId,
        analysisRunId: runId,
        queueName: 'test-run',
        idempotencyKey:
          `job-${runId}`,
        attemptNo: 1,
        status: 'QUEUED',
        correlationId,
      },
    });

    // ---------------------------------
    // PG-BOSS JOB
    // ---------------------------------

    const bossJobId =
      await this.boss.send('test-run', {
        runId,
        jobExecutionId,
        correlationId,
      });

    if (bossJobId) {
      await this.prisma.jobExecution.update({
        where: {
          id: jobExecutionId,
        },
        data: {
          bossJobId:
            bossJobId as string,
        },
      });
    }

    return run;
  }

  // =========================================
  // GET RUN
  // =========================================

  async getRun(
    runId: string,
  ): Promise<TestRun> {
    const memoryRun =
      this.runs.get(runId);

    if (memoryRun) {
      return memoryRun;
    }

    const dbRun =
      await this.prisma.analysisRun.findUnique({
        where: {
          id: runId,
        },
      });

    if (!dbRun) {
      throw new Error(
        `Run ${runId} not found`,
      );
    }

    const run: TestRun = {
      runId: dbRun.id,
      status:
        dbRun.status as TestRunStatus,
      progress:
        dbRun.status === 'COMPLETED'
          ? 100
          : dbRun.status === 'PROCESSING'
            ? 50
            : 0,
      createdAt:
        dbRun.createdAt.toISOString(),
      startedAt:
        dbRun.startedAt?.toISOString(),
      completedAt:
        dbRun.finishedAt?.toISOString(),
    };

    this.runs.set(runId, run);

    return run;
  }

  // =========================================
  // GET RUN EVENTS
  // =========================================

  async getRunEvents(runId: string) {
    const dbRun =
      await this.prisma.analysisRun.findUnique({
        where: {
          id: runId,
        },
      });

    if (!dbRun) {
      throw new Error(
        `Run ${runId} not found`,
      );
    }

    const events =
      await this.prisma.runEvent.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          occurredAt: 'asc',
        },
      });

    return {
      runId,
      events: events.map((event) => ({
        eventId: event.id.toString(),
        status: event.status,
        stage: event.stage,
        progressPercent:
          event.progressPercent === null
            ? null
            : Number(event.progressPercent),
        safeMessage:
          event.safeMessage,
        errorCode:
          event.errorCode,
        retryable:
          event.retryable,
        correlationId:
          event.correlationId,
        details:
          event.details,
        occurredAt:
          event.occurredAt.toISOString(),
      })),
    };
  }

  // =========================================
  // GET RUN ARTIFACTS
  // =========================================

  async getRunArtifacts(runId: string) {
    const dbRun =
      await this.prisma.analysisRun.findUnique({
        where: {
          id: runId,
        },
      });

    if (!dbRun) {
      throw new Error(
        `Run ${runId} not found`,
      );
    }

    const artifacts =
      await this.prisma.artifact.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          createdAt: 'asc',
        },
      });

    return {
      runId,
      artifacts: artifacts.map(
        (artifact) => ({
          artifactId: artifact.id,
          role: null,
          logicalName:
            artifact.logicalName,
          artifactVersion:
            artifact.artifactVersion,
          uri:
            artifact.uri,
          mediaType:
            artifact.mediaType,
          checksumSha256:
            artifact.checksumSha256,
          sizeBytes:
            artifact.sizeBytes === null
              ? null
              : artifact.sizeBytes.toString(),
          timeStartUtc:
            artifact.timeStartUtc?.toISOString(),
          timeEndUtc:
            artifact.timeEndUtc?.toISOString(),
          metadata:
            artifact.metadata,
          createdAt:
            artifact.createdAt.toISOString(),
        }),
      ),
    };
  }

  // =========================================
  // COMPLETE DASHBOARD
  // =========================================

  async getDashboard(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: {
        id: runId,
      },
    });

    if (!run) {
      throw new Error(`Run ${runId} not found`);
    }

    const [phase1, artifacts, layers, timeline] = await Promise.all([
      this.prisma.phase1Result.findUnique({
        where: { analysisRunId: runId },
        include: {
          modelVersion: true,
          detections: { orderBy: { regionNo: 'asc' } },
          metricSets: { orderBy: { context: 'asc' } },
        },
      }),
      this.prisma.artifact.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          createdAt: 'asc',
        },
      }),

      this.prisma.dashboardLayer.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          displayOrder: 'asc',
        },
      }),

      this.prisma.timelineFrame.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          frameTimeUtc: 'asc',
        },
      }),
    ]);

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

      phase1: phase1
        ? {
            modelVersion: {
              modelVersionId: phase1.modelVersion.id,
              modelName: phase1.modelVersion.modelName,
              semanticVersion: phase1.modelVersion.semanticVersion,
              stage: phase1.modelVersion.stage,
              architecture: phase1.modelVersion.architecture,
              framework: phase1.modelVersion.framework,
              inputProfile: phase1.modelVersion.inputProfile,
              preprocessingVersion: phase1.modelVersion.preprocessingVersion,
              thresholdVersion: phase1.modelVersion.thresholdVersion,
              thresholdValue: phase1.modelVersion.thresholdValue.toString(),
              evaluationSummary: phase1.modelVersion.evaluationSummary,
            },
            observationTimeUtc: phase1.observationTimeUtc.toISOString(),
            sceneMetricAvailability: phase1.sceneMetricAvailability,
            detectionCount: phase1.detectionCount,
            summary: phase1.summary,
            detections: phase1.detections.map((detection) => ({
              detectionRegionId: detection.id,
              regionNo: detection.regionNo,
              classification: detection.classification,
              areaM2: detection.areaM2 === null ? null : detection.areaM2.toString(),
              perimeterM: detection.perimeterM === null ? null : detection.perimeterM.toString(),
              orientationDeg: detection.orientationDeg === null ? null : detection.orientationDeg.toString(),
              meanLikelihood: detection.meanLikelihood === null ? null : detection.meanLikelihood.toString(),
              properties: detection.properties,
            })),
            metricSets: phase1.metricSets.map((metricSet) => ({
              phase1MetricSetId: metricSet.id,
              context: metricSet.context,
              datasetVersion: metricSet.datasetVersion,
              availability: metricSet.availability,
              sampleCount: metricSet.sampleCount,
              metrics: metricSet.metrics,
              reason: metricSet.reason,
            })),
          }
        : null,

      artifacts: artifacts.map((artifact) => ({
        artifactId: artifact.id,
        role: null,
        logicalName: artifact.logicalName,
        artifactVersion: artifact.artifactVersion,
        uri: artifact.uri,
        mediaType: artifact.mediaType,
        checksumSha256: artifact.checksumSha256,
        sizeBytes:
          artifact.sizeBytes === null
            ? null
            : artifact.sizeBytes.toString(),
        timeStartUtc:
          artifact.timeStartUtc?.toISOString() ?? null,
        timeEndUtc:
          artifact.timeEndUtc?.toISOString() ?? null,
        metadata: artifact.metadata,
        createdAt: artifact.createdAt.toISOString(),
      })),

      layers: layers.map((layer) => ({
        layerId: layer.id,
        analysisRunId: layer.analysisRunId,
        artifactId: layer.artifactId,
        layerKey: layer.layerKey,
        kind: layer.kind,
        role: layer.role,
        visibleByDefault: layer.visibleByDefault,
        displayOrder: layer.displayOrder,
        style: layer.style,
        availability: layer.availability,
      })),

      timeline: timeline.map((frame) => ({
        frameId: frame.id,
        analysisRunId: frame.analysisRunId,
        dashboardLayerId: frame.dashboardLayerId,
        artifactId: frame.artifactId,
        frameTimeUtc: frame.frameTimeUtc.toISOString(),
        relativeSeconds: frame.relativeSeconds,
        availability: frame.availability,
        metadata: frame.metadata,
      })),
    };
  }
  // =========================================
  // PHASE-3 ATTRIBUTION
  // Privacy-safe public candidate response.
  // Restricted vessel identity / MMSI is never exposed.
  // =========================================

  async getAttribution(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: {
        id: runId,
      },
    });

    if (!run) {
      throw new Error(`Run ${runId} not found`);
    }

    const candidates =
      await this.prisma.phase3Candidate.findMany({
        where: {
          analysisRunId: runId,
        },
        orderBy: {
          createdAt: 'asc',
        },
        include: {
          scores: {
            orderBy: {
              rank: 'asc',
            },
            include: {
              components: {
                orderBy: {
                  componentName: 'asc',
                },
              },
            },
          },
          features: {
            orderBy: {
              featureName: 'asc',
            },
          },
          evidenceEvents: {
            orderBy: {
              eventTimeUtc: 'asc',
            },
          },
        },
      });

    const result = candidates
      .map((candidate) => {
        const score = candidate.scores[0] ?? null;

        return {
          candidateId: candidate.id,

          candidateSetVersion:
            candidate.candidateSetVersion,

          publicMetadata: this.sanitizeAttributionMetadata(candidate.publicMetadata),

          score: score
            ? {
                scoreVersion:
                  score.scoreVersion,

                investigativeScore:
                  Number(score.investigativeScore),

                rank:
                  score.rank,

                // Prisma does not expose
                // Unsupported("evidence_confidence").
                confidence:
                  null,

                positiveTotal:
                  Number(score.positiveTotal),

                negativeTotal:
                  Number(score.negativeTotal),

                confidenceCap:
                  score.confidenceCap === null
                    ? null
                    : Number(score.confidenceCap),

                explanation:
                  score.explanation,

                components:
                  score.components.map(
                    (component) => ({
                      componentName:
                        component.componentName,

                      rawValue:
                        component.rawValue === null
                          ? null
                          : Number(component.rawValue),

                      normalizedValue:
                        component.normalizedValue === null
                          ? null
                          : Number(component.normalizedValue),

                      weight:
                        Number(component.weight),

                      contribution:
                        Number(component.contribution),

                      isDeduction:
                        component.isDeduction,

                      capApplied:
                        component.capApplied === null
                          ? null
                          : Number(component.capApplied),

                      reason:
                        component.reason,
                    }),
                  ),
              }
            : null,

          features:
            candidate.features.map(
              (feature) => ({
                featureName:
                  feature.featureName,

                featureVersion:
                  feature.featureVersion,

                rawValue:
                  feature.rawValue === null
                    ? null
                    : Number(feature.rawValue),

                normalizedValue:
                  feature.normalizedValue === null
                    ? null
                    : Number(feature.normalizedValue),

                unit:
                  feature.unit,

                availability:
                  feature.availability,

                confidenceCap:
                  feature.confidenceCap === null
                    ? null
                    : Number(feature.confidenceCap),

                reason:
                  feature.reason,

                provenance:
                  feature.provenance,
              }),
            ),

          evidence:
            candidate.evidenceEvents.map(
              (event) => ({
                evidenceEventId:
                  event.id,

                // Prisma does not expose
                // Unsupported("evidence_kind").
                kind:
                  null,

                eventCode:
                  event.eventCode,

                eventTimeUtc:
                  event.eventTimeUtc?.toISOString() ?? null,

                // Unsupported enum in Prisma.
                confidence:
                  null,

                // DB model has explanation,
                // not summary.
                summary:
                  event.explanation,

                details:
                  event.details,
              }),
            ),
        };
      })
      .sort((a, b) => {
        const rankA =
          a.score?.rank ??
          Number.MAX_SAFE_INTEGER;

        const rankB =
          b.score?.rank ??
          Number.MAX_SAFE_INTEGER;

        return rankA - rankB;
      });

    return {
      runId,
      phase: run.phase,
      status: run.status,
      dataOrigin: run.dataOrigin,

      candidates: result,

      disclaimer:
        'Candidate ranking supports investigation and does not constitute legal attribution or proof of responsibility.',
    };
  }
}







