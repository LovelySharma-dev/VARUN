import os
import pytest
import numpy as np
import rasterio
from ml.phase1.infer import run_inference, create_sample_image


def test_create_sample_image(tmp_path):
    """Verify synthetic 2-band SAR GeoTIFF sample creation."""
    sample_path = os.path.join(tmp_path, "sample.tif")
    out_path = create_sample_image(sample_path)
    assert os.path.exists(out_path)

    with rasterio.open(out_path) as src:
        assert src.count == 2
        assert src.height == 512
        assert src.width == 512
        assert src.dtypes[0] == "float32"


def test_run_inference_end_to_end(sample_2band_tiff, model_weights_path, tmp_path):
    """Verify full tile-based inference pipeline execution on valid input."""
    output_mask = os.path.join(tmp_path, "output_mask.tif")

    run_inference(
        image_path=sample_2band_tiff,
        model_path=model_weights_path,
        output_mask_path=output_mask,
        threshold=0.5,
    )

    # Verify generated mask GeoTIFF file
    assert os.path.exists(output_mask)

    with rasterio.open(output_mask) as src:
        assert src.count == 1
        assert src.height == 512
        assert src.width == 512
        mask_data = src.read(1)
        unique_vals = set(np.unique(mask_data))
        assert unique_vals.issubset({0, 1}), f"Invalid mask values: {unique_vals}"

    # Verify visualization overlay image file
    overlay_path = output_mask.rsplit(".", 1)[0] + "_overlay.png"
    assert os.path.exists(overlay_path)


def test_run_inference_missing_input(model_weights_path, tmp_path):
    """Verify FileNotFoundError is raised when input image does not exist."""
    missing_path = os.path.join(tmp_path, "non_existent.tif")
    output_mask = os.path.join(tmp_path, "mask.tif")

    with pytest.raises(FileNotFoundError):
        run_inference(missing_path, model_weights_path, output_mask)


def test_run_inference_invalid_channels(sample_3band_tiff, model_weights_path, tmp_path):
    """Verify ValueError is raised when input image has wrong band count."""
    output_mask = os.path.join(tmp_path, "mask.tif")

    with pytest.raises(ValueError, match="2 SAR bands"):
        run_inference(sample_3band_tiff, model_weights_path, output_mask)
