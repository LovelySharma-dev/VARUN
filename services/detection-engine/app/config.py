from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

REGISTRY_PATH = Path(
    os.getenv(
        "VARUN_MODEL_REGISTRY",
        str(ROOT / "models" / "phase1" / "registry.json"),
    )
).resolve()

DEFAULT_MODEL = (
    ROOT
    / "models"
    / "phase1"
    / "unet_oil_spill_v0.1.pth"
)


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {
            "activeProductionModel": None,
            "models": [],
        }

    return json.loads(
        REGISTRY_PATH.read_text(encoding="utf-8")
    )


def get_active_model() -> dict[str, Any]:
    registry = load_registry()

    active = registry.get("activeProductionModel")

    for model in registry.get("models", []):
        if model.get("modelVersionId") == active:
            resolved = dict(model)

            path = Path(
                model.get(
                    "weights",
                    str(DEFAULT_MODEL),
                )
            )

            if not path.is_absolute():
                path = ROOT / path

            resolved["weightsPath"] = str(
                path.resolve()
            )

            return resolved

    return {
        "modelVersionId": "unet-oil-spill-v0.1",
        "modelName": "VARUN U-Net Oil Spill",
        "semanticVersion": "0.1.0",
        "stage": "PRODUCTION",
        "architecture": "U-Net",
        "framework": "PyTorch",
        "inputProfile": "sar-2ch-f32",
        "preprocessingVersion": "sar-percentile-v1",
        "thresholdVersion": "binary-threshold-v1",
        "thresholdValue": 0.5,
        "minAreaPixels": 20,
        "weightsPath": str(DEFAULT_MODEL.resolve()),
    }
