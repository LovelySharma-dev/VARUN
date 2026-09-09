"""Canonical public request/response contracts for Phase 3 integration."""

from datetime import datetime
from math import isclose
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


SCORE_SEMANTICS = (
    "INVESTIGATIVE_PRIORITY_NOT_RESPONSIBILITY_PROBABILITY"
)
LEGAL_DISCLAIMER = (
    "Candidate ranking supports investigation and does not constitute "
    "legal attribution or proof of responsibility."
)


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


class ScoreBreakdownPointsPublic(PublicContractModel):
    """Weighted score-v1 contributions expressed on a 0-100 scale."""

    origin_proximity: float = Field(ge=0, le=100)
    origin_dwell: float = Field(ge=0, le=100)
    release_time_alignment: float = Field(ge=0, le=100)
    corridor_alignment: float = Field(ge=0, le=100)
    behaviour_rules: float = Field(ge=0, le=100)
    lstm_anomaly: float = Field(ge=0, le=100)
    dark_gap: float = Field(ge=0, le=100)

    def total(self) -> float:
        return float(
            self.origin_proximity
            + self.origin_dwell
            + self.release_time_alignment
            + self.corridor_alignment
            + self.behaviour_rules
            + self.lstm_anomaly
            + self.dark_gap
        )


class ClosestApproachPublic(PublicContractModel):
    distance_km: float = Field(ge=0)
    timestamp_utc: datetime

    @field_validator("timestamp_utc")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestampUtc must contain a UTC timezone")
        if value.utcoffset() is None:
            raise ValueError("timestampUtc must contain a UTC timezone")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("timestampUtc must be UTC")
        return value


class CandidateTrackRefPublic(PublicContractModel):
    artifact_file: Literal["candidate_tracks.geojson"]
    candidate_id: str = Field(min_length=1)


class DataQualityPublic(PublicContractModel):
    """Descriptive eligibility metadata; never a score-v1 component."""

    status: Literal["MODEL_ELIGIBLE"]
    observation_count: int = Field(ge=1)
    eligible_window_count: int = Field(ge=1)
    anomaly_window_count: int = Field(ge=0)
    included_in_score_v1: Literal[False]

    @model_validator(mode="after")
    def anomaly_count_cannot_exceed_windows(self):
        if self.anomaly_window_count > self.eligible_window_count:
            raise ValueError(
                "anomalyWindowCount cannot exceed eligibleWindowCount"
            )
        return self


class RankedCandidatePublic(PublicContractModel):
    # Existing canonical fields remain unchanged.
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

    # Additive dashboard projection fields.
    rank_label: str = Field(pattern=r"^CAND-[0-9]{3,}$")
    investigative_score: float = Field(ge=0, le=100)
    score_breakdown_points: ScoreBreakdownPointsPublic
    closest_approach: ClosestApproachPublic
    candidate_track_ref: CandidateTrackRefPublic
    data_quality: DataQualityPublic
    supporting_evidence: list[str]
    negative_evidence: list[str]
    warnings: list[str]
    legal_disclaimer: Literal[
        "Candidate ranking supports investigation and does not constitute "
        "legal attribution or proof of responsibility."
    ]

    @model_validator(mode="after")
    def validate_dashboard_projection(self):
        expected_label = f"CAND-{self.rank:03d}"
        if self.rank_label != expected_label:
            raise ValueError(
                f"rankLabel must be {expected_label} for rank {self.rank}"
            )

        expected_display_score = (
            self.investigative_priority_score * 100.0
        )
        if not isclose(
            self.investigative_score,
            expected_display_score,
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            raise ValueError(
                "investigativeScore must equal "
                "investigativePriorityScore multiplied by 100"
            )

        if not isclose(
            self.score_breakdown_points.total(),
            self.investigative_score,
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            raise ValueError(
                "scoreBreakdownPoints must reproduce investigativeScore"
            )

        if self.candidate_track_ref.candidate_id != self.candidate_id:
            raise ValueError(
                "candidateTrackRef.candidateId must match candidateId"
            )

        return self


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
