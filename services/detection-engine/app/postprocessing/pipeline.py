from typing import Any

from app.geometry.nms import non_max_suppression
from app.postprocessing.threshold import filter_detections
from app.postprocessing.stitching import stitch_predictions


def process_predictions(
    predictions: list[Any],
    tiles: list[Any],
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.5,
) -> list[Any]:

    filtered = filter_detections(
        predictions,
        threshold=confidence_threshold,
    )

    stitched = stitch_predictions(
        filtered,
        tiles,
    )

    return non_max_suppression(
        stitched,
        iou_threshold=iou_threshold,
    )
