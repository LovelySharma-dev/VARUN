"""Reusable end-to-end Phase 3 AIS attribution pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.ais_loader import AISLoadResult, load_ais_csv
from app.behaviour_rules import (
    BehaviourEvidenceResult,
    BehaviourRuleConfig,
    build_behaviour_evidence,
)
from app.candidate_features import (
    CandidateFeatureResult,
    build_candidate_features,
)
from app.candidate_filter import (
    CandidateFilterResult,
    filter_ais_candidates,
)
from app.candidate_ranker import (
    CandidateRankingResult,
    RankingNormalization,
    RankingWeights,
    rank_candidates,
)
from app.inference_v21 import score_processed_ais
from app.model_registry import (
    AISModelPackage,
    load_ais_model_package,
)
from app.phase2_loader import load_phase2_bundle
from app.preprocessing_v21 import preprocess_ais_v21
from app.schemas import Phase2ToPhase3Contract


@dataclass
class Phase3AttributionResult:
    contract: Phase2ToPhase3Contract
    model_package: AISModelPackage
    ais_load: AISLoadResult
    candidate_filter: CandidateFilterResult
    spatial_evidence: CandidateFeatureResult
    behaviour_evidence: BehaviourEvidenceResult
    ranking: CandidateRankingResult
    processed_candidate_tracks: pd.DataFrame
    window_scores: pd.DataFrame
    model_summary: pd.DataFrame
    dark_gap_events: list[dict[str, Any]]
    preprocessing_audit: dict[str, Any]
    inference_audit: dict[str, Any]


def run_phase3_attribution(
    phase2_folder: str | Path,
    ais_csv_path: str | Path,
    *,
    window_stride: int = 2,
    batch_size: int = 1024,
    rule_config: BehaviourRuleConfig | None = None,
    ranking_weights: RankingWeights | None = None,
    ranking_normalization: RankingNormalization | None = None,
) -> Phase3AttributionResult:
    """Run filtering, v2.1 inference, evidence, and hybrid ranking."""
    contract = load_phase2_bundle(phase2_folder)
    ais_load = load_ais_csv(ais_csv_path)
    candidate_filter = filter_ais_candidates(
        ais_load.data, contract
    )

    if candidate_filter.candidate_tracks.empty:
        raise ValueError(
            "No AIS candidates matched the Phase 2 time/space gate"
        )

    model_input = candidate_filter.candidate_tracks.rename(
        columns={"mmsi": "vessel_id"}
    )
    (
        processed_candidate_tracks,
        dark_gap_events,
        preprocessing_audit,
    ) = preprocess_ais_v21(model_input)

    model_package = load_ais_model_package()
    window_scores, model_summary, inference_audit = (
        score_processed_ais(
            processed_candidate_tracks,
            model_package,
            window_stride=window_stride,
            batch_size=batch_size,
        )
    )

    if model_summary.empty:
        raise ValueError(
            "Candidate tracks contain no eligible 10-ping model windows"
        )

    spatial_evidence = build_candidate_features(
        candidate_filter, contract
    )
    behaviour_evidence = build_behaviour_evidence(
        processed_candidate_tracks,
        candidate_filter.identity_map,
        model_summary,
        dark_gap_events,
        config=rule_config,
        model_threshold=model_package.threshold,
    )
    ranking = rank_candidates(
        spatial_evidence.features,
        behaviour_evidence.features,
        weights=ranking_weights,
        normalization=ranking_normalization,
    )

    return Phase3AttributionResult(
        contract=contract,
        model_package=model_package,
        ais_load=ais_load,
        candidate_filter=candidate_filter,
        spatial_evidence=spatial_evidence,
        behaviour_evidence=behaviour_evidence,
        ranking=ranking,
        processed_candidate_tracks=processed_candidate_tracks,
        window_scores=window_scores,
        model_summary=model_summary,
        dark_gap_events=dark_gap_events,
        preprocessing_audit=preprocessing_audit,
        inference_audit=inference_audit,
    )
