from typing import Any, Protocol


class Detection:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        confidence: float,
        label: str = "oil_spill",
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = confidence
        self.label = label


class Predictor(Protocol):
    def predict(self, image: Any) -> list[Detection]:
        ...
