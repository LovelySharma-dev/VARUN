"""Phase 2 time/space filtering for Phase 3 AIS candidates."""

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import covers, distance, points
from shapely.geometry import shape
from shapely.ops import transform

from app.schemas import Phase2ToPhase3Contract


@dataclass
class CandidateFilterResult:
    candidate_tracks: pd.DataFrame
    matching_points: pd.DataFrame
    identity_map: pd.DataFrame
    audit: dict[str, Any]


def _candidate_id(case_id: str, mmsi: str) -> str:
    digest = hashlib.sha256(
        f"{case_id}:{mmsi}".encode("utf-8")
    ).hexdigest()[:12]
    return f"candidate-{digest}"


def _build_local_projection(geometry):
    centroid = geometry.centroid
    local_crs = CRS.from_proj4(
        "+proj=aeqd "
        f"+lat_0={centroid.y} "
        f"+lon_0={centroid.x} "
        "+datum=WGS84 +units=m +no_defs"
    )
    transformer = Transformer.from_crs(
        "EPSG:4326",
        local_crs,
        always_xy=True,
    )
    return transformer


def filter_ais_candidates(
    ais_df: pd.DataFrame,
    contract: Phase2ToPhase3Contract,
) -> CandidateFilterResult:
    """Find vessels entering the buffered search region in the time window.

    Matching points must satisfy both time and spatial gates. Once a vessel
    matches, all of its rows in the buffered time interval are retained as
    candidate-track context for reconstruction and behaviour scoring.
    """
    required_columns = [
        "mmsi",
        "timestamp",
        "latitude",
        "longitude",
        "speed",
        "course",
    ]
    missing_columns = [
        column
        for column in required_columns
        if column not in ais_df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"AIS columns missing for candidate filtering: {missing_columns}"
        )

    dataframe = ais_df.copy()
    dataframe["mmsi"] = dataframe["mmsi"].astype("string")
    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"], errors="coerce", utc=True
    )

    if dataframe["timestamp"].isna().any():
        raise ValueError("Invalid timestamps reached candidate filter")

    region = shape(contract.search_region.geometry)
    if region.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            "search_region geometry must be Polygon or MultiPolygon"
        )
    if region.is_empty or not region.is_valid:
        raise ValueError("search_region geometry is empty or invalid")

    buffer_minutes = int(
        contract.release_window.time_buffer_minutes
    )
    time_delta = pd.Timedelta(minutes=buffer_minutes)
    buffered_start = pd.Timestamp(
        contract.release_window.start_utc
    ) - time_delta
    buffered_end = pd.Timestamp(
        contract.release_window.end_utc
    ) + time_delta

    time_mask = dataframe["timestamp"].between(
        buffered_start, buffered_end, inclusive="both"
    )
    time_rows = dataframe.loc[time_mask].copy()

    transformer = _build_local_projection(region)
    projected_region = transform(transformer.transform, region)
    spatial_buffer_m = float(
        contract.search_region.spatial_buffer_m
    )
    buffered_region = projected_region.buffer(spatial_buffer_m)

    if time_rows.empty:
        matching_points = time_rows.assign(
            distance_to_search_region_m=pd.Series(dtype=float)
        )
        candidate_tracks = matching_points.copy()
        identity_map = pd.DataFrame(
            columns=["candidate_id", "mmsi"]
        )
    else:
        projected_x, projected_y = transformer.transform(
            time_rows["longitude"].to_numpy(dtype=float),
            time_rows["latitude"].to_numpy(dtype=float),
        )
        projected_points = points(projected_x, projected_y)
        spatial_mask = np.asarray(
            covers(buffered_region, projected_points), dtype=bool
        )
        distances_m = np.asarray(
            distance(projected_region, projected_points), dtype=float
        )

        time_rows["distance_to_search_region_m"] = distances_m
        matching_points = time_rows.loc[spatial_mask].copy()

        candidate_mmsi = (
            matching_points["mmsi"].drop_duplicates().tolist()
        )
        candidate_tracks = time_rows.loc[
            time_rows["mmsi"].isin(candidate_mmsi)
        ].copy()

        identity_map = pd.DataFrame(
            {
                "mmsi": candidate_mmsi,
                "candidate_id": [
                    _candidate_id(contract.case_id, value)
                    for value in candidate_mmsi
                ],
            }
        )[["candidate_id", "mmsi"]]

        id_lookup = dict(
            zip(
                identity_map["mmsi"],
                identity_map["candidate_id"],
                strict=True,
            )
        )
        matching_points["candidate_id"] = (
            matching_points["mmsi"].map(id_lookup)
        )
        candidate_tracks["candidate_id"] = (
            candidate_tracks["mmsi"].map(id_lookup)
        )

    audit = {
        "case_id": contract.case_id,
        "phase2_run_id": contract.phase2_run_id,
        "input_rows": int(len(dataframe)),
        "input_vessels": int(dataframe["mmsi"].nunique()),
        "buffered_time_start_utc": buffered_start.isoformat(),
        "buffered_time_end_utc": buffered_end.isoformat(),
        "time_buffer_minutes": buffer_minutes,
        "spatial_buffer_m": spatial_buffer_m,
        "rows_inside_time_gate": int(len(time_rows)),
        "rows_matching_time_and_space": int(len(matching_points)),
        "candidate_track_rows": int(len(candidate_tracks)),
        "candidate_vessels": int(len(identity_map)),
        "public_identity_field": "candidate_id",
        "restricted_identity_field": "mmsi",
    }

    return CandidateFilterResult(
        candidate_tracks=candidate_tracks.reset_index(drop=True),
        matching_points=matching_points.reset_index(drop=True),
        identity_map=identity_map.reset_index(drop=True),
        audit=audit,
    )
