from __future__ import annotations

from typing import Any


def rank_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    ordered = sorted(
        candidates,
        key=lambda item: (
            -float(item.get("score", 0.0)),
            str(item.get("candidateId", "")),
        ),
    )

    ranked: list[dict[str, Any]] = []

    for index, candidate in enumerate(ordered, start=1):
        result = dict(candidate)
        result["rank"] = index
        ranked.append(result)

    return ranked
