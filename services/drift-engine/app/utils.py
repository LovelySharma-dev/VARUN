"""
Utility functions for VARUN Phase 2.

Including time normalization, logging, path handling, etc.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from app.exceptions import TimeNormalizationError

logger = logging.getLogger(__name__)


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return f"RUN-{uuid.uuid4().hex[:12].upper()}"


def normalize_simulation_time(
    dt: datetime | np.datetime64 | str,
    name: str = "datetime",
) -> datetime:
    """
    Normalize any datetime representation to timezone-naive UTC datetime.

    OpenDrift expects timezone-naive UTC datetimes internally.
    This function ensures consistent time handling throughout Phase 2.

    Args:
        dt: datetime in any format
        name: description of the time for error messages

    Returns:
        Timezone-naive UTC datetime

    Raises:
        TimeNormalizationError: If normalization fails
    """
    try:
        # Handle string ISO-8601
        if isinstance(dt, str):
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed

        # Handle numpy datetime64
        if isinstance(dt, np.datetime64):
            # Convert to pandas Timestamp then to datetime
            import pandas as pd
            ts = pd.Timestamp(dt)
            if ts.tzinfo is not None:
                ts = ts.tz_convert("UTC").tz_localize(None)
            return ts.to_pydatetime()

        # Handle datetime
        if isinstance(dt, datetime):
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        raise ValueError(f"Cannot normalize {type(dt).__name__}")

    except Exception as e:
        raise TimeNormalizationError(
            f"Failed to normalize {name}: {e}",
            details={"input": str(dt), "type": type(dt).__name__},
        ) from e


def to_iso_utc(dt: datetime) -> str:
    """Convert datetime to ISO-8601 UTC string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def ensure_output_dir(base_dir: Path, run_id: str) -> Path:
    """
    Ensure output directory exists.

    Args:
        base_dir: Base output directory
        run_id: Run identifier

    Returns:
        Path to run output directory
    """
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger_obj = logging.getLogger(name)
    if not logger_obj.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger_obj.addHandler(handler)
    return logger_obj


def get_time_offset(dt_ref: datetime, dt_target: datetime) -> timedelta:
    """Get time offset from reference to target datetime."""
    return dt_target - dt_ref


def hours_to_timedelta(hours: float) -> timedelta:
    """Convert hours to timedelta."""
    return timedelta(hours=hours)


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp value to [minimum, maximum]."""
    return max(minimum, min(value, maximum))


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate distance between two lat/lon points in kilometers.

    Uses Haversine formula.
    """
    R_KM = 6371.0  # Earth radius in kilometers

    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    return R_KM * c