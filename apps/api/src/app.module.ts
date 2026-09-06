import { Phase3Module } from './phase3/phase3.module';
import { Phase2Module } from './phase2/phase2.module';
import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { HealthController } from './health.controller';
import { DatabaseModule } from './database/database.module';
import { RunsModule } from './runs/runs.module';
import { CasesModule } from './cases/cases.module';
import { ScenesModule } from './scenes/scenes.module';
import { ArtifactsModule } from './artifacts/artifacts.module';

@Module({
  imports: [
    Phase3Module,
    Phase2Module,
    DatabaseModule,
    RunsModule,
    CasesModule,
    ScenesModule,
    ArtifactsModule,
  ],
  controllers: [AppController, HealthController],
  providers: [AppService],
})
export class AppModule {}


