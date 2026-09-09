import { Injectable, NotFoundException } from '@nestjs/common';
import { promises as fs } from 'fs';
import path from 'path';
import { PrismaService } from '../database/prisma.service';

@Injectable()
export class ArtifactsService {
  constructor(private readonly prisma: PrismaService) {}

  async getRunArtifacts(runId: string) {
    const run = await this.prisma.analysisRun.findUnique({
      where: { id: runId },
      select: { id: true },
    });
    if (!run) return null;

    const artifacts = await this.prisma.artifact.findMany({
      where: { analysisRunId: runId },
      orderBy: { createdAt: 'asc' },
    });

    return {
      runId,
      artifacts: artifacts.map((artifact) => ({
        artifactId: artifact.id,
        logicalName: artifact.logicalName,
        artifactVersion: artifact.artifactVersion,
        uri: artifact.uri,
        mediaType: artifact.mediaType,
        checksumSha256: artifact.checksumSha256,
        sizeBytes: artifact.sizeBytes?.toString() ?? null,
        timeStartUtc: artifact.timeStartUtc?.toISOString() ?? null,
        timeEndUtc: artifact.timeEndUtc?.toISOString() ?? null,
        metadata: artifact.metadata,
        createdAt: artifact.createdAt.toISOString(),
      })),
    };
  }

  private repositoryRoot() {
    return path.resolve(process.cwd());
  }

  private allowedRoots() {
    const root = this.repositoryRoot();
    return [
      path.resolve(root, 'artifacts'),
      path.resolve(root, 'data'),
    ];
  }

  private safePath(uri: string) {
    const raw = uri.replace(/^file:\/\//, '');
    const resolved = path.resolve(this.repositoryRoot(), raw);
    const allowed = this.allowedRoots().some(
      (base) => resolved === base || resolved.startsWith(`${base}${path.sep}`),
    );
    if (!allowed) {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }
    return resolved;
  }

  private mediaType(logicalName: string, fallback: string) {
    const lower = logicalName.toLowerCase();
    if (lower.endsWith('.geojson')) return 'application/geo+json';
    if (lower.endsWith('.json')) return 'application/json';
    if (lower.endsWith('.csv')) return 'text/csv';
    return ['application/geo+json', 'application/json', 'text/csv'].includes(fallback)
      ? fallback
      : 'application/octet-stream';
  }

  async resolveArtifact(artifactId: string) {
    const artifact = await this.prisma.artifact.findUnique({
      where: { id: artifactId },
    });
    if (!artifact) {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }

    const filename = artifact.logicalName;
    if (filename.includes('..') || path.isAbsolute(filename)) {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }

    const fullPath = this.safePath(artifact.uri);
    try {
      const bytes = await fs.readFile(fullPath);
      return {
        bytes,
        mediaType: this.mediaType(filename, artifact.mediaType),
      };
    } catch {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }
  }

  async resolveLatestPhase3Artifact(logicalName: string) {
    if (
      !logicalName ||
      logicalName.includes('..') ||
      path.isAbsolute(logicalName) ||
      !/^[A-Za-z0-9._-]+$/.test(logicalName)
    ) {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }

    const artifact = await this.prisma.artifact.findFirst({
      where: {
        logicalName,
        analysisRun: { phase: 'PHASE3' },
      },
      orderBy: { createdAt: 'desc' },
    });

    if (!artifact) {
      throw new NotFoundException({
        error: {
          code: 'ARTIFACT_NOT_FOUND',
          message: 'Artifact is not available.',
          retryable: false,
        },
      });
    }

    return this.resolveArtifact(artifact.id);
  }
}
