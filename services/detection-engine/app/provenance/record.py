from typing import Any


def create_provenance(
    *,
    run_id: str,
    model_version: str,
    preprocessing_version: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "model_version": model_version,
        "preprocessing_version": preprocessing_version,
    }
