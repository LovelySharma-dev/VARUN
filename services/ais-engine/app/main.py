
# Health endpoint  and phase 2 validation endpoint
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError
from app.phase2_loader import load_phase2_bundle
from app.inference_v21 import score_ais_csv
from app.model_registry import load_ais_model_package
from app.attribution_pipeline import run_phase3_attribution
from app.artifact_writer import write_phase3_artifacts
from app.dashboard_projection import project_dashboard_candidates
from app.public_contracts import (
    Phase3RunPublicRequest,
    Phase3RunPublicResponse,
)
app = FastAPI(
    title="VARUN Phase 3 AIS Engine",
    version="0.1.0",
)


class Phase2FolderRequest(BaseModel):
    phase2_folder: str

class AISAnalysisRequest(BaseModel):
    ais_csv_path: str
    window_stride: int = Field(default=2, ge=1, le=10)
    batch_size: int = Field(default=1024, ge=1, le=4096)
    top_vessels: int = Field(default=20, ge=1, le=100)

class CandidateRankingRequest(BaseModel):
    phase2_folder: str
    ais_csv_path: str
    window_stride: int = Field(default=2, ge=1, le=10)
    batch_size: int = Field(default=1024, ge=1, le=4096)
    top_candidates: int = Field(default=20, ge=1, le=100)

class Phase3RunRequest(CandidateRankingRequest):
    output_directory: str


@app.get("/health")
def health():
    return {
        "service": "ais-engine",
        "phase": 3,
        "status": "healthy",
    }

@app.get("/model-info")
def model_info():
    try:
        package = load_ais_model_package()

        return {
            "status": "loaded",
            "model_version": package.metadata["model_version"],
            "model_type": package.metadata["model_type"],
            "time_steps": package.metadata["time_steps"],
            "feature_order": package.metadata["feature_order"],
            "input_shape": list(package.model.input_shape),
            "output_shape": list(package.model.output_shape),
            "scaler_feature_count": int(
                package.scaler.n_features_in_
            ),
            "reconstruction_error_threshold": (
                package.threshold
            ),
        }

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AIS model unavailable: {exc}",
        ) from exc
@app.post("/analyze-ais")
def analyze_ais(request: AISAnalysisRequest):
    try:
        package = load_ais_model_package()

        result = score_ais_csv(
            request.ais_csv_path,
            package,
            window_stride=request.window_stride,
            batch_size=request.batch_size,
        )

        top_vessels = json.loads(
            result.vessel_summary
            .head(request.top_vessels)
            .to_json(orient="records")
        )

        return {
            "status": "completed",
            "model_version": package.metadata["model_version"],
            "threshold": package.threshold,
            "load_audit": result.load_audit,
            "preprocessing_audit": (
                result.preprocessing_audit
            ),
            "inference_audit": result.inference_audit,
            "dark_gap_event_count": len(
                result.dark_gap_events
            ),
            "top_vessels": top_vessels,
        }

    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.post("/rank-candidates")
def rank_phase3_candidates(
    request: CandidateRankingRequest,
):
    try:
        result = run_phase3_attribution(
            request.phase2_folder,
            request.ais_csv_path,
            window_stride=request.window_stride,
            batch_size=request.batch_size,
        )

        rankings = json.loads(
            result.ranking.rankings
            .head(request.top_candidates)
            .to_json(orient="records")
        )

        return {
            "status": "completed",
            "case_id": result.contract.case_id,
            "phase2_run_id": result.contract.phase2_run_id,
            "model_version": (
                result.model_package
                .metadata["model_version"]
            ),
            "candidate_count": (
                result.ranking.audit["candidate_count"]
            ),
            "scored_windows": (
                result.inference_audit["scored_windows"]
            ),
            "dark_gap_event_count": len(
                result.dark_gap_events
            ),
            "score_semantics": (
                result.ranking.audit["score_semantics"]
            ),
            "calibration_status": (
                result.ranking.audit["normalization"][
                    "calibration_status"
                ]
            ),
            "ranked_candidates": rankings,
            "warnings": result.contract.warnings,
        }

    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
@app.post("/run-phase3")
def run_phase3(request: Phase3RunRequest):
    try:
        result = run_phase3_attribution(
            request.phase2_folder,
            request.ais_csv_path,
            window_stride=request.window_stride,
            batch_size=request.batch_size,
        )

        artifacts = write_phase3_artifacts(
            result,
            request.output_directory,
        )

        top_candidates = json.loads(
            result.ranking.rankings
            .head(request.top_candidates)
            .to_json(orient="records")
        )

        return {
            "status": "completed",
            "case_id": result.contract.case_id,
            "phase2_run_id": result.contract.phase2_run_id,
            "model_version": (
                result.model_package
                .metadata["model_version"]
            ),
            "output_directory": (
                artifacts["output_directory"]
            ),
            "files": artifacts["files"],
            "artifact_sha256": (
                artifacts["artifact_sha256"]
            ),
            "candidate_count": (
                result.ranking.audit["candidate_count"]
            ),
            "scored_windows": (
                result.inference_audit["scored_windows"]
            ),
            "score_semantics": (
                result.ranking.audit["score_semantics"]
            ),
            "calibration_status": (
                result.ranking.audit["normalization"][
                    "calibration_status"
                ]
            ),
            "top_candidates": top_candidates,
            "warnings": result.contract.warnings,
        }

    except (
        FileExistsError,
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    


@app.post(
    "/v1/phase3/run",
    response_model=Phase3RunPublicResponse,
    response_model_by_alias=True,
)
def run_phase3_public(
    request: Phase3RunPublicRequest,
) -> Phase3RunPublicResponse:
    """Stable additive dashboard contract for NestJS integration."""
    try:
        result = run_phase3_attribution(
            request.phase2_folder,
            request.ais_csv_path,
            window_stride=request.window_stride,
            batch_size=request.batch_size,
        )

        artifacts = write_phase3_artifacts(
            result,
            request.output_directory,
        )

        response_payload = {
            "status": "completed",
            "case_id": result.contract.case_id,
            "phase2_run_id": result.contract.phase2_run_id,
            "model_version": result.model_package.metadata[
                "model_version"
            ],
            "output_directory": artifacts["output_directory"],
            "files": artifacts["files"],
            "artifact_sha256": artifacts["artifact_sha256"],
            "candidate_count": result.ranking.audit[
                "candidate_count"
            ],
            "scored_windows": result.inference_audit[
                "scored_windows"
            ],
            "score_semantics": result.ranking.audit[
                "score_semantics"
            ],
            "calibration_status": result.ranking.audit[
                "normalization"
            ]["calibration_status"],
            "top_candidates": project_dashboard_candidates(
                result,
                top_candidates=request.top_candidates,
            ),
            "warnings": result.contract.warnings,
        }

        return Phase3RunPublicResponse.model_validate(
            response_payload
        )

    except (
        FileExistsError,
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

@app.post("/validate-phase2")
def validate_phase2(request: Phase2FolderRequest):
    try:
        contract = load_phase2_bundle(
            Path(request.phase2_folder)
        )

        return {
            "valid": True,
            "case_id": contract.case_id,
            "phase2_run_id": contract.phase2_run_id,
            "contract_version": contract.contract_version,
            "release_window": contract.release_window.model_dump(
                mode="json"
            ),
            "warnings": contract.warnings,
        }

    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        ValidationError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
