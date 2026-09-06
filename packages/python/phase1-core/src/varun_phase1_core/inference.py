from dataclasses import dataclass
from typing import Protocol, Sequence

from .postprocess import Detection


class Detector(Protocol):
    def predict(self, image: object) -> Sequence[Detection]:
        """Run inference on one image/tile and return detections."""
        ...


@dataclass(frozen=True)
class InferenceConfig:
    confidence_threshold: float = 0.5


def run_inference(
    detector: Detector,
    image: object,
    config: InferenceConfig | None = None,
) -> list[Detection]:
    config = config or InferenceConfig()

    detections = detector.predict(image)

    return [
        detection
        for detection in detections
        if detection.score >= config.confidence_threshold
    ]
