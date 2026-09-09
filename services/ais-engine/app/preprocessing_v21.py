"""Exact production preprocessing used by VARUNA AIS LSTM-AE v2.1."""

from typing import Any

import numpy as np
import pandas as pd


FEATURE_COLUMNS_V21 = [
    "speed",
    "speed_change",
    "time_diff_min",
    "distance_step_km",
    "turn_angle_deg",
    "acceleration_kn_per_min",
    "net_displacement_km",
    "path_efficiency",
]

GAP_THRESHOLD_MIN = 120.0
LOW_SPEED_THRESHOLD_KN = 0.5
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1.astype(float))
    lon1 = np.radians(lon1.astype(float))
    lat2 = np.radians(lat2.astype(float))
    lon2 = np.radians(lon2.astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )
    a = np.clip(a, 0.0, 1.0)

    return EARTH_RADIUS_KM * (
        2.0 * np.arcsin(np.sqrt(a))
    )


def preprocess_ais_v21(
    raw_df: pd.DataFrame,
    gap_threshold_min: float = GAP_THRESHOLD_MIN,
    low_speed_threshold_kn: float = LOW_SPEED_THRESHOLD_KN,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    """Validate AIS rows, segment dark gaps, and build v2.1 features."""
    required_columns = [
        "vessel_id",
        "timestamp",
        "latitude",
        "longitude",
        "speed",
        "course",
    ]
    missing_columns = [
        column
        for column in required_columns
        if column not in raw_df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Missing input columns: {missing_columns}"
        )

    df = raw_df.copy()
    original_rows = len(df)

    df["vessel_id"] = (
        df["vessel_id"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce", utc=True
    )

    for column in ["latitude", "longitude", "speed", "course"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    valid_vessel = (
        df["vessel_id"].notna()
        & (df["vessel_id"].str.len() > 0)
    )
    valid_timestamp = df["timestamp"].notna()
    valid_coordinates = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    )
    valid_speed = (
        df["speed"].notna()
        & df["speed"].between(0, 102.3)
    )
    valid_mask = (
        valid_vessel
        & valid_timestamp
        & valid_coordinates
        & valid_speed
    )
    removed_invalid_rows = int((~valid_mask).sum())
    df = df.loc[valid_mask].copy()

    df = df.sort_values(
        ["vessel_id", "timestamp"], kind="stable"
    )
    duplicate_mask = df.duplicated(
        subset=["vessel_id", "timestamp"], keep="first"
    )
    removed_duplicate_rows = int(duplicate_mask.sum())
    df = df.loc[~duplicate_mask].copy().reset_index(drop=True)

    vessel_group = df.groupby("vessel_id", sort=False)
    df["previous_timestamp"] = (
        vessel_group["timestamp"].shift(1)
    )
    df["raw_time_diff_min"] = (
        df["timestamp"] - df["previous_timestamp"]
    ).dt.total_seconds() / 60.0

    invalid_time_mask = (
        df["raw_time_diff_min"].notna()
        & (df["raw_time_diff_min"] <= 0)
    )
    removed_time_inversions = int(invalid_time_mask.sum())
    df = df.loc[~invalid_time_mask].copy().reset_index(drop=True)

    vessel_group = df.groupby("vessel_id", sort=False)
    df["previous_timestamp"] = (
        vessel_group["timestamp"].shift(1)
    )
    df["previous_latitude"] = (
        vessel_group["latitude"].shift(1)
    )
    df["previous_longitude"] = (
        vessel_group["longitude"].shift(1)
    )
    df["raw_time_diff_min"] = (
        df["timestamp"] - df["previous_timestamp"]
    ).dt.total_seconds() / 60.0

    dark_gap_mask = df["raw_time_diff_min"] > gap_threshold_min
    dark_gap_events_df = df.loc[
        dark_gap_mask,
        [
            "vessel_id",
            "previous_timestamp",
            "timestamp",
            "previous_latitude",
            "previous_longitude",
            "latitude",
            "longitude",
            "raw_time_diff_min",
        ],
    ].copy()
    dark_gap_events_df = dark_gap_events_df.rename(
        columns={
            "previous_timestamp": "gap_start_utc",
            "timestamp": "gap_end_utc",
            "previous_latitude": "latitude_before",
            "previous_longitude": "longitude_before",
            "latitude": "latitude_after",
            "longitude": "longitude_after",
            "raw_time_diff_min": "gap_duration_minutes",
        }
    )
    dark_gap_events_df["event_type"] = "AIS_GAP_EVENT"
    dark_gap_events_df["coverage_status"] = "UNKNOWN"

    df["track_segment_id"] = (
        dark_gap_mask.groupby(df["vessel_id"])
        .cumsum()
        .astype(int)
    )
    segment_columns = ["vessel_id", "track_segment_id"]
    segment_group = df.groupby(segment_columns, sort=False)

    df["time_diff_min"] = (
        segment_group["timestamp"]
        .diff()
        .dt.total_seconds()
        .div(60.0)
        .fillna(0.0)
    )
    df["speed_change"] = (
        segment_group["speed"].diff().fillna(0.0)
    )

    previous_latitude = segment_group["latitude"].shift(1)
    previous_longitude = segment_group["longitude"].shift(1)
    df["distance_step_km"] = haversine_km(
        previous_latitude,
        previous_longitude,
        df["latitude"],
        df["longitude"],
    ).fillna(0.0)

    valid_course = (
        df["course"].notna()
        & df["course"].between(0, 360, inclusive="left")
    )
    df["course_reliable"] = (
        valid_course
        & (df["speed"] >= low_speed_threshold_kn)
    )
    previous_course = segment_group["course"].shift(1)
    previous_course_reliable = (
        segment_group["course_reliable"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )
    circular_turn = np.abs(
        (df["course"] - previous_course + 180.0)
        % 360.0
        - 180.0
    )
    turn_reliable = (
        df["course_reliable"] & previous_course_reliable
    )
    df["turn_angle_deg"] = np.where(
        turn_reliable, circular_turn, 0.0
    )

    df["acceleration_kn_per_min"] = np.where(
        df["time_diff_min"] > 0,
        df["speed_change"] / df["time_diff_min"],
        0.0,
    )

    segment_start_latitude = (
        segment_group["latitude"].transform("first")
    )
    segment_start_longitude = (
        segment_group["longitude"].transform("first")
    )
    df["net_displacement_km"] = haversine_km(
        segment_start_latitude,
        segment_start_longitude,
        df["latitude"],
        df["longitude"],
    ).fillna(0.0)
    df["cumulative_distance_km"] = (
        df.groupby(segment_columns, sort=False)[
            "distance_step_km"
        ].cumsum()
    )
    df["path_efficiency"] = np.where(
        df["cumulative_distance_km"] > 1e-6,
        df["net_displacement_km"]
        / df["cumulative_distance_km"],
        0.0,
    )
    df["path_efficiency"] = (
        df["path_efficiency"].clip(0.0, 1.0)
    )

    df[FEATURE_COLUMNS_V21] = (
        df[FEATURE_COLUMNS_V21]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    feature_values = df[FEATURE_COLUMNS_V21].to_numpy(
        dtype=np.float64
    )
    if not np.isfinite(feature_values).all():
        raise ValueError(
            "Non-finite values remain in model features"
        )

    dark_gap_records = dark_gap_events_df.to_dict(
        orient="records"
    )
    audit = {
        "pipeline_version": "ais-preprocessing-v2.1",
        "original_rows": int(original_rows),
        "processed_rows": int(len(df)),
        "removed_invalid_rows": removed_invalid_rows,
        "removed_duplicate_rows": removed_duplicate_rows,
        "removed_time_inversions": removed_time_inversions,
        "unique_vessels": int(df["vessel_id"].nunique()),
        "track_segments": int(
            df.groupby(segment_columns).ngroups
        ),
        "dark_gap_events": int(len(dark_gap_records)),
        "gap_threshold_minutes": gap_threshold_min,
        "low_speed_threshold_knots": low_speed_threshold_kn,
    }

    return df, dark_gap_records, audit
