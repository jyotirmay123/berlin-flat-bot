"""Shared async Playwright utilities for scrapers that require JS rendering."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

_stealth = Stealth()

_BROWSER: Browser | None = None
_PW = None


async def get_browser() -> Browser:
    """Return a shared long-lived Chromium instance (lazy-init)."""
    global _BROWSER, _PW
    if _BROWSER is None or not _BROWSER.is_connected():
        _PW = await async_playwright().start()
        _BROWSER = await _PW.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
    return _BROWSER


async def close_browser() -> None:
    global _BROWSER, _PW
    if _BROWSER and _BROWSER.is_connected():
        await _BROWSER.close()
        _BROWSER = None
    if _PW:
        await _PW.stop()
        _PW = None


@asynccontextmanager
async def new_page(locale: str = "de-DE") -> AsyncGenerator[Page, None]:
    """Open a fresh stealth browser context + page, close on exit."""
    browser = await get_browser()
    context: BrowserContext = await browser.new_context(
        locale=locale,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        java_script_enabled=True,
        ignore_https_errors=True,
    )
    page: Page = await context.new_page()
    await _stealth.apply_stealth_async(page)
    try:
        yield page
    finally:
        await context.close()
