import hashlib
import json
from pathlib import Path

import pytest

from app.artifact_writer import (
    PUBLIC_ARTIFACT_FILES,
    write_phase3_artifacts,
)
from app.attribution_pipeline import run_phase3_attribution


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE2_FIXTURE = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "phase2-attribution-demo"
)
AIS_FIXTURE = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "ais-phase2-aligned"
    / "ais_input.csv"
)
GROUND_TRUTH = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "ais-phase2-aligned"
    / "ground_truth.json"
)
RESTRICTED_MMSI = {
    "419000001",
    "419000002",
    "419000003",
    "419000004",
}


@pytest.fixture(scope="module")
def attribution_result():
    return run_phase3_attribution(
        PHASE2_FIXTURE,
        AIS_FIXTURE,
        window_stride=2,
        batch_size=256,
    )


def test_known_target_is_ranked_first(attribution_result):
    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    rankings = attribution_result.ranking.rankings

    assert len(rankings) == 3
    assert rankings.iloc[0]["rank"] == 1
    assert rankings.iloc[0]["candidate_id"] == (
        truth["expected_candidate_id"]
    )
    assert rankings.iloc[0]["investigative_priority_score"] == (
        pytest.approx(0.8721806411, abs=1e-6)
    )
    assert attribution_result.inference_audit["scored_windows"] == 240


def test_artifacts_are_complete_private_and_checksum_verified(
    attribution_result,
    tmp_path,
):
    output = tmp_path / "phase3-output"
    write_result = write_phase3_artifacts(
        attribution_result, output
    )

    assert set(write_result["files"]) == set(PUBLIC_ARTIFACT_FILES)
    assert all((output / name).is_file() for name in PUBLIC_ARTIFACT_FILES)

    summary = json.loads(
        (output / "phase3_summary.json").read_text(
            encoding="utf-8"
        )
    )
    rankings = json.loads(
        (output / "ranked_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    tracks = json.loads(
        (output / "candidate_tracks.geojson").read_text(
            encoding="utf-8"
        )
    )

    assert summary["status"] == "COMPLETED"
    assert summary["candidate_count"] == 3
    assert summary["real_world_liability_claim_allowed"] is False
    assert rankings["ranked_candidates"][0]["rank"] == 1
    assert tracks["type"] == "FeatureCollection"
    assert len(tracks["features"]) == 3

    for filename, expected_hash in summary[
        "artifact_sha256"
    ].items():
        actual_hash = hashlib.sha256(
            (output / filename).read_bytes()
        ).hexdigest()
        assert actual_hash == expected_hash

    for filename in PUBLIC_ARTIFACT_FILES:
        text = (output / filename).read_text(encoding="utf-8")
        assert all(mmsi not in text for mmsi in RESTRICTED_MMSI)

    with pytest.raises(FileExistsError):
        write_phase3_artifacts(attribution_result, output)
