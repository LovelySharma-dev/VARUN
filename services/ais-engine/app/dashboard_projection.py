"""UI-facing projection for Phase 3 results without changing score-v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.attribution_pipeline import Phase3AttributionResult


SCORE_SEMANTICS = (
    "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
)
LEGAL_DISCLAIMER = (
    "Candidate ranking supports investigation and does not constitute "
    "legal attribution or proof of responsibility."
)
TRACK_ARTIFACT_FILE = "candidate_tracks.geojson"


def _utc_iso(value: Any) -> str | None:
    """Serialize a timestamp as ISO-8601 UTC, returning None when absent."""
    if value is None or pd.isna(value):
        return None

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    return timestamp.isoformat().replace("+00:00", "Z")


def _score_breakdown_points(
    ranking: pd.Series,
    weights: dict[str, float],
) -> dict[str, float]:
    mapping = {
        "originProximity": (
            "origin_proximity_score",
            "origin_proximity",
        ),
        "originDwell": ("origin_dwell_score", "origin_dwell"),
        "releaseTimeAlignment": (
            "release_time_alignment_score",
            "release_time_alignment",
        ),
        "corridorAlignment": (
            "corridor_alignment_score",
            "corridor_alignment",
        ),
        "behaviourRules": (
            "behaviour_rule_score",
            "behaviour_rules",
        ),
        "lstmAnomaly": (
            "lstm_continuous_score",
            "lstm_continuous",
        ),
        "darkGap": ("dark_gap_score", "dark_gap"),
    }

    breakdown = {
        public_name: float(ranking[score_column])
        * float(weights[weight_name])
        * 100.0
        for public_name, (score_column, weight_name) in mapping.items()
    }

    expected = float(ranking["investigative_priority_score"]) * 100.0
    if not np.isclose(sum(breakdown.values()), expected, atol=1e-7):
        raise ValueError(
            "UI score breakdown does not reproduce score-v1"
        )

    return breakdown


def _evidence(
    ranking: pd.Series,
    spatial: pd.Series,
    behaviour: pd.Series,
    normalization: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    supporting: list[str] = []
    negative: list[str] = []
    warnings: list[str] = []

    if bool(ranking["entered_origin_50"]):
        supporting.append(
            "Track entered the highest-density origin evidence contour."
        )
    elif bool(ranking["entered_origin_90"]):
        supporting.append(
            "Track entered the broader origin evidence region."
        )
        negative.append(
            "Track did not enter the highest-density origin contour."
        )
    else:
        negative.append(
            "Track did not enter any supplied origin evidence contour."
        )

    corridor_scale = float(
        normalization["corridor_distance_scale_m"]
    )
    corridor_distance = float(
        ranking["minimum_corridor_distance_m"]
    )
    if corridor_distance <= corridor_scale:
        supporting.append(
            "Track was spatially aligned with the hindcast corridor."
        )
    else:
        negative.append(
            "Track remained beyond the score-v1 corridor distance scale."
        )

    time_scale = float(
        normalization["release_midpoint_scale_minutes"]
    )
    time_offset = float(
        ranking["closest_origin_midpoint_offset_min"]
    )
    if time_offset <= time_scale:
        supporting.append(
            "Closest origin approach aligned with the release-time scale."
        )
    else:
        negative.append(
            "Closest origin approach was outside the release-time scale."
        )

    rule_messages = [
        ("loitering_rule_alert", "Loitering-transition rule matched."),
        ("abrupt_turn_rule_alert", "Abrupt-turn rule matched."),
        ("speed_drop_rule_alert", "Sudden-speed-drop rule matched."),
    ]
    matched_rules = [
        message
        for column, message in rule_messages
        if bool(behaviour[column])
    ]
    if matched_rules:
        supporting.extend(matched_rules)
    else:
        negative.append("No configured behaviour rule matched.")

    if bool(behaviour["lstm_binary_alert"]):
        supporting.append(
            "At least one window exceeded the frozen LSTM threshold."
        )
    else:
        negative.append(
            "No window exceeded the frozen LSTM threshold."
        )

    dark_gap_count = int(behaviour["dark_gap_event_count"])
    if dark_gap_count > 0:
        supporting.append("AIS dark-gap evidence was observed.")
        warnings.append(
            f"{dark_gap_count} AIS dark-gap event(s) were detected; "
            "a gap is an investigative signal, not proof of shutdown."
        )
    else:
        negative.append("No AIS dark-gap event was detected.")

    if float(spatial["release_window_point_ratio"]) < 1.0:
        warnings.append(
            "Some candidate observations fall outside the release window."
        )

    return supporting, negative, warnings


def project_dashboard_candidates(
    result: Phase3AttributionResult,
    *,
    top_candidates: int = 3,
) -> list[dict[str, Any]]:
    """Create an additive, privacy-safe dashboard projection."""
    if top_candidates < 1:
        raise ValueError("top_candidates must be at least 1")

    rankings = result.ranking.rankings.head(top_candidates)
    spatial = result.spatial_evidence.features.set_index("candidate_id")
    behaviour = result.behaviour_evidence.features.set_index(
        "candidate_id"
    )
    weights = result.ranking.audit["weights"]
    normalization = result.ranking.audit["normalization"]

    if set(rankings["candidate_id"]) - set(spatial.index):
        raise ValueError("Ranking candidate missing from spatial evidence")
    if set(rankings["candidate_id"]) - set(behaviour.index):
        raise ValueError("Ranking candidate missing from behaviour evidence")

    projected: list[dict[str, Any]] = []

    for _, ranking in rankings.iterrows():
        candidate_id = str(ranking["candidate_id"])
        spatial_row = spatial.loc[candidate_id]
        behaviour_row = behaviour.loc[candidate_id]
        rank = int(ranking["rank"])

        supporting, negative, candidate_warnings = _evidence(
            ranking,
            spatial_row,
            behaviour_row,
            normalization,
        )

        record = {
            "rank": rank,
            "candidateId": candidate_id,
            "rankLabel": f"CAND-{rank:03d}",
            "investigativePriorityScore": float(
                ranking["investigative_priority_score"]
            ),
            "originProximityScore": float(
                ranking["origin_proximity_score"]
            ),
            "originDwellScore": float(
                ranking["origin_dwell_score"]
            ),
            "releaseTimeAlignmentScore": float(
                ranking["release_time_alignment_score"]
            ),
            "corridorAlignmentScore": float(
                ranking["corridor_alignment_score"]
            ),
            "behaviourRuleScore": float(
                ranking["behaviour_rule_score"]
            ),
            "lstmContinuousScore": float(
                ranking["lstm_continuous_score"]
            ),
            "darkGapScore": float(ranking["dark_gap_score"]),
            "enteredOrigin50": bool(ranking["entered_origin_50"]),
            "enteredOrigin75": bool(ranking["entered_origin_75"]),
            "enteredOrigin90": bool(ranking["entered_origin_90"]),
            "minimumOriginCenterDistanceM": float(
                ranking["minimum_origin_center_distance_m"]
            ),
            "minimumCorridorDistanceM": float(
                ranking["minimum_corridor_distance_m"]
            ),
            "closestOriginMidpointOffsetMin": float(
                ranking["closest_origin_midpoint_offset_min"]
            ),
            "investigativeScore": float(
                ranking["investigative_priority_score"]
            )
            * 100.0,
            "scoreBreakdownPoints": _score_breakdown_points(
                ranking, weights
            ),
            "closestApproach": {
                "distanceKm": float(
                    ranking["minimum_origin_center_distance_m"]
                )
                / 1000.0,
                "timestampUtc": _utc_iso(
                    spatial_row["closest_origin_time_utc"]
                ),
            },
            "candidateTrackRef": {
                "artifactFile": TRACK_ARTIFACT_FILE,
                "candidateId": candidate_id,
            },
            "dataQuality": {
                "status": "MODEL_ELIGIBLE",
                "observationCount": int(behaviour_row["ping_count"]),
                "eligibleWindowCount": int(
                    behaviour_row["window_count"]
                ),
                "anomalyWindowCount": int(
                    behaviour_row["anomaly_window_count"]
                ),
                "includedInScoreV1": False,
            },
            "supportingEvidence": supporting,
            "negativeEvidence": negative,
            "warnings": candidate_warnings,
            "scoreSemantics": SCORE_SEMANTICS,
            "calibrationStatus": str(ranking["calibration_status"]),
            "legalDisclaimer": LEGAL_DISCLAIMER,
        }

        forbidden = {"mmsi", "imo", "shipName", "ship_name"}
        if forbidden.intersection(record):
            raise ValueError("Restricted vessel identity reached projection")

        projected.append(record)

    return projected
