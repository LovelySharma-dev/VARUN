import { Module } from '@nestjs/common';
import { ArtifactsController } from './artifacts.controller';
import { ArtifactsService } from './artifacts.service';

@Module({
  controllers: [ArtifactsController],
  providers: [ArtifactsService],
})
export class ArtifactsModule {}
