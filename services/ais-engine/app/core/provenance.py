from typing import Any


REQUIRED_PROVENANCE_FIELDS = {
    "source",
    "provider",
    "synthetic",
}


def validate_provenance(
    provenance: dict[str, Any],
) -> list[str]:

    errors = []

    for field in REQUIRED_PROVENANCE_FIELDS:
        if field not in provenance:
            errors.append(
                f"Missing provenance field: {field}"
            )

    if "synthetic" in provenance and not isinstance(
        provenance["synthetic"],
        bool,
    ):
        errors.append(
            "Provenance field 'synthetic' must be boolean."
        )

    return errors


def validate_candidate(candidate: dict[str, Any]) -> list[str]:

    errors = []

    if not candidate.get("candidateId"):
        errors.append("candidateId is required.")

    if not isinstance(
        candidate.get("features"),
        dict,
    ):
        errors.append("features object is required.")

    provenance = candidate.get("provenance")

    if not isinstance(provenance, dict):
        errors.append("provenance object is required.")
    else:
        errors.extend(
            validate_provenance(provenance)
        )

    # Privacy: never accept raw MMSI in public candidate objects.
    if "mmsi" in candidate:
        errors.append(
            "MMSI must not be present in public candidate response."
        )

    if "groundTruth" in candidate:
        errors.append(
            "Ground truth must not be present in candidate response."
        )

    return errors
