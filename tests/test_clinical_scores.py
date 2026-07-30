"""
Tests for the lab-derived clinical scores that need static patient constants
(age / sex / height) on top of the tracked lab values.
"""
import pytest
from labtracker_lib import (
    bmi,
    ideal_body_weight_kg,
    gnri,
    gnri_band,
    cockcroft_gault_crcl,
    ckd_epi_2021_egfr,
    fib4,
    fib4_band,
)


# ── BMI ──────────────────────────────────────────────────────────────────────
def test_bmi_is_weight_over_height_squared():
    assert bmi(54, 168) == pytest.approx(19.13, abs=0.01)


def test_bmi_returns_none_for_zero_height():
    assert bmi(54, 0) is None


def test_bmi_returns_none_for_missing_weight():
    assert bmi(None, 168) is None


# ── Ideal body weight (Devine) ───────────────────────────────────────────────
def test_ideal_body_weight_male_uses_50kg_base():
    # 168 cm = 66.14 in -> 50 + 2.3 * 6.14
    assert ideal_body_weight_kg(168, "Male") == pytest.approx(64.13, abs=0.01)


def test_ideal_body_weight_female_uses_45_5kg_base():
    assert ideal_body_weight_kg(168, "Female") == pytest.approx(59.63, abs=0.01)


def test_ideal_body_weight_is_case_insensitive_on_sex():
    assert ideal_body_weight_kg(168, "male") == ideal_body_weight_kg(168, "MALE")


def test_ideal_body_weight_returns_none_for_unknown_sex():
    assert ideal_body_weight_kg(168, "unspecified") is None


# ── GNRI (Geriatric Nutritional Risk Index) ──────────────────────────────────
def test_gnri_combines_albumin_and_weight_ratio():
    # 14.89 * 3.2 + 41.7 * (54 / 64.126)
    assert gnri(3.2, 54, 168, "Male") == pytest.approx(82.76, abs=0.01)


def test_gnri_caps_weight_ratio_at_one_when_above_ideal():
    # weight 70 > IBW 64.13, so the ratio term is exactly 41.7
    assert gnri(4.0, 70, 168, "Male") == pytest.approx(14.89 * 4.0 + 41.7, abs=0.01)


def test_gnri_returns_none_without_albumin():
    assert gnri(None, 54, 168, "Male") is None


def test_gnri_band_thresholds():
    assert gnri_band(99) == "no risk"
    assert gnri_band(95) == "low risk"
    assert gnri_band(85) == "moderate risk"
    assert gnri_band(80) == "major risk"


# ── Cockcroft-Gault creatinine clearance ─────────────────────────────────────
def test_cockcroft_gault_for_male():
    # ((140 - 65) * 54) / (72 * 0.9)
    assert cockcroft_gault_crcl(65, 54, 0.9, "Male") == pytest.approx(62.5, abs=0.01)


def test_cockcroft_gault_applies_female_correction():
    male = cockcroft_gault_crcl(65, 54, 0.9, "Male")
    female = cockcroft_gault_crcl(65, 54, 0.9, "Female")
    assert female == pytest.approx(male * 0.85, abs=0.01)


def test_cockcroft_gault_returns_none_for_zero_creatinine():
    assert cockcroft_gault_crcl(65, 54, 0, "Male") is None


# ── CKD-EPI 2021 (race-free) ─────────────────────────────────────────────────
def test_ckd_epi_male_at_kappa_boundary():
    # Scr 0.9 == kappa for males, so both power terms collapse to 1
    assert ckd_epi_2021_egfr(0.9, 65, "Male") == pytest.approx(94.78, abs=0.05)


def test_ckd_epi_male_above_kappa_uses_decline_exponent():
    assert ckd_epi_2021_egfr(1.5, 65, "Male") == pytest.approx(51.35, abs=0.05)


def test_ckd_epi_female_applies_sex_multiplier():
    assert ckd_epi_2021_egfr(0.9, 65, "Female") == pytest.approx(70.95, abs=0.05)


def test_ckd_epi_returns_none_for_missing_creatinine():
    assert ckd_epi_2021_egfr(None, 65, "Male") is None


# ── FIB-4 ────────────────────────────────────────────────────────────────────
def test_fib4_combines_age_ast_alt_and_platelets():
    # (65 * 45) / (180 * sqrt(30))
    assert fib4(65, 45, 30, 180) == pytest.approx(2.967, abs=0.01)


def test_fib4_returns_none_for_zero_platelets():
    assert fib4(65, 45, 30, 0) is None


def test_fib4_returns_none_for_zero_alt():
    assert fib4(65, 45, 0, 180) is None


def test_fib4_band_uses_standard_cutoffs_under_65():
    assert fib4_band(1.2, 50) == "advanced fibrosis unlikely"
    assert fib4_band(2.0, 50) == "indeterminate"
    assert fib4_band(4.0, 50) == "advanced fibrosis likely"


def test_fib4_band_raises_lower_cutoff_at_65_and_over():
    # The 1.45 cutoff over-calls fibrosis in older patients; 2.0 is the
    # recommended lower bound from age 65.
    assert fib4_band(1.8, 65) == "advanced fibrosis unlikely"
    assert fib4_band(1.8, 50) == "indeterminate"
