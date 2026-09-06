import {
  Controller,
  Get,
  NotFoundException,
  Param,
  Res,
} from '@nestjs/common';
import type { Response } from 'express';
import { ArtifactsService } from './artifacts.service';

@Controller()
export class ArtifactsController {
  constructor(private readonly artifactsService: ArtifactsService) {}

  @Get('runs/:runId/artifacts')
  async getRunArtifacts(@Param('runId') runId: string) {
    const result = await this.artifactsService.getRunArtifacts(runId);

    if (!result) {
      throw new NotFoundException({
        error: {
          code: 'RUN_NOT_FOUND',
          message: 'Analysis run not found.',
          retryable: false,
        },
      });
    }

    return result;
  }

  @Get('artifacts/by-run/:logicalName')
  async serveLatestRunArtifact(
    @Param('logicalName') logicalName: string,
    @Res() response: Response,
  ) {
    const file = await this.artifactsService.resolveLatestPhase3Artifact(logicalName);
    response.setHeader('Content-Type', file.mediaType);
    response.setHeader('Cache-Control', 'no-store');
    response.send(file.bytes);
  }

  @Get('artifacts/:artifactId')
  async serveArtifact(
    @Param('artifactId') artifactId: string,
    @Res() response: Response,
  ) {
    const file = await this.artifactsService.resolveArtifact(artifactId);
    response.setHeader('Content-Type', file.mediaType);
    response.setHeader('Cache-Control', 'no-store');
    response.send(file.bytes);
  }
}
