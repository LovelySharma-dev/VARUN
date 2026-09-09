from typing import Any

from app.postprocessing.pipeline import process_predictions


def run_detection_pipeline(
    predictions: list[Any],
    tiles: list[Any],
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.5,
) -> list[Any]:
    return process_predictions(
        predictions=predictions,
        tiles=tiles,
        confidence_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
    )
