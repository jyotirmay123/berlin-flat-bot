"""Abstract base class for all scrapers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Listing:
    listing_id: str
    source: str
    period: str          # 'short' | 'long'
    rooms: int | None
    price: int | None
    space: int | None
    address: str
    district: str
    photo_url: str
    listing_url: str
    is_paywall: bool = False
    is_swap: bool = False


class BaseScraper(ABC):
    """All scrapers must implement fetch_listings()."""

    source_name: str = ""

    @abstractmethod
    async def fetch_listings(self, since: datetime | None = None) -> list[Listing]:
        """Return freshly scraped listings newer than `since` (UTC).

        Pass None to fetch all currently visible listings (first-run behaviour).
        Must not raise — catch internally.
        """
        ...
