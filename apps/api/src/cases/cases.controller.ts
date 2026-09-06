import { Controller, Get, Param, NotFoundException } from '@nestjs/common';
import { CasesService } from './cases.service';

@Controller('cases')
export class CasesController {
  constructor(private readonly casesService: CasesService) {}

  @Get()
  getCases() {
    return this.casesService.getCases();
  }

  @Get(':caseId')
  async getCase(@Param('caseId') caseId: string) {
    const result = await this.casesService.getCase(caseId);

    if (!result) {
      throw new NotFoundException({
        error: {
          code: 'CASE_NOT_FOUND',
          message: 'Case not found.',
          retryable: false,
        },
      });
    }

    return result;
  }
}
