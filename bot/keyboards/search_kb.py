"""All inline keyboards for the /search configuration panel."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import UserPreference

DISTRICTS = [
    "Mitte",
    "Friedrichshain-Kreuzberg",
    "Pankow",
    "Charlottenburg-Wilmersdorf",
    "Spandau",
    "Steglitz-Zehlendorf",
    "Tempelhof-Schöneberg",
    "Neukölln",
    "Treptow-Köpenick",
    "Marzahn-Hellersdorf",
    "Lichtenberg",
    "Reinickendorf",
]

SOURCES = [
    "ImmobilienScout24",
    "CityWohnen",
    "FurnishedFlats",
    "ShoreCapital",
    "LivingInBerlin",
    "BUWOG",
    "EngelVoelkers",
    "Allod",
]

PRICE_PRESETS = list(range(100, 3100, 100))  # 100..3000
SPACE_PRESETS = list(range(10, 160, 10))     # 10..150
ROOMS_PRESETS = [1, 2, 3, 4]


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


# ── Status text ──────────────────────────────────────────────────────────────


def build_status_text(user: UserPreference) -> str:
    active = "Active" if user.is_active else "Inactive"
    period = user.period if user.period != "any" else "any"
    period_display = {"any": "any", "short": "short term", "long": "long term"}[period]

    rooms_min = f"from {user.rooms_min}" if user.rooms_min else "any"
    rooms_max = f"to {user.rooms_max}" if user.rooms_max else None
    rooms_display = rooms_min if not rooms_max else f"{rooms_min}, {rooms_max}"

    price_min = f"from €{user.price_min}" if user.price_min else None
    price_max = f"to €{user.price_max}" if user.price_max else None
    price_parts = [p for p in [price_min, price_max] if p]
    price_display = ", ".join(price_parts) if price_parts else "any"

    space_min = f"from {user.space_min}m²" if user.space_min else None
    space_max = f"to {user.space_max}m²" if user.space_max else None
    space_parts = [p for p in [space_min, space_max] if p]
    space_display = ", ".join(space_parts) if space_parts else "any"

    locality_display = user.locality if user.locality != "any" else "any"

    skipped = user.skipped_resources or []
    skipped_display = ", ".join(skipped) if skipped else "none"
    tausch = user.tauschwohnung

    return (
        f"<b>Current search:</b> {active}\n"
        f"Rental period: {period_display}\n"
        f"Rooms: {rooms_display}\n"
        f"Price: {price_display}\n"
        f"Living space: {space_display}\n"
        f"Localities: {locality_display}\n"
        f"<b>Advanced filters:</b>\n"
        f"  Tauschwohnung: {tausch}\n"
        f"  Skipped resources: {skipped_display}"
    )


# ── Main panel ───────────────────────────────────────────────────────────────


def main_panel_kb(is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("Period", "search:period"),
        _btn("Rooms", "search:rooms"),
        _btn("Price", "search:price"),
        _btn("L.Space", "search:space"),
    )
    builder.row(_btn("Localities", "search:localities"))
    builder.row(_btn("Advanced filters", "search:advanced"))
    label = "Deactivate" if is_active else "Activate"
    builder.row(_btn(label, "search:toggle_active"))
    return builder.as_markup()


# ── Period sub-menu ──────────────────────────────────────────────────────────


def period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Any", "period:any"))
    builder.row(_btn("Short term", "period:short"), _btn("Long term", "period:long"))
    builder.row(_btn("🏠 Start", "search:main"))
    return builder.as_markup()


# ── Rooms sub-menu ───────────────────────────────────────────────────────────


def rooms_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("🏠 Start", "search:main"),
        _btn("Set min", "rooms:set_min"),
        _btn("Set max", "rooms:set_max"),
    )
    return builder.as_markup()


def rooms_value_kb(bound: str) -> InlineKeyboardMarkup:
    """bound is 'min' or 'max'."""
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Any", f"rooms_val:{bound}:any"))
    row_btns = [_btn(str(r), f"rooms_val:{bound}:{r}") for r in ROOMS_PRESETS]
    builder.row(*row_btns)
    builder.row(
        _btn("« Back to Rooms", "search:rooms"),
        _btn("🏠 Start", "search:main"),
    )
    return builder.as_markup()


# ── Price sub-menu ───────────────────────────────────────────────────────────


def price_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("🏠 Start", "search:main"),
        _btn("Set min", "price:set_min"),
        _btn("Set max", "price:set_max"),
    )
    return builder.as_markup()


def price_value_kb(bound: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Any", f"price_val:{bound}:any"))
    # 5 per row
    for i in range(0, len(PRICE_PRESETS), 5):
        chunk = PRICE_PRESETS[i : i + 5]
        builder.row(*[_btn(str(p), f"price_val:{bound}:{p}") for p in chunk])
    builder.row(
        _btn("« Back to Price", "search:price"),
        _btn("🏠 Start", "search:main"),
    )
    return builder.as_markup()


# ── Living space sub-menu ────────────────────────────────────────────────────


def space_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("🏠 Start", "search:main"),
        _btn("Set min", "space:set_min"),
        _btn("Set max", "space:set_max"),
    )
    return builder.as_markup()


def space_value_kb(bound: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Any", f"space_val:{bound}:any"))
    for i in range(0, len(SPACE_PRESETS), 5):
        chunk = SPACE_PRESETS[i : i + 5]
        builder.row(*[_btn(str(s), f"space_val:{bound}:{s}") for s in chunk])
    builder.row(
        _btn("« Back to L.Space", "search:space"),
        _btn("🏠 Start", "search:main"),
    )
    return builder.as_markup()


# ── Localities sub-menu ──────────────────────────────────────────────────────


def localities_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Any", "locality:any"))
    # 2 per row
    for i in range(0, len(DISTRICTS), 2):
        pair = DISTRICTS[i : i + 2]
        builder.row(*[_btn(d, f"locality:{d}") for d in pair])
    builder.row(_btn("🏠 Start", "search:main"))
    return builder.as_markup()


# ── Advanced filters sub-menu ────────────────────────────────────────────────


def advanced_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("Tauschwohnung", "adv:tauschwohnung"))
    builder.row(_btn("Skip resources", "adv:skip_resources"))
    builder.row(_btn("🏠 Start", "search:main"))
    return builder.as_markup()


def tauschwohnung_kb(current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current == "excluded":
        builder.row(_btn("Include", "tausch:included"))
    else:
        builder.row(_btn("Exclude", "tausch:excluded"))
    builder.row(
        _btn("« Back to Advanced filters", "search:advanced"),
        _btn("🏠 Start", "search:main"),
    )
    return builder.as_markup()


def skip_resources_kb(skipped: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("None", "skip:__none__"))
    for src in SOURCES:
        mark = "✓" if src not in skipped else "✗"
        builder.row(_btn(f"{mark} {src}", f"skip:{src}"))
    builder.row(
        _btn("« Back to Advanced filters", "search:advanced"),
        _btn("🏠 Start", "search:main"),
    )
    return builder.as_markup()
