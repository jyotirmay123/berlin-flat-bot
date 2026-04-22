"""degewo scraper — long-term rentals in Berlin.

Original source "LivingInBerlin" (living-in-berlin.de) returns 403 for all
automated requests including Playwright. Replaced with degewo.de, Berlin's
largest municipal housing company with 192+ live listings and SSR pages.
source_name kept as "LivingInBerlin" for DB compatibility.
"""
from __future__ import annotations

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.degewo.de"
SEARCH_URL = f"{BASE_URL}/immosuche"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class LivingInBerlinScraper(BaseScraper):
    source_name = "LivingInBerlin"  # kept for DB compat; actual source: degewo

    async def fetch_listings(self) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("LivingInBerlin/degewo: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("LivingInBerlin/degewo scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        seen: set[str] = set()

        # degewo: each listing links to /immosuche/details/[slug]
        for link in soup.select("a[href*='/immosuche/details/']"):
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
            listing_id = hashlib.md5(url.encode()).hexdigest()[:16]

            # Walk up to card container
            container = card
            for _ in range(6):
                if container.parent is None:
                    break
                container = container.parent
                if container.name in ("article", "li", "div") and container.get("class"):
                    break

            text = container.get_text(" ", strip=True)

            # Address: "[Street] | [District]"
            address = ""
            address_el = container.select_one("[class*='address'], [class*='street'], h3, h2")
            if address_el:
                address = address_el.get_text(strip=True)
            elif "|" in text:
                address = text.split("|")[0].strip()[:80]

            # Warmmiete (warm rent = total monthly cost)
            # degewo uses German decimal format: "376,65 €" (comma = decimal separator)
            price = None
            m = re.search(r"([\d.]+),(\d{2})\s*€", text)
            if m:
                price = round(float(m.group(1).replace(".", "") + "." + m.group(2)))
            else:
                m = re.search(r"([\d.]+)\s*€", text)
                if m:
                    price = int(m.group(1).replace(".", ""))

            # Rooms
            rooms = None
            rooms_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:Zimmer|Zi\.|rooms?)", text, re.I)
            if rooms_match:
                rooms = int(float(rooms_match.group(1).replace(",", ".")))

            # Space
            space = None
            space_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text)
            if space_match:
                space = int(float(space_match.group(1).replace(",", ".")))

            # District: degewo apartments are all Berlin
            district = "Berlin"
            district_match = re.search(
                r"(Mitte|Friedrichshain|Kreuzberg|Prenzlauer Berg|Charlottenburg|"
                r"Wilmersdorf|Steglitz|Zehlendorf|Neukölln|Tempelhof|Schöneberg|"
                r"Lichtenberg|Pankow|Spandau|Reinickendorf|Marzahn|Treptow|Köpenick|"
                r"Hellersdorf|Weißensee|Hohenschönhausen)",
                text, re.I,
            )
            if district_match:
                district = district_match.group(1)

            img = container.select_one("img[src]")
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
                address=address or "Berlin",
                district=district,
                photo_url=photo_url,
                listing_url=url,
            )
        except Exception:
            return None
