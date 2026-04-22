"""Engel & Völkers scraper — long-term rentals in Berlin."""
from __future__ import annotations

from datetime import datetime

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.engelvoelkers.com"
SEARCH_URL = f"{BASE_URL}/de/en/properties/res/rent/apartment/berlin/berlin"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.8",
}


class EngelVoelkersScraper(BaseScraper):
    source_name = "EngelVoelkers"

    async def fetch_listings(self, since: datetime | None = None) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("EngelVoelkers: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("EngelVoelkers scraper unavailable: {}", exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []

        # Each listing card has an anchor with href containing /exposes/
        seen: set[str] = set()
        for link in soup.select("a[href*='/exposes/']"):
            href = link.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            listing = self._parse_expose_link(link, href)
            if listing:
                listings.append(listing)
        return listings

    def _parse_expose_link(self, link: BeautifulSoup, href: str) -> Listing | None:
        try:
            url = href if href.startswith("http") else BASE_URL + href
            listing_id = hashlib.md5(url.encode()).hexdigest()[:16]

            # Walk up until we find a container with price text (max 8 levels)
            card = link
            for _ in range(8):
                parent = card.parent
                if parent is None:
                    break
                card = parent
                t = card.get_text(" ", strip=True)
                if card.name in ("article", "section", "li", "div") and card.get("class") and "€" in t:
                    break

            text = card.get_text(" ", strip=True)

            # Address: look for location heading inside the card
            address = ""
            for selector in [
                "[class*='location']", "[class*='address']", "[class*='subtitle']",
                "h3", "h4", "p",
            ]:
                el = card.select_one(selector)
                if el:
                    candidate = el.get_text(strip=True)
                    if "berlin" in candidate.lower() or len(candidate) > 5:
                        address = candidate
                        break

            # Price: "€X,XXX"
            price = None
            price_match = re.search(r"€\s*([\d,.]+)", text)
            if price_match:
                price = int(re.sub(r"[^\d]", "", price_match.group(1)))

            # Rooms: "X Bedroom(s)"
            rooms = None
            rooms_match = re.search(r"(\d+)\s*[Bb]edroom", text)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            # Space: "~XX m² Living area" or "XX m²"
            space = None
            space_match = re.search(r"~?(\d+(?:[.,]\d+)?)\s*m²", text)
            if space_match:
                space = int(float(space_match.group(1).replace(",", ".")))

            # Image
            img = card.select_one("img[src]")
            photo_url = img["src"] if img else ""
            if photo_url and not photo_url.startswith("http"):
                photo_url = BASE_URL + photo_url

            # District from address text
            district = "Berlin"
            district_match = re.search(
                r"(Mitte|Friedrichshain|Kreuzberg|Prenzlauer Berg|Charlottenburg|"
                r"Wilmersdorf|Steglitz|Zehlendorf|Neukölln|Tempelhof|Schöneberg|"
                r"Lichtenberg|Pankow|Spandau|Reinickendorf|Marzahn|Treptow|Köpenick)",
                address, re.I
            )
            if district_match:
                district = district_match.group(1)

            return Listing(
                listing_id=listing_id,
                source=self.source_name,
                period="long",
                rooms=rooms,
                price=price,
                space=space,
                address=address or "Berlin",
                district=district,
                photo_url=photo_url,
                listing_url=url,
                is_paywall="sign in" in text.lower() or "login" in text.lower(),
            )
        except Exception:
            return None
