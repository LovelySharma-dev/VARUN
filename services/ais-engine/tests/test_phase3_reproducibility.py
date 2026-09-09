import json
import os
import subprocess
import sys
from pathlib import Path


EXPECTED_CANDIDATE_ORDER = [
    "candidate-68f8b1f0ac34",
    "candidate-7669d2a91e2d",
    "candidate-8fcff6b97422",
]

EXPECTED_ARTIFACTS = {
    "ranked_candidates.json",
    "candidate_features.csv",
    "candidate_tracks.geojson",
    "dark_gap_events.json",
    "phase3_summary.json",
}


def test_repository_replay_is_deterministic_private_and_ground_truth_free(
    tmp_path: Path,
) -> None:
    service_root = Path(__file__).resolve().parents[1]
    repository_root = service_root.parents[1]
    output_root = tmp_path / "phase3-replay"

    environment = os.environ.copy()
    environment.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_phase3_reproducibility",
            "--output-root",
            str(output_root),
            "--batch-size",
            "256",
        ],
        cwd=service_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "REPOSITORY REPRODUCIBILITY: PASSED" in completed.stdout

    report_path = output_root / "reproducibility_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["inputs"]["phase2_folder"] == (
        "data/fixtures/phase2-attribution-demo"
    )
    assert report["inputs"]["ais_csv"] == (
        "data/fixtures/ais-phase2-aligned/ais_input.csv"
    )
    assert report["inputs"]["ground_truth_supplied_to_pipeline"] is False

    proofs = report["proofs"]
    assert proofs["ground_truth_not_read"] is True
    assert proofs["public_mmsi_exposure"] is False
    assert proofs["same_candidate_set_and_rank_order"] is True

    result = report["result"]
    assert result["candidate_count"] == 3
    assert result["scored_windows"] == 240
    assert result["candidate_ids_in_rank_order"] == (
        EXPECTED_CANDIDATE_ORDER
    )

    score = report["score_v1"]
    assert round(score["weight_sum"], 6) == 1.0
    assert score["semantics"] == (
        "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
    )

    for replay_name in ("replay_1", "replay_2"):
        replay_directory = output_root / replay_name
        assert {
            path.name for path in replay_directory.iterdir() if path.is_file()
        } == EXPECTED_ARTIFACTS

        combined_public_content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in replay_directory.iterdir()
            if path.is_file()
        )
        assert "candidate_id" in combined_public_content

    manifest_path = (
        repository_root
        / "data"
        / "fixtures"
        / "phase3-reproducibility-output"
        / "sha256_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    assert manifest["deterministic_replay_passed"] is True
    assert manifest["ground_truth_supplied_to_pipeline"] is False
    assert manifest["public_mmsi_exposure"] is False
    assert set(manifest["artifact_sha256"]) == EXPECTED_ARTIFACTS
