"""Aiogram bot entry point."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import get_settings
from app.handlers import ai_pick, catalog, garment_styles, generations, start, user_photo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.is_configured:
        logger.error("TELEGRAM_BOT_TOKEN is not configured; bot will not start.")
        return
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    for router in [start.router, catalog.router, garment_styles.router, ai_pick.router, user_photo.router, generations.router]:
        dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
