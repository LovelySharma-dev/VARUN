from pathlib import Path

import pandas as pd

from app.candidate_filter import filter_ais_candidates
from app.phase2_loader import load_phase2_bundle


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE2_FIXTURE = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "phase2-demo"
)


def test_candidate_filter_applies_time_space_and_private_identity():
    contract = load_phase2_bundle(PHASE2_FIXTURE)

    ais_df = pd.DataFrame(
        [
            {
                "mmsi": "111111111",
                "timestamp": "2026-08-19T10:00:00Z",
                "latitude": 18.70,
                "longitude": 72.40,
                "speed": 8.0,
                "course": 90.0,
            },
            {
                "mmsi": "111111111",
                "timestamp": "2026-08-19T11:00:00Z",
                "latitude": 19.20,
                "longitude": 73.00,
                "speed": 8.5,
                "course": 95.0,
            },
            {
                "mmsi": "222222222",
                "timestamp": "2026-08-19T10:30:00Z",
                "latitude": 20.50,
                "longitude": 75.00,
                "speed": 10.0,
                "course": 180.0,
            },
            {
                "mmsi": "333333333",
                "timestamp": "2026-08-18T10:00:00Z",
                "latitude": 18.70,
                "longitude": 72.40,
                "speed": 6.0,
                "course": 45.0,
            },
        ]
    )

    result = filter_ais_candidates(ais_df, contract)

    assert result.audit["candidate_vessels"] == 1
    assert result.audit["rows_inside_time_gate"] == 3
    assert result.audit["rows_matching_time_and_space"] == 1
    assert result.audit["candidate_track_rows"] == 2

    assert result.identity_map["mmsi"].tolist() == ["111111111"]
    candidate_id = result.identity_map.iloc[0]["candidate_id"]
    assert candidate_id.startswith("candidate-")
    assert "111111111" not in candidate_id

    assert result.matching_points["candidate_id"].tolist() == [
        candidate_id
    ]
    assert set(result.candidate_tracks["candidate_id"]) == {
        candidate_id
    }
    assert result.matching_points.iloc[0][
        "distance_to_search_region_m"
    ] == 0.0
