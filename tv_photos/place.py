"""Build a concise 'Locality, Country' label from an osxphotos PlaceInfo.

Apple Photos reverse-geocodes photos on-device, so osxphotos exposes the place
names without any network call. The label is burned onto the uploaded image
(bottom-left), near where Google TV Ambient mode shows the album name. Returns
None when the photo has no usable location, so the caller can skip the overlay.
"""
from __future__ import annotations


def _first(value) -> str | None:
    """First non-empty, stripped string from a PlaceNames field (list) or scalar."""
    if not value:
        return None
    if isinstance(value, str):
        return value.strip() or None
    for item in value:  # list, most-specific first
        if item and str(item).strip():
            return str(item).strip()
    return None


def place_label(place) -> str | None:
    """Concise 'Locality, Country' label for a photo's PlaceInfo, or None.

    Prefers a human locality (city, then a named point/area of interest, then the
    administrative area) and appends the country. Deduplicates when they coincide
    (e.g. city-states), so we never render "Singapore, Singapore".
    """
    if place is None:
        return None
    names = getattr(place, "names", None)
    if names is None:
        return None

    locality = (
        _first(getattr(names, "city", None))
        or _first(getattr(names, "area_of_interest", None))
        or _first(getattr(names, "sub_administrative_area", None))
        or _first(getattr(names, "state_province", None))
        or _first(getattr(names, "additional_city_info", None))
    )
    country = _first(getattr(names, "country", None))

    parts: list[str] = []
    for part in (locality, country):
        if part and part not in parts:
            parts.append(part)
    return ", ".join(parts) if parts else None


def photo_place_label(photo) -> str:
    """Place label for an osxphotos PhotoInfo, as a string ("" when unavailable).

    Defensive: a photo's ``.place`` reverse-geocode lookup can occasionally raise,
    and a missing location is the common case — both collapse to "".
    """
    try:
        return place_label(getattr(photo, "place", None)) or ""
    except Exception:  # noqa: BLE001 - a bad place lookup must not abort the scan
        return ""
