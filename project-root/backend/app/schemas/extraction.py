"""Pydantic schemas describing the structured extraction/validation envelope.

Field lists are intentionally NOT hard-coded to a fixed set: the case study
requires ALL meaningful visible fields to be extracted, so `extracted_data`
and `tables` are flexible containers. The minimum-required keys per document
type (Table 4 of the brief) are enforced only loosely by the extraction
prompt, not by strict schema validation, so the model can surface extra
fields it finds without being rejected.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source_text: Optional[str] = None
    page_number: Optional[int] = None


class ExtractedField(BaseModel):
    value: Any = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None


class FileValidation(BaseModel):
    file_type: str
    is_supported: bool
    is_readable: bool
    page_count: int
    status: str  # PASS / FAILED
    reason: Optional[str] = None


class ValidationCheck(BaseModel):
    name: str
    formula: str
    operands: dict[str, Any] = Field(default_factory=dict)
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: str  # PASS / FAIL / NOT_APPLICABLE
    period: Optional[str] = None
    message: Optional[str] = None


class ValidationResult(BaseModel):
    checks: list[ValidationCheck] = Field(default_factory=list)
    overall_status: str = "NOT_APPLICABLE"
    issues: list[str] = Field(default_factory=list)


class ProcessingMetadata(BaseModel):
    ocr_used: bool
    ocr_engine: Optional[str] = None
    llm_model: Optional[str] = None
    processed_at: str
    processing_time_ms: int


class DocumentResult(BaseModel):
    document_name: str
    document_type: str
    processing_status: str  # PASS / FAILED
    overall_confidence: Optional[float] = None
    file_validation: FileValidation
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    tables: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationResult
    processing_metadata: ProcessingMetadata
    error: Optional[dict[str, Any]] = None
