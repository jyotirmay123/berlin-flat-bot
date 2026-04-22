"""Matching logic: checks a listing against a user's filter preferences."""
from __future__ import annotations

from bot.database.models import UserPreference
from bot.scrapers.base import Listing


def matches(listing: Listing, user: UserPreference) -> bool:
    """Return True if the listing satisfies all of the user's filter criteria."""
    skipped: list[str] = user.skipped_resources or []
    if listing.source in skipped:
        return False

    if user.period != "any" and listing.period != user.period:
        return False

    if listing.rooms is not None:
        if user.rooms_min is not None and listing.rooms < user.rooms_min:
            return False
        if user.rooms_max is not None and listing.rooms > user.rooms_max:
            return False

    if listing.price is not None:
        if user.price_min is not None and listing.price < user.price_min:
            return False
        if user.price_max is not None and listing.price > user.price_max:
            return False

    if listing.space is not None:
        if user.space_min is not None and listing.space < user.space_min:
            return False
        if user.space_max is not None and listing.space > user.space_max:
            return False

    if user.locality != "any" and listing.district and listing.district != user.locality:
        return False

    if user.tauschwohnung == "excluded" and listing.is_swap:
        return False

    return True
