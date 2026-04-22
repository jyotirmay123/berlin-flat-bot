"""Wunderflats scraper — short-term furnished rentals in Berlin.

Source listed in requirements as "ShoreCapital" (domain defunct).
Replaced with Wunderflats, the leading Berlin short-term furnished flat platform.
The source_name is kept as "ShoreCapital" for DB compatibility.
"""
from __future__ import annotations

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://wunderflats.com"
SEARCH_URL = f"{BASE_URL}/en/furnished-apartments/berlin"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.8",
}


class ShoreCapitalScraper(BaseScraper):
    source_name = "ShoreCapital"  # kept for DB compat; actual source: Wunderflats

    async def fetch_listings(self) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("ShoreCapital/Wunderflats: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("ShoreCapital/Wunderflats scraper unavailable: {}", exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        seen: set[str] = set()

        # Wunderflats: each card is an <a href="/en/furnished-apartment/...">
        for link in soup.select("a[href*='/furnished-apartment/']"):
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
            clean_url = url.split("?")[0]
            listing_id = hashlib.md5(clean_url.encode()).hexdigest()[:16]

            # Walk up to the card container (the <a> itself is an image link with no text)
            node = card
            for _ in range(8):
                if node.parent is None:
                    break
                node = node.parent
                t = node.get_text(" ", strip=True)
                if node.name in ("article", "li", "div") and node.get("class") and "€" in t:
                    card = node
                    break

            text = card.get_text(" ", strip=True)

            # Price: "€1,790per month" → 1790
            price = None
            price_match = re.search(r"€\s*([\d,\.]+)\s*per\s*month", text, re.I)
            if not price_match:
                price_match = re.search(r"€\s*([\d,\.]+)", text)
            if price_match:
                price = int(re.sub(r"[^\d]", "", price_match.group(1)))

            # Rooms: "2 Rooms" or "1 Room"
            rooms = None
            rooms_match = re.search(r"(\d+)\s*[Rr]oom", text)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            # Space: "52 m²"
            space = None
            space_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text)
            if space_match:
                space = int(float(space_match.group(1).replace(",", ".")))

            # Address/title — the link title text or an inner heading
            address = ""
            heading = card.select_one("h2, h3, [class*='title'], [class*='name']")
            if heading:
                address = heading.get_text(strip=True)
            elif text:
                # First non-numeric, non-price text segment
                address = text[:80]

            # District detection
            district = "Berlin"
            district_match = re.search(
                r"(Mitte|Friedrichshain|Kreuzberg|Prenzlauer Berg|Charlottenburg|"
                r"Wilmersdorf|Steglitz|Zehlendorf|Neukölln|Tempelhof|Schöneberg|"
                r"Lichtenberg|Pankow|Spandau|Reinickendorf|Marzahn|Treptow|Köpenick)",
                text, re.I
            )
            if district_match:
                district = district_match.group(1)

            img = card.select_one("img[src*='listingimages'], img[src]")
            photo_url = img["src"] if img else ""

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
