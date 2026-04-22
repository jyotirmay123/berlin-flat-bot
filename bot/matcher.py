"""Matching logic: checks a listing against a user's filter preferences."""
from __future__ import annotations

from bot.database.models import UserPreference
from bot.scrapers.base import Listing

# Maps sub-district names (and common transliterations) → official Berlin Bezirk name.
# Keys are lowercase; values match the DISTRICTS list in search_kb.py exactly.
_DISTRICT_NORM: dict[str, str] = {
    # ── Mitte ──────────────────────────────────────────────────────────
    "mitte": "Mitte",
    "tiergarten": "Mitte",
    "wedding": "Mitte",
    "gesundbrunnen": "Mitte",
    "moabit": "Mitte",
    "hansaviertel": "Mitte",
    # ── Friedrichshain-Kreuzberg ────────────────────────────────────────
    "friedrichshain": "Friedrichshain-Kreuzberg",
    "kreuzberg": "Friedrichshain-Kreuzberg",
    "friedrichshain-kreuzberg": "Friedrichshain-Kreuzberg",
    # ── Pankow ─────────────────────────────────────────────────────────
    "pankow": "Pankow",
    "prenzlauer berg": "Pankow",
    "prenzlauerberg": "Pankow",
    "weißensee": "Pankow",
    "weissensee": "Pankow",
    "niederschönhausen": "Pankow",
    "niederschonhausen": "Pankow",
    "buch": "Pankow",
    "karow": "Pankow",
    "blankenburg": "Pankow",
    "heinersdorf": "Pankow",
    "wilhelmsruh": "Pankow",
    "rosenthal": "Pankow",
    "blankenfelde": "Pankow",
    "frohnau": "Reinickendorf",   # placed below, override below
    # ── Charlottenburg-Wilmersdorf ──────────────────────────────────────
    "charlottenburg": "Charlottenburg-Wilmersdorf",
    "wilmersdorf": "Charlottenburg-Wilmersdorf",
    "charlottenburg-wilmersdorf": "Charlottenburg-Wilmersdorf",
    "westend": "Charlottenburg-Wilmersdorf",
    "halensee": "Charlottenburg-Wilmersdorf",
    "schmargendorf": "Charlottenburg-Wilmersdorf",
    # ── Spandau ─────────────────────────────────────────────────────────
    "spandau": "Spandau",
    "haselhorst": "Spandau",
    "siemensstadt": "Spandau",
    "staaken": "Spandau",
    "gatow": "Spandau",
    "kladow": "Spandau",
    # ── Steglitz-Zehlendorf ─────────────────────────────────────────────
    "steglitz": "Steglitz-Zehlendorf",
    "zehlendorf": "Steglitz-Zehlendorf",
    "steglitz-zehlendorf": "Steglitz-Zehlendorf",
    "lichterfelde": "Steglitz-Zehlendorf",
    "lankwitz": "Steglitz-Zehlendorf",
    "wannsee": "Steglitz-Zehlendorf",
    "nikolassee": "Steglitz-Zehlendorf",
    # ── Tempelhof-Schöneberg ────────────────────────────────────────────
    "tempelhof": "Tempelhof-Schöneberg",
    "schöneberg": "Tempelhof-Schöneberg",
    "schoeneberg": "Tempelhof-Schöneberg",
    "tempelhof-schöneberg": "Tempelhof-Schöneberg",
    "tempelhof-schoneberg": "Tempelhof-Schöneberg",
    "mariendorf": "Tempelhof-Schöneberg",
    "marienfelde": "Tempelhof-Schöneberg",
    "lichtenrade": "Tempelhof-Schöneberg",
    # ── Neukölln ────────────────────────────────────────────────────────
    "neukölln": "Neukölln",
    "neukoelln": "Neukölln",
    "neukoln": "Neukölln",
    "britz": "Neukölln",
    "buckow": "Neukölln",
    "rudow": "Neukölln",
    "gropiusstadt": "Neukölln",
    # ── Treptow-Köpenick ────────────────────────────────────────────────
    "treptow": "Treptow-Köpenick",
    "köpenick": "Treptow-Köpenick",
    "koepenick": "Treptow-Köpenick",
    "kopenick": "Treptow-Köpenick",
    "treptow-köpenick": "Treptow-Köpenick",
    "treptow-koepenick": "Treptow-Köpenick",
    "alt-treptow": "Treptow-Köpenick",
    "oberschöneweide": "Treptow-Köpenick",
    "oberschoneweide": "Treptow-Köpenick",
    "johannisthal": "Treptow-Köpenick",
    "adlershof": "Treptow-Köpenick",
    "altglienicke": "Treptow-Köpenick",
    "bohnsdorf": "Treptow-Köpenick",
    "grünau": "Treptow-Köpenick",
    "grunau": "Treptow-Köpenick",
    "friedrichshagen": "Treptow-Köpenick",
    "baumschulenweg": "Treptow-Köpenick",
    "niederschöneweide": "Treptow-Köpenick",
    "niederschoneweide": "Treptow-Köpenick",
    # ── Marzahn-Hellersdorf ─────────────────────────────────────────────
    "marzahn": "Marzahn-Hellersdorf",
    "hellersdorf": "Marzahn-Hellersdorf",
    "marzahn-hellersdorf": "Marzahn-Hellersdorf",
    "biesdorf": "Marzahn-Hellersdorf",
    "kaulsdorf": "Marzahn-Hellersdorf",
    "mahlsdorf": "Marzahn-Hellersdorf",
    # ── Lichtenberg ─────────────────────────────────────────────────────
    "lichtenberg": "Lichtenberg",
    "friedrichsfelde": "Lichtenberg",
    "rummelsburg": "Lichtenberg",
    "karlshorst": "Lichtenberg",
    "fennpfuhl": "Lichtenberg",
    "hohenschönhausen": "Lichtenberg",
    "hohenschonhausen": "Lichtenberg",
    "alt-hohenschönhausen": "Lichtenberg",
    "neu-hohenschönhausen": "Lichtenberg",
    "malchow": "Lichtenberg",
    "wartenberg": "Lichtenberg",
    "falkenberg": "Lichtenberg",
    # ── Treptow-Köpenick (additional micro-quarters) ────────────────────
    "kietzer": "Treptow-Köpenick",        # Kietzer Feld, Köpenick
    "müggelheim": "Treptow-Köpenick",
    "muggelheim": "Treptow-Köpenick",
    "schmöckwitz": "Treptow-Köpenick",
    "schmockwitz": "Treptow-Köpenick",
    "plänterwald": "Treptow-Köpenick",
    "planterwald": "Treptow-Köpenick",
    # ── Lichtenberg (additional) ────────────────────────────────────────
    "allendeviertel": "Lichtenberg",      # social housing quarter near Fennpfuhl
    "neu-hohenschönhausen": "Lichtenberg",
    "alt-hohenschönhausen": "Lichtenberg",
    # ── Marzahn-Hellersdorf (additional) ────────────────────────────────
    "springpfuhl": "Marzahn-Hellersdorf",
    "ackermannshof": "Marzahn-Hellersdorf",
    # ── Reinickendorf ───────────────────────────────────────────────────
    "reinickendorf": "Reinickendorf",
    "tegel": "Reinickendorf",
    "waidmannslust": "Reinickendorf",
    "heiligensee": "Reinickendorf",
    "hermsdorf": "Reinickendorf",
    "lübars": "Reinickendorf",
    "lubars": "Reinickendorf",
    "wittenau": "Reinickendorf",
    "frohnau": "Reinickendorf",
    "konradshöhe": "Reinickendorf",
    "konradshohe": "Reinickendorf",
}

# Generic strings that mean "district unknown" — pass through any locality filter.
_UNKNOWN_DISTRICT = {"berlin", ""}


def _normalize_district(raw: str) -> str | None:
    """Return the official Bezirk name for a listing's district string.

    Returns None if the district is unknown/generic (should pass through any filter).
    """
    if not raw or raw.lower().strip() in _UNKNOWN_DISTRICT:
        return None
    key = raw.lower().strip()
    # Direct lookup
    if key in _DISTRICT_NORM:
        return _DISTRICT_NORM[key]
    # Partial match: e.g. "Reinickendorf (Reinickendorf)" contains "reinickendorf"
    for sub, bezirk in _DISTRICT_NORM.items():
        if sub in key:
            return bezirk
    # Return as-is (capitalised) so an exact match against the stored locality still works
    return raw.strip()


def matches(listing: Listing, user: UserPreference) -> bool:
    """Return True if the listing satisfies all of the user's filter criteria."""
    # ── Source skip ──────────────────────────────────────────────────────
    if listing.source in (user.skipped_resources or []):
        return False

    # ── Rental period ────────────────────────────────────────────────────
    if user.period != "any" and listing.period != user.period:
        return False

    # ── Rooms ────────────────────────────────────────────────────────────
    # Unknown room count is treated as "possibly matching" (permissive).
    if listing.rooms is not None:
        if user.rooms_min is not None and listing.rooms < user.rooms_min:
            return False
        if user.rooms_max is not None and listing.rooms > user.rooms_max:
            return False

    # ── Price ────────────────────────────────────────────────────────────
    if listing.price is not None:
        if user.price_min is not None and listing.price < user.price_min:
            return False
        if user.price_max is not None and listing.price > user.price_max:
            return False

    # ── Living space ─────────────────────────────────────────────────────
    if listing.space is not None:
        if user.space_min is not None and listing.space < user.space_min:
            return False
        if user.space_max is not None and listing.space > user.space_max:
            return False

    # ── Locality ─────────────────────────────────────────────────────────
    # Normalize the listing's raw district to an official Bezirk name so that
    # sub-districts ("Friedrichshain") and transliterations ("Neukoelln") map
    # correctly to what the user selected ("Friedrichshain-Kreuzberg", "Neukölln").
    # A None result means the district is unknown → pass through rather than block.
    if user.locality != "any":
        bezirk = _normalize_district(listing.district)
        if bezirk is not None and bezirk != user.locality:
            return False

    # ── Tauschwohnung ────────────────────────────────────────────────────
    if user.tauschwohnung == "excluded" and listing.is_swap:
        return False

    return True
