from __future__ import annotations

from typing import Any


def calculate_negative_evidence(
    *,
    expected_corridor_overlap: float,
    actual_corridor_overlap: float,
    expected_time_overlap: float,
    actual_time_overlap: float,
    maximum_gap_minutes: float,
) -> dict[str, Any]:

    corridor_mismatch = max(
        0.0,
        expected_corridor_overlap - actual_corridor_overlap,
    )

    time_mismatch = max(
        0.0,
        expected_time_overlap - actual_time_overlap,
    )

    gap_signal = 0.0

    if maximum_gap_minutes >= 60:
        gap_signal = 1.0
    elif maximum_gap_minutes >= 30:
        gap_signal = 0.5

    negative_evidence = min(
        1.0,
        0.5 * corridor_mismatch
        + 0.3 * time_mismatch
        + 0.2 * gap_signal,
    )

    return {
        "negativeEvidence": round(negative_evidence, 6),
        "corridorMismatch": round(corridor_mismatch, 6),
        "timeMismatch": round(time_mismatch, 6),
        "gapSignal": round(gap_signal, 6),
    }
