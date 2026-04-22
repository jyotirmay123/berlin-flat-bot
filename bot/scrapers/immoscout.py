"""ImmobilienScout24 scraper — long-term rentals in Berlin.

Fetch strategy (tried in order):
  1. ScrapFly API (if SCRAPFLY_KEY is set) — bypasses Cloudflare ASP reliably.
  2. Playwright + stealth — works only when the Cloudflare Turnstile auto-solves
     (requires a residential IP; typically fails on VPS/cloud).

Set SCRAPFLY_KEY in .env to enable reliable IS24 scraping.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import TimeoutError as PWTimeout

from bot.config import settings
from bot.scrapers.base import BaseScraper, Listing
from bot.scrapers.playwright_base import new_page

BASE_URL = "https://www.immobilienscout24.de"
SEARCH_URL = (
    f"{BASE_URL}/Suche/de/berlin/berlin/wohnung-mieten"
    "?sorting=2"  # newest first
)

_SCRAPFLY_ENDPOINT = "https://api.scrapfly.io/scrape"


class ImmoScout24Scraper(BaseScraper):
    source_name = "ImmobilienScout24"

    async def fetch_listings(self, since: datetime | None = None) -> list[Listing]:
        if settings.scrapfly_key:
            return await self._fetch_via_scrapfly(since)
        return await self._fetch_via_playwright(since)

    # ------------------------------------------------------------------
    # ScrapFly path
    # ------------------------------------------------------------------

    async def _fetch_via_scrapfly(self, since: datetime | None = None) -> list[Listing]:
        params = {
            "key": settings.scrapfly_key,
            "url": SEARCH_URL,
            "asp": "true",       # anti-scraping protection bypass
            "render_js": "true", # execute JS so embedded JSON is populated
            "country": "de",
            "lang": "de",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    _SCRAPFLY_ENDPOINT,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(
                            "ImmoScout24/ScrapFly: HTTP {} — {}",
                            resp.status, body[:200],
                        )
                        return []
                    data = await resp.json()

            result = data.get("result", {})
            status_code = result.get("status_code", 0)
            if status_code != 200:
                logger.warning(
                    "ImmoScout24/ScrapFly: target returned HTTP {}", status_code
                )
                return []

            html = result.get("content", "")
            listings = self._parse(html, since)
            logger.info("ImmoScout24/ScrapFly: {} listings fetched", len(listings))
            return listings

        except Exception as exc:
            logger.warning(
                "ImmoScout24/ScrapFly request failed: {} {} — falling back to Playwright",
                type(exc).__name__, exc,
            )
            return await self._fetch_via_playwright(since)

    # ------------------------------------------------------------------
    # Playwright path (fallback)
    # ------------------------------------------------------------------

    async def _fetch_via_playwright(self, since: datetime | None = None) -> list[Listing]:
        try:
            async with new_page(locale="de-DE") as page:
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(2_000)
                await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30_000)

                try:
                    await page.wait_for_function(
                        "() => document.title !== 'Ich bin kein Roboter - ImmobilienScout24'",
                        timeout=12_000,
                    )
                except PWTimeout:
                    logger.warning(
                        "ImmoScout24: Cloudflare Turnstile not auto-solved. "
                        "Add SCRAPFLY_KEY to .env to bypass this — "
                        "free tier: https://scrapfly.io (1000 calls/month)."
                    )
                    return []

                try:
                    await page.wait_for_selector("article[data-obid], script", timeout=8_000)
                except PWTimeout:
                    pass
                html = await page.content()
            return self._parse(html, since)
        except Exception as exc:
            logger.warning("ImmoScout24 scraper unavailable: {} {}", type(exc).__name__, exc)
            return []

    # ------------------------------------------------------------------
    # Parsing (shared by both fetch paths)
    # ------------------------------------------------------------------

    def _parse(self, html: str, since: datetime | None = None) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []

        for script in soup.find_all("script"):
            text = script.string or ""
            if "searchResponseModel" in text or "resultlistEntries" in text:
                parsed = self._extract_json(text, since)
                if parsed:
                    listings.extend(parsed)
                    return listings

        for card in soup.select("article[data-obid]"):
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)
        return listings

    def _extract_json(self, js: str, since: datetime | None = None) -> list[Listing]:
        results: list[Listing] = []

        # Locate "resultlistEntries": [ ... ] and decode using the stdlib JSON parser
        # (regex with .*? fails on deeply nested objects — misses closing brackets).
        pos = js.find('"resultlistEntries":')
        if pos < 0:
            return results
        arr_start = js.find("[", pos)
        if arr_start < 0:
            return results
        try:
            entries, _ = json.JSONDecoder().raw_decode(js[arr_start:])
        except json.JSONDecodeError:
            return results

        for entry_wrapper in entries:
            entry_list = entry_wrapper.get("resultlistEntry", entry_wrapper)
            if isinstance(entry_list, dict):
                entry_list = [entry_list]
            for entry in entry_list:
                if since is not None:
                    pub_date_str = entry.get("@publishDate", "")
                    if pub_date_str:
                        try:
                            pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                            if pub_date.tzinfo is None:
                                pub_date = pub_date.replace(tzinfo=timezone.utc)
                            if pub_date < since:
                                continue
                        except ValueError:
                            pass  # unparseable date → include conservatively
                listing = self._entry_to_listing(entry)
                if listing:
                    results.append(listing)
        return results

    def _entry_to_listing(self, entry: dict) -> Listing | None:
        try:
            expose_id = str(entry.get("@id", "") or entry.get("realEstateId", ""))
            # IS24 search results embed data under "resultlist.realEstate"
            re_ = entry.get("resultlist.realEstate") or entry.get("expose") or entry
            address_obj = re_.get("address", {}) if isinstance(re_, dict) else {}
            price_obj = re_.get("price", {}) if isinstance(re_, dict) else {}

            street = address_obj.get("street", "") if isinstance(address_obj, dict) else ""
            house_nr = address_obj.get("houseNumber", "") if isinstance(address_obj, dict) else ""
            address = f"{street} {house_nr}".strip() or address_obj.get("description", {}).get("text", "") if isinstance(address_obj, dict) else ""
            quarter = address_obj.get("quarter", "") if isinstance(address_obj, dict) else ""
            # quarter comes as "Neukölln (Neukölln)" — strip the parenthetical
            district = re.sub(r"\s*\(.*?\)", "", quarter).strip() or (
                address_obj.get("city", "Berlin") if isinstance(address_obj, dict) else "Berlin"
            )

            price_raw = price_obj.get("value", 0) if isinstance(price_obj, dict) else 0
            rooms_raw = re_.get("numberOfRooms", 0) or 0 if isinstance(re_, dict) else 0
            space_raw = re_.get("livingSpace", 0) or 0 if isinstance(re_, dict) else 0

            # First photo from galleryAttachments; replace size placeholders with 600x400
            photo_url = ""
            if isinstance(re_, dict):
                attachments = re_.get("galleryAttachments", {}).get("attachment", [])
                if attachments:
                    href = attachments[0].get("urls", [{}])[0].get("url", {}).get("@href", "")
                    photo_url = href.replace("%WIDTH%", "600").replace("%HEIGHT%", "400")

            title = re_.get("title", "") if isinstance(re_, dict) else ""

            return Listing(
                listing_id=expose_id or hashlib.md5(str(entry).encode()).hexdigest()[:12],
                source=self.source_name,
                period="long",
                rooms=int(float(rooms_raw)) or None,
                price=int(float(price_raw)) or None,
                space=int(float(space_raw)) or None,
                address=address or "Berlin",
                district=district or "Berlin",
                photo_url=photo_url,
                listing_url=f"{BASE_URL}/expose/{expose_id}",
                is_paywall=not bool(re_.get("realtorCompanyName") if isinstance(re_, dict) else None),
                is_swap="tausch" in title.lower(),
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
