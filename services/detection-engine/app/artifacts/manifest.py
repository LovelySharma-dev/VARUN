from typing import Any


def create_manifest(
    *,
    run_id: str,
    artifacts: list[Any],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "artifacts": artifacts,
    }
