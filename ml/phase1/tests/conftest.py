import os
import sys
import pytest
import numpy as np
import rasterio

# Add workspace root to sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


@pytest.fixture
def model_weights_path():
    path = os.path.join(WORKSPACE_ROOT, "models", "phase1", "unet_oil_spill_v0.1.pth")
    assert os.path.exists(path), f"Model checkpoint missing at {path}"
    return path


@pytest.fixture
def sample_2band_tiff(tmp_path):
    """Creates a temporary 2-band SAR GeoTIFF image (512x512) for testing."""
    tiff_path = os.path.join(tmp_path, "test_sar.tif")
    height, width = 512, 512
    band1 = np.random.uniform(0, 1, (height, width)).astype(np.float32)
    band2 = np.random.uniform(0, 1, (height, width)).astype(np.float32)
    data = np.stack([band1, band2], axis=0)

    transform = rasterio.transform.from_origin(0.0, 0.0, 1.0, 1.0)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 2,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
    }

    with rasterio.open(tiff_path, "w", **profile) as dst:
        dst.write(data)

    return str(tiff_path)


@pytest.fixture
def sample_3band_tiff(tmp_path):
    """Creates an invalid 3-band GeoTIFF image to test channel validation."""
    tiff_path = os.path.join(tmp_path, "test_3band.tif")
    data = np.random.uniform(0, 1, (3, 256, 256)).astype(np.float32)
    profile = {
        "driver": "GTiff",
        "height": 256,
        "width": 256,
        "count": 3,
        "dtype": "float32",
    }
    with rasterio.open(tiff_path, "w", **profile) as dst:
        dst.write(data)
    return str(tiff_path)
