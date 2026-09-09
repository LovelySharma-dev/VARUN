import { Controller, Get, Param, NotFoundException } from '@nestjs/common';
import { ScenesService } from './scenes.service';

@Controller('scenes')
export class ScenesController {
  constructor(private readonly scenesService: ScenesService) {}

  @Get()
  getScenes() {
    return this.scenesService.getScenes();
  }

  @Get(':sceneId')
  async getScene(@Param('sceneId') sceneId: string) {
    const scene = await this.scenesService.getScene(sceneId);

    if (!scene) {
      throw new NotFoundException({
        error: {
          code: 'SCENE_NOT_FOUND',
          message: 'Scene not found.',
          retryable: false,
        },
      });
    }

    return scene;
  }
}
