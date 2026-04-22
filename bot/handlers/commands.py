"""Handlers for /start, /stop, /thanks commands."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from bot.config import settings
from bot.database.db import get_or_create_user, update_user

router = Router()

DEACTIVATED_TEXT = (
    "Your subscription was deactivated, "
    "send the request with /search to activate it again."
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await get_or_create_user(message.from_user.id)
    text = (
        "This bot was created to automate searching of apartments in Berlin. "
        "It will notify you when a new apartment becomes available.\n\n"
        "Use /search to set up your filter preferences.\n"
        "Use /stop to deactivate notifications.\n\n"
        "<b>Sources monitored:</b>\n"
        "<b>General:</b> ImmobilienScout24\n"
        "<b>Short-term:</b> ShoreCapital, FurnishedFlats\n"
        "<b>Long-term:</b> Engel &amp; Völkers, Living in Berlin, Allod, "
        "CityWohnen, BUWOG\n\n"
        f"Feedback and /thanks: @{settings.developer_handle}"
    )
    await message.answer(text, parse_mode="HTML")
    logger.info("User {} triggered /start", message.from_user.id)


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    await update_user(message.from_user.id, is_active=False)
    await message.answer(DEACTIVATED_TEXT)
    logger.info("User {} deactivated via /stop", message.from_user.id)


@router.message(Command("thanks"))
async def cmd_thanks(message: Message) -> None:
    text = (
        "This bot is fully for free, but if you wanted, "
        "feel free to buy me some coffee or beer.\n\n"
        "It inspires:\n"
        f"► PayPal.Me/{settings.developer_handle}\n"
        "► Amazon Wish list\n\n"
        f"For any useful feedback, write to @{settings.developer_handle}"
    )
    await message.answer(text)
