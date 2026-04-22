"""Immowelt scraper — long-term rentals in Berlin.

Original source "BUWOG" (buwog.de) has zero rental listings available (developer/buyer
platform only). Replaced with Immowelt, one of Germany's largest SSR rental portals.
source_name kept as "BUWOG" for DB compatibility.
"""
from __future__ import annotations

from datetime import datetime

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from bot.scrapers.base import BaseScraper, Listing

BASE_URL = "https://www.immowelt.de"
SEARCH_URL = f"{BASE_URL}/suche/berlin/wohnungen/mieten"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    # No brotli — aiohttp lacks a brotli decoder by default
    "Accept-Encoding": "gzip, deflate",
}


class BuwogScraper(BaseScraper):
    source_name = "BUWOG"  # kept for DB compat; actual source: Immowelt

    async def fetch_listings(self, since: datetime | None = None) -> list[Listing]:
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    SEARCH_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.warning("BUWOG/Immowelt: HTTP {}", resp.status)
                        return []
                    html = await resp.text()
            return self._parse(html)
        except Exception as exc:
            logger.warning("BUWOG/Immowelt scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        seen: set[str] = set()

        for link in soup.select("a[href*='/expose/']"):
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
            listing_id = re.search(r"/expose/([a-z0-9-]+)", href)
            listing_id = listing_id.group(1) if listing_id else hashlib.md5(url.encode()).hexdigest()[:16]

            # Card container is one level up from the <a> link
            container = card.parent or card
            text = container.get_text(" ", strip=True)

            # Price: "2.290\xa0€ Kaltmiete" — period is thousands separator
            price = None
            m = re.search(r"([\d.]+)\s*€", text)
            if m:
                price = int(m.group(1).replace(".", "").replace("\xa0", ""))

            # Rooms: "4 Zimmer"
            rooms = None
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*Zimmer", text)
            if m:
                rooms = int(float(m.group(1).replace(",", ".")))

            # Space: "104,2 m²"
            space = None
            m = re.search(r"([\d]+(?:[.,]\d+)?)\s*m²", text)
            if m:
                space = int(float(m.group(1).replace(",", ".")))

            # Address: "Archenholdstrasse 19, Friedrichsfelde, Berlin (10315)"
            # Match word directly attached to street suffix; stop at zip code if present
            address = ""
            m = re.search(
                r"([A-ZÄÖÜ]\w+(?:straße|strasse|allee|platz|weg|gasse|damm|chaussee)\b[^·\n]*?(?:\(\d{5}\)|(?<=Berlin)))",
                text,
            )
            if not m:
                m = re.search(
                    r"([A-ZÄÖÜ]\w+(?:straße|strasse|allee|platz|weg|gasse|damm|chaussee)\b[^·\n]*)",
                    text,
                )
            if m:
                address = m.group(1).strip()[:80]

            # District
            district = "Berlin"
            m = re.search(
                r"(Mitte|Friedrichshain|Kreuzberg|Prenzlauer Berg|Charlottenburg|"
                r"Wilmersdorf|Steglitz|Zehlendorf|Neukölln|Tempelhof|Schöneberg|"
                r"Lichtenberg|Pankow|Spandau|Reinickendorf|Marzahn|Treptow|Köpenick|"
                r"Hellersdorf|Weißensee|Hohenschönhausen|Friedrichsfelde)",
                text, re.I,
            )
            if m:
                district = m.group(1)

            img = container.select_one("img[src]")
            photo_url = img["src"] if img else ""
            if photo_url and not photo_url.startswith("http"):
                photo_url = BASE_URL + photo_url

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
