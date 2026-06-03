from __future__ import annotations

from fastapi import FastAPI

from .database import init_db
from .routers import bot, catalog

app = FastAPI(title="Fabric Telegram Bot Backend")
app.include_router(catalog.router)
app.include_router(bot.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
