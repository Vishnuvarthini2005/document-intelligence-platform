"""API routes for document processing, retrieval and the dashboard list."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.repositories import document_repository
from app.services import document_service
from app.utils.exceptions import AppError

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["documents"])

ALLOWED_DOCUMENT_TYPES = {"invoice", "balance_sheet", "profit_and_loss", "cash_flow_statement"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/documents/process")
async def process_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_DOCUMENT_TYPE",
                               "message": f"document_type must be one of {sorted(ALLOWED_DOCUMENT_TYPES)}"}},
        )

    try:
        data = await file.read()
        result = document_service.process_document(
            db, file.filename, file.content_type, data, document_type
        )
        return result
    except AppError as exc:
        logger.error("Unhandled AppError in route: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail={"error": {"code": exc.code, "message": exc.message}})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error processing document")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred while processing the document."}},
        )


@router.get("/documents/{document_name}")
def get_document(document_name: str, db: Session = Depends(get_db)):
    try:
        record = document_repository.get_latest_by_name(db, document_name)
        return json.loads(record.result_json)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": {"code": exc.code, "message": exc.message}})


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    records = document_repository.list_all(db)
    return [
        {
            "id": r.id,
            "document_name": r.document_name,
            "document_type": r.document_type,
            "processing_status": r.processing_status,
            "overall_confidence": r.overall_confidence,
            "created_at": r.created_at.isoformat() + "Z",
        }
        for r in records
    ]
