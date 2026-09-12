"""AI-based field & table extraction using an LLM (Google Gemini).

Design notes:
- The OCR/text-extraction step (ocr_service) is kept fully separate from
  this step, so the LLM provider can be swapped without touching OCR code.
- We ask the model to return ONLY JSON (response_mime_type=application/json)
  to avoid brittle regex/markdown-fence parsing.
- The prompt explicitly forbids inventing values: missing fields must be
  returned as null. This mirrors the case-study requirement.
- If the LLM call fails (no key / quota / network), we raise
  ExtractionFailureError so the caller can fail gracefully with a
  controlled error response instead of a stack trace.
"""
import json

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.exceptions import ExtractionFailureError

logger = get_logger(__name__)
settings = get_settings()

MIN_FIELDS_BY_TYPE = {
    "invoice": [
        "invoice_number", "invoice_date", "vendor_name", "customer_name",
        "currency", "subtotal", "tax_amount", "discount", "total_amount",
    ],
    "balance_sheet": ["total_assets", "total_liabilities", "total_equity"],
    "profit_and_loss": [
        "revenue", "cost_of_sales", "gross_profit", "operating_expenses",
        "operating_profit", "tax", "net_profit",
    ],
    "cash_flow_statement": [
        "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
        "opening_cash", "net_change_in_cash", "closing_cash",
    ],
}

SYSTEM_INSTRUCTIONS = """You are a meticulous financial document extraction engine.
You will be given OCR/text-extracted page content of a single financial document.
Extract ALL meaningful information visible in the document - not just a small fixed list.
This includes header fields, dates, parties, currencies, totals, every financial
statement line item, comparative-period values, and invoice/statement tables.

Rules (must follow exactly):
1. Only use values that are actually present in the given text. NEVER invent, guess
   or infer a value that is not supported by the document. If a field is not present
   or not legible, its value must be null.
2. For every extracted field, include the exact short source text snippet you used
   (source_text) and the page number it came from (page_number), when available.
3. Return ONLY valid JSON matching the schema described below. No markdown, no commentary.
4. Table / line-item data (e.g. invoice line items, statement line items across periods)
   must be returned as arrays of objects under "tables".
5. Numbers must be plain JSON numbers (no currency symbols or thousands separators).
   Treat bracketed/parenthesised accounting values, e.g. (1,234), as negative numbers.

Output JSON schema:
{
  "extracted_data": {
    "<field_name>": {"value": <string|number|null>, "page_number": <int|null>, "source_text": "<string|null>"}
  },
  "tables": {
    "<table_name>": [ {"<column>": <value>, ...}, ... ]
  }
}

At minimum, for this document type, try to populate these fields if present in the text: {min_fields}
"""


def _build_prompt(document_type: str, pages_text: list[str]) -> str:
    min_fields = ", ".join(MIN_FIELDS_BY_TYPE.get(document_type, []))
    # NOTE: use a plain replace (not str.format) because the instructions
    # contain literal JSON braces that would otherwise be mis-parsed as
    # format placeholders.
    instructions = SYSTEM_INSTRUCTIONS.replace("{min_fields}", min_fields)
    body_parts = []
    for i, text in enumerate(pages_text, start=1):
        body_parts.append(f"--- PAGE {i} ---\n{text}")
    body = "\n\n".join(body_parts)
    return f"{instructions}\n\nDOCUMENT TYPE: {document_type}\n\nDOCUMENT TEXT:\n{body}"


def extract_fields(document_type: str, pages_text: list[str]) -> dict:
    """Calls the configured LLM and returns a dict with keys
    'extracted_data' and 'tables'. Raises ExtractionFailureError on any
    failure (missing key, API error, invalid JSON, etc.).
    """
    if not settings.gemini_api_key:
        raise ExtractionFailureError(
            "No LLM API key configured (GEMINI_API_KEY). Set it in the environment to enable extraction.",
            code="LLM_NOT_CONFIGURED",
        )

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json", "temperature": 0.0},
        )
        prompt = _build_prompt(document_type, pages_text)
        response = model.generate_content(prompt)
        raw = response.text
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.exception("LLM returned invalid JSON")
        raise ExtractionFailureError(f"Model returned invalid JSON: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM extraction call failed")
        raise ExtractionFailureError(f"LLM extraction failed: {exc}") from exc

    parsed.setdefault("extracted_data", {})
    parsed.setdefault("tables", {})
    return parsed
