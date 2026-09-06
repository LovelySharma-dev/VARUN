import os
import torch
import pytest
from ml.phase1.infer import UNet, DoubleConv


def test_double_conv_layer():
    """Verify DoubleConv block output shape."""
    conv = DoubleConv(in_channels=2, out_channels=64)
    dummy_input = torch.randn(2, 2, 64, 64)
    output = conv(dummy_input)
    assert output.shape == (2, 64, 64, 64)


def test_unet_instantiation():
    """Verify UNet initializes with expected input and output channels."""
    model = UNet(in_channels=2, out_channels=1)
    assert isinstance(model, torch.nn.Module)


def test_unet_forward_pass_shape():
    """Verify U-Net forward pass tensor dimensions."""
    model = UNet(in_channels=2, out_channels=1)
    model.eval()
    dummy_input = torch.randn(1, 2, 512, 512)
    with torch.no_grad():
        output = model(dummy_input)
    assert output.shape == (1, 1, 512, 512)


def test_load_trained_model_weights(model_weights_path):
    """Verify trained checkpoint weights load into UNet without key mismatch."""
    model = UNet(in_channels=2, out_channels=1)
    state_dict = torch.load(model_weights_path, map_location="cpu")

    # Ensure state dict loads cleanly
    missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=True)
    assert len(missing_keys) == 0, f"Missing keys in model: {missing_keys}"
    assert len(unexpected_keys) == 0, f"Unexpected keys in model: {unexpected_keys}"
