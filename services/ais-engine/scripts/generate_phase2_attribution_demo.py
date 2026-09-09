"""Generate a deterministic synthetic Phase 2 bundle for attribution tests."""

import csv
import json
import math
from pathlib import Path


CASE_ID = "CASE_DEMO_001"
PHASE2_RUN_ID = "DRIFT_RUN_001"
ORIGIN_LON = 72.4200
ORIGIN_LAT = 18.6500

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT
    / "data"
    / "fixtures"
    / "phase2-attribution-demo"
)


def write_json(filename: str, payload: object) -> None:
    path = OUTPUT_DIRECTORY / filename
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def ellipse_ring(radius_m: float, vertices: int = 48):
    latitude_degrees = radius_m / 111_320.0
    longitude_degrees = radius_m / (
        111_320.0 * math.cos(math.radians(ORIGIN_LAT))
    )
    coordinates = []
    for index in range(vertices):
        angle = 2.0 * math.pi * index / vertices
        coordinates.append(
            [
                ORIGIN_LON + longitude_degrees * math.cos(angle),
                ORIGIN_LAT + latitude_degrees * math.sin(angle),
            ]
        )
    coordinates.append(coordinates[0])
    return coordinates


def origin_feature(level: int, radius_m: float):
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ellipse_ring(radius_m)],
        },
        "properties": {
            "case_id": CASE_ID,
            "phase2_run_id": PHASE2_RUN_ID,
            "density_level": level,
            "radius_m": radius_m,
            "scenario_type": "controlled_synthetic_demo",
        },
    }


def main() -> None:
    required_names = [
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

    if OUTPUT_DIRECTORY.exists():
        existing = [
            name
            for name in required_names
            if (OUTPUT_DIRECTORY / name).exists()
        ]
        if existing:
            raise FileExistsError(
                "Refusing to overwrite attribution fixture: "
                + ", ".join(existing)
            )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    search_window = {
        "contract_version": "phase2-to-phase3-v1",
        "case_id": CASE_ID,
        "phase2_run_id": PHASE2_RUN_ID,
        "detection_time_utc": "2026-08-20T05:30:00Z",
        "crs": "EPSG:4326",
        "release_window": {
            "start_utc": "2026-08-19T05:30:00Z",
            "end_utc": "2026-08-19T17:30:00Z",
            "time_buffer_minutes": 60,
        },
        "search_region": {
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [72.10, 18.40],
                        [72.80, 18.40],
                        [72.80, 19.00],
                        [72.10, 19.00],
                        [72.10, 18.40],
                    ]
                ],
            },
            "spatial_buffer_m": 5000,
        },
        "hindcast_corridor": {
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [72.30, 18.55],
                    [72.42, 18.65],
                    [72.55, 18.76],
                ],
            },
            "direction_deg": 245.0,
            "time_bands": [],
        },
    }
    write_json("search_window.json", search_window)

    write_json("origin_50.geojson", origin_feature(50, 2_000.0))
    write_json("origin_75.geojson", origin_feature(75, 5_000.0))
    write_json("origin_90.geojson", origin_feature(90, 9_000.0))

    backward_tracks = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [72.56, 18.77],
                        [72.49, 18.71],
                        [72.42, 18.65],
                        [72.36, 18.59],
                    ],
                },
                "properties": {
                    "particle_id": particle_id,
                    "direction": "backward",
                    "scenario_type": "controlled_synthetic_demo",
                },
            }
            for particle_id in range(1, 6)
        ],
    }
    write_json("backward_tracks.geojson", backward_tracks)

    forward_reconstruction = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [72.42, 18.65],
                        [72.49, 18.71],
                        [72.56, 18.77],
                    ],
                },
                "properties": {
                    "simulation": "forward_reconstruction",
                    "scenario_type": "controlled_synthetic_demo",
                },
            }
        ],
    }
    write_json(
        "forward_reconstruction.geojson",
        forward_reconstruction,
    )

    release_rows = [
        ("2026-08-19T06:00:00Z", 0.18),
        ("2026-08-19T08:00:00Z", 0.42),
        ("2026-08-19T10:00:00Z", 0.91),
        ("2026-08-19T12:00:00Z", 1.00),
        ("2026-08-19T14:00:00Z", 0.72),
        ("2026-08-19T16:00:00Z", 0.31),
    ]
    with (OUTPUT_DIRECTORY / "release_time_scores.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["release_time_utc", "normalized_score"])
        writer.writerows(release_rows)

    write_json(
        "reconstruction_metrics.json",
        {
            "metric_version": "synthetic-demo-v1",
            "centroid_error_km": 1.8,
            "iou": 0.71,
            "scenario_type": "controlled_synthetic_demo",
        },
    )
    write_json(
        "summary.json",
        {
            "case_id": CASE_ID,
            "phase2_run_id": PHASE2_RUN_ID,
            "status": "COMPLETED",
            "origin_center": [ORIGIN_LON, ORIGIN_LAT],
            "scenario_type": "controlled_synthetic_demo",
            "real_world_claim_allowed": False,
        },
    )
    write_json(
        "run_config.json",
        {
            "run_id": PHASE2_RUN_ID,
            "random_seed": 42,
            "crs": "EPSG:4326",
            "scenario_type": "controlled_synthetic_demo",
        },
    )
    write_json(
        "validation_report.json",
        {
            "status": "PASSED",
            "warnings": [
                "Controlled synthetic Phase 2 attribution fixture; "
                "not a real hindcast result."
            ],
            "real_world_claim_allowed": False,
        },
    )

    missing = [
        name
        for name in required_names
        if not (OUTPUT_DIRECTORY / name).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Generator failed to create: " + ", ".join(missing)
        )

    print("==============================================")
    print("PHASE 2 ATTRIBUTION DEMO GENERATED")
    print("==============================================")
    print(f"Output directory: {OUTPUT_DIRECTORY}")
    print(f"Required files: {len(required_names)}")
    print(f"Origin center: [{ORIGIN_LON}, {ORIGIN_LAT}]")
    print("Origin radii: 2000 m, 5000 m, 9000 m")
    print("Release-score rows: 6")
    print("Scenario: CONTROLLED SYNTHETIC DEMO")
    print("Real-world claim allowed: False")
    print("==============================================")


if __name__ == "__main__":
    main()
