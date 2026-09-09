"""Reproduce and audit the controlled VARUNA Phase 3 attribution demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from app.artifact_writer import PUBLIC_ARTIFACT_FILES, write_phase3_artifacts
from app.attribution_pipeline import run_phase3_attribution


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def artifact_hashes(output_directory: Path) -> dict[str, str]:
    return {
        filename: sha256(output_directory / filename)
        for filename in PUBLIC_ARTIFACT_FILES
    }


def ranking_records(result: Any) -> list[dict[str, Any]]:
    return json.loads(
        result.ranking.rankings.to_json(
            orient="records",
            double_precision=15,
        )
    )


def assert_same_ranking(first: Any, second: Any) -> None:
    first_frame = first.ranking.rankings.reset_index(drop=True)
    second_frame = second.ranking.rankings.reset_index(drop=True)

    if list(first_frame.columns) != list(second_frame.columns):
        raise AssertionError("Replay ranking columns differ")

    if first_frame["candidate_id"].tolist() != second_frame[
        "candidate_id"
    ].tolist():
        raise AssertionError("Replay candidate order differs")

    if first_frame["rank"].tolist() != second_frame["rank"].tolist():
        raise AssertionError("Replay rank values differ")

    numeric_columns = first_frame.select_dtypes(
        include=["number"]
    ).columns
    if not np.allclose(
        first_frame[numeric_columns].to_numpy(dtype=float),
        second_frame[numeric_columns].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-12,
        equal_nan=True,
    ):
        raise AssertionError("Replay numeric ranking values differ")

    other_columns = [
        column
        for column in first_frame.columns
        if column not in numeric_columns
    ]
    if not first_frame[other_columns].equals(
        second_frame[other_columns]
    ):
        raise AssertionError("Replay non-numeric ranking values differ")


def assert_public_outputs_hide_mmsi(
    result: Any,
    output_directory: Path,
) -> None:
    restricted_ids = set(
        result.candidate_filter.identity_map["mmsi"]
        .astype(str)
        .tolist()
    )
    for filename in PUBLIC_ARTIFACT_FILES:
        content = (output_directory / filename).read_text(
            encoding="utf-8"
        )
        leaked = sorted(
            mmsi for mmsi in restricted_ids if mmsi in content
        )
        if leaked:
            raise AssertionError(
                f"Restricted MMSI exposed in {filename}: {leaked}"
            )


def score_formula(weights: dict[str, float]) -> str:
    return (
        "priority = "
        f"{weights['origin_proximity']}*origin_proximity_score + "
        f"{weights['origin_dwell']}*origin_dwell_score + "
        f"{weights['release_time_alignment']}*release_time_alignment_score + "
        f"{weights['corridor_alignment']}*corridor_alignment_score + "
        f"{weights['behaviour_rules']}*behaviour_rule_score + "
        f"{weights['lstm_continuous']}*lstm_continuous_score + "
        f"{weights['dark_gap']}*dark_gap_score"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        default="artifacts/reproducibility/phase3_demo",
        help=(
            "New repository-relative or absolute output directory. "
            "The script refuses to overwrite it."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")

    script_path = Path(__file__).resolve()
    repository_root = script_path.parents[3]
    phase2_folder = (
        repository_root
        / "data"
        / "fixtures"
        / "phase2-attribution-demo"
    )
    source_ais = (
        repository_root
        / "data"
        / "fixtures"
        / "ais-phase2-aligned"
        / "ais_input.csv"
    )
    source_ground_truth = source_ais.parent / "ground_truth.json"

    output_root_arg = Path(args.output_root)
    output_root = (
        output_root_arg.resolve()
        if output_root_arg.is_absolute()
        else (repository_root / output_root_arg).resolve()
    )
    if output_root.exists():
        raise FileExistsError(
            f"Refusing to overwrite reproducibility output: {output_root}"
        )

    required_phase2_files = [
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
    missing = [
        name
        for name in required_phase2_files
        if not (phase2_folder / name).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing Phase 2 fixture files: " + ", ".join(missing)
        )
    if not source_ais.is_file():
        raise FileNotFoundError(f"AIS fixture missing: {source_ais}")

    first_directory = output_root / "replay_1"
    second_directory = output_root / "replay_2"

    # The scoring pipeline receives an isolated AIS directory containing only
    # ais_input.csv. ground_truth.json is deliberately not copied or opened.
    with tempfile.TemporaryDirectory(
        prefix="varuna-phase3-isolated-ais-"
    ) as temporary_directory:
        isolated_directory = Path(temporary_directory)
        isolated_ais = isolated_directory / "ais_input.csv"
        shutil.copy2(source_ais, isolated_ais)
        if (isolated_directory / "ground_truth.json").exists():
            raise AssertionError("Ground truth entered isolated input")

        first = run_phase3_attribution(
            phase2_folder,
            isolated_ais,
            window_stride=2,
            batch_size=args.batch_size,
        )
        write_phase3_artifacts(first, first_directory)

        second = run_phase3_attribution(
            phase2_folder,
            isolated_ais,
            window_stride=2,
            batch_size=args.batch_size,
        )
        write_phase3_artifacts(second, second_directory)

    assert_same_ranking(first, second)
    assert_public_outputs_hide_mmsi(first, first_directory)
    assert_public_outputs_hide_mmsi(second, second_directory)

    first_hashes = artifact_hashes(first_directory)
    second_hashes = artifact_hashes(second_directory)
    byte_identical = first_hashes == second_hashes

    weights = {
        key: float(value)
        for key, value in first.ranking.audit["weights"].items()
    }
    candidate_ids = first.ranking.rankings[
        "candidate_id"
    ].tolist()
    top_three = ranking_records(first)[:3]

    report = {
        "schema_version": "phase3-reproducibility-v1",
        "repository_commit": git_commit(repository_root),
        "inputs": {
            "phase2_folder": str(
                phase2_folder.relative_to(repository_root)
            ).replace("\\", "/"),
            "phase2_required_files": required_phase2_files,
            "ais_csv": str(
                source_ais.relative_to(repository_root)
            ).replace("\\", "/"),
            "ground_truth_present_in_source_fixture": (
                source_ground_truth.is_file()
            ),
            "ground_truth_supplied_to_pipeline": False,
            "window_stride": 2,
            "batch_size": args.batch_size,
        },
        "model": {
            "model_version": first.model_package.metadata["model_version"],
            "threshold": float(first.model_package.threshold),
        },
        "result": {
            "candidate_count": int(
                first.ranking.audit["candidate_count"]
            ),
            "scored_windows": int(
                first.inference_audit["scored_windows"]
            ),
            "candidate_ids_in_rank_order": candidate_ids,
            "top_3": top_three,
        },
        "score_v1": {
            "weights": weights,
            "weight_sum": float(sum(weights.values())),
            "formula": score_formula(weights),
            "semantics": first.ranking.audit["score_semantics"],
            "calibration_status": first.ranking.audit[
                "normalization"
            ]["calibration_status"],
        },
        "proofs": {
            "ground_truth_not_read": True,
            "public_mmsi_exposure": False,
            "same_candidate_set_and_rank_order": True,
            "numeric_scores_equal_at_absolute_tolerance": 1e-12,
            "all_generated_artifacts_byte_identical": byte_identical,
        },
        "replay_1_sha256": first_hashes,
        "replay_2_sha256": second_hashes,
    }

    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "reproducibility_report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=" * 62)
    print("VARUNA PHASE 3 - REPOSITORY REPRODUCIBILITY")
    print("=" * 62)
    print("Repository commit:", report["repository_commit"])
    print("Phase 2 input:", report["inputs"]["phase2_folder"])
    print("AIS input:", report["inputs"]["ais_csv"])
    print("Ground truth supplied/read: False")
    print("Candidate count:", report["result"]["candidate_count"])
    print("Scored windows:", report["result"]["scored_windows"])
    print("Candidate order:", " -> ".join(candidate_ids))
    print("Same candidate set and ranking: PASSED")
    print("Public MMSI exposure: FALSE")
    print("Byte-identical artifacts:", byte_identical)
    print("\nACTUAL REPLAY 1 SHA256")
    for filename, digest in first_hashes.items():
        print(f"{filename}: {digest}")
    print("\nScore-v1 formula:")
    print(report["score_v1"]["formula"])
    print("\nReport:", report_path)
    print("=" * 62)
    print("REPOSITORY REPRODUCIBILITY: PASSED")
    print("=" * 62)


if __name__ == "__main__":
    main()
