from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .api_client import BackendApiClient
from .handlers import ai_pick, catalog, selected_fabric, start


def build_dispatcher(api_client: BackendApiClient, backend_public_url: str) -> Dispatcher:
    dp = Dispatcher(api_client=api_client, backend_public_url=backend_public_url.rstrip("/"))
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(ai_pick.router)
    dp.include_router(selected_fabric.router)
    return dp


async def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    backend_public_url = os.getenv("BACKEND_PUBLIC_URL", backend_url)
    api_client = BackendApiClient(backend_url)
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(api_client, backend_public_url)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
