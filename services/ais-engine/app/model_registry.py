import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import tensorflow as tf




@dataclass(frozen=True)
class AISModelPackage:
    model: Any
    scaler: Any
    threshold: float
    metadata: dict[str, Any]
    feature_config: dict[str, Any]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def get_model_directory() -> Path:
    repository_root = Path(__file__).resolve().parents[3]

    model_version = os.getenv(
        "AIS_MODEL_VERSION",
        "v2_1",
    ).strip()

    supported_versions = {
        "v2",
        "v2_1",
    }

    if model_version not in supported_versions:
        raise ValueError(
            f"Unsupported AIS model version: {model_version}. "
            f"Supported versions: {sorted(supported_versions)}"
        )

    model_directory = (
        repository_root
        / "models"
        / "phase3"
        / "ais-lstm-ae"
        / model_version
    )

    if not model_directory.is_dir():
        raise FileNotFoundError(
            f"AIS model directory not found: {model_directory}"
        )

    return model_directory
@lru_cache(maxsize=1)
def load_ais_model_package() -> AISModelPackage:
    model_directory = get_model_directory()


    required_files = [
        "model.keras",
        "feature_scaler.joblib",
        "threshold.json",
        "model_metadata.json",
        "feature_config.json",
    ]

    missing_files = [
        filename
        for filename in required_files
        if not (model_directory / filename).exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Missing model artifacts: " + ", ".join(missing_files)
        )

    metadata = read_json(model_directory / "model_metadata.json")
    feature_config = read_json(model_directory / "feature_config.json")
    threshold_data = read_json(model_directory / "threshold.json")

    model = tf.keras.models.load_model(
        model_directory / "model.keras",
        compile=False,
    )

    scaler = joblib.load(
        model_directory / "feature_scaler.joblib"
    )

    metadata_features = metadata["feature_order"]
    config_features = feature_config["feature_order"]

    if metadata_features != config_features:
        raise ValueError(
            "Feature order mismatch between metadata and feature config"
        )

    time_steps = int(metadata["time_steps"])
    feature_count = len(metadata_features)

    expected_shape = (None, time_steps, feature_count)

    if tuple(model.input_shape) != expected_shape:
        raise ValueError(
            f"Invalid model input shape: {model.input_shape}; "
            f"expected {expected_shape}"
        )

    if tuple(model.output_shape) != expected_shape:
        raise ValueError(
            f"Invalid model output shape: {model.output_shape}; "
            f"expected {expected_shape}"
        )

    if int(scaler.n_features_in_) != feature_count:
        raise ValueError(
            f"Scaler expects {scaler.n_features_in_} features; "
            f"metadata defines {feature_count}"
        )

    threshold = float(
        threshold_data["reconstruction_error_threshold"]
    )

    if threshold <= 0:
        raise ValueError("Reconstruction threshold must be positive")

    return AISModelPackage(
        model=model,
        scaler=scaler,
        threshold=threshold,
        metadata=metadata,
        feature_config=feature_config,
    )
