"""Explainable hybrid candidate ranking for the Phase 3 demo."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RankingWeights:
    origin_proximity: float = 0.25
    origin_dwell: float = 0.15
    release_time_alignment: float = 0.15
    corridor_alignment: float = 0.15
    behaviour_rules: float = 0.20
    lstm_continuous: float = 0.05
    dark_gap: float = 0.05


@dataclass(frozen=True)
class RankingNormalization:
    origin_distance_scale_m: float = 5000.0
    origin_50_dwell_reference_pings: int = 24
    release_midpoint_scale_minutes: float = 360.0
    corridor_distance_scale_m: float = 5000.0
    calibration_status: str = (
        "CONTROLLED_DEMO_HEURISTIC_NOT_REAL_WORLD_CALIBRATED"
    )


@dataclass
class CandidateRankingResult:
    rankings: pd.DataFrame
    audit: dict[str, Any]


def _validate_weights(weights: RankingWeights) -> None:
    values = np.asarray(list(asdict(weights).values()), dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Ranking weights must be finite and non-negative")
    if not np.isclose(values.sum(), 1.0, atol=1e-9):
        raise ValueError(
            f"Ranking weights must sum to 1.0; received {values.sum()}"
        )


def _validate_normalization(config: RankingNormalization) -> None:
    positive_values = [
        config.origin_distance_scale_m,
        config.origin_50_dwell_reference_pings,
        config.release_midpoint_scale_minutes,
        config.corridor_distance_scale_m,
    ]
    if any(value <= 0 for value in positive_values):
        raise ValueError("Ranking normalization scales must be positive")


def rank_candidates(
    spatial_features: pd.DataFrame,
    behaviour_features: pd.DataFrame,
    *,
    weights: RankingWeights | None = None,
    normalization: RankingNormalization | None = None,
) -> CandidateRankingResult:
    """Merge evidence and calculate a non-probabilistic priority score."""
    weights = weights or RankingWeights()
    normalization = normalization or RankingNormalization()
    _validate_weights(weights)
    _validate_normalization(normalization)

    spatial_required = [
        "candidate_id",
        "minimum_origin_center_distance_m",
        "closest_origin_midpoint_offset_min",
        "origin_50_point_count",
        "minimum_corridor_distance_m",
        "entered_origin_50",
        "entered_origin_75",
        "entered_origin_90",
    ]
    behaviour_required = [
        "candidate_id",
        "lstm_threshold_ratio",
        "loitering_rule_alert",
        "abrupt_turn_rule_alert",
        "speed_drop_rule_alert",
        "dark_gap_rule_alert",
    ]

    missing_spatial = [
        column
        for column in spatial_required
        if column not in spatial_features.columns
    ]
    missing_behaviour = [
        column
        for column in behaviour_required
        if column not in behaviour_features.columns
    ]
    if missing_spatial:
        raise ValueError(
            f"Spatial ranking columns missing: {missing_spatial}"
        )
    if missing_behaviour:
        raise ValueError(
            f"Behaviour ranking columns missing: {missing_behaviour}"
        )

    if spatial_features["candidate_id"].duplicated().any():
        raise ValueError("Duplicate candidate IDs in spatial features")
    if behaviour_features["candidate_id"].duplicated().any():
        raise ValueError("Duplicate candidate IDs in behaviour features")

    spatial_ids = set(spatial_features["candidate_id"])
    behaviour_ids = set(behaviour_features["candidate_id"])
    if spatial_ids != behaviour_ids:
        raise ValueError(
            "Spatial and behaviour candidate sets do not match"
        )

    merged = spatial_features.merge(
        behaviour_features,
        on="candidate_id",
        how="inner",
        validate="one_to_one",
        suffixes=("_spatial", "_behaviour"),
    )

    merged["origin_proximity_score"] = np.exp(
        -merged["minimum_origin_center_distance_m"]
        / normalization.origin_distance_scale_m
    )
    merged["origin_dwell_score"] = np.clip(
        merged["origin_50_point_count"]
        / normalization.origin_50_dwell_reference_pings,
        0.0,
        1.0,
    )
    merged["release_time_alignment_score"] = np.exp(
        -merged["closest_origin_midpoint_offset_min"]
        / normalization.release_midpoint_scale_minutes
    )
    merged["corridor_alignment_score"] = np.exp(
        -merged["minimum_corridor_distance_m"]
        / normalization.corridor_distance_scale_m
    )

    rule_columns = [
        "loitering_rule_alert",
        "abrupt_turn_rule_alert",
        "speed_drop_rule_alert",
    ]
    merged["behaviour_rule_score"] = (
        merged[rule_columns].astype(float).mean(axis=1)
    )
    merged["lstm_continuous_score"] = np.clip(
        merged["lstm_threshold_ratio"], 0.0, 1.0
    )
    merged["dark_gap_score"] = merged[
        "dark_gap_rule_alert"
    ].astype(float)

    merged["investigative_priority_score"] = (
        weights.origin_proximity
        * merged["origin_proximity_score"]
        + weights.origin_dwell * merged["origin_dwell_score"]
        + weights.release_time_alignment
        * merged["release_time_alignment_score"]
        + weights.corridor_alignment
        * merged["corridor_alignment_score"]
        + weights.behaviour_rules
        * merged["behaviour_rule_score"]
        + weights.lstm_continuous
        * merged["lstm_continuous_score"]
        + weights.dark_gap * merged["dark_gap_score"]
    )

    component_columns = [
        "origin_proximity_score",
        "origin_dwell_score",
        "release_time_alignment_score",
        "corridor_alignment_score",
        "behaviour_rule_score",
        "lstm_continuous_score",
        "dark_gap_score",
        "investigative_priority_score",
    ]
    component_values = merged[component_columns].to_numpy(dtype=float)
    if not np.isfinite(component_values).all():
        raise ValueError("Non-finite ranking components found")
    if ((component_values < 0) | (component_values > 1)).any():
        raise ValueError("Ranking components must remain inside [0, 1]")

    merged = merged.sort_values(
        "investigative_priority_score",
        ascending=False,
        kind="stable",
    ).reset_index(drop=True)
    merged.insert(0, "rank", np.arange(1, len(merged) + 1))
    merged["score_semantics"] = (
        "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
    )
    merged["calibration_status"] = normalization.calibration_status

    output_columns = [
        "rank",
        "candidate_id",
        "investigative_priority_score",
        "origin_proximity_score",
        "origin_dwell_score",
        "release_time_alignment_score",
        "corridor_alignment_score",
        "behaviour_rule_score",
        "lstm_continuous_score",
        "dark_gap_score",
        "entered_origin_50",
        "entered_origin_75",
        "entered_origin_90",
        "minimum_origin_center_distance_m",
        "minimum_corridor_distance_m",
        "closest_origin_midpoint_offset_min",
        "score_semantics",
        "calibration_status",
    ]
    rankings = merged[output_columns].copy()

    audit = {
        "candidate_count": int(len(rankings)),
        "weights": asdict(weights),
        "weight_sum": float(sum(asdict(weights).values())),
        "normalization": asdict(normalization),
        "score_semantics": (
            "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
        ),
        "mmsi_exposed": False,
    }

    return CandidateRankingResult(rankings=rankings, audit=audit)
