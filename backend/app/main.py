"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin_fabrics, admin_garment_styles, auth, bot_users, generations, public_catalog, uploads
from app.config import get_settings
from app.database import SessionLocal
from app.schemas.common import HealthResponse
from app.services.seed_service import seed_demo_data, seed_initial_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_admin_auth_config()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    for folder in ["fabrics", "garment-styles", "generations", "user-photos"]:
        (settings.upload_dir / folder).mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        seed_initial_admin(db, settings.initial_admin_email, settings.initial_admin_password)
        if settings.seed_demo_data:
            seed_demo_data(db)
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
app.include_router(uploads.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()
