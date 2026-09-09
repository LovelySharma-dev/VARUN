import { Injectable } from '@nestjs/common';

@Injectable()
export class Phase3EngineClient {
  async run(payload: unknown) {
    const engineUrl =
      process.env.PHASE3_ENGINE_URL ??
      'http://127.0.0.1:8103';

    const response = await fetch(
      `${engineUrl}/v1/phase3/run`,
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
        },
        body: JSON.stringify(payload),
      },
    );

    if (!response.ok) {
      throw new Error(
        `PHASE3_ENGINE_HTTP_${response.status}`,
      );
    }

    return response.json();
  }
}