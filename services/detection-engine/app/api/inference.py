from pathlib import Path

import rasterio
from fastapi import APIRouter, HTTPException

from app.contracts.inference import (
    DetectionResponse,
    InferenceRequest,
    InferenceResponse,
    TileResponse,
)
from app.inference.pipeline import run_inference
from app.inference.tiling import create_tiles


router = APIRouter()

MODEL_PATH = (
    Path(__file__).resolve().parents[4]
    / "models"
    / "phase1"
    / "unet_oil_spill_v0.1.pth"
)


@router.post(
    "/inference",
    response_model=InferenceResponse,
)
def inference(request: InferenceRequest):

    # ---------------------------------
    # TILE-ONLY VALIDATION MODE
    # ---------------------------------
    if request.image_path is None:
        tiles = create_tiles(
            image_width=request.image_width,
            image_height=request.image_height,
            tile_size=request.tile_size,
            overlap=request.overlap,
        )

        return InferenceResponse(
            status="SUCCESS",
            tile_count=len(tiles),
            detection_count=0,
            detections=[],
            tiles=[
                TileResponse(
                    x=int(t.x),
                    y=int(t.y),
                    width=int(t.width),
                    height=int(t.height),
                )
                for t in tiles
            ],
            model_version="unet_oil_spill_v0.1",
        )

    image_path = Path(request.image_path)

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Image not found: {image_path}",
        )

    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Model not found: {MODEL_PATH}",
        )

    try:
        with rasterio.open(image_path) as src:
            image = src.read()
            height = src.height
            width = src.width

        if width != request.image_width or height != request.image_height:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Image dimensions ({width}, {height}) do not match "
                    f"request ({request.image_width}, {request.image_height})"
                ),
            )

        result = run_inference(
            image=image,
            image_width=width,
            image_height=height,
            model_path=str(MODEL_PATH),
            tile_size=request.tile_size,
            overlap=request.overlap,
            confidence_threshold=request.confidence_threshold,
            iou_threshold=request.iou_threshold,
        )

        detections = [
            DetectionResponse(
                x=float(d.x),
                y=float(d.y),
                width=float(d.width),
                height=float(d.height),
                confidence=float(d.score),
                label="OIL_LIKELIHOOD",
            )
            for d in result["detections"]
        ]

        tiles = [
            TileResponse(
                x=int(t.x),
                y=int(t.y),
                width=int(t.width),
                height=int(t.height),
            )
            for t in result["tiles"]
        ]

        return InferenceResponse(
            status="SUCCESS",
            tile_count=len(tiles),
            detection_count=len(detections),
            detections=detections,
            tiles=tiles,
            model_version="unet_oil_spill_v0.1",
        )

    except HTTPException:
        raise

    except Exception as exc:
        print("INFERENCE ERROR:", repr(exc))

        raise HTTPException(
            status_code=500,
            detail={
                "error": "INFERENCE_FAILED",
                "message": str(exc),
            },
        ) from exc
