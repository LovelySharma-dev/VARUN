from __future__ import annotations

from datetime import datetime
from typing import Any


REQUIRED_FIELDS = (
    "timestampUtc",
    "latitude",
    "longitude",
)


def validate_point(point: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in point:
            errors.append(f"MISSING_{field.upper()}")

    if "latitude" in point:
        lat = float(point["latitude"])
        if lat < -90 or lat > 90:
            errors.append("INVALID_LATITUDE")

    if "longitude" in point:
        lon = float(point["longitude"])
        if lon < -180 or lon > 180:
            errors.append("INVALID_LONGITUDE")

    return errors


def audit_points(
    points: list[dict[str, Any]],
    *,
    dataset: str,
    provider: str,
    synthetic: bool,
) -> dict[str, Any]:

    valid = 0
    invalid = 0
    errors: list[dict[str, Any]] = []

    for index, point in enumerate(points):
        point_errors = validate_point(point)

        if point_errors:
            invalid += 1
            errors.append(
                {
                    "index": index,
                    "errors": point_errors,
                }
            )
        else:
            valid += 1

    total = len(points)

    quality = (
        valid / total
        if total > 0
        else 0.0
    )

    return {
        "totalPoints": total,
        "validPoints": valid,
        "invalidPoints": invalid,
        "quality": round(quality, 6),
        "errors": errors,
        "provenance": {
            "dataset": dataset,
            "provider": provider,
            "synthetic": synthetic,
        },
    }
