from typing import Any


def stitch_predictions(
    predictions: list[Any],
    tiles: list[Any],
) -> list[Any]:

    # Predictions are already in global coordinates.
    # If no tiles are supplied, preserve them as-is.
    if not tiles:
        return predictions

    results = []

    for prediction, tile in zip(predictions, tiles):

        results.append(
            type(prediction)(
                x=prediction.x + tile.x,
                y=prediction.y + tile.y,
                width=prediction.width,
                height=prediction.height,
                score=prediction.score,
            )
        )

    return results
