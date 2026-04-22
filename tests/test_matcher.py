"""Tests for the matching logic."""
from __future__ import annotations

import pytest

from bot.database.models import UserPreference
from bot.matcher import matches
from bot.scrapers.base import Listing


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        listing_id="test-id",
        source="ImmobilienScout24",
        period="long",
        rooms=2,
        price=1000,
        space=60,
        address="Hauptstraße 1",
        district="Mitte",
        photo_url="https://example.com/photo.jpg",
        listing_url="https://example.com/listing",
        is_paywall=False,
        is_swap=False,
    )
    defaults.update(kwargs)
    return Listing(**defaults)


def make_user(**kwargs) -> UserPreference:
    user = UserPreference(
        user_id=1,
        is_active=True,
        period="any",
        rooms_min=None,
        rooms_max=None,
        price_min=None,
        price_max=None,
        space_min=None,
        space_max=None,
        locality="any",
        tauschwohnung="excluded",
        skipped_resources=[],
    )
    for key, value in kwargs.items():
        setattr(user, key, value)
    return user


class TestPeriodFilter:
    def test_any_period_matches_long(self):
        assert matches(make_listing(period="long"), make_user(period="any"))

    def test_any_period_matches_short(self):
        assert matches(make_listing(period="short"), make_user(period="any"))

    def test_long_filter_matches_long(self):
        assert matches(make_listing(period="long"), make_user(period="long"))

    def test_long_filter_rejects_short(self):
        assert not matches(make_listing(period="short"), make_user(period="long"))

    def test_short_filter_matches_short(self):
        assert matches(make_listing(period="short"), make_user(period="short"))

    def test_short_filter_rejects_long(self):
        assert not matches(make_listing(period="long"), make_user(period="short"))


class TestRoomsFilter:
    def test_no_filter_matches(self):
        assert matches(make_listing(rooms=3), make_user())

    def test_min_rooms_passes(self):
        assert matches(make_listing(rooms=3), make_user(rooms_min=2))

    def test_min_rooms_fails(self):
        assert not matches(make_listing(rooms=1), make_user(rooms_min=2))

    def test_max_rooms_passes(self):
        assert matches(make_listing(rooms=2), make_user(rooms_max=3))

    def test_max_rooms_fails(self):
        assert not matches(make_listing(rooms=4), make_user(rooms_max=3))

    def test_min_and_max_rooms(self):
        assert matches(make_listing(rooms=2), make_user(rooms_min=2, rooms_max=3))
        assert not matches(make_listing(rooms=4), make_user(rooms_min=2, rooms_max=3))

    def test_null_rooms_not_filtered(self):
        assert matches(make_listing(rooms=None), make_user(rooms_min=2))


class TestPriceFilter:
    def test_no_filter_matches(self):
        assert matches(make_listing(price=1200), make_user())

    def test_max_price_passes(self):
        assert matches(make_listing(price=1000), make_user(price_max=1200))

    def test_max_price_fails(self):
        assert not matches(make_listing(price=1500), make_user(price_max=1200))

    def test_min_price_passes(self):
        assert matches(make_listing(price=800), make_user(price_min=500))

    def test_min_price_fails(self):
        assert not matches(make_listing(price=400), make_user(price_min=500))

    def test_null_price_not_filtered(self):
        assert matches(make_listing(price=None), make_user(price_max=1000))


class TestSpaceFilter:
    def test_no_filter_matches(self):
        assert matches(make_listing(space=70), make_user())

    def test_min_space_passes(self):
        assert matches(make_listing(space=60), make_user(space_min=50))

    def test_min_space_fails(self):
        assert not matches(make_listing(space=40), make_user(space_min=50))

    def test_null_space_not_filtered(self):
        assert matches(make_listing(space=None), make_user(space_min=50))


class TestLocalityFilter:
    def test_any_locality_matches_any_district(self):
        assert matches(make_listing(district="Neukölln"), make_user(locality="any"))

    def test_matching_district_passes(self):
        assert matches(make_listing(district="Mitte"), make_user(locality="Mitte"))

    def test_wrong_district_fails(self):
        assert not matches(make_listing(district="Neukölln"), make_user(locality="Mitte"))


class TestTauschwohnungFilter:
    def test_excluded_blocks_swap(self):
        assert not matches(make_listing(is_swap=True), make_user(tauschwohnung="excluded"))

    def test_excluded_allows_non_swap(self):
        assert matches(make_listing(is_swap=False), make_user(tauschwohnung="excluded"))

    def test_included_allows_swap(self):
        assert matches(make_listing(is_swap=True), make_user(tauschwohnung="included"))


class TestSkippedResources:
    def test_skipped_source_rejected(self):
        assert not matches(
            make_listing(source="ImmobilienScout24"),
            make_user(skipped_resources=["ImmobilienScout24"]),
        )

    def test_non_skipped_source_allowed(self):
        assert matches(
            make_listing(source="CityWohnen"),
            make_user(skipped_resources=["ImmobilienScout24"]),
        )

    def test_empty_skip_list_allows_all(self):
        assert matches(make_listing(), make_user(skipped_resources=[]))


class TestCombinedFilters:
    def test_all_criteria_match(self):
        listing = make_listing(period="long", rooms=2, price=950, space=55, district="Mitte")
        user = make_user(
            period="long",
            rooms_min=2,
            rooms_max=3,
            price_max=1000,
            space_min=50,
            locality="Mitte",
        )
        assert matches(listing, user)

    def test_one_failing_criterion_blocks(self):
        listing = make_listing(period="long", rooms=2, price=1100, space=55, district="Mitte")
        user = make_user(
            period="long",
            rooms_min=2,
            price_max=1000,  # this fails
            locality="Mitte",
        )
        assert not matches(listing, user)
