import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from app.inference_v21 import score_ais_csv
from app.model_registry import (
    get_model_directory,
    load_ais_model_package,
)
from app.preprocessing_v21 import (
    FEATURE_COLUMNS_V21,
    preprocess_ais_v21,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_CSV = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "ais-demo"
    / "ais_input.csv"
)
EXPECTED_MODEL_SHA256 = (
    "1996072bab24d9325131ca54eb8f13e1f"
    "82641f938de5fbdc60eff2aab46d075"
)


def test_preprocessing_v21_builds_exact_finite_features():
    start = pd.Timestamp("2025-01-01T00:00:00Z")
    raw_df = pd.DataFrame(
        {
            "vessel_id": ["123456789"] * 10,
            "timestamp": [
                start + pd.Timedelta(minutes=5 * index)
                for index in range(10)
            ],
            "latitude": [20.0 + 0.01 * index for index in range(10)],
            "longitude": [70.0 + 0.01 * index for index in range(10)],
            "speed": [8.0 + 0.1 * index for index in range(10)],
            "course": [30.0 + index for index in range(10)],
        }
    )

    processed, dark_gaps, audit = preprocess_ais_v21(raw_df)

    assert list(processed[FEATURE_COLUMNS_V21].columns) == (
        FEATURE_COLUMNS_V21
    )
    assert np.isfinite(
        processed[FEATURE_COLUMNS_V21].to_numpy(dtype=np.float64)
    ).all()
    assert dark_gaps == []
    assert audit["pipeline_version"] == "ais-preprocessing-v2.1"
    assert audit["track_segments"] == 1


def test_selected_v21_model_package_checksum_and_cache():
    model_directory = get_model_directory()

    assert model_directory.name == "v2_1"

    model_hash = hashlib.sha256(
        (model_directory / "model.keras").read_bytes()
    ).hexdigest()
    assert model_hash == EXPECTED_MODEL_SHA256

    load_ais_model_package.cache_clear()
    first_package = load_ais_model_package()
    second_package = load_ais_model_package()

    assert first_package is second_package
    assert first_package.metadata["model_version"] == (
        "ais-lstm-ae-v2.1"
    )
    assert first_package.metadata["time_steps"] == 10
    assert first_package.metadata["feature_order"] == (
        FEATURE_COLUMNS_V21
    )
    assert first_package.model.input_shape == (None, 10, 8)
    assert first_package.model.output_shape == (None, 10, 8)
    assert first_package.threshold == 0.06935688848908478


def test_fixture_runs_complete_v21_inference():
    assert FIXTURE_CSV.is_file()

    package = load_ais_model_package()
    result = score_ais_csv(
        FIXTURE_CSV,
        package,
        window_stride=2,
        batch_size=256,
    )

    audit = result.inference_audit

    assert result.load_audit["valid_rows"] == 148
    assert result.preprocessing_audit["track_segments"] == 15
    assert len(result.dark_gap_events) == 10
    assert audit["model_version"] == "ais-lstm-ae-v2.1"
    assert audit["window_size"] == 10
    assert audit["window_stride"] == 2
    assert audit["scored_windows"] == 12
    assert audit["scored_vessels"] == 5
    assert 0 <= audit["alert_windows"] <= audit["scored_windows"]
    assert len(result.vessel_summary) == 5
    assert np.isfinite(
        result.window_scores["reconstruction_mse"].to_numpy()
    ).all()
