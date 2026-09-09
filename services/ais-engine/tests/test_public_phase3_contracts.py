"""Contract and privacy tests for the public Phase 3 API boundary."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ais_loader import load_ais_csv
from app.main import app
from app.public_contracts import (
    Phase3RunPublicRequest,
    Phase3RunPublicResponse,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "packages" / "contracts" / "schemas"
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "packages" / "contracts" / "fixtures"

FORBIDDEN_PUBLIC_TERMS = (
    '"mmsi"',
    '"imo"',
    '"shipname"',
    '"ship_name"',
    '"candidate_id"',
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_public_phase3_schemas_are_camel_case_and_private():
    request_schema = _read_json(
        SCHEMA_DIRECTORY / "phase3-run-request-v1.schema.json"
    )
    response_schema = _read_json(
        SCHEMA_DIRECTORY / "phase3-run-response-v1.schema.json"
    )

    assert set(request_schema["properties"]) == {
        "phase2Folder",
        "aisCsvPath",
        "outputDirectory",
        "windowStride",
        "batchSize",
        "topCandidates",
    }

    response_text = json.dumps(response_schema).lower()
    assert "candidateId" in json.dumps(response_schema)
    assert not any(term in response_text for term in FORBIDDEN_PUBLIC_TERMS)


def test_valid_nestjs_request_and_response_fixtures():
    request_payload = _read_json(
        FIXTURE_DIRECTORY / "phase3-run-v1.request.valid.json"
    )
    response_path = (
        FIXTURE_DIRECTORY / "phase3-run-v1.response.valid.json"
    )
    response_payload = _read_json(response_path)

    request = Phase3RunPublicRequest.model_validate(request_payload)
    response = Phase3RunPublicResponse.model_validate(response_payload)

    assert request.top_candidates == 3
    assert response.candidate_count == 3
    assert response.scored_windows == 240
    assert response.top_candidates[0].rank == 1
    assert (
        response.top_candidates[0].candidate_id
        == "candidate-68f8b1f0ac34"
    )

    public_text = response_path.read_text(encoding="utf-8-sig").lower()
    assert not any(term in public_text for term in FORBIDDEN_PUBLIC_TERMS)


def test_public_response_forbids_restricted_identity_fields():
    response_payload = _read_json(
        FIXTURE_DIRECTORY / "phase3-run-v1.response.valid.json"
    )
    response_payload["topCandidates"][0]["mmsi"] = "111111111"

    with pytest.raises(ValidationError):
        Phase3RunPublicResponse.model_validate(response_payload)


def test_no_candidate_fixture_has_exact_422_semantics():
    request = Phase3RunPublicRequest.model_validate(
        _read_json(
            FIXTURE_DIRECTORY
            / "phase3-run-v1.request.no-candidate.json"
        )
    )
    response = _read_json(
        FIXTURE_DIRECTORY
        / "phase3-run-v1.response.no-candidate.json"
    )

    assert request.ais_csv_path.endswith("data/fixtures/ais-demo/ais_input.csv")
    assert response == {
        "detail": "No AIS candidates matched the Phase 2 time/space gate"
    }


def test_low_quality_fixture_has_no_eligible_lstm_window():
    request = Phase3RunPublicRequest.model_validate(
        _read_json(
            FIXTURE_DIRECTORY
            / "phase3-run-v1.request.low-ais-quality.json"
        )
    )
    response = _read_json(
        FIXTURE_DIRECTORY
        / "phase3-run-v1.response.low-ais-quality.json"
    )

    ais_result = load_ais_csv(REPOSITORY_ROOT / request.ais_csv_path)

    assert ais_result.audit["original_rows"] == 8
    assert ais_result.audit["valid_rows"] == 8
    assert ais_result.audit["unique_vessels"] == 1
    assert response == {
        "detail": "Candidate tracks contain no eligible 10-ping model windows"
    }


def test_versioned_public_endpoint_is_registered_once():
    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/v1/phase3/run"
    ]

    assert len(matching_routes) == 1
    assert "POST" in matching_routes[0].methods
