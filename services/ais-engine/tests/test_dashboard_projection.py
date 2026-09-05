"""Regression tests for the additive Phase 3 dashboard projection."""

from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from app.attribution_pipeline import run_phase3_attribution
from app.dashboard_projection import project_dashboard_candidates
from app.public_contracts import RankedCandidatePublic


@pytest.fixture(scope="module")
def projection():
    result = run_phase3_attribution(
        "../../data/fixtures/phase2-attribution-demo",
        "../../data/fixtures/ais-phase2-aligned/ais_input.csv",
        batch_size=256,
    )
    candidates = project_dashboard_candidates(
        result,
        top_candidates=3,
    )
    return result, candidates


def test_projection_preserves_ranking_and_legacy_scores(projection):
    result, candidates = projection

    expected_ids = list(result.ranking.rankings["candidate_id"])
    actual_ids = [item["candidateId"] for item in candidates]
    assert actual_ids == expected_ids

    assert [item["rankLabel"] for item in candidates] == [
        "CAND-001",
        "CAND-002",
        "CAND-003",
    ]

    field_mapping = {
        "investigativePriorityScore": (
            "investigative_priority_score"
        ),
        "originProximityScore": "origin_proximity_score",
        "originDwellScore": "origin_dwell_score",
        "releaseTimeAlignmentScore": (
            "release_time_alignment_score"
        ),
        "corridorAlignmentScore": "corridor_alignment_score",
        "behaviourRuleScore": "behaviour_rule_score",
        "lstmContinuousScore": "lstm_continuous_score",
        "darkGapScore": "dark_gap_score",
    }

    for index, candidate in enumerate(candidates):
        original = result.ranking.rankings.iloc[index]
        for public_field, source_field in field_mapping.items():
            assert candidate[public_field] == pytest.approx(
                float(original[source_field]),
                abs=1e-12,
            )


def test_display_score_and_breakdown_exactly_reproduce_score_v1(
    projection,
):
    _, candidates = projection

    for candidate in candidates:
        expected = candidate["investigativePriorityScore"] * 100.0
        assert candidate["investigativeScore"] == pytest.approx(
            expected,
            abs=1e-9,
        )
        assert sum(candidate["scoreBreakdownPoints"].values()) == (
            pytest.approx(expected, abs=1e-7)
        )


def test_projection_is_private_factual_and_model_eligible(projection):
    _, candidates = projection
    serialized = json.dumps(candidates).lower()

    for forbidden in [
        '"mmsi"',
        '"imo"',
        '"shipname"',
        '"ship_name"',
    ]:
        assert forbidden not in serialized

    for candidate in candidates:
        assert candidate["closestApproach"]["distanceKm"] >= 0
        assert candidate["closestApproach"]["timestampUtc"].endswith(
            "Z"
        )
        assert candidate["dataQuality"]["status"] == (
            "MODEL_ELIGIBLE"
        )
        assert candidate["dataQuality"]["observationCount"] >= 10
        assert candidate["dataQuality"]["eligibleWindowCount"] >= 1
        assert candidate["dataQuality"]["includedInScoreV1"] is False
        assert candidate["candidateTrackRef"] == {
            "artifactFile": "candidate_tracks.geojson",
            "candidateId": candidate["candidateId"],
        }
        assert candidate["supportingEvidence"]
        assert candidate["negativeEvidence"]


def test_public_contract_enforces_cross_field_relationships(projection):
    _, candidates = projection
    validated = RankedCandidatePublic.model_validate(candidates[0])
    payload = validated.model_dump(mode="json", by_alias=True)

    assert payload["rankLabel"] == "CAND-001"
    assert payload["closestApproach"]["timestampUtc"].endswith("Z")

    wrong_label = copy.deepcopy(candidates[0])
    wrong_label["rankLabel"] = "CAND-999"
    with pytest.raises(ValidationError):
        RankedCandidatePublic.model_validate(wrong_label)

    scored_quality = copy.deepcopy(candidates[0])
    scored_quality["dataQuality"]["includedInScoreV1"] = True
    with pytest.raises(ValidationError):
        RankedCandidatePublic.model_validate(scored_quality)

    wrong_track = copy.deepcopy(candidates[0])
    wrong_track["candidateTrackRef"]["candidateId"] = "candidate-wrong"
    with pytest.raises(ValidationError):
        RankedCandidatePublic.model_validate(wrong_track)
