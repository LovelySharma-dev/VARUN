from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.features import (
    AISPoint,
    extract_features,
    interpolate_track,
)


app = FastAPI(
    title="VARUN Phase 3 AIS",
    version="1.0.0",
)


# ------------------------------------------------------------
# Models
# ------------------------------------------------------------

class AISObservation(BaseModel):
    timestampUtc: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sogKnots: float | None = Field(default=None, ge=0)
    cogDegrees: float | None = Field(default=None, ge=0, le=360)


class CandidateInput(BaseModel):
    privateKey: str
    observations: list[AISObservation]

    originLatitude: float = Field(ge=-90, le=90)
    originLongitude: float = Field(ge=-180, le=180)

    originTimeStart: datetime
    originTimeEnd: datetime

    corridorOverlap: float = Field(default=0.0, ge=0, le=1)


class AnalysisRequest(BaseModel):
    contract_version: str
    case_id: str
    phase2_run_id: str
    phase3_run_id: str

    candidates: list[CandidateInput] = Field(default_factory=list)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def candidate_id(index: int) -> str:
    # Public identifier only.
    # Never expose privateKey / MMSI.
    return f"CAND-{index:03d}"


def behaviour_score(features: dict[str, Any]) -> float:
    """
    MVP behaviour component.

    Uses the currently available deterministic speed-behaviour
    feature. Missing behavioural data is neutral, not suspicious.
    """
    value = features.get("speedBehaviour")

    if value is None:
        return 0.0

    return max(0.0, min(1.0, float(value)))


def gap_score(features: dict[str, Any]) -> float:
    """
    AIS gap is treated as a limited evidence component.

    A gap is NOT automatically interpreted as intentional shutdown.
    """
    gap = float(features.get("maximumGapMinutes", 0.0))

    if gap <= 5:
        return 1.0
    if gap <= 15:
        return 0.8
    if gap <= 30:
        return 0.6
    if gap <= 60:
        return 0.3

    return 0.0


def negative_evidence(features: dict[str, Any]) -> tuple[float, list[str]]:
    """
    Deterministic negative evidence.

    Maximum deduction is 4 points, matching the project
    score-v1 design constraint.
    """

    penalty = 0.0
    reasons: list[str] = []

    distance = features.get("minimumOriginDistanceKm")
    overlap = float(features.get("timeOverlap", 0.0))
    corridor = float(features.get("corridorOverlap", 0.0))

    if distance is not None and float(distance) > 20:
        penalty += 2.0
        reasons.append(
            "Minimum distance exceeds the defined 20 km relevance threshold."
        )

    if overlap <= 0:
        penalty += 1.0
        reasons.append(
            "No temporal overlap with the Phase-2 release window."
        )

    if corridor <= 0:
        penalty += 1.0
        reasons.append(
            "Track does not intersect the supplied hindcast corridor."
        )

    return min(penalty, 4.0), reasons


def score_candidate(features: dict[str, Any]) -> dict[str, Any]:
    """
    Explainable score-v1.

    Maximum positive contribution:
      Origin proximity   30
      Time overlap       25
      Corridor match     20
      Behaviour          10
      AIS gap             5
      Data quality       10
      --------------------------------
      Positive total     100

    Negative evidence is a deduction of up to 4.

    This is an investigative relevance score,
    NOT a probability of guilt.
    """

    proximity = float(features.get("originProximity", 0.0))
    temporal = float(features.get("timeOverlap", 0.0))
    corridor = float(features.get("corridorOverlap", 0.0))
    behaviour = behaviour_score(features)
    gap = gap_score(features)
    quality = float(features.get("dataQuality", 0.0))

    components = [
        {
            "componentName": "ORIGIN_PROXIMITY",
            "rawValue": features.get("minimumOriginDistanceKm"),
            "normalizedValue": round(proximity, 6),
            "weight": 30,
            "contribution": round(proximity * 30, 4),
            "isDeduction": False,
            "reason": "Normalized minimum distance to Phase-2 origin.",
        },
        {
            "componentName": "TIME_OVERLAP",
            "rawValue": features.get("timeOverlap"),
            "normalizedValue": round(temporal, 6),
            "weight": 25,
            "contribution": round(temporal * 25, 4),
            "isDeduction": False,
            "reason": "Temporal overlap with Phase-2 release window.",
        },
        {
            "componentName": "CORRIDOR_MATCH",
            "rawValue": features.get("corridorOverlap"),
            "normalizedValue": round(corridor, 6),
            "weight": 20,
            "contribution": round(corridor * 20, 4),
            "isDeduction": False,
            "reason": "Overlap with supplied Phase-2 hindcast corridor.",
        },
        {
            "componentName": "BEHAVIOUR",
            "rawValue": features.get("speedBehaviour"),
            "normalizedValue": round(behaviour, 6),
            "weight": 10,
            "contribution": round(behaviour * 10, 4),
            "isDeduction": False,
            "reason": "Deterministic speed-behaviour feature.",
        },
        {
            "componentName": "AIS_GAP",
            "rawValue": features.get("maximumGapMinutes"),
            "normalizedValue": round(gap, 6),
            "weight": 5,
            "contribution": round(gap * 5, 4),
            "isDeduction": False,
            "reason": "Limited AIS continuity evidence.",
        },
        {
            "componentName": "DATA_QUALITY",
            "rawValue": features.get("dataQuality"),
            "normalizedValue": round(quality, 6),
            "weight": 10,
            "contribution": round(quality * 10, 4),
            "isDeduction": False,
            "reason": "AIS observation and track quality.",
        },
    ]

    positive_total = sum(
        float(component["contribution"])
        for component in components
    )

    negative_total, negative_reasons = negative_evidence(features)

    final_score = max(
        0.0,
        min(100.0, positive_total - negative_total),
    )

    return {
        "scoreVersion": "score-v1",
        "investigativeScore": round(final_score, 4),
        "positiveTotal": round(positive_total, 4),
        "negativeTotal": round(negative_total, 4),
        "components": components,
        "negativeEvidence": negative_reasons,
    }


def public_features(features: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Public evidence projection.

    No MMSI/private identity.
    """

    mapping = [
        (
            "ORIGIN_PROXIMITY",
            features.get("minimumOriginDistanceKm"),
            features.get("originProximity"),
            "km",
            "Distance to possible Phase-2 origin region.",
        ),
        (
            "TIME_OVERLAP",
            features.get("timeOverlap"),
            features.get("timeOverlap"),
            "ratio",
            "Overlap with possible release window.",
        ),
        (
            "CORRIDOR_MATCH",
            features.get("corridorOverlap"),
            features.get("corridorOverlap"),
            "ratio",
            "Track overlap with supplied hindcast corridor.",
        ),
        (
            "TRACK_COVERAGE",
            features.get("trackCoverage"),
            features.get("trackCoverage"),
            "ratio",
            "Observed AIS track coverage.",
        ),
        (
            "AIS_GAP",
            features.get("maximumGapMinutes"),
            gap_score(features),
            "minutes",
            "Maximum observed AIS reporting gap.",
        ),
        (
            "SPEED_BEHAVIOUR",
            features.get("speedBehaviour"),
            features.get("speedBehaviour"),
            "ratio",
            "Deterministic speed-behaviour indicator.",
        ),
        (
            "DATA_QUALITY",
            features.get("dataQuality"),
            features.get("dataQuality"),
            "ratio",
            "Overall AIS data quality.",
        ),
    ]

    result = []

    for name, raw, normalized, unit, reason in mapping:
        result.append(
            {
                "featureName": name,
                "featureVersion": "1.0.0",
                "rawValue": raw,
                "normalizedValue": normalized,
                "unit": unit,
                "availability": (
                    "AVAILABLE"
                    if raw is not None
                    else "UNAVAILABLE"
                ),
                "reason": reason,
                "provenance": {
                    "source": "ais_observations",
                    "synthetic": True,
                },
            }
        )

    return result


def analyse_candidate(
    candidate: CandidateInput,
    public_index: int,
) -> dict[str, Any]:

    points = [
        AISPoint(
            timestamp_utc=utc(point.timestampUtc),
            latitude=point.latitude,
            longitude=point.longitude,
            sog_knots=point.sogKnots,
            cog_degrees=point.cogDegrees,
        )
        for point in candidate.observations
    ]

    features = extract_features(
        points=points,
        origin_latitude=candidate.originLatitude,
        origin_longitude=candidate.originLongitude,
        origin_time_start=utc(candidate.originTimeStart),
        origin_time_end=utc(candidate.originTimeEnd),
        corridor_overlap=candidate.corridorOverlap,
    )

    reconstructed = interpolate_track(points)

    score = score_candidate(features)

    warnings: list[str] = []

    if features["observationCount"] == 0:
        warnings.append("No AIS observations available.")

    if features["maximumGapMinutes"] > 30:
        warnings.append(
            f'{features["maximumGapMinutes"]:.1f}-minute AIS reporting gap observed. '
            "The available data does not establish its cause."
        )

    if features["trackCoverage"] < 0.75:
        warnings.append(
            "AIS track coverage is incomplete; confidence should be reduced."
        )

    if features["dataQuality"] < 0.5:
        warnings.append(
            "Low AIS data quality limits interpretation."
        )

    if not reconstructed:
        warnings.append("Track reconstruction unavailable.")

    return {
        "candidateId": candidate_id(public_index),
        "publicMetadata": {
            "source": "AIS_FILTER",
            "dataOrigin": "SYNTHETIC",
            "candidateLabel": "Synthetic AIS candidate",
        },
        "score": {
            **score,
            "rank": None,
            "confidence": None,
            "confidenceCap": None,
            "explanation": (
                "Investigative relevance score calculated from "
                "spatio-temporal, trajectory and data-quality evidence."
            ),
        },
        "features": public_features(features),
        "track": reconstructed,
        "evidence": [
            {
                "eventCode": "AIS_POINT_COUNT",
                "rawValue": features["observationCount"],
                "unit": "count",
                "explanation": (
                    f'{features["observationCount"]} valid AIS observations available.'
                ),
                "details": {
                    "synthetic": True,
                },
            },
            {
                "eventCode": "TRACK_COVERAGE",
                "rawValue": features["trackCoverage"],
                "unit": "ratio",
                "explanation": "Observed AIS track coverage.",
                "details": {
                    "synthetic": True,
                },
            },
            {
                "eventCode": "AIS_GAP",
                "rawValue": features["maximumGapMinutes"],
                "unit": "minutes",
                "explanation": (
                    "Maximum interval between consecutive AIS observations."
                ),
                "details": {
                    "synthetic": True,
                },
            },
        ],
        "warnings": warnings,
    }


# ------------------------------------------------------------
# Health
# ------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "phase3-ais",
        "version": "1.0.0",
    }


# ------------------------------------------------------------
# Phase-3 analysis
# ------------------------------------------------------------

@app.post("/v1/phase3/run")
@app.post("/internal/v1/analysis-runs")
def analyse(request: AnalysisRequest):

    if request.contract_version != "phase2-to-phase3-v1":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PHASE2_CONTRACT",
                "message": (
                    "Expected phase2-to-phase3-v1 contract."
                ),
            },
        )

    if not request.candidates:
        return {
            "runId": request.phase3_run_id,
            "caseId": request.case_id,
            "phase": "PHASE3",
            "status": "NO_CANDIDATES_FOUND",
            "dataOrigin": "SYNTHETIC",
            "candidates": [],
            "disclaimer": (
                "Candidate ranking supports investigation and "
                "does not constitute legal attribution or proof "
                "of responsibility."
            ),
        }

    results = []

    for index, candidate in enumerate(request.candidates, start=1):
        results.append(
            analyse_candidate(
                candidate=candidate,
                public_index=index,
            )
        )

    # Deterministic ranking:
    # score DESC, then candidateId ASC.
    results.sort(
        key=lambda item: (
            -float(item["score"]["investigativeScore"]),
            item["candidateId"],
        )
    )

    top_three = results[:3]

    for rank, candidate in enumerate(top_three, start=1):
        candidate["score"]["rank"] = rank

    return {
        "runId": request.phase3_run_id,
        "caseId": request.case_id,
        "phase": "PHASE3",
        "status": "COMPLETED",
        "dataOrigin": "SYNTHETIC",
        "rankingMethod": "explainable-score-v1",
        "candidates": top_three,
        "disclaimer": (
            "Candidate ranking supports investigation and "
            "does not constitute legal attribution or proof "
            "of responsibility."
        ),
    }

