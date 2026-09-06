from typing import Sequence

from varun_phase1_core import Detection


def filter_detections(
    detections: Sequence[Detection],
    threshold: float = 0.5,
) -> list[Detection]:

    if not 0 <= threshold <= 1:
        raise ValueError(
            "threshold must be between 0 and 1"
        )

    return [
        detection
        for detection in detections
        if detection.score >= threshold
    ]
