from varun_phase1_core import generate_tiles


def create_tiles(
    image_width: int,
    image_height: int,
    tile_size: int = 1024,
    overlap: int = 128,
):
    return list(
        generate_tiles(
            width=image_width,
            height=image_height,
            tile_size=tile_size,
            overlap=overlap,
        )
    )
