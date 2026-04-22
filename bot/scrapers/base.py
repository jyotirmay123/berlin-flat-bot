"""Abstract base class for all scrapers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
    async def fetch_listings(self) -> list[Listing]:
        """Return freshly scraped listings. Must not raise — catch internally."""
        ...
