#Is file mein Phase 2 → Phase 3 contract define karo:

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ReleaseWindow(BaseModel):
    start_utc: datetime
    end_utc: datetime
    time_buffer_minutes: int = Field(ge=0, le=1440)

    @field_validator("start_utc", "end_utc")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timestamp must contain UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("Timestamp must be UTC")
        return value

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.start_utc > self.end_utc:
            raise ValueError("start_utc must be before end_utc")
        return self


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)


class OriginContours(BaseModel):
    density_50: GeoJSONFeature
    density_75: GeoJSONFeature
    density_90: GeoJSONFeature


class EvidenceSurface(BaseModel):
    kind: str
    path: str | None = None


class SearchRegion(BaseModel):
    geometry: dict[str, Any]
    spatial_buffer_m: float = Field(ge=0)


class HindcastCorridor(BaseModel):
    geometry: dict[str, Any]
    direction_deg: float | None = Field(default=None, ge=0, lt=360)
    time_bands: list[dict[str, Any]] = Field(default_factory=list)


class Phase2ToPhase3Contract(BaseModel):
    contract_version: Literal["phase2-to-phase3-v1"]

    case_id: str = Field(min_length=1)
    phase2_run_id: str = Field(min_length=1)

    detection_time_utc: datetime
    crs: Literal["EPSG:4326"]

    release_window: ReleaseWindow
    origin_contours: OriginContours

    origin_evidence_surface: EvidenceSurface | None = None
    search_region: SearchRegion
    hindcast_corridor: HindcastCorridor

    ranked_origin_regions: list[dict[str, Any]] = Field(default_factory=list)
    alternative_modes: list[dict[str, Any]] = Field(default_factory=list)

    reconstruction_metrics: dict[str, Any] = Field(default_factory=dict)
    forcing_uncertainty: dict[str, Any] = Field(default_factory=dict)
    dashboard_artifacts: dict[str, Any] = Field(default_factory=dict)

    warnings: list[Any] = Field(default_factory=list)
    provenance: dict[str, Any]

    @field_validator("detection_time_utc")
    @classmethod
    def detection_time_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("detection_time_utc must contain UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("detection_time_utc must be UTC")
        return value

    @model_validator(mode="after")
    def release_must_not_exceed_detection(self):
        if self.release_window.end_utc > self.detection_time_utc:
            raise ValueError(
                "release_window.end_utc cannot be after detection_time_utc"
            )
        return self