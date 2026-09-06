import argparse
import os
import sys
import numpy as np
import rasterio

# Ensure utf-8 stdout on Windows CMD / PowerShell
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, in_channels=2, out_channels=1):
        super().__init__()
        self.enc1 = DoubleConv(in_channels, 64)
        self.enc2 = DoubleConv(64, 128)
        self.enc3 = DoubleConv(128, 256)
        self.enc4 = DoubleConv(256, 512)
        self.pool = nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(512, 1024)

        self.up4 = nn.ConvTranspose2d(1024, 512, 2, stride=2)
        self.dec4 = DoubleConv(1024, 512)

        self.up3 = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.dec3 = DoubleConv(512, 256)

        self.up2 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec2 = DoubleConv(256, 128)

        self.up1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec1 = DoubleConv(128, 64)

        self.out = nn.Conv2d(64, out_channels, 1)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        b = self.bottleneck(self.pool(e4))

        d4 = self.up4(b)
        d4 = torch.cat([d4, e4], dim=1)
        d4 = self.dec4(d4)

        d3 = self.up3(d4)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.dec1(d1)

        return self.out(d1)


def run_inference(image_path, model_path, output_mask_path, threshold=0.5, tile_size=512):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input image not found: {image_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model weights not found: {model_path}")

    # Load Model
    model = UNet(in_channels=2, out_channels=1).to(device)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"Loaded weights from {model_path}")

    # Read GeoTIFF
    with rasterio.open(image_path) as src:
        full_image = src.read().astype(np.float32)
        profile = src.profile.copy()
        height, width = src.height, src.width
        bands = src.count

    print(f"Input Image: {image_path} ({width}x{height}, {bands} bands)")
    if bands != 2:
        raise ValueError(f"Model expects 2 SAR bands, but image has {bands} bands.")

    # Global normalization across full image to avoid tile-level distribution distortion
    norm_image = np.zeros_like(full_image)
    for b in range(bands):
        band = full_image[b]
        low, high = np.percentile(band, 2), np.percentile(band, 98)
        if high > low:
            norm_image[b] = np.clip((band - low) / (high - low), 0, 1)
        else:
            norm_image[b] = 0.0

    # Calculate padding if needed
    pad_h = (tile_size - (height % tile_size)) % tile_size
    pad_w = (tile_size - (width % tile_size)) % tile_size

    if pad_h > 0 or pad_w > 0:
        padded_image = np.pad(norm_image, ((0, 0), (0, pad_h), (0, pad_w)), mode='reflect')
    else:
        padded_image = norm_image

    padded_h, padded_w = padded_image.shape[1], padded_image.shape[2]
    rows = padded_h // tile_size
    cols = padded_w // tile_size

    final_padded_mask = np.zeros((padded_h, padded_w), dtype=np.uint8)

    print(f"Processing image in {rows}x{cols} tiles of size {tile_size}x{tile_size}...")

    with torch.no_grad():
        for r in range(rows):
            for c in range(cols):
                y1, y2 = r * tile_size, (r + 1) * tile_size
                x1, x2 = c * tile_size, (c + 1) * tile_size

                tile = padded_image[:, y1:y2, x1:x2]
                tile_tensor = torch.from_numpy(tile).unsqueeze(0).to(device)

                output = model(tile_tensor)
                prob = torch.sigmoid(output).squeeze().cpu().numpy()
                pred = (prob > threshold).astype(np.uint8)

                final_padded_mask[y1:y2, x1:x2] = pred

    # Crop mask back to original dimensions
    final_mask = final_padded_mask[:height, :width]

    # Statistics
    oil_pixels = int(final_mask.sum())
    total_pixels = int(final_mask.size)
    oil_pct = (oil_pixels / total_pixels) * 100

    print("\n========== INFERENCE RESULTS ==========")
    print(f"Total Pixels    : {total_pixels:,}")
    print(f"Oil Pixels      : {oil_pixels:,}")
    print(f"Oil Coverage    : {oil_pct:.4f}%")

    if oil_pixels > 0:
        print("🚨 RESULT: Potential Oil Spill Detected!")
    else:
        print("✅ RESULT: No Oil Spill Detected.")

    # Save Output GeoTIFF
    output_profile = profile.copy()
    output_profile.update(dtype=rasterio.uint8, count=1, compress="lzw")

    os.makedirs(os.path.dirname(os.path.abspath(output_mask_path)), exist_ok=True)
    with rasterio.open(output_mask_path, "w", **output_profile) as dst:
        dst.write(final_mask, 1)

    print(f"\nMask saved to: {output_mask_path}")

    # Optional Overlay Plot
    try:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        axes[0].imshow(norm_image[0], cmap="gray")
        axes[0].set_title("SAR Image (Band 1)")
        axes[0].axis("off")

        axes[1].imshow(final_mask, cmap="gray")
        axes[1].set_title("Predicted Oil Mask")
        axes[1].axis("off")

        axes[2].imshow(norm_image[0], cmap="gray")
        axes[2].imshow(np.ma.masked_where(final_mask == 0, final_mask), cmap="autumn", alpha=0.5)
        axes[2].set_title("Overlay (Oil Spill)")
        axes[2].axis("off")

        plt.tight_layout()
        overlay_path = output_mask_path.rsplit(".", 1)[0] + "_overlay.png"
        plt.savefig(overlay_path, bbox_inches="tight")
        print(f"Overlay image saved to: {overlay_path}")
    except Exception as e:
        print(f"Note: Could not render visualization plot ({e})")


def create_sample_image(output_path="data/sample_sar_image.tif"):
    """Generates a synthetic 2-band SAR GeoTIFF image (512x512) for testing."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    height, width = 512, 512
    # Create synthetic SAR data with random noise and a simulated dark oil slick region
    band1 = np.random.normal(loc=0.5, scale=0.15, size=(height, width)).astype(np.float32)
    band2 = np.random.normal(loc=0.4, scale=0.12, size=(height, width)).astype(np.float32)

    # Add dark region (simulating oil damping)
    y, x = np.ogrid[:height, :width]
    mask_region = (x - 256)**2 + (y - 256)**2 <= 60**2
    band1[mask_region] *= 0.2
    band2[mask_region] *= 0.2

    sample_data = np.stack([band1, band2], axis=0)

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

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(sample_data)

    print(f"Created synthetic sample SAR GeoTIFF: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oil Spill U-Net Segmentation Inference")
    parser.add_argument("--image", default=None, help="Path to input 2-band SAR GeoTIFF (.tif)")
    parser.add_argument("--model", default="models/phase1/unet_oil_spill_v0.1.pth", help="Path to model weights (.pth)")
    parser.add_argument("--output", default="output_mask.tif", help="Path to save output mask GeoTIFF (.tif)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Probability threshold for positive oil classification (0.0 - 1.0)")
    parser.add_argument("--create-sample", action="store_true", help="Generate a synthetic test SAR GeoTIFF image and run inference on it")

    args = parser.parse_args()

    image_path = args.image
    if args.create_sample or image_path is None:
        sample_path = "data/sample_sar_image.tif"
        print(f"No input image specified or --create-sample flag used. Generating sample test image at '{sample_path}'...")
        image_path = create_sample_image(sample_path)

    run_inference(image_path, args.model, args.output, args.threshold)

