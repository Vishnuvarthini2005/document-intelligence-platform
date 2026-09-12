"""Request/response schemas for the API layer."""
from typing import Optional
from pydantic import BaseModel


class DocumentListItem(BaseModel):
    id: int
    document_name: str
    document_type: str
    processing_status: str
    overall_confidence: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    error: dict
