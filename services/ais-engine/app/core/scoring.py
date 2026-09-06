from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCORE_VERSION = "score-v1"


@dataclass(frozen=True)
class ScoreWeights:
    origin_proximity: float = 30.0
    time_overlap: float = 25.0
    corridor_trajectory: float = 20.0
    behaviour: float = 10.0
    ais_gap: float = 5.0
    data_quality: float = 10.0
    negative_evidence_penalty: float = 4.0


DEFAULT_WEIGHTS = ScoreWeights()


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _gap_score(maximum_gap_minutes: float) -> float:
    gap = max(0.0, float(maximum_gap_minutes))

    if gap <= 5:
        return 1.0
    if gap <= 15:
        return 0.8
    if gap <= 30:
        return 0.6
    if gap <= 60:
        return 0.3
    return 0.0


def calculate_score(
    features: dict[str, Any] | None = None,
    *,
    origin_proximity: float | None = None,
    time_overlap: float | None = None,
    corridor_trajectory: float | None = None,
    behaviour: float | None = None,
    ais_gap: float | None = None,
    data_quality: float | None = None,
    negative_evidence: float = 0.0,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, Any]:

    if features is not None:
        origin_proximity = features.get("originProximity", 0.0)
        time_overlap = features.get("timeOverlap", 0.0)
        corridor_trajectory = features.get("corridorOverlap", 0.0)
        behaviour = features.get(
            "speedBehaviour",
            features.get("behaviour", 0.0),
        )
        data_quality = features.get("dataQuality", 0.0)
        ais_gap = _gap_score(
            features.get("maximumGapMinutes", 0.0)
        )

    origin_proximity = origin_proximity or 0.0
    time_overlap = time_overlap or 0.0
    corridor_trajectory = corridor_trajectory or 0.0
    behaviour = behaviour or 0.0
    ais_gap = ais_gap or 0.0
    data_quality = data_quality or 0.0

    components = {
        "originProximity": round(clamp01(origin_proximity), 6),
        "timeOverlap": round(clamp01(time_overlap), 6),
        "corridorTrajectory": round(clamp01(corridor_trajectory), 6),
        "behaviour": round(clamp01(behaviour), 6),
        "aisGap": round(clamp01(ais_gap), 6),
        "dataQuality": round(clamp01(data_quality), 6),
    }

    positive_score = (
        components["originProximity"] * weights.origin_proximity
        + components["timeOverlap"] * weights.time_overlap
        + components["corridorTrajectory"] * weights.corridor_trajectory
        + components["behaviour"] * weights.behaviour
        + components["aisGap"] * weights.ais_gap
        + components["dataQuality"] * weights.data_quality
    )

    penalty = clamp01(negative_evidence) * weights.negative_evidence_penalty

    final_score = max(0.0, positive_score - penalty)

    confidence = (
        0.45 * components["dataQuality"]
        + 0.25 * components["aisGap"]
        + 0.15 * components["timeOverlap"]
        + 0.15 * components["originProximity"]
    )

    return {
        "scoreVersion": SCORE_VERSION,
        "score": round(final_score, 6),
        "confidence": round(clamp01(confidence), 6),
        "negativeEvidencePenalty": round(penalty, 6),
        "components": components,
    }


def score_candidate(
    features: dict[str, Any] | None = None,
    *,
    origin_proximity: float | None = None,
    time_overlap: float | None = None,
    corridor_overlap: float | None = None,
    behaviour: float | None = None,
    track_coverage: float | None = None,
    maximum_gap_minutes: float | None = None,
    data_quality: float | None = None,
    negative_evidence: float = 0.0,
) -> dict[str, Any]:
    """
    Compatibility entry point used by both the AIS engine and
    repository scientific tests.

    Supports:
      score_candidate(features_dict)

    and:
      score_candidate(
          origin_proximity=...,
          time_overlap=...,
          corridor_overlap=...,
          behaviour=...,
          track_coverage=...,
          maximum_gap_minutes=...,
          data_quality=...,
          negative_evidence=...
      )
    """

    if features is not None:
        origin_proximity = features.get("originProximity", 0.0)
        time_overlap = features.get("timeOverlap", 0.0)
        corridor_overlap = features.get("corridorOverlap", 0.0)
        behaviour = features.get("speedBehaviour", features.get("behaviour", 0.0))
        track_coverage = features.get("trackCoverage", 0.0)
        maximum_gap_minutes = features.get("maximumGapMinutes", 0.0)
        data_quality = features.get("dataQuality", 0.0)

    origin_proximity = clamp01(origin_proximity or 0.0)
    time_overlap = clamp01(time_overlap or 0.0)
    corridor_overlap = clamp01(corridor_overlap or 0.0)
    behaviour = clamp01(behaviour or 0.0)
    data_quality = clamp01(data_quality or 0.0)
    gap = _gap_score(maximum_gap_minutes or 0.0)

    return calculate_score(
        origin_proximity=origin_proximity,
        time_overlap=time_overlap,
        corridor_trajectory=corridor_overlap,
        behaviour=behaviour,
        ais_gap=gap,
        data_quality=data_quality,
        negative_evidence=negative_evidence,
    )


def rank_candidates(
    candidates,
    top_k=None,
    limit=None,
    **kwargs,
):
    """
    Deterministic descending ranking.

    Existing score values are preserved.
    Rank is added as 1-based presentation metadata.
    """

    items = list(candidates or [])

    def candidate_score(item):
        if isinstance(item, dict):
            for key in (
                "investigativeScore",
                "investigative_priority_score",
                "investigative_priority",
                "score",
            ):
                value = item.get(key)

                if isinstance(value, (int, float)):
                    return float(value)

            nested = item.get("score")

            if isinstance(nested, dict):
                for key in (
                    "investigativeScore",
                    "investigative_score",
                    "value",
                    "score",
                ):
                    value = nested.get(key)

                    if isinstance(value, (int, float)):
                        return float(value)

        return 0.0

    ordered = sorted(
        enumerate(items),
        key=lambda pair: (
            -candidate_score(pair[1]),
            pair[0],
        ),
    )

    ranked = []

    for index, (_, item) in enumerate(ordered, start=1):
        if isinstance(item, dict):
            result = dict(item)
            result["rank"] = index
            ranked.append(result)
        else:
            ranked.append(item)

    requested = (
        top_k
        if top_k is not None
        else limit
    )

    if requested is None:
        requested = kwargs.get("top_candidates")

    if requested is not None:
        ranked = ranked[:max(0, int(requested))]

    return ranked
