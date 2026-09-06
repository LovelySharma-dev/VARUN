import { Injectable } from '@nestjs/common';

export interface Phase1EngineDetection {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  label: string;
}

export interface Phase1EngineResult {
  status: string;
  tile_count: number;
  detection_count: number;
  detections: Phase1EngineDetection[];
  tiles: Array<{
    x: number;
    y: number;
    width: number;
    height: number;
  }>;
  model_version?: string | null;
}

@Injectable()
export class Phase1EngineClient {
  private readonly baseUrl =
    process.env.DETECTION_ENGINE_URL ??
    'http://127.0.0.1:8000';

  async infer(input: {
    imagePath: string;
    imageWidth: number;
    imageHeight: number;
    tileSize?: number;
    overlap?: number;
    confidenceThreshold?: number;
    iouThreshold?: number;
  }): Promise<Phase1EngineResult> {
    const response = await fetch(
      `${this.baseUrl}/v1/inference`,
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          image_path: input.imagePath,
          image_width: input.imageWidth,
          image_height: input.imageHeight,
          tile_size: input.tileSize ?? 512,
          overlap: input.overlap ?? 64,
          confidence_threshold:
            input.confidenceThreshold ?? 0.5,
          iou_threshold:
            input.iouThreshold ?? 0.5,
        }),
      },
    );

    const text = await response.text();

    if (!response.ok) {
      throw new Error(
        `DETECTION_ENGINE_${response.status}: ${text}`,
      );
    }

    return JSON.parse(text) as Phase1EngineResult;
  }
}
