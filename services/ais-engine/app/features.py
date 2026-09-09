from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Iterable


@dataclass(frozen=True)
class AISPoint:
    timestamp_utc: datetime
    latitude: float
    longitude: float
    sog_knots: float | None = None
    cog_degrees: float | None = None


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius_km = 6371.0088

    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)

    a = (
        sin(dp / 2) ** 2
        + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    )

    return 2 * earth_radius_km * atan2(
        sqrt(a),
        sqrt(max(0.0, 1.0 - a)),
    )


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def proximity_normalized(distance_km: float) -> float:
    if distance_km <= 2:
        return 1.0
    if distance_km <= 5:
        return 0.80
    if distance_km <= 10:
        return 0.50
    if distance_km <= 20:
        return 0.20
    return 0.0


def time_overlap_normalized(
    candidate_start: datetime,
    candidate_end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> float:
    start = max(candidate_start, window_start)
    end = min(candidate_end, window_end)

    if end <= start:
        return 0.0

    overlap_seconds = (end - start).total_seconds()
    window_seconds = max(
        1.0,
        (window_end - window_start).total_seconds(),
    )

    return clamp01(overlap_seconds / window_seconds)


def track_coverage(points: Iterable[AISPoint]) -> float:
    ordered = sorted(points, key=lambda p: p.timestamp_utc)

    if len(ordered) < 2:
        return 0.0

    expected = (
        ordered[-1].timestamp_utc
        - ordered[0].timestamp_utc
    ).total_seconds()

    observed = 0.0

    for first, second in zip(ordered, ordered[1:]):
        gap = (second.timestamp_utc - first.timestamp_utc).total_seconds()

        if gap <= 30 * 60:
            observed += gap

    if expected <= 0:
        return 1.0

    return clamp01(observed / expected)


def maximum_gap_minutes(points: Iterable[AISPoint]) -> float:
    ordered = sorted(points, key=lambda p: p.timestamp_utc)

    if len(ordered) < 2:
        return 0.0

    return max(
        (
            second.timestamp_utc - first.timestamp_utc
        ).total_seconds() / 60.0
        for first, second in zip(ordered, ordered[1:])
    )


def interpolate_track(
    points: Iterable[AISPoint],
    max_gap_minutes: float = 30.0,
) -> list[dict[str, Any]]:
    ordered = sorted(points, key=lambda p: p.timestamp_utc)

    result: list[dict[str, Any]] = []

    for index, point in enumerate(ordered):
        result.append(
            {
                "timestampUtc": point.timestamp_utc.astimezone(
                    timezone.utc
                ).isoformat(),
                "latitude": point.latitude,
                "longitude": point.longitude,
                "sogKnots": point.sog_knots,
                "cogDegrees": point.cog_degrees,
                "segmentType": "OBSERVED",
            }
        )

        if index == len(ordered) - 1:
            continue

        nxt = ordered[index + 1]
        gap_seconds = (
            nxt.timestamp_utc - point.timestamp_utc
        ).total_seconds()

        if gap_seconds <= 0:
            continue

        gap_minutes = gap_seconds / 60.0

        if gap_minutes > max_gap_minutes:
            continue

        steps = int(gap_minutes // 5)

        for step in range(1, steps):
            ratio = step / steps

            timestamp = point.timestamp_utc + (
                nxt.timestamp_utc - point.timestamp_utc
            ) * ratio

            latitude = point.latitude + (
                nxt.latitude - point.latitude
            ) * ratio

            longitude = point.longitude + (
                nxt.longitude - point.longitude
            ) * ratio

            result.append(
                {
                    "timestampUtc": timestamp.astimezone(
                        timezone.utc
                    ).isoformat(),
                    "latitude": latitude,
                    "longitude": longitude,
                    "sogKnots": None,
                    "cogDegrees": None,
                    "segmentType": "INTERPOLATED",
                }
            )

    result.sort(key=lambda item: item["timestampUtc"])
    return result


def extract_features(
    points: Iterable[AISPoint],
    origin_latitude: float,
    origin_longitude: float,
    origin_time_start: datetime,
    origin_time_end: datetime,
    corridor_overlap: float = 0.0,
) -> dict[str, Any]:
    ordered = sorted(points, key=lambda p: p.timestamp_utc)

    if not ordered:
        return {
            "observationCount": 0,
            "minimumOriginDistanceKm": None,
            "timeOverlap": 0.0,
            "trackCoverage": 0.0,
            "maximumGapMinutes": 0.0,
            "corridorOverlap": clamp01(corridor_overlap),
            "speedBehaviour": 0.0,
            "dataQuality": 0.0,
        }

    distances = [
        haversine_km(
            point.latitude,
            point.longitude,
            origin_latitude,
            origin_longitude,
        )
        for point in ordered
    ]

    minimum_distance = min(distances)

    candidate_start = ordered[0].timestamp_utc
    candidate_end = ordered[-1].timestamp_utc

    speeds = [
        point.sog_knots
        for point in ordered
        if point.sog_knots is not None
    ]

    if len(speeds) >= 2:
        mean_speed = sum(speeds) / len(speeds)
        variation = sum(
            abs(speed - mean_speed)
            for speed in speeds
        ) / len(speeds)

        speed_behaviour = clamp01(variation / 10.0)
    else:
        speed_behaviour = 0.0

    coverage = track_coverage(ordered)
    max_gap = maximum_gap_minutes(ordered)

    gap_quality = 1.0
    if max_gap > 60:
        gap_quality = 0.2
    elif max_gap > 30:
        gap_quality = 0.5

    data_quality = clamp01(
        0.5 * coverage
        + 0.3 * min(len(ordered) / 10.0, 1.0)
        + 0.2 * gap_quality
    )

    return {
        "observationCount": len(ordered),
        "minimumOriginDistanceKm": round(minimum_distance, 4),
        "originProximity": round(
            proximity_normalized(minimum_distance),
            6,
        ),
        "timeOverlap": round(
            time_overlap_normalized(
                candidate_start,
                candidate_end,
                origin_time_start,
                origin_time_end,
            ),
            6,
        ),
        "corridorOverlap": round(
            clamp01(corridor_overlap),
            6,
        ),
        "trackCoverage": round(coverage, 6),
        "maximumGapMinutes": round(max_gap, 4),
        "speedBehaviour": round(speed_behaviour, 6),
        "dataQuality": round(data_quality, 6),
    }
