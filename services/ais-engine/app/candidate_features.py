"""Explainable Phase 2 spatial/temporal evidence for AIS candidates."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import covers, distance, points
from shapely.geometry import shape
from shapely.ops import transform

from app.candidate_filter import CandidateFilterResult
from app.schemas import Phase2ToPhase3Contract


@dataclass
class CandidateFeatureResult:
    features: pd.DataFrame
    audit: dict[str, Any]


def _projection_for_geometry(geometry):
    centroid = geometry.centroid
    local_crs = CRS.from_proj4(
        "+proj=aeqd "
        f"+lat_0={centroid.y} "
        f"+lon_0={centroid.x} "
        "+datum=WGS84 +units=m +no_defs"
    )
    return Transformer.from_crs(
        "EPSG:4326", local_crs, always_xy=True
    )


def build_candidate_features(
    filtered: CandidateFilterResult,
    contract: Phase2ToPhase3Contract,
) -> CandidateFeatureResult:
    """Calculate raw, unweighted evidence for every candidate vessel."""
    tracks = filtered.candidate_tracks.copy()

    required_columns = [
        "candidate_id",
        "mmsi",
        "timestamp",
        "latitude",
        "longitude",
    ]
    missing_columns = [
        column
        for column in required_columns
        if column not in tracks.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Candidate track columns missing: {missing_columns}"
        )

    if tracks.empty:
        return CandidateFeatureResult(
            features=pd.DataFrame(),
            audit={
                "case_id": contract.case_id,
                "candidate_vessels": 0,
                "feature_rows": 0,
            },
        )

    tracks["timestamp"] = pd.to_datetime(
        tracks["timestamp"], errors="coerce", utc=True
    )
    if tracks["timestamp"].isna().any():
        raise ValueError("Invalid candidate timestamps")

    contour_50 = shape(
        contract.origin_contours.density_50.geometry
    )
    contour_75 = shape(
        contract.origin_contours.density_75.geometry
    )
    contour_90 = shape(
        contract.origin_contours.density_90.geometry
    )
    corridor = shape(contract.hindcast_corridor.geometry)
    search_region = shape(contract.search_region.geometry)

    named_geometries = {
        "origin_50": contour_50,
        "origin_75": contour_75,
        "origin_90": contour_90,
        "corridor": corridor,
        "search_region": search_region,
    }
    for name, geometry in named_geometries.items():
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid Phase 2 geometry: {name}")

    transformer = _projection_for_geometry(contour_90)
    projected = {
        name: transform(transformer.transform, geometry)
        for name, geometry in named_geometries.items()
    }
    origin_center = projected["origin_50"].centroid

    release_start = pd.Timestamp(
        contract.release_window.start_utc
    )
    release_end = pd.Timestamp(
        contract.release_window.end_utc
    )
    release_midpoint = release_start + (
        release_end - release_start
    ) / 2

    records: list[dict[str, Any]] = []

    for candidate_id, candidate_track in tracks.groupby(
        "candidate_id", sort=False
    ):
        candidate_track = candidate_track.sort_values(
            "timestamp", kind="stable"
        )
        x_values, y_values = transformer.transform(
            candidate_track["longitude"].to_numpy(dtype=float),
            candidate_track["latitude"].to_numpy(dtype=float),
        )
        candidate_points = points(x_values, y_values)

        center_distances = np.asarray(
            distance(origin_center, candidate_points), dtype=float
        )
        contour_50_membership = np.asarray(
            covers(projected["origin_50"], candidate_points),
            dtype=bool,
        )
        contour_75_membership = np.asarray(
            covers(projected["origin_75"], candidate_points),
            dtype=bool,
        )
        contour_90_membership = np.asarray(
            covers(projected["origin_90"], candidate_points),
            dtype=bool,
        )
        corridor_distances = np.asarray(
            distance(projected["corridor"], candidate_points),
            dtype=float,
        )
        search_distances = np.asarray(
            distance(projected["search_region"], candidate_points),
            dtype=float,
        )

        closest_position = int(np.argmin(center_distances))
        closest_timestamp = candidate_track.iloc[
            closest_position
        ]["timestamp"]
        midpoint_offset_minutes = abs(
            (closest_timestamp - release_midpoint).total_seconds()
        ) / 60.0

        release_mask = candidate_track["timestamp"].between(
            release_start, release_end, inclusive="both"
        )
        release_rows = int(release_mask.sum())

        records.append(
            {
                "candidate_id": str(candidate_id),
                "track_point_count": int(len(candidate_track)),
                "release_window_point_count": release_rows,
                "release_window_point_ratio": float(
                    release_rows / len(candidate_track)
                ),
                "minimum_origin_center_distance_m": float(
                    center_distances.min()
                ),
                "closest_origin_time_utc": closest_timestamp,
                "closest_origin_midpoint_offset_min": float(
                    midpoint_offset_minutes
                ),
                "entered_origin_50": bool(
                    contour_50_membership.any()
                ),
                "entered_origin_75": bool(
                    contour_75_membership.any()
                ),
                "entered_origin_90": bool(
                    contour_90_membership.any()
                ),
                "origin_50_point_count": int(
                    contour_50_membership.sum()
                ),
                "origin_75_point_count": int(
                    contour_75_membership.sum()
                ),
                "origin_90_point_count": int(
                    contour_90_membership.sum()
                ),
                "minimum_corridor_distance_m": float(
                    corridor_distances.min()
                ),
                "minimum_search_region_distance_m": float(
                    search_distances.min()
                ),
            }
        )

    features = pd.DataFrame(records).sort_values(
        [
            "minimum_origin_center_distance_m",
            "minimum_corridor_distance_m",
        ],
        ascending=[True, True],
        kind="stable",
    ).reset_index(drop=True)

    numeric_columns = features.select_dtypes(
        include=[np.number]
    ).columns
    if not np.isfinite(
        features[numeric_columns].to_numpy(dtype=float)
    ).all():
        raise ValueError("Non-finite candidate features found")

    audit = {
        "case_id": contract.case_id,
        "phase2_run_id": contract.phase2_run_id,
        "candidate_vessels": int(
            tracks["candidate_id"].nunique()
        ),
        "feature_rows": int(len(features)),
        "release_start_utc": release_start.isoformat(),
        "release_end_utc": release_end.isoformat(),
        "distance_unit": "metres",
        "scoring_applied": False,
        "mmsi_exposed_in_features": False,
    }

    return CandidateFeatureResult(features=features, audit=audit)
