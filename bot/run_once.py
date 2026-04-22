"""Single-run entry point for GitHub Actions (no polling loop).

Bootstraps user preferences from env vars, runs one scrape-match-notify
cycle, then exits. The SQLite DB persists between runs via actions/cache.

Required env vars (set as GitHub Actions secrets):
  BOT_TOKEN          — Telegram bot token
  CHANNEL_ID         — your personal Telegram channel ID (send /start to the
                       bot once to discover it, or use @userinfobot)
  SCRAPFLY_KEY       — ScrapFly key for ImmobilienScout24 (optional but recommended)

Optional filter env vars (set as GitHub Actions variables, not secrets):
  FILTER_PERIOD        — any | long | short          (default: any)
  FILTER_LOCALITY      — e.g. Neukölln, Mitte, any  (default: any)
  FILTER_PRICE_MAX     — integer €                   (default: no limit)
  FILTER_PRICE_MIN     — integer €                   (default: no limit)
  FILTER_ROOMS_MIN     — integer                     (default: no limit)
  FILTER_ROOMS_MAX     — integer                     (default: no limit)
  FILTER_SPACE_MIN     — integer m²                  (default: no limit)
  FILTER_TAUSCHWOHNUNG — excluded | included         (default: excluded)
"""
from __future__ import annotations

import asyncio
import os
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.config import settings
from bot.database.db import init_db, update_user
from bot.notifier import run_scrape_cycle


def _int_env(name: str) -> int | None:
    val = os.environ.get(name, "").strip()
    return int(val) if val else None


async def main() -> None:
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level, colorize=False,
               format="{time:HH:mm:ss} | {level} | {message}")

    chat_id_str = os.environ.get("CHANNEL_ID", "").strip()
    if not chat_id_str:
        logger.error("CHANNEL_ID is not set — cannot send notifications")
        sys.exit(1)

    user_id = int(chat_id_str)

    await init_db()

    # Upsert user preferences from env on every run so changes to GH vars
    # take effect immediately without touching the DB manually.
    prefs: dict = {
        "is_active": True,
        "period": os.environ.get("FILTER_PERIOD", "any").strip() or "any",
        "locality": os.environ.get("FILTER_LOCALITY", "any").strip() or "any",
        "tauschwohnung": os.environ.get("FILTER_TAUSCHWOHNUNG", "excluded").strip() or "excluded",
        "skipped_resources": [],
    }
    for key, env in (
        ("price_max", "FILTER_PRICE_MAX"),
        ("price_min", "FILTER_PRICE_MIN"),
        ("rooms_min", "FILTER_ROOMS_MIN"),
        ("rooms_max", "FILTER_ROOMS_MAX"),
        ("space_min", "FILTER_SPACE_MIN"),
    ):
        v = _int_env(env)
        if v is not None:
            prefs[key] = v

    await update_user(user_id, **prefs)
    logger.info("Preferences applied for user {}: {}", user_id, prefs)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        await run_scrape_cycle(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
