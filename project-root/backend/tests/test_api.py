"""Basic API flow tests using FastAPI's TestClient + an isolated SQLite DB."""
import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./data/test_documents.db"

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()  # TestClient doesn't run startup events unless used as a context manager
client = TestClient(app)


def test_health_check():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_process_rejects_unsupported_document_type():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    buf.seek(0)
    res = client.post(
        "/api/v1/documents/process",
        files={"file": ("scan.png", buf, "image/png")},
        data={"document_type": "not_a_real_type"},
    )
    assert res.status_code == 400


def test_process_rejects_unsupported_file_type():
    res = client.post(
        "/api/v1/documents/process",
        files={"file": ("resume.docx", io.BytesIO(b"not a real docx"), "application/octet-stream")},
        data={"document_type": "invoice"},
    )
    assert res.status_code == 200  # graceful FAILED response, not a crash
    body = res.json()
    assert body["processing_status"] == "FAILED"
    assert body["file_validation"]["status"] == "FAILED"


def test_list_documents_endpoint_works():
    res = client.get("/api/v1/documents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_unknown_document_returns_404():
    res = client.get("/api/v1/documents/does-not-exist.pdf")
    assert res.status_code == 404
