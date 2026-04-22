"""Bot entry point — starts the dispatcher and APScheduler."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from bot.config import settings
from bot.database.db import init_db
from bot.handlers.commands import router as commands_router
from bot.handlers.search import router as search_router
from bot.notifier import run_scrape_cycle
from bot.scrapers.playwright_base import close_browser


async def main() -> None:
    logger.remove()
    logger.add(
        "logs/bot.log",
        rotation="10 MB",
        retention="7 days",
        level=settings.log_level,
        enqueue=True,
    )
    logger.add(lambda msg: print(msg, end=""), level=settings.log_level, colorize=True)

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(commands_router)
    dp.include_router(search_router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scrape_cycle,
        trigger="interval",
        minutes=settings.scrape_interval_minutes,
        args=[bot],
        id="scrape_cycle",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — scraping every {} minutes",
        settings.scrape_interval_minutes,
    )

    try:
        logger.info("Bot polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await close_browser()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
