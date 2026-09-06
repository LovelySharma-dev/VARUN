import { Body, Controller, Get, Param, Post } from '@nestjs/common';
import { Phase3Service } from './phase3.service';
import type { Phase3RunInput } from './phase3.service';

@Controller()
export class Phase3Controller {
  constructor(private readonly phase3Service: Phase3Service) {}

  @Post('cases/:caseId/phase-run')
  createRun(
    @Param('caseId') caseId: string,
    @Body() body: Phase3RunInput,
  ) {
    return this.phase3Service.createRun(caseId, body);
  }

  @Get('cases/:caseId/attribution')
  getAttributionByCase(@Param('caseId') caseId: string) {
    return this.phase3Service.getAttributionByCase(caseId);
  }

  @Get('cases/:caseId/dashboard')
  getCaseDashboard(@Param('caseId') caseId: string) {
    return this.phase3Service.getCaseDashboard(caseId);
  }

  @Get('runs/:runId/status')
  getStatus(@Param('runId') runId: string) {
    return this.phase3Service.getStatus(runId);
  }

  @Get('runs/:runId/attribution')
  getAttribution(@Param('runId') runId: string) {
    return this.phase3Service.getAttribution(runId);
  }

  @Get('runs/:runId/phase3/candidates')
  getCandidates(@Param('runId') runId: string) {
    return this.phase3Service.getCandidates(runId);
  }

  @Get('runs/:runId/phase3/candidates/:candidateId')
  getCandidate(
    @Param('runId') runId: string,
    @Param('candidateId') candidateId: string,
  ) {
    return this.phase3Service.getCandidate(runId, candidateId);
  }
}

