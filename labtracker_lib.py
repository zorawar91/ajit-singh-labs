"""
Pure-logic helpers for the Lab Tracker redesign — no Streamlit imports here
on purpose, so this module can be unit-tested directly with pytest instead
of spinning up a Streamlit script run.
"""
from __future__ import annotations
import math
from collections import namedtuple

# ── Unified time-range control ───────────────────────────────────────────────
# Replaces the 3 separate "Period" selectboxes (Trends / Compare Trends /
# Full Table) that each reinvented their own bucket set. One shared control,
# one shared bucket set, used everywhere a chart or table needs a date cutoff.
PERIOD_OPTIONS = ["3M", "6M", "9M", "1Y", "ALL"]
PERIOD_DAYS = {
    "3M": 90,
    "6M": 182,
    "9M": 273,
    "1Y": 365,
    "ALL": None,
}


def period_days_for(label: str) -> int | None:
    """Return the day-count cutoff for a period bucket label, or None for 'ALL'."""
    return PERIOD_DAYS[label]


# ── Body-size derived scores ─────────────────────────────────────────────────
# These need static patient constants (sex, height) that aren't lab readings,
# so they live in secrets rather than the readings table. Every function here
# returns None on missing/degenerate input — callers treat None as "can't
# compute" and skip the insight rather than showing a wrong number.

def bmi(weight_kg, height_cm):
    """Body Mass Index in kg/m²."""
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def ideal_body_weight_kg(height_cm, sex):
    """Devine (1974) ideal body weight — the denominator GNRI expects."""
    if not height_cm or not sex:
        return None
    base = {"male": 50.0, "female": 45.5}.get(str(sex).strip().lower())
    if base is None:
        return None
    inches_over_five_feet = (height_cm / 2.54) - 60
    return base + 2.3 * inches_over_five_feet


def gnri(albumin_gdl, weight_kg, height_cm, sex):
    """
    Geriatric Nutritional Risk Index (Bouillanne 2005).

    GNRI = 14.89 × albumin(g/dL) + 41.7 × (weight / ideal body weight)

    The weight ratio is capped at 1 — being above ideal weight doesn't earn
    extra nutritional credit.
    """
    if not albumin_gdl or not weight_kg:
        return None
    ibw = ideal_body_weight_kg(height_cm, sex)
    if not ibw or ibw <= 0:
        return None
    ratio = min(weight_kg / ibw, 1.0)
    return 14.89 * albumin_gdl + 41.7 * ratio


def gnri_band(value):
    """GNRI risk band. >98 no risk · 92–98 low · 82–92 moderate · <82 major."""
    if value > 98:
        return "no risk"
    if value >= 92:
        return "low risk"
    if value >= 82:
        return "moderate risk"
    return "major risk"


# ── Renal function ───────────────────────────────────────────────────────────
# Two different estimates on purpose. Cockcroft-Gault is what chemotherapy
# dosing nomograms (carboplatin AUC, capecitabine) are built on; CKD-EPI is
# the nephrology standard for staging CKD. They disagree in low-body-weight
# patients, and that disagreement is itself worth showing.

def cockcroft_gault_crcl(age_years, weight_kg, creatinine_mgdl, sex):
    """Cockcroft-Gault creatinine clearance in mL/min (not BSA-normalised)."""
    if not age_years or not weight_kg or not creatinine_mgdl:
        return None
    crcl = ((140 - age_years) * weight_kg) / (72 * creatinine_mgdl)
    if str(sex).strip().lower() == "female":
        crcl *= 0.85
    return crcl


def ckd_epi_2021_egfr(creatinine_mgdl, age_years, sex):
    """CKD-EPI 2021 race-free eGFR in mL/min/1.73m²."""
    if not creatinine_mgdl or not age_years:
        return None
    s = str(sex).strip().lower()
    if s == "female":
        kappa, alpha, sex_factor = 0.7, -0.241, 1.012
    elif s == "male":
        kappa, alpha, sex_factor = 0.9, -0.302, 1.0
    else:
        return None
    ratio = creatinine_mgdl / kappa
    return (
        142
        * (min(ratio, 1.0) ** alpha)
        * (max(ratio, 1.0) ** -1.200)
        * (0.9938 ** age_years)
        * sex_factor
    )


# ── Liver fibrosis ───────────────────────────────────────────────────────────

def fib4(age_years, ast, alt, platelets_k):
    """
    FIB-4 index = (age × AST) / (platelets[10⁹/L] × √ALT).

    Platelets are passed in thou/µL, which is numerically identical to 10⁹/L.
    """
    if not age_years or not ast or not alt or not platelets_k:
        return None
    if alt <= 0 or platelets_k <= 0:
        return None
    return (age_years * ast) / (platelets_k * math.sqrt(alt))


def fib4_band(value, age_years):
    """
    FIB-4 interpretation. The conventional 1.45 lower cutoff has poor
    specificity from age 65 onward, where 2.0 is recommended instead.
    """
    lower = 2.0 if age_years and age_years >= 65 else 1.45
    if value < lower:
        return "advanced fibrosis unlikely"
    if value <= 3.25:
        return "indeterminate"
    return "advanced fibrosis likely"


# ── Sidebar navigation (replaces st.tabs) ────────────────────────────────────
NavItem = namedtuple("NavItem", ["slug", "label", "icon"])
NAV_ITEMS = [
    NavItem("overview", "Overview", "📊"),
    NavItem("trends", "Trends Browser", "📈"),
    NavItem("compare", "Compare Data", "🗂️"),
    NavItem("records", "Full Records", "📋"),
]

# ── Icon translation (lucide icon name -> emoji) ─────────────────────────────
# The Superdesign mockups use <iconify-icon icon="lucide:..."> which needs a
# <script> tag to register the custom element. Streamlit's st.markdown strips
# <script> tags for security, so every icon becomes an emoji instead — this
# also matches the app's existing convention (🔒 on the auth gate, 🧪 in the
# page icon, etc.)
ICONS = {
    "lucide:test-tube-2": "🧪",
    "lucide:layout-dashboard": "📊",
    "lucide:trending-up": "📈",
    "lucide:layers": "🗂️",
    "lucide:table": "📋",
    "lucide:log-out": "🔒",
    "lucide:alert-circle": "⚠️",
    "lucide:activity": "🫀",
    "lucide:microscope": "🔬",
    "lucide:utensils": "🍽️",
    "lucide:check-circle-2": "✅",
    "lucide:alert-triangle": "⚠️",
    "lucide:maximize-2": "⛶",
    "lucide:chevron-down": "▾",
    "lucide:info": "ℹ️",
    "lucide:x": "✕",
    "lucide:plus": "➕",
    "lucide:download": "⬇️",
    "lucide:search": "🔍",
    "lucide:arrow-down": "↓",
    "lucide:calendar": "📅",
}
