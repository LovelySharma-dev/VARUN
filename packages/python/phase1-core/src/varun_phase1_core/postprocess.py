from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Detection:
    x: float
    y: float
    width: float
    height: float
    score: float


def filter_detections(
    detections: Sequence[Detection],
    threshold: float,
) -> list[Detection]:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    return [
        detection
        for detection in detections
        if detection.score >= threshold
    ]
