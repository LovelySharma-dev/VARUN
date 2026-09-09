"""Generate a deterministic Phase-2-aligned AIS attribution demo."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_SEED = 42
CASE_ID = "CASE_DEMO_001"
CULPRIT_MMSI = "419000001"
OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "fixtures"
    / "ais-phase2-aligned"
)


def candidate_id(mmsi: str) -> str:
    digest = hashlib.sha256(
        f"{CASE_ID}:{mmsi}".encode("utf-8")
    ).hexdigest()[:12]
    return f"candidate-{digest}"


def main() -> None:
    csv_path = OUTPUT_DIRECTORY / "ais_input.csv"
    truth_path = OUTPUT_DIRECTORY / "ground_truth.json"

    existing = [
        str(path)
        for path in (csv_path, truth_path)
        if path.exists()
    ]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing demo artifacts: "
            + ", ".join(existing)
        )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(RANDOM_SEED)
    timestamps = pd.date_range(
        "2026-08-19T04:30:00Z",
        "2026-08-19T18:30:00Z",
        freq="5min",
    )
    rows: list[dict[str, object]] = []

    for index, timestamp in enumerate(timestamps):
        # Known target: approaches the likely origin, loiters with repeated
        # turns during the release window, then departs.
        if index < 60:
            target_lon = 72.3500 + 0.00110 * index
            target_lat = 18.6000 + 0.00070 * index
            target_speed = 8.2 + 0.15 * np.sin(index / 5.0)
            target_course = 55.0
        elif index < 97:
            angle_deg = (index - 60) * 35.0
            angle_rad = np.radians(angle_deg)
            target_lon = 72.4200 + 0.0080 * np.cos(angle_rad)
            target_lat = 18.6500 + 0.0080 * np.sin(angle_rad)
            target_speed = 1.2 + 0.2 * np.sin(index)
            target_course = (angle_deg + 90.0) % 360.0
        else:
            departure_index = index - 97
            target_lon = 72.4280 + 0.00100 * departure_index
            target_lat = 18.6500 + 0.00040 * departure_index
            target_speed = 7.8 + 0.15 * np.cos(index / 6.0)
            target_course = 68.0

        rows.append(
            {
                "mmsi": CULPRIT_MMSI,
                "timestamp": timestamp.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "latitude": target_lat
                + rng.normal(0.0, 0.00003),
                "longitude": target_lon
                + rng.normal(0.0, 0.00003),
                "speed": max(
                    0.0, target_speed + rng.normal(0.0, 0.03)
                ),
                "course": (
                    target_course + rng.normal(0.0, 0.4)
                )
                % 360.0,
            }
        )

        # Nearby normal candidate: steady transit across the search region.
        rows.append(
            {
                "mmsi": "419000002",
                "timestamp": timestamp.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "latitude": 18.5000
                + 0.00180 * index
                + rng.normal(0.0, 0.00002),
                "longitude": 72.1800
                + 0.00280 * index
                + rng.normal(0.0, 0.00002),
                "speed": 10.0 + rng.normal(0.0, 0.08),
                "course": (55.0 + rng.normal(0.0, 0.5)) % 360.0,
            }
        )

        # Secondary candidate: steady opposing transit near the outer region.
        rows.append(
            {
                "mmsi": "419000003",
                "timestamp": timestamp.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "latitude": 18.9000
                - 0.00070 * index
                + rng.normal(0.0, 0.00002),
                "longitude": 72.7500
                - 0.00150 * index
                + rng.normal(0.0, 0.00002),
                "speed": 7.0 + rng.normal(0.0, 0.07),
                "course": (225.0 + rng.normal(0.0, 0.5)) % 360.0,
            }
        )

        # Irrelevant vessel: correct time, but well outside the search region.
        rows.append(
            {
                "mmsi": "419000004",
                "timestamp": timestamp.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "latitude": 20.2000 + 0.00040 * index,
                "longitude": 74.0000 + 0.00050 * index,
                "speed": 9.0 + rng.normal(0.0, 0.05),
                "course": (40.0 + rng.normal(0.0, 0.3)) % 360.0,
            }
        )

    dataframe = pd.DataFrame(rows).sort_values(
        ["mmsi", "timestamp"], kind="stable"
    )
    dataframe.to_csv(csv_path, index=False, encoding="utf-8")

    truth = {
        "scenario_version": "phase3-known-target-v1",
        "random_seed": RANDOM_SEED,
        "case_id": CASE_ID,
        "phase2_run_id": "DRIFT_RUN_001",
        "scenario_type": "controlled_synthetic_attribution_demo",
        "culprit_mmsi_restricted": CULPRIT_MMSI,
        "expected_candidate_id": candidate_id(CULPRIT_MMSI),
        "expected_primary_behaviour": "LOITERING_AND_ABRUPT_MANOEUVRING",
        "anomalous_interval_start_utc": "2026-08-19T09:30:00Z",
        "anomalous_interval_end_utc": "2026-08-19T12:30:00Z",
        "release_window_alignment": True,
        "real_world_claim_allowed": False,
        "notes": (
            "Synthetic known-target fixture for deterministic Phase 3 "
            "integration testing; not evidence of a real spill or vessel."
        ),
    }
    truth_path.write_text(
        json.dumps(truth, indent=2) + "\n",
        encoding="utf-8",
    )

    print("==============================================")
    print("PHASE 3 ALIGNED AIS FIXTURE GENERATED")
    print("==============================================")
    print(f"Rows: {len(dataframe)}")
    print(f"Vessels: {dataframe['mmsi'].nunique()}")
    print(f"Time start: {dataframe['timestamp'].min()}")
    print(f"Time end: {dataframe['timestamp'].max()}")
    print(f"Known candidate: {truth['expected_candidate_id']}")
    print(f"AIS CSV: {csv_path}")
    print(f"Ground truth: {truth_path}")
    print("==============================================")


if __name__ == "__main__":
    main()
