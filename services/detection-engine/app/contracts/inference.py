from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    image_path: str | None = None
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    tile_size: int = Field(default=512, gt=0)
    overlap: int = Field(default=64, ge=0)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class TileResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int


class DetectionResponse(BaseModel):
    x: float
    y: float
    width: float
    height: float
    confidence: float
    label: str


class InferenceResponse(BaseModel):
    status: str
    tile_count: int
    detection_count: int
    detections: list[DetectionResponse]
    tiles: list[TileResponse]
    model_version: str | None = None
