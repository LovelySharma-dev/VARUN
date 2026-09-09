"""Atomic, privacy-safe output writer for Phase 3 attribution results."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.attribution_pipeline import Phase3AttributionResult


PUBLIC_ARTIFACT_FILES = [
    "ranked_candidates.json",
    "candidate_features.csv",
    "candidate_tracks.geojson",
    "dark_gap_events.json",
    "phase3_summary.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(
        dataframe.to_json(
            orient="records",
            date_format="iso",
            date_unit="ms",
        )
    )


def _candidate_tracks_geojson(
    result: Phase3AttributionResult,
) -> dict[str, Any]:
    tracks = result.candidate_filter.candidate_tracks.copy()
    ranks = dict(
        zip(
            result.ranking.rankings["candidate_id"],
            result.ranking.rankings["rank"],
            strict=True,
        )
    )
    scores = dict(
        zip(
            result.ranking.rankings["candidate_id"],
            result.ranking.rankings[
                "investigative_priority_score"
            ],
            strict=True,
        )
    )

    features = []
    for candidate_id, track in tracks.groupby(
        "candidate_id", sort=False
    ):
        track = track.sort_values("timestamp", kind="stable")
        coordinates = track[
            ["longitude", "latitude"]
        ].to_numpy(dtype=float).tolist()

        if len(coordinates) == 1:
            geometry = {
                "type": "Point",
                "coordinates": coordinates[0],
            }
        else:
            geometry = {
                "type": "LineString",
                "coordinates": coordinates,
            }

        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "candidate_id": str(candidate_id),
                    "rank": int(ranks[candidate_id]),
                    "investigative_priority_score": float(
                        scores[candidate_id]
                    ),
                    "point_count": int(len(track)),
                    "time_start_utc": pd.Timestamp(
                        track["timestamp"].min()
                    ).isoformat(),
                    "time_end_utc": pd.Timestamp(
                        track["timestamp"].max()
                    ).isoformat(),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _public_dark_gap_events(
    result: Phase3AttributionResult,
) -> list[dict[str, Any]]:
    identity_lookup = dict(
        zip(
            result.candidate_filter.identity_map["mmsi"].astype(str),
            result.candidate_filter.identity_map["candidate_id"],
            strict=True,
        )
    )
    public_events = []

    for event in result.dark_gap_events:
        vessel_id = str(event["vessel_id"])
        candidate_id = identity_lookup.get(vessel_id)
        if candidate_id is None:
            continue

        public_event = {
            "candidate_id": str(candidate_id),
            "event_type": event["event_type"],
            "coverage_status": event["coverage_status"],
            "gap_start_utc": pd.Timestamp(
                event["gap_start_utc"]
            ).isoformat(),
            "gap_end_utc": pd.Timestamp(
                event["gap_end_utc"]
            ).isoformat(),
            "gap_duration_minutes": float(
                event["gap_duration_minutes"]
            ),
            "latitude_before": float(event["latitude_before"]),
            "longitude_before": float(event["longitude_before"]),
            "latitude_after": float(event["latitude_after"]),
            "longitude_after": float(event["longitude_after"]),
        }
        public_events.append(public_event)

    return public_events


def write_phase3_artifacts(
    result: Phase3AttributionResult,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Write all public artifacts as one new atomic directory."""
    output_path = Path(output_directory).resolve()

    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite Phase 3 output: {output_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(
        tempfile.mkdtemp(
            prefix=f".{output_path.name}-building-",
            dir=output_path.parent,
        )
    )

    try:
        rankings_path = temporary_path / "ranked_candidates.json"
        features_path = temporary_path / "candidate_features.csv"
        tracks_path = temporary_path / "candidate_tracks.geojson"
        gaps_path = temporary_path / "dark_gap_events.json"
        summary_path = temporary_path / "phase3_summary.json"

        ranking_payload = {
            "schema_version": "phase3-ranked-candidates-v1",
            "case_id": result.contract.case_id,
            "phase2_run_id": result.contract.phase2_run_id,
            "model_version": result.model_package.metadata[
                "model_version"
            ],
            "score_semantics": result.ranking.audit[
                "score_semantics"
            ],
            "calibration_status": result.ranking.audit[
                "normalization"
            ]["calibration_status"],
            "ranked_candidates": _records(
                result.ranking.rankings
            ),
        }
        rankings_path.write_text(
            json.dumps(ranking_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        combined_features = result.spatial_evidence.features.merge(
            result.behaviour_evidence.features,
            on="candidate_id",
            how="inner",
            validate="one_to_one",
            suffixes=("_spatial", "_behaviour"),
        )
        if "mmsi" in combined_features.columns:
            raise ValueError("MMSI reached public candidate features")
        combined_features.to_csv(
            features_path, index=False, encoding="utf-8"
        )

        tracks_path.write_text(
            json.dumps(
                _candidate_tracks_geojson(result), indent=2
            )
            + "\n",
            encoding="utf-8",
        )

        gaps_path.write_text(
            json.dumps(
                {
                    "schema_version": "phase3-dark-gaps-v1",
                    "case_id": result.contract.case_id,
                    "events": _public_dark_gap_events(result),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        pre_summary_files = [
            rankings_path,
            features_path,
            tracks_path,
            gaps_path,
        ]
        checksums = {
            path.name: _sha256(path) for path in pre_summary_files
        }
        summary_payload = {
            "schema_version": "phase3-summary-v1",
            "case_id": result.contract.case_id,
            "phase2_run_id": result.contract.phase2_run_id,
            "status": "COMPLETED",
            "model_version": result.model_package.metadata[
                "model_version"
            ],
            "threshold": float(result.model_package.threshold),
            "candidate_count": int(
                result.ranking.audit["candidate_count"]
            ),
            "scored_windows": int(
                result.inference_audit["scored_windows"]
            ),
            "dark_gap_event_count": int(
                len(result.dark_gap_events)
            ),
            "score_semantics": result.ranking.audit[
                "score_semantics"
            ],
            "calibration_status": result.ranking.audit[
                "normalization"
            ]["calibration_status"],
            "model_threshold_calibrated": True,
            "ranking_weights_real_world_calibrated": False,
            "real_world_liability_claim_allowed": False,
            "warnings": result.contract.warnings,
            "audits": {
                "ais_load": result.ais_load.audit,
                "candidate_filter": result.candidate_filter.audit,
                "preprocessing": result.preprocessing_audit,
                "inference": result.inference_audit,
                "spatial_evidence": result.spatial_evidence.audit,
                "behaviour_evidence": result.behaviour_evidence.audit,
                "ranking": result.ranking.audit,
            },
            "artifact_sha256": checksums,
        }
        summary_path.write_text(
            json.dumps(summary_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        missing = [
            filename
            for filename in PUBLIC_ARTIFACT_FILES
            if not (temporary_path / filename).is_file()
        ]
        if missing:
            raise RuntimeError(
                "Artifact build incomplete: " + ", ".join(missing)
            )

        temporary_path.replace(output_path)

    except Exception:
        if temporary_path.exists():
            shutil.rmtree(temporary_path)
        raise

    return {
        "output_directory": str(output_path),
        "files": PUBLIC_ARTIFACT_FILES,
        "artifact_sha256": checksums,
    }
