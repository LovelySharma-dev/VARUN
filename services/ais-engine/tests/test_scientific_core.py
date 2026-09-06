from datetime import datetime, timedelta, timezone

from app.core.ais_core import (
    AISRecord,
    behaviour_features,
    detect_impossible_jumps,
    interpolate_track,
)
from app.core.scoring import rank_candidates, score_candidate


def point(minutes, lat, lon, speed=5.0, cog=90.0):
    return AISRecord(
        timestamp_utc=datetime(
            2026,
            8,
            20,
            4,
            30,
            tzinfo=timezone.utc,
        ) + timedelta(minutes=minutes),
        latitude=lat,
        longitude=lon,
        sog_knots=speed,
        cog_degrees=cog,
    )


def test_impossible_jump():
    a = point(0, 20.0, 70.0)
    b = point(1, 30.0, 80.0)

    result = detect_impossible_jumps([a, b])

    assert len(result) == 1


def test_interpolation_marks_segments():
    a = point(0, 20.0, 70.0)
    b = point(15, 20.1, 70.1)

    result = interpolate_track([a, b])

    assert result[0]["segmentType"] == "OBSERVED"
    assert any(
        item["segmentType"] == "INTERPOLATED"
        for item in result
    )


def test_behaviour_features():
    records = [
        point(0, 20.0, 70.0, 2.0, 0),
        point(5, 20.001, 70.001, 8.0, 180),
        point(10, 20.001, 70.001, 1.0, 0),
    ]

    result = behaviour_features(records)

    assert 0 <= result["behaviour"] <= 1
    assert 0 <= result["headingAnomaly"] <= 1


def test_score_deterministic():
    args = dict(
        origin_proximity=1,
        time_overlap=1,
        corridor_overlap=0.8,
        behaviour=0.5,
        track_coverage=1,
        maximum_gap_minutes=5,
        data_quality=1,
        negative_evidence=0,
    )

    first = score_candidate(**args)
    second = score_candidate(**args)

    assert first == second
    assert 0 <= first["score"] <= 100


def test_ranking_deterministic():
    candidates = [
        {"candidateId": "B", "score": 80},
        {"candidateId": "A", "score": 90},
    ]

    result = rank_candidates(candidates)

    assert result[0]["candidateId"] == "A"
    assert result[0]["rank"] == 1
    assert result[1]["rank"] == 2
