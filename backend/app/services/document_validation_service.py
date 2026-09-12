"""Input-control layer: validates uploaded files BEFORE OCR/extraction.

This only checks file type / readability / page count / integrity.
It intentionally does not attempt document-type classification.
"""
import io

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.extraction import FileValidation

logger = get_logger(__name__)
settings = get_settings()

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
}

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image"}


def _guess_kind(filename: str, content_type: str | None) -> str | None:
    if content_type in SUPPORTED_TYPES:
        return SUPPORTED_TYPES[content_type]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return SUPPORTED_EXTENSIONS.get(ext)


def validate_file(filename: str, content_type: str | None, data: bytes) -> tuple[FileValidation, str | None, int]:
    """Returns (FileValidation, kind['pdf'|'image'|None], page_count).

    Never raises for expected validation failures; encodes them in
    FileValidation.status == "FAILED" with a `reason`, so the caller can
    fail gracefully with a controlled JSON error instead of a stack trace.
    """
    if not data:
        logger.warning("Empty file uploaded: %s", filename)
        return FileValidation(
            file_type=content_type or "unknown",
            is_supported=False,
            is_readable=False,
            page_count=0,
            status="FAILED",
            reason="Uploaded file is empty.",
        ), None, 0

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        return FileValidation(
            file_type=content_type or "unknown",
            is_supported=False,
            is_readable=False,
            page_count=0,
            status="FAILED",
            reason=f"File exceeds the {settings.max_file_size_mb}MB size limit.",
        ), None, 0

    kind = _guess_kind(filename, content_type)
    if kind is None:
        logger.warning("Unsupported file type: %s (%s)", filename, content_type)
        return FileValidation(
            file_type=content_type or "unknown",
            is_supported=False,
            is_readable=False,
            page_count=0,
            status="FAILED",
            reason="Only PDF / JPG / PNG documents are supported.",
        ), None, 0

    if kind == "pdf":
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            page_count = doc.page_count
            if page_count == 0:
                raise ValueError("PDF has zero pages")
            # touch first page to confirm it's readable, not just a valid header
            _ = doc[0].get_text()
            doc.close()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Corrupted/unreadable PDF: %s", filename)
            return FileValidation(
                file_type=content_type or "application/pdf",
                is_supported=True,
                is_readable=False,
                page_count=0,
                status="FAILED",
                reason=f"PDF could not be read: {exc}",
            ), None, 0

        if page_count > settings.max_pages:
            return FileValidation(
                file_type=content_type or "application/pdf",
                is_supported=True,
                is_readable=True,
                page_count=page_count,
                status="FAILED",
                reason=f"Document has {page_count} pages; maximum allowed is {settings.max_pages}.",
            ), "pdf", page_count

        return FileValidation(
            file_type=content_type or "application/pdf",
            is_supported=True,
            is_readable=True,
            page_count=page_count,
            status="PASS",
        ), "pdf", page_count

    # image
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Corrupted/unreadable image: %s", filename)
        return FileValidation(
            file_type=content_type or "image",
            is_supported=True,
            is_readable=False,
            page_count=0,
            status="FAILED",
            reason=f"Image could not be read: {exc}",
        ), None, 0

    return FileValidation(
        file_type=content_type or "image",
        is_supported=True,
        is_readable=True,
        page_count=1,
        status="PASS",
    ), "image", 1
