"""Allod scraper — long-term rentals in Berlin.

Allod (allod.de) is a property management company, not a public rental
marketplace. They list properties through third-party portals. This scraper
fetches their website and extracts any vacancy/rental listings that appear
in their news or project pages.
"""
from __future__ import annotations

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.allod.de"
# Allod publishes rental vacancies on their news/project pages
SEARCH_URLS = [
    f"{BASE_URL}/en",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class AllodScraper(BaseScraper):
    source_name = "Allod"

    async def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                for url in SEARCH_URLS:
                    try:
                        async with session.get(
                            url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True
                        ) as resp:
                            if resp.status != 200:
                                logger.debug("Allod: {} returned HTTP {}", url, resp.status)
                                continue
                            html = await resp.text()
                            listings.extend(self._parse(html, url))
                    except Exception as exc:
                        logger.debug("Allod: error fetching {}: {}", url, exc)
            if not listings:
                logger.debug("Allod: no listings found in static HTML (managed property site)")
            return listings
        except Exception as exc:
            logger.warning("Allod scraper unavailable: {}", exc)
            return []

    def _parse(self, html: str, page_url: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []

        for card in soup.select(
            ".property-item, .immobilie, article, .angebot, "
            ".news-item, .project-item, [class*='listing']"
        ):
            listing = self._parse_card(card, page_url)
            if listing:
                listings.append(listing)
        return listings

    def _parse_card(self, card: BeautifulSoup, page_url: str) -> Listing | None:
        try:
            text = card.get_text(" ", strip=True)
            # Only consider cards that mention rental pricing
            if not re.search(r"(?:miete|rent|€|EUR)", text, re.I):
                return None

            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el else ""
            url = href if href.startswith("http") else BASE_URL + href if href else page_url
            listing_id = hashlib.md5((url + text[:50]).encode()).hexdigest()[:16]

            address = ""
            for selector in [".address", ".ort", ".title", "h2", "h3"]:
                el = card.select_one(selector)
                if el:
                    address = el.get_text(strip=True)
                    break

            price, rooms, space = None, None, None

            price_match = re.search(r"(\d[\d.,]+)\s*(?:€|EUR)", text)
            if price_match:
                price = int(re.sub(r"[^\d]", "", price_match.group(1)))

            rooms_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:rooms?|Zimmer|Zi\.?)", text, re.I)
            if rooms_match:
                rooms = int(float(rooms_match.group(1).replace(",", ".")))

            space_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text)
            if space_match:
                space = int(float(space_match.group(1).replace(",", ".")))

            img = card.select_one("img[src]")
            photo_url = img["src"] if img else ""
            if photo_url and not photo_url.startswith("http"):
                photo_url = BASE_URL + photo_url

            return Listing(
                listing_id=listing_id,
                source=self.source_name,
                period="long",
                rooms=rooms,
                price=price,
                space=space,
                address=address,
                district="Berlin",
                photo_url=photo_url,
                listing_url=url,
                is_swap="tausch" in text.lower(),
            )
        except Exception:
            return None
