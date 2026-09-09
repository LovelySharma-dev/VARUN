from math import atan2, cos, radians, sin, sqrt
from datetime import datetime
from typing import Any


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:

    radius = 6371.0088

    p1 = radians(lat1)
    p2 = radians(lat2)

    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)

    a = (
        sin(dp / 2) ** 2
        + cos(p1)
        * cos(p2)
        * sin(dl / 2) ** 2
    )

    return 2 * radius * atan2(
        sqrt(a),
        sqrt(max(0.0, 1.0 - a)),
    )


def course_change_degrees(
    previous_course: float,
    current_course: float,
) -> float:

    difference = abs(current_course - previous_course) % 360.0

    return min(
        difference,
        360.0 - difference,
    )


def course_change_score(
    courses: list[float],
) -> float:

    if len(courses) < 2:
        return 0.0

    changes = [
        course_change_degrees(a, b)
        for a, b in zip(courses, courses[1:])
    ]

    mean_change = sum(changes) / len(changes)

    return clamp01(mean_change / 90.0)


def gap_quality(maximum_gap_minutes: float) -> float:

    if maximum_gap_minutes <= 30:
        return 1.0

    if maximum_gap_minutes <= 60:
        return 0.5

    return 0.2


def time_overlap_ratio(
    candidate_start: datetime,
    candidate_end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> float:

    start = max(candidate_start, window_start)
    end = min(candidate_end, window_end)

    if end <= start:
        return 0.0

    overlap = (end - start).total_seconds()
    window = max(
        1.0,
        (window_end - window_start).total_seconds(),
    )

    return clamp01(overlap / window)


def build_feature_dictionary(
    *,
    observation_count: int,
    minimum_origin_distance_km: float | None,
    origin_proximity: float,
    time_overlap: float,
    corridor_overlap: float,
    track_coverage: float,
    maximum_gap_minutes: float,
    speed_behaviour: float,
    course_behaviour: float,
    data_quality: float,
) -> dict[str, Any]:

    return {
        "observationCount": observation_count,
        "minimumOriginDistanceKm": (
            round(minimum_origin_distance_km, 4)
            if minimum_origin_distance_km is not None
            else None
        ),
        "originProximity": round(
            clamp01(origin_proximity),
            6,
        ),
        "timeOverlap": round(
            clamp01(time_overlap),
            6,
        ),
        "corridorOverlap": round(
            clamp01(corridor_overlap),
            6,
        ),
        "trackCoverage": round(
            clamp01(track_coverage),
            6,
        ),
        "maximumGapMinutes": round(
            max(0.0, maximum_gap_minutes),
            4,
        ),
        "speedBehaviour": round(
            clamp01(speed_behaviour),
            6,
        ),
        "courseBehaviour": round(
            clamp01(course_behaviour),
            6,
        ),
        "dataQuality": round(
            clamp01(data_quality),
            6,
        ),
    }
