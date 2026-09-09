from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def tile_to_image_box(
    x: float,
    y: float,
    width: float,
    height: float,
) -> BoundingBox:
    if width < 0 or height < 0:
        raise ValueError("width and height must be non-negative")

    return BoundingBox(
        min_x=x,
        min_y=y,
        max_x=x + width,
        max_y=y + height,
    )


def clamp_box(
    box: BoundingBox,
    image_width: float,
    image_height: float,
) -> BoundingBox:
    return BoundingBox(
        min_x=max(0, min(box.min_x, image_width)),
        min_y=max(0, min(box.min_y, image_height)),
        max_x=max(0, min(box.max_x, image_width)),
        max_y=max(0, min(box.max_y, image_height)),
    )
