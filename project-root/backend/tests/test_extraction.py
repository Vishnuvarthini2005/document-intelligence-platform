"""Tests around the extraction service's behavior when unconfigured."""
import pytest

from app.services import extraction_service
from app.utils.exceptions import ExtractionFailureError


def test_extraction_raises_when_no_api_key(monkeypatch):
    monkeypatch.setattr(extraction_service.settings, "gemini_api_key", "")
    with pytest.raises(ExtractionFailureError):
        extraction_service.extract_fields("invoice", ["some text"])


def test_prompt_includes_document_type_and_min_fields():
    prompt = extraction_service._build_prompt("invoice", ["Invoice total: 100"])
    assert "invoice" in prompt.lower()
    assert "invoice_number" in prompt
