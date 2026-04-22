"""Tests for notification message text generation."""
from __future__ import annotations

import pytest

from bot.notifier import _build_notification_text
from bot.scrapers.base import Listing


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        listing_id="abc123",
        source="ImmobilienScout24",
        period="long",
        rooms=2,
        price=985,
        space=60,
        address="Ravenestraße 6",
        district="Gesundbrunnen",
        photo_url="https://example.com/photo.jpg",
        listing_url="https://www.immobilienscout24.de/expose/123",
        is_paywall=False,
        is_swap=False,
    )
    defaults.update(kwargs)
    return Listing(**defaults)


def test_long_term_listing_text():
    text = _build_notification_text(make_listing(period="long"))
    assert text.startswith("Long term:")


def test_short_term_listing_text():
    text = _build_notification_text(make_listing(period="short"))
    assert text.startswith("Short term:")


def test_rooms_in_text():
    text = _build_notification_text(make_listing(rooms=2, price=985))
    assert "2 rooms" in text
    assert "€985" in text


def test_address_in_text():
    text = _build_notification_text(make_listing(address="Ravenestraße 6"))
    assert "Ravenestraße 6" in text


def test_url_in_text():
    url = "https://www.immobilienscout24.de/expose/123"
    text = _build_notification_text(make_listing(listing_url=url))
    assert url in text


def test_paywall_notice_appended():
    text = _build_notification_text(make_listing(is_paywall=True))
    assert "paywall" in text.lower()


def test_no_paywall_notice_for_free_listings():
    text = _build_notification_text(make_listing(is_paywall=False))
    assert "paywall" not in text.lower()


def test_unknown_rooms_uses_placeholder():
    text = _build_notification_text(make_listing(rooms=None))
    assert "? rooms" in text


def test_unknown_price_uses_placeholder():
    text = _build_notification_text(make_listing(price=None))
    assert "price unknown" in text
