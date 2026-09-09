from dataclasses import replace
from typing import Any

from app.preprocessing import preprocess_image
from app.inference.tiling import create_tiles
from app.predictor.unet_predictor import UNetPredictor


def run_inference(
    image: Any,
    image_width: int,
    image_height: int,
    model_path: str,
    tile_size: int = 512,
    overlap: int = 64,
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.5,
) -> dict:

    prepared = preprocess_image(image)

    tiles = create_tiles(
        image_width=image_width,
        image_height=image_height,
        tile_size=tile_size,
        overlap=overlap,
    )

    predictor = UNetPredictor(
        model_path=model_path,
        threshold=confidence_threshold,
    )

    all_detections = []

    for tile in tiles:
        tile_image = prepared[
            ...,
            tile.y:tile.y + tile.height,
            tile.x:tile.x + tile.width,
        ]

        if tile_image.ndim == 3:
            tile_image = tile_image.unsqueeze(0)

        detections = predictor.predict(tile_image)

        for d in detections:
            translated = replace(
                d,
                x=d.x + tile.x,
                y=d.y + tile.y,
            )
            all_detections.append(translated)

    return {
        "tiles": tiles,
        "detections": all_detections,
    }
