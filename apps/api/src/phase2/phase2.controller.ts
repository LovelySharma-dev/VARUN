import {
  Body,
  Controller,
  Get,
  Param,
  Post,
} from '@nestjs/common';

import { Phase2Service } from './phase2.service';

@Controller('cases/:caseId/phase2')
export class Phase2Controller {
  constructor(
    private readonly phase2: Phase2Service,
  ) {}

  @Post('runs')
  createRun(
    @Param('caseId') caseId: string,
    @Body()
    body: {
      phase1RunId: string;
      mode?:
        | 'HINDCAST_AND_FORECAST'
        | 'HINDCAST'
        | 'FORECAST';
    },
  ) {
    return this.phase2.createRun({
      caseId,
      phase1RunId:
        body?.phase1RunId,
      mode:
        body?.mode ??
        'HINDCAST_AND_FORECAST',
    });
  }

  @Get('runs/:runId')
  getRun(
    @Param('caseId') caseId: string,
    @Param('runId') runId: string,
  ) {
    return this.phase2.getRun(
      caseId,
      runId,
    );
  }

  @Get('runs/:runId/status')
  getStatus(
    @Param('caseId') caseId: string,
    @Param('runId') runId: string,
  ) {
    return this.phase2.getStatus(
      caseId,
      runId,
    );
  }

  @Get('runs/:runId/result')
  getResult(
    @Param('caseId') caseId: string,
    @Param('runId') runId: string,
  ) {
    return this.phase2.getResult(
      caseId,
      runId,
    );
  }
}
