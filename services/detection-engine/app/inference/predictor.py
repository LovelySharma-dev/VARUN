from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Detection:
    x: float
    y: float
    width: float
    height: float
    confidence: float = 0.0
    label: str = "unknown"


class Predictor(Protocol):
    def predict(self, image: Any) -> list[Detection]:
        ...
