import { Module } from '@nestjs/common';
import { RunsController } from './runs.controller';
import { RunsService } from './runs.service';
import { Phase1EngineClient } from './phase1-engine.client';

@Module({
  controllers: [RunsController],
  providers: [
    RunsService,
    Phase1EngineClient,
  ],
})
export class RunsModule {}
