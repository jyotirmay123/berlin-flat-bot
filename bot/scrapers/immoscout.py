"""ImmobilienScout24 scraper — long-term rentals in Berlin.

Uses Playwright + stealth to bypass Cloudflare bot-detection (HTTP returns 401).
Listings are embedded as JSON in a <script> tag under the key 'searchResponseModel'.
"""
from __future__ import annotations

import hashlib
import json
import re

from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import TimeoutError as PWTimeout

from bot.scrapers.base import BaseScraper, Listing
from bot.scrapers.playwright_base import new_page

BASE_URL = "https://www.immobilienscout24.de"
SEARCH_URL = (
    f"{BASE_URL}/Suche/de/berlin/berlin/wohnung-mieten"
    "?sorting=2"  # newest first
)


class ImmoScout24Scraper(BaseScraper):
    source_name = "ImmobilienScout24"

    async def fetch_listings(self) -> list[Listing]:
        try:
            async with new_page(locale="de-DE") as page:
                # Visit homepage first to establish a clean session + cookies
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(2_000)

                await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30_000)

                # Cloudflare Turnstile auto-solves when the fingerprint passes.
                # Give it up to 12 s to redirect to actual content.
                try:
                    await page.wait_for_function(
                        "() => document.title !== 'Ich bin kein Roboter - ImmobilienScout24'",
                        timeout=12_000,
                    )
                except PWTimeout:
                    logger.warning(
                        "ImmoScout24: Cloudflare bot-check not auto-solved. "
                        "A residential proxy or ScrapFly API key (SCRAPFLY_KEY env var) "
                        "is required to bypass this challenge."
                    )
                    return []

                try:
                    await page.wait_for_selector("article[data-obid], script", timeout=8_000)
                except PWTimeout:
                    pass
                html = await page.content()
            return self._parse(html)
        except Exception as exc:
            logger.warning("ImmoScout24 scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    def _parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []

        # IS24 embeds results as JSON in a <script> tag.
        # Key changed from "IS24.resultList" to "searchResponseModel" in newer deployments.
        for script in soup.find_all("script"):
            text = script.string or ""
            if "searchResponseModel" in text or "resultlistEntries" in text:
                parsed = self._extract_json(text)
                if parsed:
                    listings.extend(parsed)
                    return listings

        # Fallback: static HTML cards
        for card in soup.select("article[data-obid]"):
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)
        return listings

    def _extract_json(self, js: str) -> list[Listing]:
        results: list[Listing] = []

        # Try to pull the searchResponseModel JSON object out of the script
        match = re.search(r'"searchResponseModel"\s*:\s*(\{.*?"resultlistEntries".*?\})\s*[,}]', js, re.DOTALL)
        if not match:
            # Broader fallback: locate the resultlistEntries array directly
            match = re.search(r'"resultlistEntries"\s*:\s*(\[.*?\])\s*[,}]', js, re.DOTALL)
            if not match:
                return results
            entries_json = match.group(1)
        else:
            blob = match.group(1)
            inner = re.search(r'"resultlistEntries"\s*:\s*(\[.*?\])', blob, re.DOTALL)
            if not inner:
                return results
            entries_json = inner.group(1)

        try:
            entries = json.loads(entries_json)
        except json.JSONDecodeError:
            return results

        for entry_wrapper in entries:
            # Each wrapper may be a single dict or list
            entry_list = entry_wrapper.get("resultlistEntry", entry_wrapper)
            if isinstance(entry_list, dict):
                entry_list = [entry_list]
            for entry in entry_list:
                listing = self._entry_to_listing(entry)
                if listing:
                    results.append(listing)
        return results

    def _entry_to_listing(self, entry: dict) -> Listing | None:
        try:
            expose_id = str(entry.get("@id", "") or entry.get("id", ""))
            attrs = entry.get("expose", entry)
            address_obj = attrs.get("address", {})
            price_obj = attrs.get("price", {})

            rooms_raw = attrs.get("numberOfRooms", 0) or 0
            price_raw = price_obj.get("value", 0) if isinstance(price_obj, dict) else 0
            space_raw = attrs.get("livingSpace", 0) or 0

            return Listing(
                listing_id=expose_id or hashlib.md5(str(entry).encode()).hexdigest()[:12],
                source=self.source_name,
                period="long",
                rooms=int(float(rooms_raw)) or None,
                price=int(float(price_raw)) or None,
                space=int(float(space_raw)) or None,
                address=(
                    address_obj.get("street", "") if isinstance(address_obj, dict) else ""
                ),
                district=(
                    address_obj.get("city", "Berlin") if isinstance(address_obj, dict) else "Berlin"
                ),
                photo_url=(
                    attrs.get("titlePicture", {}).get("@xlink:href", "")
                    if isinstance(attrs.get("titlePicture"), dict)
                    else ""
                ),
                listing_url=f"{BASE_URL}/expose/{expose_id}",
                is_paywall=not bool(attrs.get("realtorCompanyName")),
                is_swap="tausch" in str(attrs).lower(),
            )
        except Exception:
            return None

    def _parse_card(self, card: BeautifulSoup) -> Listing | None:
        try:
            expose_id = card.get("data-obid", "")
            title_el = card.select_one(".result-list-entry__brand-title-container")
            address_el = card.select_one(".result-list-entry__address")
            address = address_el.get_text(strip=True) if address_el else ""

            price_el = card.select_one("[data-is24-qa='onlinecore-list-entry_primaryprice']")
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = int(re.sub(r"[^\d]", "", price_text)) if re.search(r"\d", price_text) else None

            rooms_el = card.select_one("[data-is24-qa='onlinecore-list-entry_rooms']")
            rooms_text = rooms_el.get_text(strip=True) if rooms_el else ""
            rooms = int(float(re.sub(r"[^\d.]", "", rooms_text))) if re.search(r"\d", rooms_text) else None

            space_el = card.select_one("[data-is24-qa='onlinecore-list-entry_livingspace']")
            space_text = space_el.get_text(strip=True) if space_el else ""
            space = int(float(re.sub(r"[^\d.]", "", space_text))) if re.search(r"\d", space_text) else None

            img = card.select_one("img[src]")
            photo_url = img["src"] if img else ""

            return Listing(
                listing_id=expose_id or hashlib.md5(address.encode()).hexdigest()[:12],
                source=self.source_name,
                period="long",
                rooms=rooms,
                price=price,
                space=space,
                address=address,
                district="Berlin",
                photo_url=photo_url,
                listing_url=f"{BASE_URL}/expose/{expose_id}",
                is_swap="tausch" in (title_el.get_text(strip=True).lower() if title_el else ""),
            )
        except Exception:
            return None
