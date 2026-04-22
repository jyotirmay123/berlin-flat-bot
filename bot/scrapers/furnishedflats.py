"""tempoFLAT scraper — short-term furnished rentals in Berlin.

Original source "FurnishedFlats" (furnished-flats.de) no longer exists.
Replaced with tempoFLAT (tempoflat.de), a real Berlin short-term furnished
flat platform with server-side rendered listings.
source_name kept as "FurnishedFlats" for DB compatibility.
"""
from __future__ import annotations

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.tempoflat.de"
SEARCH_URL = f"{BASE_URL}/furnished-apartments/berlin/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.8",
}


class FurnishedFlatsScraper(BaseScraper):
    source_name = "FurnishedFlats"  # kept for DB compat; actual source: tempoFLAT

    async def fetch_listings(self) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("FurnishedFlats/tempoFLAT: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("FurnishedFlats/tempoFLAT scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        seen: set[str] = set()

        # tempoFLAT: listing links follow /offer-detail/[ID]/[slug]/
        for link in soup.select("a[href*='/offer-detail/']"):
            href = link.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            listing = self._parse_card(link, href)
            if listing:
                listings.append(listing)
        return listings

    def _parse_card(self, card: BeautifulSoup, href: str) -> Listing | None:
        try:
            url = href if href.startswith("http") else BASE_URL + href
            listing_id = hashlib.md5(url.split("?")[0].encode()).hexdigest()[:16]

            # Walk up until we find a container with price text (max 8 levels)
            container = card
            for _ in range(8):
                if container.parent is None:
                    break
                container = container.parent
                t = container.get_text(" ", strip=True)
                if container.name in ("article", "div", "li", "section") and container.get("class"):
                    if re.search(r"EUR|€", t, re.I):
                        break

            text = container.get_text(" ", strip=True)

            # Price: "EUR 1.200.- per month" or "EUR 4'255.-" (apostrophe thousands separator)
            price = None
            price_match = re.search(r"EUR\s*([\d.,'\s]+?)(?:\.?\-|per|\s{2,}|$)", text, re.I)
            if not price_match:
                price_match = re.search(r"(\d[\d.,']+)\s*(?:€|EUR)", text, re.I)
            if price_match:
                price = int(re.sub(r"[^\d]", "", price_match.group(1)))

            # Rooms: "2-room apartment" or "2 Zimmer"
            rooms = None
            rooms_match = re.search(r"(\d+)[\s-]*(?:room|Zimmer|Zi)", text, re.I)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            # Space: "60 m²"
            space = None
            space_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text)
            if space_match:
                space = int(float(space_match.group(1).replace(",", ".")))

            # Address: "Berlin - Mitte, 2-room apartment"
            address = ""
            title_el = container.select_one("h2, h3, .title, strong")
            if title_el:
                address = title_el.get_text(strip=True)

            # District
            district = "Berlin"
            district_match = re.search(
                r"Berlin\s*[-–]\s*([^,\n]+)", address or text
            )
            if district_match:
                district = district_match.group(1).strip()

            img = container.select_one("img[src*='/media/'], img[src]")
            photo_url = img["src"] if img else ""
            if photo_url and not photo_url.startswith("http"):
                photo_url = BASE_URL + photo_url

            return Listing(
                listing_id=listing_id,
                source=self.source_name,
                period="short",
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
