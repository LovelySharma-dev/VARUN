import {
  Controller,
  Get,
  Param,
  Post,
} from '@nestjs/common';
import { RunsService } from './runs.service';

@Controller()
export class RunsController {
  constructor(private readonly runsService: RunsService) {}

  @Post('test-runs')
  createTestRun() {
    return this.runsService.createTestRun();
  }

  @Get('runs/:runId')
  getRun(@Param('runId') runId: string) {
    return this.runsService.getRun(runId);
  }

  @Get('runs/:runId/events')
  getRunEvents(@Param('runId') runId: string) {
    return this.runsService.getRunEvents(runId);
  }

  @Get('runs/:runId/dashboard')
  getDashboard(@Param('runId') runId: string) {
    return this.runsService.getDashboard(runId);
  }
}
