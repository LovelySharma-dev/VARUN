import { Module } from '@nestjs/common';
import { Phase2Controller } from './phase2.controller';
import { Phase2Service } from './phase2.service';

@Module({
  controllers: [Phase2Controller],
  providers: [Phase2Service],
  exports: [Phase2Service],
})
export class Phase2Module {}
