"""
Data models for forcing files.

Represents the structure of forcing data and audit results.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SpatialBounds(BaseModel):
    """Spatial bounds of forcing data."""

    lat_min: float = Field(..., description="Minimum latitude")
    lat_max: float = Field(..., description="Maximum latitude")
    lon_min: float = Field(..., description="Minimum longitude")
    lon_max: float = Field(..., description="Maximum longitude")

    def contains(self, lat: float, lon: float) -> bool:
        """Check if point is within bounds."""
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lon_min <= lon <= self.lon_max
        )


class TemporalBounds(BaseModel):
    """Temporal bounds of forcing data."""

    time_start: datetime = Field(..., description="Start time")
    time_end: datetime = Field(..., description="End time")

    @property
    def duration_hours(self) -> float:
        """Duration in hours."""
        return (self.time_end - self.time_start).total_seconds() / 3600


class VariableInfo(BaseModel):
    """Information about a forcing variable."""

    name: str = Field(..., description="Variable name in file")
    standard_name: Optional[str] = Field(
        None, description="Standard name (current_u, current_v, wind_u, wind_v)"
    )
    units: str = Field(..., description="Units of variable")
    shape: tuple[int, ...] = Field(..., description="Shape of data array")
    missing_fraction: float = Field(..., description="Fraction of missing values")


class ForcingAuditResult(BaseModel):
    """Result of forcing file audit."""

    file_path: Path = Field(..., description="Path to forcing file")
    passed: bool = Field(..., description="Whether audit passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")

    # Structure
    variables: dict[str, VariableInfo] = Field(
        ..., description="Available variables"
    )
    coordinates: dict[str, bool] = Field(
        ..., description="Which coordinates are present"
    )

    # Bounds
    spatial_bounds: Optional[SpatialBounds] = Field(
        None, description="Spatial domain"
    )
    temporal_bounds: Optional[TemporalBounds] = Field(
        None, description="Temporal domain"
    )

    # Data quality
    current_variables_found: list[str] = Field(
        default_factory=list, description="Found current velocity variables"
    )
    wind_variables_found: list[str] = Field(
        default_factory=list, description="Found wind variables"
    )

    file_size_mb: float = Field(..., description="File size in MB")
    is_valid_netcdf: bool = Field(..., description="Is valid NetCDF")

    def summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Forcing Audit: {self.file_path.name}",
            f"  Valid NetCDF: {self.is_valid_netcdf}",
            f"  Passed: {self.passed}",
            f"  File size: {self.file_size_mb:.2f} MB",
        ]

        if self.spatial_bounds:
            b = self.spatial_bounds
            lines.append(
                f"  Spatial: lat [{b.lat_min:.2f}, {b.lat_max:.2f}] "
                f"lon [{b.lon_min:.2f}, {b.lon_max:.2f}]"
            )

        if self.temporal_bounds:
            t = self.temporal_bounds
            lines.append(
                f"  Temporal: {t.time_start.isoformat()} → "
                f"{t.time_end.isoformat()} ({t.duration_hours:.1f} hours)"
            )

        lines.append(f"  Variables: {len(self.variables)}")
        for var_name, info in self.variables.items():
            lines.append(
                f"    - {var_name}: {info.standard_name} "
                f"({info.units}, {info.missing_fraction*100:.1f}% missing)"
            )

        if self.errors:
            lines.append("  ERRORS:")
            for err in self.errors:
                lines.append(f"    - {err}")

        if self.warnings:
            lines.append("  WARNINGS:")
            for warn in self.warnings:
                lines.append(f"    - {warn}")

        return "\n".join(lines)


class ForcingConfig(BaseModel):
    """Configuration for forcing files."""

    current_file: Optional[Path] = Field(None, description="Path to current NetCDF")
    wind_file: Optional[Path] = Field(None, description="Path to wind NetCDF")
    combined_file: Optional[Path] = Field(
        None, description="Path to combined NetCDF with both currents and wind"
    )

    def get_files(self) -> list[Path]:
        """Get all configured forcing files."""
        files = []
        if self.current_file:
            files.append(self.current_file)
        if self.wind_file:
            files.append(self.wind_file)
        if self.combined_file:
            files.append(self.combined_file)
        return files