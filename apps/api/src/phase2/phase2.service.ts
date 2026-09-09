import {
  BadRequestException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { createHash, randomUUID } from 'crypto';
import { PgBoss } from 'pg-boss';
import { Prisma } from '@prisma/client';
import path from 'path';
import { PrismaService } from '../database/prisma.service';

type Phase2Mode =
  | 'HINDCAST_AND_FORECAST'
  | 'HINDCAST'
  | 'FORECAST';

interface Phase2Job {
  runId: string;
  caseId: string;
  phase1RunId: string;
  correlationId: string;
  mode: Phase2Mode;
}

interface Phase2EngineResponse {
  status: 'COMPLETED' | 'COMPLETED_WITH_WARNINGS';
  contract_version: string;
  phase2_run_id: string;
  case_id: string;
  data_origin: string;
  forcing: Record<string, unknown>;
  seeding: Record<string, unknown>;
  hindcast: Record<string, unknown>;
  reconstruction: Record<string, unknown>;
  forecast: Record<string, unknown>;
  trajectories: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  warnings: string[];
}

@Injectable()
export class Phase2Service {
  private readonly logger = new Logger(Phase2Service.name);
  private boss: PgBoss | null = null;

  constructor(private readonly prisma: PrismaService) {}

  async onModuleInit() {
    const connectionString = process.env.DATABASE_URL;

    if (!connectionString) {
      this.logger.warn(
        'DATABASE_URL is missing. Phase-2 queue disabled.',
      );
      return;
    }

    try {
      this.boss = new PgBoss(connectionString);

      await this.boss.start();

      await this.boss.createQueue('phase2.hindcast');

      await this.boss.work<Phase2Job>(
        'phase2.hindcast',
        async (jobs) => {
          const job = jobs[0];

          if (!job) {
            return;
          }

          await this.execute(job.data);
        },
      );

      this.logger.log(
        'Phase-2 pg-boss queue initialized.',
      );
    } catch (_error) {
      this.logger.warn(
        'Phase-2 queue unavailable; Phase-2 creation disabled for this session.',
      );

      this.boss = null;
    }
  }

  async onModuleDestroy() {
    if (this.boss) {
      await this.boss.stop();
      this.boss = null;
    }
  }

  async createRun(input: {
    caseId: string;
    phase1RunId: string;
    mode: Phase2Mode;
  }) {
    if (!input.caseId || !input.phase1RunId) {
      throw new BadRequestException({
        error: {
          code: 'INVALID_PHASE2_REQUEST',
          message:
            'caseId and phase1RunId are required.',
          retryable: false,
        },
      });
    }

    if (!this.boss) {
      throw new BadRequestException({
        error: {
          code: 'JOB_QUEUE_UNAVAILABLE',
          message:
            'Phase-2 job queue is unavailable.',
          retryable: true,
        },
      });
    }

    const phase1 =
      await this.prisma.analysisRun.findUnique({
        where: {
          id: input.phase1RunId,
        },
      });

    if (!phase1) {
      throw new NotFoundException({
        error: {
          code: 'PHASE1_RUN_NOT_FOUND',
          message:
            'The supplied Phase-1 run does not exist.',
          retryable: false,
        },
      });
    }

    if (phase1.caseId !== input.caseId) {
      throw new BadRequestException({
        error: {
          code: 'PHASE1_CASE_MISMATCH',
          message:
            'Phase-1 run does not belong to the requested case.',
          retryable: false,
        },
      });
    }

    if (phase1.phase !== 'PHASE1') {
      throw new BadRequestException({
        error: {
          code: 'INVALID_PHASE1_RUN',
          message:
            'The supplied run is not a Phase-1 run.',
          retryable: false,
        },
      });
    }

    if (phase1.status !== 'COMPLETED') {
      throw new BadRequestException({
        error: {
          code: 'PHASE1_RESULT_NOT_READY',
          message:
            'Phase 2 requires a completed Phase 1 result.',
          retryable: false,
        },
      });
    }

    const phase1Result =
      await this.prisma.phase1Result.findUnique({
        where: {
          analysisRunId: input.phase1RunId,
        },
      });

    if (!phase1Result) {
      throw new BadRequestException({
        error: {
          code: 'PHASE1_RESULT_MISSING',
          message:
            'Phase-1 run is completed but its result is unavailable.',
          retryable: false,
        },
      });
    }

    const snapshot = {
      phase1RunId: input.phase1RunId,
      mode: input.mode,
      contractVersion:
        'phase1-to-phase2-v1',
    };

    const configHash = createHash('sha256')
      .update(JSON.stringify(snapshot))
      .digest('hex');

    const idempotencyKey =
      `phase2-${input.caseId}-${input.phase1RunId}-${input.mode}`;

    const existing =
      await this.prisma.analysisRun.findFirst({
        where: {
          idempotencyKey,
          phase: 'PHASE2',
        },
      });

    if (existing) {
      return {
        runId: existing.id,
        caseId: existing.caseId,
        phase: existing.phase,
        status: existing.status,
        progress:
          existing.status === 'COMPLETED' ||
          existing.status === 'COMPLETED_WITH_WARNINGS'
            ? 100
            : 0,
      };
    }

    const runId = randomUUID();
    const correlationId = randomUUID();

    await this.prisma.analysisRun.create({
      data: {
        id: runId,
        caseId: input.caseId,
        sceneId: phase1.sceneId,
        phase: 'PHASE2',
        status: 'QUEUED',
        dataOrigin: phase1.dataOrigin,
        idempotencyKey,
        inputContractVersion:
          'phase1-to-phase2-v1',
        outputContractVersion:
          'phase2-to-phase3-v1',
        configHash,
        codeVersion:
          'VARUN-PHASE2-BACKEND-V2',
        requestedBy: 'AKHILESH',
        inputSnapshot:
          snapshot as Prisma.InputJsonValue,
        provenance:
          {
            source: 'phase1',
            phase1RunId:
              input.phase1RunId,
            contractVersion:
              'phase1-to-phase2-v1',
          } as Prisma.InputJsonValue,
      },
    });

    await this.prisma.runEvent.create({
      data: {
        analysisRunId: runId,
        status: 'QUEUED',
        stage: 'PHASE2_QUEUED',
        progressPercent: 0,
        safeMessage:
          'Phase-2 drift run queued.',
        correlationId,
        details: {
          phase1RunId:
            input.phase1RunId,
          mode: input.mode,
        },
      },
    });

    const jobExecutionId = randomUUID();

    await this.prisma.jobExecution.create({
      data: {
        id: jobExecutionId,
        analysisRunId: runId,
        queueName:
          'phase2.hindcast',
        idempotencyKey:
          `phase2-job-${runId}`,
        attemptNo: 1,
        status: 'QUEUED',
        correlationId,
      },
    });

    const bossJobId =
      await this.boss.send(
        'phase2.hindcast',
        {
          runId,
          caseId: input.caseId,
          phase1RunId:
            input.phase1RunId,
          correlationId,
          mode: input.mode,
        },
      );

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

    return {
      runId,
      caseId: input.caseId,
      phase: 'PHASE2',
      status: 'QUEUED',
      progress: 0,
    };
  }

  private async execute(
    job: Phase2Job,
  ) {
    const startedAt = new Date();

    await this.prisma.analysisRun.update({
      where: {
        id: job.runId,
      },
      data: {
        status: 'PROCESSING',
        startedAt,
      },
    });

    await this.prisma.jobExecution.updateMany({
      where: {
        analysisRunId: job.runId,
        status: 'QUEUED',
      },
      data: {
        status: 'RUNNING',
        startedAt,
      },
    });

    await this.prisma.runEvent.create({
      data: {
        analysisRunId: job.runId,
        status: 'PROCESSING',
        stage: 'PHASE2_RUNNING',
        progressPercent: 25,
        safeMessage:
          'Phase-2 drift processing started.',
        correlationId:
          job.correlationId,
        details: {
          phase1RunId:
            job.phase1RunId,
          mode: job.mode,
        },
      },
    });

    try {
      const engineUrl =
        process.env.PHASE2_ENGINE_URL ??
        'http://127.0.0.1:8102';

      const response =
        await fetch(
          `${engineUrl.replace(/\/$/, '')}/internal/v1/drift-runs`,
          {
            method: 'POST',
            headers: {
              'content-type':
                'application/json',
            },
            body: JSON.stringify({
              case_id: job.caseId,
              phase2_run_id:
                job.runId,
              phase1_handoff_ref:
                job.phase1RunId,
              mode: job.mode,
            }),
          },
        );

      const text =
        await response.text();

      if (!response.ok) {
        throw new Error(
          `PHASE2_ENGINE_HTTP_${response.status}`,
        );
      }

      let result: Phase2EngineResponse;

      try {
        result =
          JSON.parse(text) as Phase2EngineResponse;
      } catch {
        throw new Error(
          'PHASE2_ENGINE_INVALID_JSON',
        );
      }

      if (
        !result ||
        ![
          'COMPLETED',
          'COMPLETED_WITH_WARNINGS',
        ].includes(result.status)
      ) {
        throw new Error(
          'PHASE2_ENGINE_INVALID_RESPONSE',
        );
      }

      if (
        result.phase2_run_id !==
        job.runId
      ) {
        throw new Error(
          'PHASE2_RUN_ID_MISMATCH',
        );
      }

      if (
        result.case_id !==
        job.caseId
      ) {
        throw new Error(
          'PHASE2_CASE_ID_MISMATCH',
        );
      }

      await this.prisma.runEvent.create({
        data: {
          analysisRunId:
            job.runId,
          status: 'PROCESSING',
          stage:
            'PHASE2_ENGINE_ACCEPTED',
          progressPercent: 60,
          safeMessage:
            'Phase-2 drift engine completed processing.',
          correlationId:
            job.correlationId,
          details: {
            trajectoryCount:
              result.trajectories.length,
            warningCount:
              result.warnings.length,
            contractVersion:
              result.contract_version,
          },
        },
      });

      /*
       * Persist the complete engine response in provenance first.
       * This preserves the exact scientific handoff even when some
       * specialised relational fields are unavailable.
       */
      const existingRun =
        await this.prisma.analysisRun.findUnique({
          where: {
            id: job.runId,
          },
        });

      const previousProvenance =
        existingRun?.provenance &&
        typeof existingRun.provenance === 'object' &&
        !Array.isArray(existingRun.provenance)
          ? existingRun.provenance
          : {};

      const provenance = {
        ...(previousProvenance as Record<
          string,
          unknown
        >),
        source:
          'phase2-drift-engine',
        engine:
          result.provenance,
        forcing:
          result.forcing,
        seeding:
          result.seeding,
        hindcast:
          result.hindcast,
        reconstruction:
          result.reconstruction,
        forecast:
          result.forecast,
        trajectories:
          result.trajectories,
        artifacts:
          result.artifacts,
        warnings:
          result.warnings,
        contractVersion:
          result.contract_version,
        dataOrigin:
          result.data_origin,
      };

      await this.prisma.analysisRun.update({
        where: {
          id: job.runId,
        },
        data: {
          provenance:
            provenance as Prisma.InputJsonValue,
        },
      });

      /*
       * Persist engine artifacts when the engine has materialised
       * files locally. We only accept simple logical names and never
       * allow arbitrary absolute paths from the engine response.
       */
      const root =
        path.resolve(process.cwd());

      const artifactRoot =
        path.resolve(
          root,
          'artifacts',
        );

      for (
        const artifact
        of result.artifacts ?? []
      ) {
        const logicalName =
          typeof artifact.logicalName ===
          'string'
            ? artifact.logicalName
            : null;

        if (
          !logicalName ||
          !/^[A-Za-z0-9._-]+$/.test(
            logicalName,
          )
        ) {
          continue;
        }

        const candidatePath =
          path.resolve(
            artifactRoot,
            logicalName,
          );

        if (
          candidatePath !==
            artifactRoot &&
          !candidatePath.startsWith(
            `${artifactRoot}${path.sep}`,
          )
        ) {
          continue;
        }

        let stat:
          import('fs').Stats | null =
          null;

        try {
          stat =
            await (
              await import('fs/promises')
            ).stat(candidatePath);
        } catch {
          stat = null;
        }

        await this.prisma.$executeRawUnsafe(
          `INSERT INTO artifacts
            (
              artifact_id,
              analysis_run_id,
              role,
              logical_name,
              artifact_version,
              uri,
              media_type,
              checksum_sha256,
              size_bytes,
              metadata
            )
           VALUES
            (
              gen_random_uuid(),
              $1::uuid,
              'SCIENTIFIC'::artifact_role,
              $2,
              '1.0.0',
              $3,
              $4,
              $5,
              $6,
              $7::jsonb
            )
           ON CONFLICT
            (
              analysis_run_id,
              logical_name,
              artifact_version
            )
           DO UPDATE SET
              uri =
                EXCLUDED.uri,
              media_type =
                EXCLUDED.media_type,
              checksum_sha256 =
                EXCLUDED.checksum_sha256,
              size_bytes =
                EXCLUDED.size_bytes,
              metadata =
                EXCLUDED.metadata`,
          job.runId,
          logicalName,
          `artifacts/${logicalName}`,
          typeof artifact.mediaType ===
            'string'
            ? artifact.mediaType
            : 'application/octet-stream',
          typeof artifact.checksumSha256 ===
            'string'
            ? artifact.checksumSha256
            : createHash('sha256')
                .update(
                  JSON.stringify(
                    artifact,
                  ),
                )
                .digest('hex'),
          stat?.size ?? null,
          JSON.stringify({
            phase:
              'PHASE2',
            source:
              'services/drift-engine',
            materialized:
              Boolean(stat),
          }),
        );
      }

      await this.prisma.analysisRun.update({
        where: {
          id: job.runId,
        },
        data: {
          status:
            result.status ===
            'COMPLETED_WITH_WARNINGS'
              ? 'COMPLETED_WITH_WARNINGS'
              : 'COMPLETED',
          finishedAt:
            new Date(),
        },
      });

      await this.prisma.jobExecution.updateMany({
        where: {
          analysisRunId: job.runId,
        },
        data: {
          status: 'COMPLETED',
          completedAt:
            new Date(),
        },
      });

      await this.prisma.runEvent.create({
        data: {
          analysisRunId:
            job.runId,
          status:
            result.status ===
            'COMPLETED_WITH_WARNINGS'
              ? 'COMPLETED_WITH_WARNINGS'
              : 'COMPLETED',
          stage:
            'PHASE2_COMPLETED',
          progressPercent: 100,
          safeMessage:
            result.status ===
            'COMPLETED_WITH_WARNINGS'
              ? 'Phase-2 completed with warnings.'
              : 'Phase-2 drift processing completed.',
          correlationId:
            job.correlationId,
          details: {
            trajectoryCount:
              result.trajectories.length,
            warnings:
              result.warnings,
            contractVersion:
              result.contract_version,
          },
        },
      });

      for (
        const warning of
        result.warnings ?? []
      ) {
        await this.prisma.runWarning.create({
          data: {
            analysisRunId:
              job.runId,
            code:
              'PHASE2_ENGINE_WARNING',
            severity:
              'WARNING',
            message:
              warning,
            stage:
              'PHASE2',
            details: {},
          },
        });
      }

      this.logger.log(
        `Phase-2 run ${job.runId} completed.`,
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : String(error);

      await this.prisma.analysisRun.update({
        where: {
          id: job.runId,
        },
        data: {
          status: 'FAILED',
          finishedAt:
            new Date(),
          provenance:
            {
              source:
                'phase2-drift-engine',
              error: {
                code:
                  'PHASE2_ENGINE_FAILED',
                message:
                  message.startsWith(
                    'PHASE2_',
                  )
                    ? message
                    : 'PHASE2_ENGINE_FAILED',
                retryable: false,
              },
            } as Prisma.InputJsonValue,
        },
      });

      await this.prisma.jobExecution.updateMany({
        where: {
          analysisRunId: job.runId,
        },
        data: {
          status: 'FAILED',
          completedAt:
            new Date(),
          safeError:
            {
              code:
                'PHASE2_ENGINE_FAILED',
              message:
                'Phase-2 processing failed.',
            } as Prisma.InputJsonValue,
        },
      });

      await this.prisma.runEvent.create({
        data: {
          analysisRunId:
            job.runId,
          status: 'FAILED',
          stage:
            'PHASE2_FAILED',
          progressPercent: 100,
          safeMessage:
            'Phase-2 processing failed.',
          errorCode:
            'PHASE2_ENGINE_FAILED',
          retryable: false,
          correlationId:
            job.correlationId,
          details: {
            reason:
              message.startsWith(
                'PHASE2_',
              )
                ? message
                : 'PHASE2_ENGINE_FAILED',
          },
        },
      });

      this.logger.error(
        `Phase-2 run ${job.runId} failed: ${message}`,
      );
    }
  }
  async getRun(caseId: string, runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
    });

    if (!run || run.caseId !== caseId || run.phase !== 'PHASE2') {
      throw new NotFoundException({
        error: {
          code: 'PHASE2_RUN_NOT_FOUND',
          message: 'Phase-2 run not found for this case.',
          retryable: false,
        },
      });
    }

    const latestEvent = await this.prisma.runEvent.findFirst({
      where: { analysisRunId: runId },
      orderBy: { occurredAt: 'desc' },
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
      progressPercentage: Number(
        latestEvent?.progressPercent ??
          (run.status === 'COMPLETED' ||
          run.status === 'COMPLETED_WITH_WARNINGS'
            ? 100
            : 0),
      ),
      inputContractVersion: run.inputContractVersion,
      outputContractVersion: run.outputContractVersion,
      codeVersion: run.codeVersion,
      configHash: run.configHash,
      provenance: run.provenance,
    };
  }

  async getStatus(caseId: string, runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
    });

    if (!run || run.caseId !== caseId || run.phase !== 'PHASE2') {
      throw new NotFoundException({
        error: {
          code: 'PHASE2_RUN_NOT_FOUND',
          message: 'Phase-2 run not found for this case.',
          retryable: false,
        },
      });
    }

    const latestEvent = await this.prisma.runEvent.findFirst({
      where: { analysisRunId: runId },
      orderBy: { occurredAt: 'desc' },
    });

    const provenance: any = run.provenance ?? {};
    const failure = provenance.error ?? null;

    return {
      runId: run.id,
      caseId: run.caseId,
      phase: 'PHASE2',
      status: run.status,
      progressPercentage: Number(
        latestEvent?.progressPercent ??
          (run.status === 'COMPLETED' ||
          run.status === 'COMPLETED_WITH_WARNINGS'
            ? 100
            : 0),
      ),
      message:
        latestEvent?.safeMessage ??
        (run.status === 'QUEUED'
          ? 'Phase-2 drift run queued.'
          : run.status === 'PROCESSING'
            ? 'Phase-2 drift processing.'
            : run.status === 'COMPLETED_WITH_WARNINGS'
              ? 'Phase-2 completed with warnings.'
              : run.status === 'COMPLETED'
                ? 'Phase-2 drift processing completed.'
                : 'Phase-2 drift processing failed.'),
      error: failure
        ? {
            code: failure.code ?? 'PHASE2_ENGINE_FAILED',
            userMessage:
              failure.userMessage ??
              'Phase-2 processing failed.',
            retryable: Boolean(failure.retryable),
          }
        : null,
    };
  }

  async getResult(caseId: string, runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
    });

    if (!run || run.caseId !== caseId || run.phase !== 'PHASE2') {
      throw new NotFoundException({
        error: {
          code: 'PHASE2_RUN_NOT_FOUND',
          message: 'Phase-2 run not found for this case.',
          retryable: false,
        },
      });
    }

    if (
      run.status !== 'COMPLETED' &&
      run.status !== 'COMPLETED_WITH_WARNINGS'
    ) {
      throw new BadRequestException({
        error: {
          code: 'PHASE2_RESULT_NOT_READY',
          message: 'Phase-2 result is not ready.',
          retryable: true,
        },
      });
    }

    const provenance: any = run.provenance ?? {};

    const trajectories = Array.isArray(provenance.trajectories)
      ? provenance.trajectories
      : [];

    const artifacts = Array.isArray(provenance.artifacts)
      ? provenance.artifacts
      : [];

    return {
      runId: run.id,
      caseId: run.caseId,
      phase: 'PHASE2',
      status: run.status,
      dataOrigin: run.dataOrigin,

      forcing: provenance.forcing ?? null,
      seeding: provenance.seeding ?? null,
      hindcast: provenance.hindcast ?? null,
      reconstruction: provenance.reconstruction ?? null,
      forecast: provenance.forecast ?? null,

      trajectories,

      artifacts,

      provenance: provenance.engine ?? provenance,

      warnings: Array.isArray(provenance.warnings)
        ? provenance.warnings
        : [],

      contractVersion:
        provenance.contractVersion ??
        run.outputContractVersion ??
        'phase2-to-phase3-v1',

      disclaimer:
        'Phase-2 trajectories and forecasts support investigation and downstream analysis. Deterministic integration fixtures must not be interpreted as scientific forecast truth.',
    };
  }





}
