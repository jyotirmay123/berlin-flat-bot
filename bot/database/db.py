from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings
from bot.database.models import Base, ListingCache, SentListing, UserPreference

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialised")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── User preference helpers ──────────────────────────────────────────────────


async def get_or_create_user(user_id: int) -> UserPreference:
    async with get_session() as session:
        user = await session.get(UserPreference, user_id)
        if user is None:
            user = UserPreference(user_id=user_id)
            session.add(user)
        return user


async def get_user(user_id: int) -> UserPreference | None:
    async with get_session() as session:
        return await session.get(UserPreference, user_id)


async def update_user(user_id: int, **kwargs: object) -> UserPreference:
    async with get_session() as session:
        user = await session.get(UserPreference, user_id)
        if user is None:
            user = UserPreference(user_id=user_id, **kwargs)
            session.add(user)
        else:
            for key, value in kwargs.items():
                setattr(user, key, value)
        return user


async def get_active_users() -> list[UserPreference]:
    async with get_session() as session:
        result = await session.execute(
            select(UserPreference).where(UserPreference.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())


# ── Sent-listings helpers ────────────────────────────────────────────────────


async def mark_sent(user_id: int, listing_id: str, source: str) -> None:
    async with get_session() as session:
        stmt = (
            sqlite_insert(SentListing)
            .values(user_id=user_id, listing_id=listing_id, source=source)
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)


async def already_sent(user_id: int, listing_id: str, source: str) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(SentListing).where(
                SentListing.user_id == user_id,
                SentListing.listing_id == listing_id,
                SentListing.source == source,
            )
        )
        return result.scalar_one_or_none() is not None


# ── Listing cache helpers ────────────────────────────────────────────────────


async def upsert_listing(listing: ListingCache) -> bool:
    """Insert listing; return True if it was new, False if already known."""
    async with get_session() as session:
        existing = await session.get(ListingCache, listing.listing_id)
        if existing is not None:
            return False
        session.add(listing)
        return True


async def search_message_expired(user: UserPreference) -> bool:
    if user.search_message_sent_at is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.search_message_ttl_hours)
    sent_at = user.search_message_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    return sent_at < cutoff
