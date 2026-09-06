from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, degrees, radians, sin, sqrt
from typing import Any, Iterable


@dataclass(frozen=True)
class AISRecord:
    timestamp_utc: datetime
    latitude: float
    longitude: float
    sog_knots: float | None = None
    cog_degrees: float | None = None
    vessel_type: str | None = None
    source: str = "ais"
    synthetic: bool = False
    mmsi: str | None = None


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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
        + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    )

    return 2 * radius * atan2(
        sqrt(a),
        sqrt(max(0.0, 1.0 - a)),
    )


def validate_coordinate(latitude: float, longitude: float) -> bool:
    return (
        -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
    )


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def clean_records(records: Iterable[AISRecord]) -> tuple[list[AISRecord], dict[str, int]]:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    valid: list[AISRecord] = []
    rejected = {
        "invalidCoordinates": 0,
        "duplicateMessages": 0,
        "invalidTimestamp": 0,
        "invalidSpeed": 0,
    }

    seen: set[tuple[Any, ...]] = set()

    for record in ordered:
        timestamp = normalize_timestamp(record.timestamp_utc)

        if not validate_coordinate(record.latitude, record.longitude):
            rejected["invalidCoordinates"] += 1
            continue

        if record.sog_knots is not None:
            if record.sog_knots < 0 or record.sog_knots > 80:
                rejected["invalidSpeed"] += 1
                continue

        key = (
            timestamp,
            round(record.latitude, 6),
            round(record.longitude, 6),
            record.sog_knots,
            record.cog_degrees,
        )

        if key in seen:
            rejected["duplicateMessages"] += 1
            continue

        seen.add(key)

        valid.append(
            AISRecord(
                timestamp_utc=timestamp,
                latitude=record.latitude,
                longitude=record.longitude,
                sog_knots=record.sog_knots,
                cog_degrees=record.cog_degrees,
                vessel_type=record.vessel_type,
                source=record.source,
                synthetic=record.synthetic,
                mmsi=record.mmsi,
            )
        )

    return valid, rejected


def implied_speed_knots(first: AISRecord, second: AISRecord) -> float:
    seconds = (
        normalize_timestamp(second.timestamp_utc)
        - normalize_timestamp(first.timestamp_utc)
    ).total_seconds()

    if seconds <= 0:
        return 0.0

    distance_km = haversine_km(
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    )

    return distance_km / seconds * 3600.0 / 1.852


def detect_impossible_jumps(
    records: Iterable[AISRecord],
    max_implied_speed_knots: float = 60.0,
) -> list[dict[str, Any]]:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    suspicious = []

    for first, second in zip(ordered, ordered[1:]):
        speed = implied_speed_knots(first, second)

        if speed > max_implied_speed_knots:
            suspicious.append(
                {
                    "from": normalize_timestamp(first.timestamp_utc).isoformat(),
                    "to": normalize_timestamp(second.timestamp_utc).isoformat(),
                    "impliedSpeedKnots": round(speed, 4),
                    "thresholdKnots": max_implied_speed_knots,
                }
            )

    return suspicious


def maximum_gap_minutes(records: Iterable[AISRecord]) -> float:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    if len(ordered) < 2:
        return 0.0

    return max(
        (
            normalize_timestamp(second.timestamp_utc)
            - normalize_timestamp(first.timestamp_utc)
        ).total_seconds() / 60.0
        for first, second in zip(ordered, ordered[1:])
    )


def track_coverage(
    records: Iterable[AISRecord],
    expected_interval_minutes: float = 5.0,
    coverage_gap_limit_minutes: float = 30.0,
) -> float:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    if len(ordered) < 2:
        return 0.0

    total = (
        normalize_timestamp(ordered[-1].timestamp_utc)
        - normalize_timestamp(ordered[0].timestamp_utc)
    ).total_seconds() / 60.0

    if total <= 0:
        return 1.0

    covered = 0.0

    for first, second in zip(ordered, ordered[1:]):
        gap = (
            normalize_timestamp(second.timestamp_utc)
            - normalize_timestamp(first.timestamp_utc)
        ).total_seconds() / 60.0

        if gap <= coverage_gap_limit_minutes:
            covered += gap

    return clamp01(covered / total)


def interpolate_track(
    records: Iterable[AISRecord],
    max_gap_minutes: float = 30.0,
    step_minutes: float = 5.0,
) -> list[dict[str, Any]]:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    output: list[dict[str, Any]] = []

    for index, current in enumerate(ordered):
        current_time = normalize_timestamp(current.timestamp_utc)

        output.append(
            {
                "timestampUtc": current_time.isoformat(),
                "latitude": current.latitude,
                "longitude": current.longitude,
                "sogKnots": current.sog_knots,
                "cogDegrees": current.cog_degrees,
                "segmentType": "OBSERVED",
            }
        )

        if index == len(ordered) - 1:
            continue

        nxt = ordered[index + 1]
        next_time = normalize_timestamp(nxt.timestamp_utc)

        gap_minutes = (
            next_time - current_time
        ).total_seconds() / 60.0

        if gap_minutes <= 0 or gap_minutes > max_gap_minutes:
            continue

        steps = int(gap_minutes // step_minutes)

        for step in range(1, steps):
            ratio = step / (gap_minutes / step_minutes)

            output.append(
                {
                    "timestampUtc": (
                        current_time
                        + (next_time - current_time) * ratio
                    ).isoformat(),
                    "latitude": current.latitude
                    + (nxt.latitude - current.latitude) * ratio,
                    "longitude": current.longitude
                    + (nxt.longitude - current.longitude) * ratio,
                    "sogKnots": None,
                    "cogDegrees": None,
                    "segmentType": "INTERPOLATED",
                }
            )

    output.sort(key=lambda item: item["timestampUtc"])

    return output


def heading_delta_degrees(first: float, second: float) -> float:
    delta = abs((second - first) % 360.0)
    return min(delta, 360.0 - delta)


def behaviour_features(
    records: Iterable[AISRecord],
) -> dict[str, float]:
    ordered = sorted(
        records,
        key=lambda record: normalize_timestamp(record.timestamp_utc),
    )

    speeds = [
        record.sog_knots
        for record in ordered
        if record.sog_knots is not None
    ]

    headings = [
        record.cog_degrees
        for record in ordered
        if record.cog_degrees is not None
    ]

    if len(speeds) >= 2:
        mean_speed = sum(speeds) / len(speeds)

        speed_variation = sum(
            abs(speed - mean_speed)
            for speed in speeds
        ) / len(speeds)

        speed_anomaly = clamp01(speed_variation / 10.0)
    else:
        speed_anomaly = 0.0

    if len(headings) >= 2:
        heading_changes = [
            heading_delta_degrees(first, second)
            for first, second in zip(headings, headings[1:])
        ]

        heading_anomaly = clamp01(
            (sum(heading_changes) / len(heading_changes)) / 90.0
        )
    else:
        heading_anomaly = 0.0

    loitering = 0.0

    if len(ordered) >= 3:
        stationary = 0

        for first, second in zip(ordered, ordered[1:]):
            if (
                haversine_km(
                    first.latitude,
                    first.longitude,
                    second.latitude,
                    second.longitude,
                ) < 0.25
                and (
                    first.sog_knots is None
                    or first.sog_knots < 2.0
                )
            ):
                stationary += 1

        loitering = clamp01(
            stationary / max(1, len(ordered) - 1)
        )

    combined = clamp01(
        0.5 * speed_anomaly
        + 0.3 * heading_anomaly
        + 0.2 * loitering
    )

    return {
        "speedAnomaly": round(speed_anomaly, 6),
        "headingAnomaly": round(heading_anomaly, 6),
        "loitering": round(loitering, 6),
        "behaviour": round(combined, 6),
    }


def filter_summary(
    total: int,
    time_filtered: int,
    spatially_filtered: int,
    quality_eligible: int,
) -> dict[str, int]:
    return {
        "totalVessels": total,
        "timeFiltered": time_filtered,
        "spatiallyFiltered": spatially_filtered,
        "qualityEligible": quality_eligible,
    }


def geojson_track(track: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "LineString",
        "coordinates": [
            [
                item["longitude"],
                item["latitude"],
            ]
            for item in track
        ],
    }


def public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """
    Public projection deliberately excludes MMSI and other direct identity.
    """

    forbidden = {
        "mmsi",
        "MMSI",
        "imo",
        "IMO",
        "groundTruth",
        "ground_truth",
        "targetLabel",
        "target_label",
    }

    return {
        key: value
        for key, value in candidate.items()
        if key not in forbidden
    }
