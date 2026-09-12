"""Orchestrates the full processing pipeline for one uploaded document:

validation -> OCR/text extraction -> AI field/table extraction ->
financial validation -> persistence -> structured JSON response.

Every expected failure mode (bad file, OCR failure, LLM failure, DB failure)
is caught here and turned into a controlled FAILED result instead of
propagating a raw stack trace to the caller.
"""
import datetime as dt
import time

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories import document_repository
from app.schemas.extraction import (
    DocumentResult, FileValidation, ProcessingMetadata, ValidationResult,
)
from app.services import (
    document_validation_service, extraction_service, financial_validation_service, ocr_service,
)
from app.utils.exceptions import AppError

logger = get_logger(__name__)


def _empty_file_validation(reason: str) -> FileValidation:
    return FileValidation(file_type="unknown", is_supported=False, is_readable=False,
                           page_count=0, status="FAILED", reason=reason)


def process_document(db: Session, filename: str, content_type: str, data: bytes, document_type: str) -> dict:
    started = time.time()
    now_iso = dt.datetime.utcnow().isoformat() + "Z"

    file_validation, kind, page_count = document_validation_service.validate_file(filename, content_type, data)

    if file_validation.status != "PASS":
        result = DocumentResult(
            document_name=filename,
            document_type=document_type,
            processing_status="FAILED",
            file_validation=file_validation,
            extracted_data={},
            tables={},
            validation=ValidationResult(checks=[], overall_status="NOT_APPLICABLE"),
            processing_metadata=ProcessingMetadata(
                ocr_used=False, processed_at=now_iso,
                processing_time_ms=int((time.time() - started) * 1000),
            ),
            error={"code": "FILE_VALIDATION_FAILED", "message": file_validation.reason},
        ).model_dump()
        document_repository.save_result(db, filename, document_type, "FAILED", result)
        return result

    ocr_used = False
    try:
        if kind == "pdf":
            pages_text, ocr_used = ocr_service.extract_text_pdf(data)
        else:
            pages_text, ocr_used = ocr_service.extract_text_image(data)

        llm_output = extraction_service.extract_fields(document_type, pages_text)
        extracted_data = llm_output.get("extracted_data", {})
        tables = llm_output.get("tables", {})

        validation = financial_validation_service.run_validation(document_type, extracted_data)

        processing_status = "FAILED" if validation.overall_status == "FAIL" else "PASS"

        confidences = [
            v.get("confidence") for v in extracted_data.values()
            if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float))
        ]
        overall_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

        result = DocumentResult(
            document_name=filename,
            document_type=document_type,
            processing_status=processing_status,
            overall_confidence=overall_confidence,
            file_validation=file_validation,
            extracted_data=extracted_data,
            tables=tables,
            validation=validation,
            processing_metadata=ProcessingMetadata(
                ocr_used=ocr_used,
                ocr_engine="tesseract" if ocr_used else None,
                llm_model="gemini",
                processed_at=now_iso,
                processing_time_ms=int((time.time() - started) * 1000),
            ),
        ).model_dump()

        document_repository.save_result(db, filename, document_type, processing_status, result, overall_confidence)
        return result

    except AppError as exc:
        logger.error("Processing failed for %s: %s", filename, exc.message)
        result = DocumentResult(
            document_name=filename,
            document_type=document_type,
            processing_status="FAILED",
            file_validation=file_validation,
            extracted_data={},
            tables={},
            validation=ValidationResult(checks=[], overall_status="NOT_APPLICABLE"),
            processing_metadata=ProcessingMetadata(
                ocr_used=ocr_used, processed_at=now_iso,
                processing_time_ms=int((time.time() - started) * 1000),
            ),
            error={"code": exc.code, "message": exc.message},
        ).model_dump()
        document_repository.save_result(db, filename, document_type, "FAILED", result)
        return result
