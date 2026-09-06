import { Module } from '@nestjs/common';
import { Phase3Controller } from './phase3.controller';
import { Phase3Service } from './phase3.service';
import { Phase3EngineClient } from './phase3-engine.client';

@Module({
  controllers: [Phase3Controller],
  providers: [Phase3Service, Phase3EngineClient],
  exports: [Phase3Service, Phase3EngineClient],
})
export class Phase3Module {}
