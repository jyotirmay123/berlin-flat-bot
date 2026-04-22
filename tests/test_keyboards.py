"""Tests for keyboard builders and status text."""
from __future__ import annotations

import pytest

from bot.database.models import UserPreference
from bot.keyboards.search_kb import (
    DISTRICTS,
    SOURCES,
    build_status_text,
    localities_kb,
    main_panel_kb,
    period_kb,
    price_value_kb,
    rooms_value_kb,
    skip_resources_kb,
    space_value_kb,
    tauschwohnung_kb,
)


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


class TestStatusText:
    def test_active_user_shows_active(self):
        text = build_status_text(make_user(is_active=True))
        assert "Active" in text

    def test_inactive_user_shows_inactive(self):
        text = build_status_text(make_user(is_active=False))
        assert "Inactive" in text

    def test_period_long_displayed(self):
        text = build_status_text(make_user(period="long"))
        assert "long term" in text

    def test_period_short_displayed(self):
        text = build_status_text(make_user(period="short"))
        assert "short term" in text

    def test_rooms_min_displayed(self):
        text = build_status_text(make_user(rooms_min=2))
        assert "from 2" in text

    def test_price_max_displayed(self):
        text = build_status_text(make_user(price_max=1400))
        assert "€1400" in text

    def test_space_min_displayed(self):
        text = build_status_text(make_user(space_min=50))
        assert "50m²" in text

    def test_locality_displayed(self):
        text = build_status_text(make_user(locality="Mitte"))
        assert "Mitte" in text

    def test_tauschwohnung_excluded_shown(self):
        text = build_status_text(make_user(tauschwohnung="excluded"))
        assert "excluded" in text

    def test_skipped_resources_shown(self):
        text = build_status_text(make_user(skipped_resources=["BUWOG"]))
        assert "BUWOG" in text

    def test_no_skipped_shows_none(self):
        text = build_status_text(make_user(skipped_resources=[]))
        assert "none" in text


class TestMainPanelKeyboard:
    def test_active_user_shows_deactivate(self):
        kb = main_panel_kb(is_active=True)
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Deactivate" in buttons

    def test_inactive_user_shows_activate(self):
        kb = main_panel_kb(is_active=False)
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Activate" in buttons

    def test_main_panel_has_all_sections(self):
        kb = main_panel_kb()
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Period" in buttons
        assert "Rooms" in buttons
        assert "Price" in buttons
        assert "L.Space" in buttons
        assert "Localities" in buttons
        assert "Advanced filters" in buttons


class TestPeriodKeyboard:
    def test_period_kb_has_three_options(self):
        kb = period_kb()
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Any" in buttons
        assert "Short term" in buttons
        assert "Long term" in buttons
        assert "🏠 Start" in buttons

    def test_period_kb_callback_data(self):
        kb = period_kb()
        data = {btn.callback_data for row in kb.inline_keyboard for btn in row}
        assert "period:any" in data
        assert "period:short" in data
        assert "period:long" in data


class TestRoomsKeyboard:
    def test_rooms_value_kb_min_has_any(self):
        kb = rooms_value_kb("min")
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Any" in buttons

    def test_rooms_value_kb_has_back(self):
        kb = rooms_value_kb("min")
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "« Back to Rooms" in buttons

    def test_rooms_value_kb_callback_data(self):
        kb = rooms_value_kb("min")
        data = {btn.callback_data for row in kb.inline_keyboard for btn in row}
        assert "rooms_val:min:any" in data
        assert "rooms_val:min:1" in data
        assert "rooms_val:min:4" in data


class TestPriceKeyboard:
    def test_price_kb_has_100_to_3000(self):
        kb = price_value_kb("max")
        data = {btn.callback_data for row in kb.inline_keyboard for btn in row}
        assert "price_val:max:100" in data
        assert "price_val:max:3000" in data
        assert "price_val:max:any" in data


class TestSpaceKeyboard:
    def test_space_kb_has_10_to_150(self):
        kb = space_value_kb("min")
        data = {btn.callback_data for row in kb.inline_keyboard for btn in row}
        assert "space_val:min:10" in data
        assert "space_val:min:150" in data


class TestLocalitiesKeyboard:
    def test_all_districts_present(self):
        kb = localities_kb()
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        for district in DISTRICTS:
            assert district in buttons

    def test_any_option_present(self):
        kb = localities_kb()
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Any" in buttons


class TestSkipResourcesKeyboard:
    def test_all_sources_in_kb(self):
        kb = skip_resources_kb([])
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        for src in SOURCES:
            assert any(src in b for b in buttons)

    def test_skipped_source_marked_with_x(self):
        kb = skip_resources_kb(["BUWOG"])
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("✗ BUWOG" in b for b in buttons)

    def test_active_source_marked_with_check(self):
        kb = skip_resources_kb([])
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("✓ BUWOG" in b for b in buttons)


class TestTauschwohnungKeyboard:
    def test_excluded_shows_include_button(self):
        kb = tauschwohnung_kb("excluded")
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Include" in buttons
        assert "Exclude" not in buttons

    def test_included_shows_exclude_button(self):
        kb = tauschwohnung_kb("included")
        buttons = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Exclude" in buttons
        assert "Include" not in buttons
