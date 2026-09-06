import { Controller, Get } from '@nestjs/common';

@Controller('health')
export class HealthController {
  @Get()
  async getHealth() {
    const engines = {
      phase1Engine: process.env.PHASE1_ENGINE_URL
        ? await this.checkService(process.env.PHASE1_ENGINE_URL)
        : 'not_configured',

      phase2Engine: process.env.PHASE2_ENGINE_URL
        ? await this.checkService(process.env.PHASE2_ENGINE_URL)
        : 'not_configured',

      phase3Engine: process.env.PHASE3_ENGINE_URL
        ? await this.checkService(process.env.PHASE3_ENGINE_URL)
        : 'not_configured',
    };

    const hasDownEngine = Object.values(engines).some(
      (status) => status === 'down',
    );

    return {
      status: hasDownEngine ? 'degraded' : 'ok',
      services: {
        api: 'up',
        ...engines,
      },
      timestamp_utc: new Date().toISOString(),
    };
  }

  private async checkService(url: string): Promise<'up' | 'down'> {
    try {
      const response = await fetch(`${url.trimEnd()}/health`, {
        signal: AbortSignal.timeout(2000),
      });

      return response.ok ? 'up' : 'down';
    } catch {
      return 'down';
    }
  }
}
