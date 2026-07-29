import pytest
from labtracker_lib import PERIOD_OPTIONS, PERIOD_DAYS, period_days_for, NAV_ITEMS, ICONS


def test_period_options_are_in_display_order():
    assert PERIOD_OPTIONS == ["3M", "6M", "9M", "1Y", "ALL"]


def test_period_days_for_known_buckets():
    assert period_days_for("3M") == 90
    assert period_days_for("6M") == 182
    assert period_days_for("9M") == 273
    assert period_days_for("1Y") == 365


def test_period_days_for_all_time_is_none():
    assert period_days_for("ALL") is None


def test_period_days_for_unknown_label_raises():
    with pytest.raises(KeyError):
        period_days_for("2Y")


def test_period_days_dict_matches_options():
    assert set(PERIOD_DAYS.keys()) == set(PERIOD_OPTIONS)


def test_nav_items_cover_all_four_pages():
    slugs = [item.slug for item in NAV_ITEMS]
    assert slugs == ["overview", "trends", "compare", "records"]


def test_nav_items_have_labels_and_icons():
    for item in NAV_ITEMS:
        assert item.label
        assert item.icon


def test_icons_map_has_no_empty_values():
    assert all(v.strip() for v in ICONS.values())
