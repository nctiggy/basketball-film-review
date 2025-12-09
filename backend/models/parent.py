"""
Pydantic models for parent-specific requests and responses.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ChildResponse(BaseModel):
    """Response model for a parent's linked children."""
    id: str
    username: Optional[str]
    display_name: str
    phone: Optional[str]
    linked_at: Optional[datetime]

    # Optional player profile info
    jersey_number: Optional[str]
    position: Optional[str]
    graduation_year: Optional[int]

    class Config:
        from_attributes = True
