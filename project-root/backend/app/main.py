"""FastAPI application entrypoint.

Serves:
- REST API under /api/v1 (see app/api/routes/documents.py)
- Swagger/OpenAPI docs at /docs
- A server-rendered HTML/CSS(+JS) frontend (dashboard + upload + result view)
  from the sibling `frontend/` directory, so the whole app deploys as a
  single web service.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents
from app.core.database import init_db
from app.core.logging import setup_logging, get_logger
from app.utils.exceptions import AppError

setup_logging()
logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app/main.py -> app -> backend -> project-root
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Document Intelligence Platform",
    description="Extraction, validation and API platform for invoices and financial statements.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup():
    logger.info("Starting up: initializing database")
    init_db()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.error("AppError: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/")
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/document/{document_name}")
def document_result_page(request: Request, document_name: str):
    return templates.TemplateResponse("document_result.html", {"request": request, "document_name": document_name})
