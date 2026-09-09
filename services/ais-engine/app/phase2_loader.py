
# This code will completly read or validate all the folder of phase 2

import json
from pathlib import Path
from typing import Any

from app.schemas import Phase2ToPhase3Contract


REQUIRED_PHASE2_FILES = [
    "summary.json",
    "search_window.json",
    "backward_tracks.geojson",
    "origin_50.geojson",
    "origin_75.geojson",
    "origin_90.geojson",
    "release_time_scores.csv",
    "forward_reconstruction.geojson",
    "reconstruction_metrics.json",
    "run_config.json",
    "validation_report.json",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path.name}") from exc


def validate_required_files(folder: Path) -> None:
    missing_files = [
        filename
        for filename in REQUIRED_PHASE2_FILES
        if not (folder / filename).exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Missing Phase 2 files: " + ", ".join(missing_files)
        )


def load_geojson_feature(path: Path) -> dict[str, Any]:
    data = read_json(path)

    if data.get("type") == "Feature":
        return data

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])

        if len(features) == 1:
            return features[0]

        raise ValueError(
            f"{path.name} must contain exactly one contour Feature"
        )

    raise ValueError(
        f"{path.name} must be GeoJSON Feature or FeatureCollection"
    )


def build_contract_payload(folder: Path) -> dict[str, Any]:
    search_window = read_json(folder / "search_window.json")
    summary = read_json(folder / "summary.json")
    reconstruction = read_json(folder / "reconstruction_metrics.json")
    run_config = read_json(folder / "run_config.json")
    validation = read_json(folder / "validation_report.json")

    payload = dict(search_window)

    # Separate Phase 2 output files ko canonical contract mein attach karta hai.
    payload.setdefault(
        "origin_contours",
        {
            "density_50": load_geojson_feature(folder / "origin_50.geojson"),
            "density_75": load_geojson_feature(folder / "origin_75.geojson"),
            "density_90": load_geojson_feature(folder / "origin_90.geojson"),
        },
    )

    payload.setdefault("reconstruction_metrics", reconstruction)
    payload.setdefault("forcing_uncertainty", {})
    payload.setdefault("ranked_origin_regions", [])
    payload.setdefault("alternative_modes", [])
    payload.setdefault("dashboard_artifacts", {})
    payload.setdefault("warnings", validation.get("warnings", []))

    payload.setdefault(
        "provenance",
        {
            "summary": summary,
            "run_config": run_config,
            "validation_status": validation.get("status", "UNKNOWN"),
        },
    )

    return payload


def load_phase2_bundle(
    phase2_folder: str | Path,
) -> Phase2ToPhase3Contract:
    folder = Path(phase2_folder).resolve()

    if not folder.exists():
        raise FileNotFoundError(f"Phase 2 folder not found: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    validate_required_files(folder)

    payload = build_contract_payload(folder)

    return Phase2ToPhase3Contract.model_validate(payload)