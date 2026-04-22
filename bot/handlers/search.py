"""Handler for /search command and all inline keyboard callbacks."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.database.db import get_or_create_user, search_message_expired, update_user
from bot.database.models import UserPreference
from bot.keyboards.search_kb import (
    advanced_kb,
    build_status_text,
    localities_kb,
    main_panel_kb,
    period_kb,
    price_kb,
    price_value_kb,
    rooms_kb,
    rooms_value_kb,
    skip_resources_kb,
    space_kb,
    space_value_kb,
    tauschwohnung_kb,
)

router = Router()

DEACTIVATED_TEXT = (
    "Your subscription was deactivated, "
    "send the request with /search to activate it again."
)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _send_search_panel(target: Message | CallbackQuery, user: UserPreference) -> None:
    """Send or edit the search config message."""
    text = build_status_text(user)
    kb = main_panel_kb(is_active=user.is_active)

    if isinstance(target, Message):
        sent = await target.answer(text, reply_markup=kb, parse_mode="HTML")
        await update_user(
            user.user_id,
            search_message_chat_id=sent.chat.id,
            search_message_id=sent.message_id,
            search_message_sent_at=datetime.now(timezone.utc),
        )
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def _edit_panel(
    call: CallbackQuery,
    text: str,
    kb: object,
    parse_mode: str = "HTML",
) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode=parse_mode)
    except TelegramBadRequest:
        pass
    await call.answer()


async def _refresh_main(call: CallbackQuery, user: UserPreference) -> None:
    text = build_status_text(user)
    await _edit_panel(call, text, main_panel_kb(is_active=user.is_active))


# ── /search command ──────────────────────────────────────────────────────────


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    user = await get_or_create_user(message.from_user.id)
    await update_user(message.from_user.id, is_active=True)
    user.is_active = True
    await _send_search_panel(message, user)
    logger.info("User {} opened /search", message.from_user.id)


# ── Guard: reject callbacks on expired messages ──────────────────────────────


async def _guard(call: CallbackQuery) -> UserPreference | None:
    user = await get_or_create_user(call.from_user.id)
    if await search_message_expired(user):
        await call.answer(
            "This search panel has expired. Please use /search to get a new one.",
            show_alert=True,
        )
        return None
    return user


# ── Main panel callbacks ─────────────────────────────────────────────────────


@router.callback_query(F.data == "search:main")
async def cb_main(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _refresh_main(call, user)


@router.callback_query(F.data == "search:toggle_active")
async def cb_toggle_active(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    new_state = not user.is_active
    user = await update_user(call.from_user.id, is_active=new_state)
    if not new_state:
        await call.answer(DEACTIVATED_TEXT, show_alert=True)
    else:
        await call.answer("Subscription activated.", show_alert=True)
    await _refresh_main(call, user)


# ── Period ───────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:period")
async def cb_period_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, build_status_text(user) + "\n\n<b>Select rental period:</b>", period_kb())


@router.callback_query(F.data.startswith("period:"))
async def cb_period_set(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    value = call.data.split(":", 1)[1]
    user = await update_user(call.from_user.id, period=value)
    await _refresh_main(call, user)


# ── Rooms ────────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:rooms")
async def cb_rooms_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        rooms_info = ""
        if user.rooms_min or user.rooms_max:
            rooms_info = f" (min: {user.rooms_min or '—'}, max: {user.rooms_max or '—'})"
        await _edit_panel(
            call,
            build_status_text(user) + f"\n\n<b>Rooms{rooms_info}</b>",
            rooms_kb(),
        )


@router.callback_query(F.data == "rooms:set_min")
async def cb_rooms_set_min(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select minimum rooms:</b>", rooms_value_kb("min"))


@router.callback_query(F.data == "rooms:set_max")
async def cb_rooms_set_max(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select maximum rooms:</b>", rooms_value_kb("max"))


@router.callback_query(F.data.startswith("rooms_val:"))
async def cb_rooms_val(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    _, bound, raw = call.data.split(":")
    value = None if raw == "any" else int(raw)
    if bound == "min":
        user = await update_user(call.from_user.id, rooms_min=value)
    else:
        user = await update_user(call.from_user.id, rooms_max=value)
    await _refresh_main(call, user)


# ── Price ────────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:price")
async def cb_price_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        price_info = ""
        if user.price_min or user.price_max:
            price_info = f" (min: €{user.price_min or '—'}, max: €{user.price_max or '—'})"
        await _edit_panel(
            call,
            build_status_text(user) + f"\n\n<b>Price{price_info}</b>",
            price_kb(),
        )


@router.callback_query(F.data == "price:set_min")
async def cb_price_set_min(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select minimum price (€):</b>", price_value_kb("min"))


@router.callback_query(F.data == "price:set_max")
async def cb_price_set_max(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select maximum price (€):</b>", price_value_kb("max"))


@router.callback_query(F.data.startswith("price_val:"))
async def cb_price_val(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    _, bound, raw = call.data.split(":")
    value = None if raw == "any" else int(raw)
    if bound == "min":
        user = await update_user(call.from_user.id, price_min=value)
    else:
        user = await update_user(call.from_user.id, price_max=value)
    await _refresh_main(call, user)


# ── Living space ─────────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:space")
async def cb_space_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        space_info = ""
        if user.space_min or user.space_max:
            space_info = f" (min: {user.space_min or '—'}m², max: {user.space_max or '—'}m²)"
        await _edit_panel(
            call,
            build_status_text(user) + f"\n\n<b>Living Space{space_info}</b>",
            space_kb(),
        )


@router.callback_query(F.data == "space:set_min")
async def cb_space_set_min(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select minimum living space (m²):</b>", space_value_kb("min"))


@router.callback_query(F.data == "space:set_max")
async def cb_space_set_max(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(call, "<b>Select maximum living space (m²):</b>", space_value_kb("max"))


@router.callback_query(F.data.startswith("space_val:"))
async def cb_space_val(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    _, bound, raw = call.data.split(":")
    value = None if raw == "any" else int(raw)
    if bound == "min":
        user = await update_user(call.from_user.id, space_min=value)
    else:
        user = await update_user(call.from_user.id, space_max=value)
    await _refresh_main(call, user)


# ── Localities ───────────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:localities")
async def cb_localities_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(
            call,
            build_status_text(user) + "\n\n<b>Select Berlin district:</b>",
            localities_kb(),
        )


@router.callback_query(F.data.startswith("locality:"))
async def cb_locality_set(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    value = call.data.split(":", 1)[1]
    user = await update_user(call.from_user.id, locality=value)
    await _refresh_main(call, user)


# ── Advanced filters ─────────────────────────────────────────────────────────


@router.callback_query(F.data == "search:advanced")
async def cb_advanced_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(
            call,
            build_status_text(user) + "\n\n<b>Advanced filters:</b>",
            advanced_kb(),
        )


@router.callback_query(F.data == "adv:tauschwohnung")
async def cb_tausch_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        await _edit_panel(
            call,
            f"<b>Tauschwohnung:</b> {user.tauschwohnung}",
            tauschwohnung_kb(user.tauschwohnung),
        )


@router.callback_query(F.data.startswith("tausch:"))
async def cb_tausch_set(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    value = call.data.split(":", 1)[1]
    user = await update_user(call.from_user.id, tauschwohnung=value)
    await _refresh_main(call, user)


@router.callback_query(F.data == "adv:skip_resources")
async def cb_skip_resources_menu(call: CallbackQuery) -> None:
    user = await _guard(call)
    if user:
        skipped = user.skipped_resources or []
        skipped_display = ", ".join(skipped) if skipped else "none"
        await _edit_panel(
            call,
            f"<b>Skipped resources:</b> {skipped_display}",
            skip_resources_kb(skipped),
        )


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip_toggle(call: CallbackQuery) -> None:
    user = await _guard(call)
    if not user:
        return
    source = call.data.split(":", 1)[1]
    skipped: list[str] = list(user.skipped_resources or [])

    if source == "__none__":
        skipped = []
    elif source in skipped:
        skipped.remove(source)
    else:
        skipped.append(source)

    user = await update_user(call.from_user.id, skipped_resources=skipped)
    skipped_display = ", ".join(skipped) if skipped else "none"
    await _edit_panel(
        call,
        f"<b>Skipped resources:</b> {skipped_display}",
        skip_resources_kb(skipped),
    )
