from varun_phase1_core.inference import InferenceConfig, run_inference
from varun_phase1_core.postprocess import Detection


class FakeDetector:
    def predict(self, image):
        return [
            Detection(x=10, y=20, width=30, height=40, score=0.9),
            Detection(x=50, y=60, width=20, height=20, score=0.3),
        ]


def test_run_inference_filters_by_confidence():
    result = run_inference(
        FakeDetector(),
        object(),
        InferenceConfig(confidence_threshold=0.5),
    )

    assert len(result) == 1
    assert result[0].score == 0.9
