"""Inference pipeline for the VARUNA AIS LSTM autoencoder v2.1."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ais_loader import load_ais_csv
from app.preprocessing_v21 import (
    FEATURE_COLUMNS_V21,
    preprocess_ais_v21,
)


WINDOW_SIZE = 10
DEFAULT_WINDOW_STRIDE = 2
DEFAULT_BATCH_SIZE = 1024


@dataclass
class AISInferenceResult:
    window_scores: pd.DataFrame
    vessel_summary: pd.DataFrame
    dark_gap_events: list[dict[str, Any]]
    load_audit: dict[str, Any]
    preprocessing_audit: dict[str, Any]
    inference_audit: dict[str, Any]


def _validate_package(package: Any) -> None:
    metadata_features = list(package.metadata["feature_order"])

    if metadata_features != FEATURE_COLUMNS_V21:
        raise ValueError(
            "Model metadata feature order does not match "
            "the v2.1 preprocessing feature order"
        )

    if int(package.metadata["time_steps"]) != WINDOW_SIZE:
        raise ValueError(
            "Model time_steps does not match WINDOW_SIZE"
        )

    if int(package.scaler.n_features_in_) != len(
        FEATURE_COLUMNS_V21
    ):
        raise ValueError("Scaler feature count mismatch")

    scaler_features = getattr(
        package.scaler, "feature_names_in_", None
    )
    if scaler_features is not None and list(
        scaler_features
    ) != FEATURE_COLUMNS_V21:
        raise ValueError("Scaler feature order mismatch")

    if float(package.threshold) <= 0:
        raise ValueError("Threshold must be positive")


def _score_batch(
    package: Any,
    batch_windows: list[np.ndarray],
) -> np.ndarray:
    input_batch = np.asarray(batch_windows, dtype=np.float32)
    reconstruction = package.model.predict(
        input_batch,
        batch_size=len(input_batch),
        verbose=0,
    )

    if reconstruction.shape != input_batch.shape:
        raise ValueError(
            "Model reconstruction shape does not match input shape"
        )

    errors = np.mean(
        np.square(input_batch - reconstruction),
        axis=(1, 2),
    )

    if not np.isfinite(errors).all():
        raise ValueError("Non-finite reconstruction errors found")

    return errors.astype(np.float64)


def score_processed_ais(
    processed_df: pd.DataFrame,
    package: Any,
    *,
    window_stride: int = DEFAULT_WINDOW_STRIDE,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Score every eligible window without applying a vessel cap."""
    _validate_package(package)

    if window_stride < 1:
        raise ValueError("window_stride must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    required_columns = [
        "vessel_id",
        "track_segment_id",
        "timestamp",
        *FEATURE_COLUMNS_V21,
    ]
    missing_columns = [
        column
        for column in required_columns
        if column not in processed_df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Processed AIS columns missing: {missing_columns}"
        )

    feature_frame = processed_df[FEATURE_COLUMNS_V21]
    scaled_features = package.scaler.transform(feature_frame).astype(
        np.float32
    )

    if not np.isfinite(scaled_features).all():
        raise ValueError("Non-finite scaled features found")

    pending_windows: list[np.ndarray] = []
    pending_metadata: list[dict[str, Any]] = []
    score_records: list[dict[str, Any]] = []

    def flush_batch() -> None:
        if not pending_windows:
            return

        errors = _score_batch(package, pending_windows)
        threshold = float(package.threshold)

        for metadata, error in zip(
            pending_metadata, errors, strict=True
        ):
            score_records.append(
                {
                    **metadata,
                    "reconstruction_mse": float(error),
                    "is_anomaly": bool(error > threshold),
                }
            )

        pending_windows.clear()
        pending_metadata.clear()

    group_columns = ["vessel_id", "track_segment_id"]

    for (vessel_id, segment_id), segment in processed_df.groupby(
        group_columns, sort=False
    ):
        row_positions = segment.index.to_numpy(dtype=np.int64)
        segment_length = len(row_positions)

        if segment_length < WINDOW_SIZE:
            continue

        for start_offset in range(
            0,
            segment_length - WINDOW_SIZE + 1,
            window_stride,
        ):
            window_positions = row_positions[
                start_offset : start_offset + WINDOW_SIZE
            ]
            start_row = processed_df.loc[window_positions[0]]
            end_row = processed_df.loc[window_positions[-1]]

            pending_windows.append(
                scaled_features[window_positions]
            )
            pending_metadata.append(
                {
                    "vessel_id": str(vessel_id),
                    "track_segment_id": int(segment_id),
                    "window_start_utc": start_row[
                        "timestamp"
                    ],
                    "window_end_utc": end_row["timestamp"],
                }
            )

            if len(pending_windows) >= batch_size:
                flush_batch()

    flush_batch()

    score_columns = [
        "vessel_id",
        "track_segment_id",
        "window_start_utc",
        "window_end_utc",
        "reconstruction_mse",
        "is_anomaly",
    ]
    window_scores = pd.DataFrame(
        score_records, columns=score_columns
    )

    if window_scores.empty:
        vessel_summary = pd.DataFrame(
            columns=[
                "vessel_id",
                "window_count",
                "anomaly_window_count",
                "anomaly_ratio",
                "median_reconstruction_mse",
                "maximum_reconstruction_mse",
                "has_anomaly",
            ]
        )
    else:
        vessel_summary = (
            window_scores.groupby("vessel_id", as_index=False)
            .agg(
                window_count=("is_anomaly", "size"),
                anomaly_window_count=("is_anomaly", "sum"),
                median_reconstruction_mse=(
                    "reconstruction_mse", "median"
                ),
                maximum_reconstruction_mse=(
                    "reconstruction_mse", "max"
                ),
            )
        )
        vessel_summary["anomaly_window_count"] = (
            vessel_summary["anomaly_window_count"].astype(int)
        )
        vessel_summary["anomaly_ratio"] = (
            vessel_summary["anomaly_window_count"]
            / vessel_summary["window_count"]
        )
        vessel_summary["has_anomaly"] = (
            vessel_summary["anomaly_window_count"] > 0
        )
        vessel_summary = vessel_summary[
            [
                "vessel_id",
                "window_count",
                "anomaly_window_count",
                "anomaly_ratio",
                "median_reconstruction_mse",
                "maximum_reconstruction_mse",
                "has_anomaly",
            ]
        ].sort_values(
            ["anomaly_ratio", "maximum_reconstruction_mse"],
            ascending=[False, False],
            kind="stable",
        ).reset_index(drop=True)

    inference_audit = {
        "model_version": package.metadata["model_version"],
        "window_size": WINDOW_SIZE,
        "window_stride": int(window_stride),
        "vessel_window_cap": None,
        "batch_size": int(batch_size),
        "scored_windows": int(len(window_scores)),
        "scored_vessels": int(
            window_scores["vessel_id"].nunique()
            if not window_scores.empty
            else 0
        ),
        "alert_windows": int(
            window_scores["is_anomaly"].sum()
            if not window_scores.empty
            else 0
        ),
        "threshold": float(package.threshold),
        "comparison_operator": "greater_than",
    }

    return window_scores, vessel_summary, inference_audit


def score_ais_csv(
    csv_path: str | Path,
    package: Any,
    *,
    window_stride: int = DEFAULT_WINDOW_STRIDE,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> AISInferenceResult:
    """Load a CSV and run the complete frozen v2.1 inference path."""
    load_result = load_ais_csv(csv_path)
    raw_df = load_result.data.rename(
        columns={"mmsi": "vessel_id"}
    )

    processed_df, dark_gap_events, preprocessing_audit = (
        preprocess_ais_v21(raw_df)
    )
    window_scores, vessel_summary, inference_audit = (
        score_processed_ais(
            processed_df,
            package,
            window_stride=window_stride,
            batch_size=batch_size,
        )
    )

    return AISInferenceResult(
        window_scores=window_scores,
        vessel_summary=vessel_summary,
        dark_gap_events=dark_gap_events,
        load_audit=load_result.audit,
        preprocessing_audit=preprocessing_audit,
        inference_audit=inference_audit,
    )
