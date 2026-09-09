from pydantic import BaseModel, Field


class PreprocessingProfile(BaseModel):
    name: str
    version: str
    tile_size: int = Field(gt=0)
    overlap: int = Field(ge=0)
