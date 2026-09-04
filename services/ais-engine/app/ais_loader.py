from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


COLUMN_ALIASES = {
    "mmsi": "mmsi",
    "vessel_id": "mmsi",
    "basedatetime": "timestamp",
    "base_date_time": "timestamp",
    "timestamp": "timestamp",
    "lat": "latitude",
    "latitude": "latitude",
    "lon": "longitude",
    "longitude": "longitude",
    "sog": "speed",
    "speed": "speed",
    "cog": "course",
    "course": "course",
}

REQUIRED_COLUMNS = [
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
    "speed",
    "course",
]


@dataclass
class AISLoadResult:
    data: pd.DataFrame
    audit: dict[str, Any]


def normalize_column_name(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def load_ais_csv(csv_path: str | Path) -> AISLoadResult:
    path = Path(csv_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"AIS CSV not found: {path}")

    if not path.is_file():
        raise ValueError(f"AIS input is not a file: {path}")

    # utf-8-sig normal UTF-8 aur BOM-containing files dono handle karta hai.
    dataframe = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype={"mmsi": "string"},
        low_memory=False,
    )

    original_rows = len(dataframe)

    normalized_columns = {
        column: normalize_column_name(column)
        for column in dataframe.columns
    }
    dataframe = dataframe.rename(columns=normalized_columns)

    alias_renames = {
        column: COLUMN_ALIASES[column]
        for column in dataframe.columns
        if column in COLUMN_ALIASES
    }
    dataframe = dataframe.rename(columns=alias_renames)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required AIS columns: "
            + ", ".join(missing_columns)
        )

    dataframe = dataframe.copy()

    # Preserve MMSI internally as restricted identity.
    dataframe["mmsi"] = (
        dataframe["mmsi"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    raw_timestamp = dataframe["timestamp"].astype("string")

    # NOAA timestamps without timezone are interpreted as UTC for this
    # registered data source. The assumption is recorded in the audit.
    timezone_missing = ~raw_timestamp.str.contains(

        r"(?:Z|[+-]\d{2}:\d{2})$",
        regex=True,
        na=False,
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    numeric_columns = [
        "latitude",
        "longitude",
        "speed",
        "course",
    ]

    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    invalid_mmsi = ~dataframe["mmsi"].str.fullmatch(
        r"\d{9}",
        na=False,
    )
    invalid_timestamp = dataframe["timestamp"].isna()
    invalid_coordinates = (
        dataframe["latitude"].isna()
        | dataframe["longitude"].isna()
        | ~dataframe["latitude"].between(-90, 90)
        | ~dataframe["longitude"].between(-180, 180)
    )
    invalid_speed = (
        dataframe["speed"].isna()
        | (dataframe["speed"] < 0)
        | (dataframe["speed"] > 102.3)
    )
    invalid_course = (
        dataframe["course"].isna()
        | (dataframe["course"] < 0)
        | (dataframe["course"] >= 360)
    )

    invalid_any = (
        invalid_mmsi
        | invalid_timestamp
        | invalid_coordinates
        | invalid_speed
        | invalid_course
    )

    invalid_rows = int(invalid_any.sum())
    dataframe = dataframe.loc[~invalid_any].copy()

    duplicate_mask = dataframe.duplicated(
        subset=[
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
        ],
        keep="first",
    )
    duplicate_rows = int(duplicate_mask.sum())
    dataframe = dataframe.loc[~duplicate_mask].copy()

    dataframe = dataframe.sort_values(
        ["mmsi", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)

    audit = {
        "source_file": path.name,
        "original_rows": original_rows,
        "valid_rows": len(dataframe),
        "removed_invalid_rows": invalid_rows,
        "removed_duplicate_rows": duplicate_rows,
        "unique_vessels": int(dataframe["mmsi"].nunique()),
        "timezone_assumption": "UTC",
        "timestamps_missing_explicit_timezone": int(
            timezone_missing.sum()
        ),
        "time_start_utc": (
            dataframe["timestamp"].min().isoformat()
            if not dataframe.empty
            else None
        ),
        "time_end_utc": (
            dataframe["timestamp"].max().isoformat()
            if not dataframe.empty
            else None
        ),
    }

    return AISLoadResult(
        data=dataframe,
        audit=audit,
    )
