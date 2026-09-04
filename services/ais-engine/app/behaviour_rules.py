"""Transparent rule evidence used beside the frozen AIS v2.1 model."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BehaviourRuleConfig:
    low_speed_knots: float = 2.0
    abrupt_turn_degrees: float = 30.0
    sudden_speed_drop_knots: float = 5.0
    calibration_status: str = "DEMO_RULES_NOT_REAL_WORLD_CALIBRATED"


@dataclass
class BehaviourEvidenceResult:
    features: pd.DataFrame
    audit: dict[str, Any]


def build_behaviour_evidence(
    processed_df: pd.DataFrame,
    identity_map: pd.DataFrame,
    model_summary: pd.DataFrame,
    dark_gap_events: list[dict[str, Any]],
    *,
    config: BehaviourRuleConfig | None = None,
    model_threshold: float,
) -> BehaviourEvidenceResult:
    """Build per-candidate rules and continuous LSTM evidence."""
    config = config or BehaviourRuleConfig()

    if model_threshold <= 0:
        raise ValueError("model_threshold must be positive")

    required_processed = [
        "vessel_id",
        "speed",
        "speed_change",
        "turn_angle_deg",
        "path_efficiency",
    ]
    missing_processed = [
        column
        for column in required_processed
        if column not in processed_df.columns
    ]
    if missing_processed:
        raise ValueError(
            f"Processed behaviour columns missing: {missing_processed}"
        )

    required_identity = ["candidate_id", "mmsi"]
    if any(
        column not in identity_map.columns
        for column in required_identity
    ):
        raise ValueError("Invalid candidate identity map")

    required_model = [
        "vessel_id",
        "window_count",
        "anomaly_window_count",
        "anomaly_ratio",
        "median_reconstruction_mse",
        "maximum_reconstruction_mse",
    ]
    if any(
        column not in model_summary.columns
        for column in required_model
    ):
        raise ValueError("Invalid model summary")

    dataframe = processed_df.copy()
    dataframe["vessel_id"] = dataframe["vessel_id"].astype("string")

    dataframe["is_low_speed"] = (
        dataframe["speed"] <= config.low_speed_knots
    )
    dataframe["is_abrupt_turn"] = (
        dataframe["turn_angle_deg"]
        >= config.abrupt_turn_degrees
    )
    dataframe["is_sudden_speed_drop"] = (
        dataframe["speed_change"]
        <= -config.sudden_speed_drop_knots
    )
    dataframe["is_loitering_signature"] = (
        dataframe["is_low_speed"]
        & dataframe["is_abrupt_turn"]
    )

    rules = (
        dataframe.groupby("vessel_id", as_index=False)
        .agg(
            ping_count=("speed", "size"),
            median_speed_knots=("speed", "median"),
            minimum_speed_knots=("speed", "min"),
            maximum_speed_drop_knots=(
                "speed_change",
                lambda values: float(max(0.0, -values.min())),
            ),
            maximum_turn_degrees=("turn_angle_deg", "max"),
            median_path_efficiency=("path_efficiency", "median"),
            low_speed_ping_count=("is_low_speed", "sum"),
            abrupt_turn_ping_count=("is_abrupt_turn", "sum"),
            sudden_speed_drop_event_count=(
                "is_sudden_speed_drop", "sum"
            ),
            loitering_signature_ping_count=(
                "is_loitering_signature", "sum"
            ),
        )
    )

    count_columns = [
        "low_speed_ping_count",
        "abrupt_turn_ping_count",
        "sudden_speed_drop_event_count",
        "loitering_signature_ping_count",
    ]
    rules[count_columns] = rules[count_columns].astype(int)
    rules["low_speed_ratio"] = (
        rules["low_speed_ping_count"] / rules["ping_count"]
    )
    rules["abrupt_turn_ratio"] = (
        rules["abrupt_turn_ping_count"] / rules["ping_count"]
    )
    rules["loitering_signature_ratio"] = (
        rules["loitering_signature_ping_count"]
        / rules["ping_count"]
    )

    gap_counts: dict[str, int] = {}
    for event in dark_gap_events:
        vessel_id = str(event["vessel_id"])
        gap_counts[vessel_id] = gap_counts.get(vessel_id, 0) + 1
    rules["dark_gap_event_count"] = (
        rules["vessel_id"].map(gap_counts).fillna(0).astype(int)
    )

    model_columns = model_summary[required_model].copy()
    model_columns["vessel_id"] = model_columns[
        "vessel_id"
    ].astype("string")
    rules = rules.merge(
        model_columns, on="vessel_id", how="left", validate="one_to_one"
    )

    if rules["window_count"].isna().any():
        raise ValueError(
            "At least one candidate has no LSTM window summary"
        )

    rules["lstm_threshold_ratio"] = (
        rules["maximum_reconstruction_mse"] / model_threshold
    )
    rules["lstm_binary_alert"] = (
        rules["anomaly_window_count"] > 0
    )
    rules["loitering_rule_alert"] = (
        rules["loitering_signature_ping_count"] > 0
    )
    rules["abrupt_turn_rule_alert"] = (
        rules["abrupt_turn_ping_count"] > 0
    )
    rules["speed_drop_rule_alert"] = (
        rules["sudden_speed_drop_event_count"] > 0
    )
    rules["dark_gap_rule_alert"] = (
        rules["dark_gap_event_count"] > 0
    )

    identity = identity_map.copy()
    identity["mmsi"] = identity["mmsi"].astype("string")
    rules = rules.merge(
        identity,
        left_on="vessel_id",
        right_on="mmsi",
        how="left",
        validate="one_to_one",
    )
    if rules["candidate_id"].isna().any():
        raise ValueError("Candidate identity mapping failed")

    rules = rules.drop(columns=["vessel_id", "mmsi"])
    rules = rules[
        ["candidate_id"]
        + [column for column in rules.columns if column != "candidate_id"]
    ]

    numeric_columns = rules.select_dtypes(include=[np.number]).columns
    if not np.isfinite(
        rules[numeric_columns].to_numpy(dtype=float)
    ).all():
        raise ValueError("Non-finite behaviour evidence found")

    audit = {
        "candidate_vessels": int(len(rules)),
        "model_threshold": float(model_threshold),
        "rule_config": asdict(config),
        "lstm_alert_candidates": int(
            rules["lstm_binary_alert"].sum()
        ),
        "loitering_rule_candidates": int(
            rules["loitering_rule_alert"].sum()
        ),
        "abrupt_turn_rule_candidates": int(
            rules["abrupt_turn_rule_alert"].sum()
        ),
        "speed_drop_rule_candidates": int(
            rules["speed_drop_rule_alert"].sum()
        ),
        "dark_gap_rule_candidates": int(
            rules["dark_gap_rule_alert"].sum()
        ),
        "mmsi_exposed_in_features": False,
        "final_responsibility_scoring_applied": False,
    }

    return BehaviourEvidenceResult(features=rules, audit=audit)
