import { Injectable } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { ScenesResponseSchema, SceneSchema } from '../contracts/schemas';
import { validateResponse } from '../contracts/validate';

@Injectable()
export class ScenesService {
  constructor(private readonly prisma: PrismaService) {}

  async getScenes() {
    const scenes = await this.prisma.scene.findMany({
      orderBy: {
        acquisitionTimeUtc: 'desc',
      },
    });

    const response = {
      scenes: scenes.map((scene) => ({
        sceneId: scene.id,
        caseId: scene.caseId,
        externalSceneId: scene.externalSceneId,
        sensor: scene.sensor,
        acquisitionTimeUtc: scene.acquisitionTimeUtc.toISOString(),
        crs: scene.crs,
        dataOrigin: scene.dataOrigin,
        metadata: scene.metadata,
      })),
    };

    return validateResponse(ScenesResponseSchema, response);
  }

  async getScene(sceneId: string) {
    const scene = await this.prisma.scene.findUnique({
      where: {
        id: sceneId,
      },
    });

    if (!scene) {
      return null;
    }

    const response = {
      sceneId: scene.id,
      caseId: scene.caseId,
      externalSceneId: scene.externalSceneId,
      sensor: scene.sensor,
      acquisitionTimeUtc: scene.acquisitionTimeUtc.toISOString(),
      crs: scene.crs,
      dataOrigin: scene.dataOrigin,
      metadata: scene.metadata,
    };

    return validateResponse(SceneSchema, response);
  }
}
