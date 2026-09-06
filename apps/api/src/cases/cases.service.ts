import { Injectable } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { CasesResponseSchema, CaseSchema } from '../contracts/schemas';
import { validateResponse } from '../contracts/validate';

@Injectable()
export class CasesService {
  constructor(private readonly prisma: PrismaService) {}

  async getCases() {
    const cases = await this.prisma.case.findMany({
      orderBy: {
        createdAt: 'desc',
      },
    });

    const response = {
      cases: cases.map((item) => ({
        caseId: item.id,
        status: item.status,
        dataOrigin: item.dataOrigin,
        createdAt: item.createdAt.toISOString(),
        updatedAt: item.updatedAt.toISOString(),
        metadata: item.metadata,
      })),
    };

    return validateResponse(CasesResponseSchema, response);
  }

  async getCase(caseId: string) {
    const item = await this.prisma.case.findUnique({
      where: {
        id: caseId,
      },
      include: {
        scenes: true,
      },
    });

    if (!item) {
      return null;
    }

    const response = {
      caseId: item.id,
      status: item.status,
      dataOrigin: item.dataOrigin,
      createdAt: item.createdAt.toISOString(),
      updatedAt: item.updatedAt.toISOString(),
      metadata: item.metadata,
      scenes: item.scenes.map((scene) => ({
        sceneId: scene.id,
        externalSceneId: scene.externalSceneId,
        sensor: scene.sensor,
        acquisitionTimeUtc: scene.acquisitionTimeUtc.toISOString(),
        crs: scene.crs,
        dataOrigin: scene.dataOrigin,
        metadata: scene.metadata,
      })),
    };

    return response;
  }
}
