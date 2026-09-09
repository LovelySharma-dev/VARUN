"""Core unit tests for Phase 2."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from app.utils import normalize_simulation_time, to_iso_utc, generate_run_id
from app.exceptions import TimeNormalizationError
from app.seeding.models import SeedingConfig


def test_time_normalization():
    """Test time normalization."""
    # ISO string
    dt_iso = "2026-09-03T08:30:00Z"
    dt_norm = normalize_simulation_time(dt_iso)
    assert isinstance(dt_norm, datetime)
    assert dt_norm.tzinfo is None

    # Native datetime
    dt_native = datetime(2026, 9, 3, 8, 30, 0)
    dt_norm2 = normalize_simulation_time(dt_native)
    assert dt_norm2 == dt_native


def test_iso_utc_conversion():
    """Test ISO UTC string conversion."""
    dt = datetime(2026, 9, 3, 8, 30, 0)
    iso_str = to_iso_utc(dt)
    assert iso_str == "2026-09-03T08:30:00Z"


def test_run_id_generation():
    """Test run ID generation."""
    run_id = generate_run_id()
    assert run_id.startswith("RUN-")
    assert len(run_id) == 16  # RUN- + 12 hex chars


def test_seeding_config():
    """Test seeding configuration."""
    config = SeedingConfig(
        particle_count=1500,
        seed_buffer_km=2.0,
        random_seed=42,
    )
    assert config.particle_count == 1500
    assert config.seed_buffer_km == 2.0
    assert config.random_seed == 42


@pytest.mark.parametrize(
    "iso_string",
    [
        "2026-09-03T08:30:00Z",
        "2026-09-03T08:30:00+00:00",
    ],
)
def test_time_normalization_variants(iso_string):
    """Test various ISO format variants."""
    dt = normalize_simulation_time(iso_string)
    assert dt.year == 2026
    assert dt.month == 9
    assert dt.day == 3


def test_time_normalization_invalid():
    """Test invalid time normalization."""
    with pytest.raises(TimeNormalizationError):
        normalize_simulation_time("not-a-valid-time")