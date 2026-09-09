from varun_phase1_core.tiling import generate_tiles


def test_tiles_cover_image():
    tiles = list(generate_tiles(2048, 2048, tile_size=1024, overlap=128))
    assert len(tiles) > 1
    assert tiles[0].x == 0
    assert tiles[0].y == 0


def test_small_image_has_one_tile():
    tiles = list(generate_tiles(500, 400, tile_size=1024))
    assert len(tiles) == 1
    assert tiles[0].width == 500
    assert tiles[0].height == 400
