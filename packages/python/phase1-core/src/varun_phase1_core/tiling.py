from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    width: int
    height: int


def generate_tiles(
    width: int,
    height: int,
    tile_size: int = 1024,
    overlap: int = 128,
) -> Iterator[Tile]:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")
    if overlap < 0 or overlap >= tile_size:
        raise ValueError("overlap must be >= 0 and < tile_size")

    stride = tile_size - overlap

    y = 0
    while y < height:
        x = 0
        tile_h = min(tile_size, height - y)

        while x < width:
            tile_w = min(tile_size, width - x)
            yield Tile(x=x, y=y, width=tile_w, height=tile_h)

            if x + tile_size >= width:
                break
            x += stride

        if y + tile_size >= height:
            break
        y += stride
