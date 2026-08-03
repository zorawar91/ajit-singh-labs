"""
Tests for whole-panel health indices and the electrolyte safety screens —
scores that need no static patient constants, only the readings themselves.
"""
from datetime import date

import pytest
from labtracker_lib import (
    filab,
    filab_band,
    select_current_observations,
    corrected_calcium,
    calcium_band,
    tls_criteria_met,
    TLS_THRESHOLDS,
)


# ── FI-LAB (Frailty Index — Laboratory) ──────────────────────────────────────
# An observation is (value, lo, hi). A parameter is a "deficit" when it falls
# outside whichever bounds it defines.

def test_filab_is_fraction_of_out_of_range_results():
    obs = [
        (5.0, 1.0, 10.0),   # in range
        (5.0, 1.0, 10.0),   # in range
        (5.0, 1.0, 10.0),   # in range
        (99.0, 1.0, 10.0),  # deficit
    ]
    assert filab(obs) == pytest.approx(0.25)


def test_filab_is_zero_when_everything_in_range():
    assert filab([(5.0, 1.0, 10.0), (2.0, 1.0, 10.0)]) == pytest.approx(0.0)


def test_filab_is_one_when_everything_out_of_range():
    assert filab([(0.5, 1.0, 10.0), (50.0, 1.0, 10.0)]) == pytest.approx(1.0)


def test_filab_counts_low_values_as_deficits():
    assert filab([(0.5, 1.0, 10.0)]) == pytest.approx(1.0)


def test_filab_handles_one_sided_bounds():
    # eGFR-style: only a lower bound. Tumour markers: only an upper bound.
    assert filab([(30.0, 60.0, None)]) == pytest.approx(1.0)
    assert filab([(90.0, 60.0, None)]) == pytest.approx(0.0)
    assert filab([(500.0, None, 37.0)]) == pytest.approx(1.0)


def test_filab_excludes_parameters_with_no_reference_range():
    # Weight has no reference range — it must not dilute the denominator.
    obs = [(99.0, 1.0, 10.0), (54.0, None, None)]
    assert filab(obs) == pytest.approx(1.0)


def test_filab_excludes_missing_values():
    obs = [(99.0, 1.0, 10.0), (None, 1.0, 10.0)]
    assert filab(obs) == pytest.approx(1.0)


def test_filab_returns_none_when_nothing_assessable():
    assert filab([]) is None
    assert filab([(54.0, None, None)]) is None


def test_filab_band_thresholds():
    assert filab_band(0.10) == "fit"
    assert filab_band(0.30) == "vulnerable"
    assert filab_band(0.50) == "frail"


# ── Selecting which readings FI-LAB sees ─────────────────────────────────────
# rows are {name, lo, hi, date, value}; the selector keeps each parameter's
# most recent reading at or before `as_of`, within `window_days`.

def _row(name, value, day, lo=1.0, hi=10.0):
    return {"name": name, "lo": lo, "hi": hi, "date": date(2026, 7, day), "value": value}


def test_selector_keeps_only_the_latest_reading_per_parameter():
    rows = [_row("ALT", 5.0, 1), _row("ALT", 99.0, 20)]
    assert select_current_observations(rows, date(2026, 7, 30), 90) == [(99.0, 1.0, 10.0)]


def test_selector_ignores_readings_after_the_as_of_date():
    rows = [_row("ALT", 5.0, 1), _row("ALT", 99.0, 20)]
    assert select_current_observations(rows, date(2026, 7, 10), 90) == [(5.0, 1.0, 10.0)]


def test_selector_drops_readings_older_than_the_window():
    rows = [{"name": "ALT", "lo": 1.0, "hi": 10.0, "date": date(2025, 1, 1), "value": 5.0}]
    assert select_current_observations(rows, date(2026, 7, 30), 90) == []


def test_selector_includes_a_reading_exactly_on_the_window_edge():
    rows = [{"name": "ALT", "lo": 1.0, "hi": 10.0, "date": date(2026, 5, 1), "value": 5.0}]
    assert select_current_observations(rows, date(2026, 7, 30), 90) == [(5.0, 1.0, 10.0)]


def test_selector_skips_parameters_with_no_reference_bounds():
    rows = [_row("Weight", 54.0, 20, lo=None, hi=None)]
    assert select_current_observations(rows, date(2026, 7, 30), 90) == []


def test_selector_skips_missing_values():
    rows = [_row("ALT", None, 20)]
    assert select_current_observations(rows, date(2026, 7, 30), 90) == []


def test_selector_returns_one_observation_per_parameter():
    rows = [_row("ALT", 5.0, 20), _row("AST", 7.0, 20), _row("ALT", 6.0, 21)]
    assert len(select_current_observations(rows, date(2026, 7, 30), 90)) == 2


# ── Albumin-corrected calcium (Payne) ────────────────────────────────────────
def test_corrected_calcium_raises_value_when_albumin_is_low():
    # 9.0 + 0.8 * (4.0 - 2.5)
    assert corrected_calcium(9.0, 2.5) == pytest.approx(10.2, abs=0.01)


def test_corrected_calcium_is_unchanged_at_reference_albumin():
    assert corrected_calcium(9.0, 4.0) == pytest.approx(9.0, abs=0.01)


def test_corrected_calcium_lowers_value_when_albumin_is_high():
    assert corrected_calcium(9.0, 5.0) == pytest.approx(8.2, abs=0.01)


def test_corrected_calcium_returns_none_without_albumin():
    assert corrected_calcium(9.0, None) is None


def test_calcium_band_thresholds():
    assert calcium_band(8.0) == "hypocalcemia"
    assert calcium_band(9.5) == "normal"
    assert calcium_band(11.0) == "mild hypercalcemia"
    assert calcium_band(13.0) == "moderate hypercalcemia"
    assert calcium_band(15.0) == "severe hypercalcemia"


# ── Cairo-Bishop laboratory TLS criteria ─────────────────────────────────────
def test_tls_no_criteria_met_on_normal_values():
    assert tls_criteria_met(uric_acid=5.0, potassium=4.0, phosphorus=3.5, calcium=9.0) == []


def test_tls_flags_high_uric_acid():
    met = tls_criteria_met(uric_acid=8.5, potassium=4.0, phosphorus=3.5, calcium=9.0)
    assert len(met) == 1
    assert "Uric acid" in met[0]


def test_tls_flags_each_criterion_independently():
    assert len(tls_criteria_met(uric_acid=5.0, potassium=6.2, phosphorus=3.5, calcium=9.0)) == 1
    assert len(tls_criteria_met(uric_acid=5.0, potassium=4.0, phosphorus=4.8, calcium=9.0)) == 1
    assert len(tls_criteria_met(uric_acid=5.0, potassium=4.0, phosphorus=3.5, calcium=6.5)) == 1


def test_tls_two_criteria_constitute_laboratory_tls():
    met = tls_criteria_met(uric_acid=8.5, potassium=6.2, phosphorus=3.5, calcium=9.0)
    assert len(met) == 2


def test_tls_ignores_missing_values():
    met = tls_criteria_met(uric_acid=None, potassium=None, phosphorus=None, calcium=None)
    assert met == []


def test_tls_thresholds_are_at_the_boundary_not_past_it():
    # Cairo-Bishop uses >= for uric acid / potassium / phosphorus and <= for calcium
    assert len(tls_criteria_met(uric_acid=TLS_THRESHOLDS["uric_acid"], potassium=4.0,
                                phosphorus=3.5, calcium=9.0)) == 1
    assert len(tls_criteria_met(uric_acid=5.0, potassium=4.0, phosphorus=3.5,
                                calcium=TLS_THRESHOLDS["calcium"])) == 1
