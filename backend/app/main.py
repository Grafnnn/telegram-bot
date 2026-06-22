"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    admin_fabrics,
    admin_garment_styles,
    auth,
    bot_users,
    generations,
    operator_review,
    public_catalog,
    uploads,
)
from app.config import get_settings
from app.database import SessionLocal
from app.schemas.common import HealthResponse
from app.services.bootstrap_service import bootstrap_database, prepare_upload_dirs
from app.utils.redaction import safe_exception_summary, safe_path_for_log

logger = logging.getLogger(__name__)
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _request_id_from_header(value: str | None) -> str:
    candidate = (value or "").strip()
    return candidate if REQUEST_ID_RE.fullmatch(candidate) else uuid4().hex


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    prepare_upload_dirs(settings.upload_dir)
    with SessionLocal() as db:
        bootstrap_database(db, settings)
    yield


settings = get_settings()
app = FastAPI(title="Fashion Fabric Bot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.admin_frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir), check_dir=False), name="uploads")
app.include_router(auth.router, prefix="/api")
app.include_router(admin_fabrics.router, prefix="/api")
app.include_router(admin_garment_styles.router, prefix="/api")
app.include_router(public_catalog.router, prefix="/api")
app.include_router(bot_users.router, prefix="/api")
app.include_router(generations.router, prefix="/api")
app.include_router(operator_review.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = _request_id_from_header(request.headers.get("X-Request-ID"))
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "Unhandled request error request_id=%s method=%s path=%s error=%s",
            request_id,
            request.method,
            safe_path_for_log(request.url.path),
            safe_exception_summary(exc),
        )
        raise
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()
