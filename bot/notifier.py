"""Scrape → match → notify pipeline."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.config import settings
from bot.database.db import (
    already_sent,
    get_active_users,
    get_last_scrape_at,
    mark_sent,
    set_last_scrape_at,
    upsert_listing,
)
from bot.database.models import ListingCache
from bot.matcher import matches
from bot.scrapers.allod import AllodScraper
from bot.scrapers.base import BaseScraper, Listing
from bot.scrapers.buwog import BuwogScraper
from bot.scrapers.citywohnen import CityWohnenScraper
from bot.scrapers.engelvoelkers import EngelVoelkersScraper
from bot.scrapers.furnishedflats import FurnishedFlatsScraper
from bot.scrapers.immoscout import ImmoScout24Scraper
from bot.scrapers.livinginberlin import LivingInBerlinScraper
from bot.scrapers.shorecapital import ShoreCapitalScraper

ALL_SCRAPERS: list[BaseScraper] = [
    ImmoScout24Scraper(),
    CityWohnenScraper(),
    FurnishedFlatsScraper(),
    ShoreCapitalScraper(),
    LivingInBerlinScraper(),
    BuwogScraper(),
    EngelVoelkersScraper(),
    AllodScraper(),
]


def _build_notification_text(listing: Listing) -> str:
    period_label = "Long term" if listing.period == "long" else "Short term"
    rooms_str = f"{listing.rooms} rooms" if listing.rooms else "? rooms"
    price_str = f"€{listing.price}" if listing.price else "price unknown"
    address = listing.address or listing.district or "Berlin"

    text = (
        f"{period_label}: {rooms_str} for {price_str} flat offering at "
        f"{address}, Berlin.\n{listing.listing_url}"
    )
    if listing.is_paywall:
        text += "\n\n<i>This offer is only for paywall accounts</i>"
    return text


_channel_available: bool = True


async def _send_to_channel(bot: Bot, listing: Listing) -> bool:
    """Return False if the channel is permanently unavailable this cycle."""
    global _channel_available
    if not _channel_available:
        return False
    try:
        text = _build_notification_text(listing)
        if listing.photo_url:
            await bot.send_photo(
                chat_id=settings.channel_id,
                photo=listing.photo_url,
                caption=text,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(settings.channel_id, text, parse_mode="HTML")
        return True
    except Exception as exc:
        logger.warning("Channel posting disabled for this cycle: {}", exc)
        _channel_available = False
        return False


async def _send_to_user(bot: Bot, user_id: int, listing: Listing) -> None:
    text = _build_notification_text(listing)
    try:
        if listing.photo_url:
            await bot.send_photo(
                chat_id=user_id,
                photo=listing.photo_url,
                caption=text,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(user_id, text, parse_mode="HTML")
    except TelegramBadRequest as exc:
        logger.warning("Could not send to user {}: {}", user_id, exc)
    except Exception as exc:
        logger.error("Error sending to user {}: {}", user_id, exc)


async def run_scrape_cycle(bot: Bot) -> None:
    """One full scrape-match-notify cycle. Called by the scheduler."""
    since = await get_last_scrape_at()
    cycle_start = datetime.now(timezone.utc)
    if since:
        logger.info("Starting scrape cycle — fetching listings since {}", since.isoformat())
    else:
        logger.info("Starting scrape cycle — first run, fetching all visible listings")

    # Scrape all sources concurrently
    results = await asyncio.gather(
        *[scraper.fetch_listings(since=since) for scraper in ALL_SCRAPERS],
        return_exceptions=True,
    )

    # Record cycle start time so the next cycle only fetches newer listings.
    # Done immediately after scraping so we don't miss listings posted during processing.
    await set_last_scrape_at(cycle_start)

    new_listings: list[Listing] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Scraper raised: {}", result)
            continue
        for listing in result:
            cache_row = ListingCache(
                listing_id=listing.listing_id,
                source=listing.source,
                period=listing.period,
                rooms=listing.rooms,
                price=listing.price,
                space=listing.space,
                address=listing.address,
                district=listing.district,
                photo_url=listing.photo_url,
                listing_url=listing.listing_url,
                is_paywall=listing.is_paywall,
                is_swap=listing.is_swap,
            )
            is_new = await upsert_listing(cache_row)
            if is_new:
                new_listings.append(listing)

    if not new_listings:
        logger.info("No new listings in this cycle")
        return

    logger.info("Found {} new listings; matching against active users", len(new_listings))

    # Reset channel availability flag at the start of each cycle
    global _channel_available
    _channel_available = True

    # Post every new listing to the companion channel
    for listing in new_listings:
        if not await _send_to_channel(bot, listing):
            break  # channel unavailable for this cycle, stop trying
        await asyncio.sleep(0.1)  # rate limit

    # Match against active user subscriptions
    active_users = await get_active_users()
    for user in active_users:
        for listing in new_listings:
            if not matches(listing, user):
                continue
            if await already_sent(user.user_id, listing.listing_id, listing.source):
                continue
            await _send_to_user(bot, user.user_id, listing)
            await mark_sent(user.user_id, listing.listing_id, listing.source)
            await asyncio.sleep(0.05)  # rate limit between messages

    logger.info("Scrape cycle complete")
