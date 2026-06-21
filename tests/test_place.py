from types import SimpleNamespace

from tv_photos.place import photo_place_label, place_label


def names(**kw):
    """Build a stand-in for osxphotos PlaceNames (each field is a list, most-specific first)."""
    fields = dict(
        country=[], state_province=[], sub_administrative_area=[], city=[],
        additional_city_info=[], area_of_interest=[],
    )
    fields.update(kw)
    return SimpleNamespace(**fields)


def place(**kw):
    return SimpleNamespace(names=names(**kw))


def test_city_and_country():
    assert place_label(place(city=["Reykjavík"], country=["Iceland"])) == "Reykjavík, Iceland"


def test_none_place_returns_none():
    assert place_label(None) is None


def test_no_usable_names_returns_none():
    assert place_label(place()) is None


def test_country_only():
    assert place_label(place(country=["Iceland"])) == "Iceland"


def test_locality_without_country():
    assert place_label(place(city=["Vík"])) == "Vík"


def test_area_of_interest_used_when_no_city():
    assert place_label(place(area_of_interest=["Þingvellir"], country=["Iceland"])) == "Þingvellir, Iceland"


def test_city_preferred_over_area_of_interest():
    assert place_label(
        place(city=["Paris"], area_of_interest=["Eiffel Tower"], country=["France"])
    ) == "Paris, France"


def test_state_province_fallback_when_no_city_or_aoi():
    assert place_label(place(state_province=["Bavaria"], country=["Germany"])) == "Bavaria, Germany"


def test_dedupes_when_locality_equals_country():
    # city-state like Singapore: don't render "Singapore, Singapore"
    assert place_label(place(city=["Singapore"], country=["Singapore"])) == "Singapore"


def test_ignores_empty_strings_and_whitespace():
    assert place_label(place(city=["  "], country=["Iceland"])) == "Iceland"


def test_handles_none_field_values():
    # a PlaceNames-like object whose fields are None rather than empty lists
    p = SimpleNamespace(names=SimpleNamespace(city=None, country=["Iceland"]))
    assert place_label(p) == "Iceland"


# --- photo_place_label: a defensive wrapper over a PhotoInfo's .place ---------

class _RaisingPlace:
    @property
    def place(self):
        raise RuntimeError("reverse-geocode lookup blew up")


def test_photo_place_label_returns_string():
    p = SimpleNamespace(place=place(city=["Vík"], country=["Iceland"]))
    assert photo_place_label(p) == "Vík, Iceland"


def test_photo_place_label_no_place_is_empty_string():
    assert photo_place_label(SimpleNamespace(place=None)) == ""


def test_photo_place_label_swallows_errors():
    assert photo_place_label(_RaisingPlace()) == ""
