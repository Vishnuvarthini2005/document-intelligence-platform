"""Text extraction / OCR service.

Strategy:
- Native PDFs: extract embedded text directly via PyMuPDF (fast, accurate,
  no OCR needed).
- Scanned PDFs (little/no embedded text) and JPG/PNG images: rasterize
  and run Tesseract OCR (pytesseract) per page.

Returns page-wise text so the extraction step can attach page numbers to
evidence, and so downstream code can tell whether OCR was actually used.
"""
import io

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.core.logging import get_logger
from app.utils.exceptions import OCRFailureError

logger = get_logger(__name__)

# A native PDF page with fewer than this many extractable characters is
# treated as "probably scanned" and falls back to OCR for that page.
MIN_NATIVE_TEXT_CHARS = 20


def extract_text_pdf(data: bytes) -> tuple[list[str], bool]:
    """Returns (list of per-page text, ocr_used)."""
    pages: list[str] = []
    ocr_used = False
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        for page_index in range(doc.page_count):
            page = doc[page_index]
            text = page.get_text().strip()
            if len(text) >= MIN_NATIVE_TEXT_CHARS:
                pages.append(text)
                continue

            # Fall back to OCR for this page (likely scanned/image-based)
            ocr_used = True
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            pages.append(ocr_text.strip())
        doc.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("OCR/text extraction failed for PDF")
        raise OCRFailureError(f"Failed to extract text from PDF: {exc}") from exc

    return pages, ocr_used


def extract_text_image(data: bytes) -> tuple[list[str], bool]:
    try:
        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
        return [text.strip()], True
    except Exception as exc:  # noqa: BLE001
        logger.exception("OCR failed for image")
        raise OCRFailureError(f"Failed to OCR image: {exc}") from exc
