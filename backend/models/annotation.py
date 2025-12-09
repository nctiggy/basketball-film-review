"""
Pydantic models for clip annotation-related requests and responses.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AnnotationData(BaseModel):
    """Request model for saving/updating annotations."""
    drawing_data: Optional[Dict[str, Any]] = Field(None, description="Fabric.js canvas JSON state")

    class Config:
        from_attributes = True


class AnnotationResponse(BaseModel):
    """Response model for annotation data."""
    id: str
    clip_id: str
    created_by: Optional[str]
    drawing_data: Optional[Dict[str, Any]]
    audio_path: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
