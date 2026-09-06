from typing import Any

from app.preprocessing.pipeline import preprocess_image


def prepare_for_inference(
    image: Any,
    width: int,
    height: int,
):
    return preprocess_image(
        image=image,
        width=width,
        height=height,
    )
