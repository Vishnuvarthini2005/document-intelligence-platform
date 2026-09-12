"""Persistence layer: all direct DB access for processed documents lives here."""
import json

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.document import ProcessedDocument
from app.utils.exceptions import DatabaseError, DocumentNotFoundError

logger = get_logger(__name__)


def save_result(db: Session, document_name: str, document_type: str,
                 processing_status: str, result: dict, overall_confidence=None) -> ProcessedDocument:
    try:
        record = ProcessedDocument(
            document_name=document_name,
            document_type=document_type,
            processing_status=processing_status,
            result_json=json.dumps(result),
            overall_confidence=str(overall_confidence) if overall_confidence is not None else None,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to persist processed document")
        raise DatabaseError(f"Failed to save processed result: {exc}") from exc


def get_latest_by_name(db: Session, document_name: str) -> ProcessedDocument:
    record = (
        db.query(ProcessedDocument)
        .filter(ProcessedDocument.document_name == document_name)
        .order_by(desc(ProcessedDocument.created_at))
        .first()
    )
    if not record:
        raise DocumentNotFoundError(f"No processed result found for document '{document_name}'.")
    return record


def list_all(db: Session, limit: int = 200) -> list[ProcessedDocument]:
    return (
        db.query(ProcessedDocument)
        .order_by(desc(ProcessedDocument.created_at))
        .limit(limit)
        .all()
    )


def get_by_id(db: Session, record_id: int) -> ProcessedDocument:
    record = db.query(ProcessedDocument).filter(ProcessedDocument.id == record_id).first()
    if not record:
        raise DocumentNotFoundError(f"No processed document with id {record_id}.")
    return record
