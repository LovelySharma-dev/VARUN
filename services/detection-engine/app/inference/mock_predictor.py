from typing import Any

from varun_phase1_core import Detection


class MockPredictor:
    def predict(self, image: Any) -> list[Detection]:
        return []
