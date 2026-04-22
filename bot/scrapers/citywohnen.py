"""WG-Gesucht scraper — long-term apartments in Berlin.

Original source "CityWohnen" (city-wohnen.de) only covers Hamburg, not Berlin.
Replaced with WG-Gesucht which is one of Germany's largest rental platforms,
fully server-side rendered, and carries hundreds of Berlin apartment listings.
source_name kept as "CityWohnen" for DB compatibility.
"""
from __future__ import annotations

from datetime import datetime

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.wg-gesucht.de"
# Type 2 = full apartment (Wohnung), city code 8 = Berlin
SEARCH_URL = f"{BASE_URL}/en/wohnungen-in-Berlin.8.2.1.0.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.8",
    "Referer": "https://www.wg-gesucht.de/",
}


class CityWohnenScraper(BaseScraper):
    source_name = "CityWohnen"  # kept for DB compat; actual source: WG-Gesucht

    async def fetch_listings(self, since: datetime | None = None) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("CityWohnen/WG-Gesucht: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("CityWohnen/WG-Gesucht scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        seen: set[str] = set()

        # WG-Gesucht: listing cards link to /en/wohnungen-in-Berlin-[district].[id].html
        for link in soup.select("a[href*='/wohnungen-in-Berlin']"):
            href = link.get("href", "")
            if not href or href in seen:
                continue
            # Skip pagination / filter links (no digit-heavy ID segment)
            if not re.search(r"\.\d{5,}", href):
                continue
            seen.add(href)
            listing = self._parse_card(link, href)
            if listing:
                listings.append(listing)
        return listings

    def _parse_card(self, card: BeautifulSoup, href: str) -> Listing | None:
        try:
            url = href if href.startswith("http") else BASE_URL + href
            listing_id = re.search(r"\.(\d+)\.html", href)
            listing_id = listing_id.group(1) if listing_id else hashlib.md5(url.encode()).hexdigest()[:16]

            # Walk up until we find a container with price text (div.row is ~12 levels up)
            container = card
            for _ in range(15):
                if container.parent is None:
                    break
                container = container.parent
                t = container.get_text(" ", strip=True)
                classes = container.get("class") or []
                if container.name in ("tr", "li", "div", "article") and classes and "€" in t:
                    break

            text = container.get_text(" ", strip=True)

            # Price: "1667 €" or "890 €"
            price = None
            price_match = re.search(r"([\d.,]+)\s*€", text)
            if price_match:
                price = int(re.sub(r"[^\d]", "", price_match.group(1)))

            # Rooms: "2 Room Flat" or "1 Room Flat"
            rooms = None
            rooms_match = re.search(r"(\d+)\s*[Rr]oom", text)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            # Space: "61 m²"
            space = None
            space_match = re.search(r"(\d+)\s*m²", text)
            if space_match:
                space = int(space_match.group(1))

            # Address: "Berlin Neukölln | Kopfstraße 1300 € ..."
            # Grab the street name between the last "|" and the price
            address = ""
            m = re.search(r"\|\s*([^|]+?)(?=\s*[\d.,]+\s*€|\s*\d{2}\.\d{2}|\s*$)", text, re.DOTALL)
            if m:
                address = re.sub(r"\s+", " ", m.group(1)).strip()[:80]
            if not address and "|" in text:
                address = text.split("|")[-1].strip()[:80]

            # District: extract from href slug or address
            district = "Berlin"
            slug_match = re.search(r"wohnungen-in-Berlin-([^.]+)\.", href)
            if slug_match:
                district = slug_match.group(1).replace("-", " ")

            img = container.select_one("img[src*='wg-gesucht'], img[src]")
            photo_url = img["src"] if img else ""

            return Listing(
                listing_id=str(listing_id),
                source=self.source_name,
                period="long",
                rooms=rooms,
                price=price,
                space=space,
                address=address or "Berlin",
                district=district,
                photo_url=photo_url,
                listing_url=url,
            )
        except Exception:
            return None
