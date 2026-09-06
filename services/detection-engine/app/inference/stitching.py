from typing import Sequence

from varun_phase1_core import Detection


def stitch_predictions(
    predictions: Sequence[Detection],
    tiles: Sequence,
) -> list[Detection]:

    results: list[Detection] = []

    for prediction, tile in zip(predictions, tiles):
        results.append(
            Detection(
                x=prediction.x + tile.x,
                y=prediction.y + tile.y,
                width=prediction.width,
                height=prediction.height,
                score=prediction.score,
            )
        )

    return results
