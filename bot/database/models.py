from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PeriodEnum(str, enum.Enum):
    any = "any"
    short = "short"
    long = "long"


class TauschwohnungEnum(str, enum.Enum):
    included = "included"
    excluded = "excluded"


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    period: Mapped[str] = mapped_column(
        Enum(PeriodEnum), default=PeriodEnum.any
    )
    rooms_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    space_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    space_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locality: Mapped[str] = mapped_column(String, default="any")
    tauschwohnung: Mapped[str] = mapped_column(
        Enum(TauschwohnungEnum), default=TauschwohnungEnum.excluded
    )
    skipped_resources: Mapped[list] = mapped_column(JSON, default=list)
    # Stores (chat_id, message_id, sent_at) of the active /search message
    search_message_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_message_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SentListing(Base):
    __tablename__ = "sent_listings"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", "source", name="uq_sent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_preferences.user_id"))
    listing_id: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ListingCache(Base):
    __tablename__ = "listings_cache"

    listing_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String)
    period: Mapped[str] = mapped_column(String)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    space: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str] = mapped_column(String, default="")
    district: Mapped[str] = mapped_column(String, default="")
    photo_url: Mapped[str] = mapped_column(String, default="")
    listing_url: Mapped[str] = mapped_column(String, default="")
    is_paywall: Mapped[bool] = mapped_column(Boolean, default=False)
    is_swap: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScrapeState(Base):
    __tablename__ = "scrape_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
