"""Canonical public request/response contracts for Phase 3 integration."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PublicContractModel(BaseModel):
    """Use camelCase publicly while allowing Python snake_case internally."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class Phase3RunPublicRequest(PublicContractModel):
    phase2_folder: str = Field(min_length=1)
    ais_csv_path: str = Field(min_length=1)
    output_directory: str = Field(min_length=1)
    window_stride: int = Field(default=2, ge=1, le=10)
    batch_size: int = Field(default=1024, ge=1, le=4096)
    top_candidates: int = Field(default=3, ge=1, le=100)


class RankedCandidatePublic(PublicContractModel):
    rank: int = Field(ge=1)
    candidate_id: str = Field(min_length=1)
    investigative_priority_score: float = Field(ge=0, le=1)
    origin_proximity_score: float = Field(ge=0, le=1)
    origin_dwell_score: float = Field(ge=0, le=1)
    release_time_alignment_score: float = Field(ge=0, le=1)
    corridor_alignment_score: float = Field(ge=0, le=1)
    behaviour_rule_score: float = Field(ge=0, le=1)
    lstm_continuous_score: float = Field(ge=0, le=1)
    dark_gap_score: float = Field(ge=0, le=1)
    entered_origin_50: bool
    entered_origin_75: bool
    entered_origin_90: bool
    minimum_origin_center_distance_m: float = Field(ge=0)
    minimum_corridor_distance_m: float = Field(ge=0)
    closest_origin_midpoint_offset_min: float = Field(ge=0)
    score_semantics: Literal[
        "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
    ]
    calibration_status: str = Field(min_length=1)


class Phase3RunPublicResponse(PublicContractModel):
    status: Literal["completed"]
    case_id: str = Field(min_length=1)
    phase2_run_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    output_directory: str = Field(min_length=1)
    files: list[str]
    artifact_sha256: dict[str, str]
    candidate_count: int = Field(ge=0)
    scored_windows: int = Field(ge=0)
    score_semantics: Literal[
        "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
    ]
    calibration_status: str = Field(min_length=1)
    top_candidates: list[RankedCandidatePublic]
    warnings: list[Any]
