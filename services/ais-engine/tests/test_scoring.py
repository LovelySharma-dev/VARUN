import pytest

from app.core.scientific import (
    course_change_degrees,
    course_change_score,
    gap_quality,
)
from app.core.scoring import (
    calculate_score,
    rank_candidates,
)


def test_course_change_wraparound():
    assert course_change_degrees(
        359,
        1,
    ) == 2


def test_course_change_score():
    result = course_change_score([
        0,
        10,
        20,
    ])

    assert result > 0
    assert result <= 1


def test_gap_quality():
    assert gap_quality(10) == 1.0
    assert gap_quality(45) == 0.5
    assert gap_quality(90) == 0.2


def test_score_is_deterministic():

    features = {
        "originProximity": 1.0,
        "timeOverlap": 1.0,
        "corridorOverlap": 1.0,
        "speedBehaviour": 0.5,
        "dataQuality": 1.0,
        "maximumGapMinutes": 10,
    }

    first = calculate_score(features)
    second = calculate_score(features)

    assert first == second


def test_negative_evidence_reduces_score():

    good = {
        "originProximity": 1.0,
        "timeOverlap": 1.0,
        "corridorOverlap": 1.0,
        "speedBehaviour": 0.5,
        "dataQuality": 1.0,
        "maximumGapMinutes": 10,
    }

    poor = {
        **good,
        "timeOverlap": 0.0,
        "corridorOverlap": 0.0,
        "maximumGapMinutes": 90,
    }

    assert (
        calculate_score(good)["score"]
        >
        calculate_score(poor)["score"]
    )


def test_top_three_deterministic():

    candidates = [
        {
            "candidateId": "CAND-003",
            "features": {
                "originProximity": 1.0,
                "timeOverlap": 1.0,
                "corridorOverlap": 1.0,
                "speedBehaviour": 0.4,
                "dataQuality": 1.0,
                "maximumGapMinutes": 10,
            },
        },
        {
            "candidateId": "CAND-002",
            "features": {
                "originProximity": 0.5,
                "timeOverlap": 0.5,
                "corridorOverlap": 0.5,
                "speedBehaviour": 0.4,
                "dataQuality": 0.8,
                "maximumGapMinutes": 20,
            },
        },
        {
            "candidateId": "CAND-001",
            "features": {
                "originProximity": 0.2,
                "timeOverlap": 0.2,
                "corridorOverlap": 0.2,
                "speedBehaviour": 0.2,
                "dataQuality": 0.5,
                "maximumGapMinutes": 70,
            },
        },
    ]

    for candidate in candidates:
        candidate["provenance"] = {
            "source": "ais_track_segments",
            "provider": "synthetic-test",
            "synthetic": True,
        }

    result = rank_candidates(candidates)

    assert len(result) == 3
    assert result[0]["candidateId"] == "CAND-003"
    assert result[0]["rank"] == 1
    assert result[1]["rank"] == 2
    assert result[2]["rank"] == 3


def test_public_candidate_never_contains_mmsi():
    candidate = {
        "candidateId": "CAND-001",
        "features": {},
        "provenance": {
            "source": "ais_track_segments",
            "provider": "test",
            "synthetic": True,
        },
    }

    assert "mmsi" not in candidate
