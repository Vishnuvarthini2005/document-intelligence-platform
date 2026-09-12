"""Unit tests for file validation and financial calculation validation."""
import io

from PIL import Image

from app.services import document_validation_service, financial_validation_service


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    return buf.getvalue()


def test_empty_file_is_rejected():
    fv, kind, pages = document_validation_service.validate_file("empty.pdf", "application/pdf", b"")
    assert fv.status == "FAILED"
    assert kind is None


def test_unsupported_extension_is_rejected():
    fv, kind, pages = document_validation_service.validate_file("resume.docx", None, b"some bytes")
    assert fv.status == "FAILED"
    assert not fv.is_supported


def test_valid_png_passes():
    fv, kind, pages = document_validation_service.validate_file("scan.png", "image/png", _tiny_png_bytes())
    assert fv.status == "PASS"
    assert kind == "image"
    assert pages == 1


def test_invoice_validation_pass():
    data = {
        "subtotal": {"value": 12500.00},
        "tax_amount": {"value": 625.00},
        "discount": {"value": 0.00},
        "total_amount": {"value": 13125.00},
    }
    result = financial_validation_service.run_validation("invoice", data)
    assert result.overall_status == "PASS"
    assert result.checks[0].status == "PASS"


def test_invoice_validation_fail_on_mismatch():
    data = {
        "subtotal": {"value": 100.00},
        "tax_amount": {"value": 5.00},
        "discount": {"value": 0.00},
        "total_amount": {"value": 999.00},  # wrong total
    }
    result = financial_validation_service.run_validation("invoice", data)
    assert result.overall_status == "FAIL"


def test_validation_not_applicable_when_fields_missing():
    data = {"vendor_name": {"value": "ACME"}}
    result = financial_validation_service.run_validation("invoice", data)
    assert result.overall_status == "NOT_APPLICABLE"


def test_balance_sheet_equation():
    data = {
        "total_assets": {"value": 1000},
        "total_liabilities": {"value": 600},
        "total_equity": {"value": 400},
    }
    result = financial_validation_service.run_validation("balance_sheet", data)
    assert result.checks[0].status == "PASS"
