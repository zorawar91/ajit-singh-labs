"""
Pure-logic helpers for the Lab Tracker redesign — no Streamlit imports here
on purpose, so this module can be unit-tested directly with pytest instead
of spinning up a Streamlit script run.
"""
from __future__ import annotations
import math
from collections import namedtuple
from datetime import timedelta

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


# ── FI-LAB — Frailty Index (Laboratory) ──────────────────────────────────────
# Howlett 2014. Unlike every other score here, FI-LAB reads the whole panel
# rather than a handful of chosen analytes: it is simply the proportion of
# results sitting outside their own reference range. That makes it a genuine
# whole-organism summary, and it trends over time in a way single-domain
# scores don't.

def filab(observations):
    """
    Fraction of results falling outside their reference range.

    `observations` is an iterable of (value, lo, hi). A parameter is assessable
    when it has a value and at least one bound; parameters with neither bound
    (Weight, ratios with no published range) are excluded from the denominator
    rather than counted as non-deficits, which would dilute the index.

    Returns None when nothing is assessable.
    """
    assessable = 0
    deficits = 0
    for value, lo, hi in observations:
        if value is None:
            continue
        if lo is None and hi is None:
            continue
        assessable += 1
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            deficits += 1
    if assessable == 0:
        return None
    return deficits / assessable


def select_current_observations(rows, as_of, window_days):
    """
    Reduce raw readings to one current observation per parameter.

    `rows` are dicts of {name, lo, hi, date, value}. Keeps each parameter's most
    recent reading at or before `as_of` and no older than `window_days`, so a
    result from a year ago can't freeze the index at a stale value. Parameters
    with no reference bounds are dropped here rather than in filab(), keeping
    the returned list and the assessed count in agreement.
    """
    cutoff = as_of - timedelta(days=window_days)
    latest = {}
    for row in rows:
        if row["value"] is None:
            continue
        if row["lo"] is None and row["hi"] is None:
            continue
        when = row["date"]
        if when > as_of or when < cutoff:
            continue
        seen = latest.get(row["name"])
        if seen is None or when >= seen["date"]:
            latest[row["name"]] = row
    return [(r["value"], r["lo"], r["hi"]) for r in latest.values()]


def filab_band(value):
    """Conventional FI-LAB cutoffs: <0.2 fit · 0.2–0.35 vulnerable · >0.35 frail."""
    if value < 0.2:
        return "fit"
    if value <= 0.35:
        return "vulnerable"
    return "frail"


# ── Calcium ──────────────────────────────────────────────────────────────────

def corrected_calcium(calcium_mgdl, albumin_gdl):
    """
    Payne's albumin-corrected calcium (mg/dL).

    Roughly half of serum calcium is albumin-bound, so hypoalbuminemia makes
    total calcium under-read true (ionised) calcium — hypercalcemia of
    malignancy can hide behind an apparently normal value.
    """
    if calcium_mgdl is None or albumin_gdl is None:
        return None
    return calcium_mgdl + 0.8 * (4.0 - albumin_gdl)


def calcium_band(value):
    """Bands for corrected calcium in mg/dL."""
    if value < 8.5:
        return "hypocalcemia"
    if value <= 10.5:
        return "normal"
    if value <= 12.0:
        return "mild hypercalcemia"
    if value <= 14.0:
        return "moderate hypercalcemia"
    return "severe hypercalcemia"


# ── Tumour lysis syndrome (Cairo-Bishop laboratory criteria) ─────────────────
# Absolute thresholds only. The published definition also accepts a 25% shift
# from a pre-treatment baseline within a −3/+7 day window around chemotherapy;
# this tracker records neither chemo dates nor daily labs, so callers must
# present the result as a pattern screen rather than a formal diagnosis.

TLS_THRESHOLDS = {
    "uric_acid": 8.0,    # mg/dL, >=
    "potassium": 6.0,    # mEq/L, >=
    "phosphorus": 4.5,   # mg/dL, >= (adult threshold)
    "calcium": 7.0,      # mg/dL, <= (use corrected calcium)
}


def tls_criteria_met(uric_acid=None, potassium=None, phosphorus=None, calcium=None):
    """
    Return the Cairo-Bishop laboratory TLS criteria currently met.

    Two or more constitutes laboratory TLS. Missing analytes are skipped, so a
    short list can mean "few criteria met" or "few criteria measurable" —
    callers should say which.
    """
    met = []
    if uric_acid is not None and uric_acid >= TLS_THRESHOLDS["uric_acid"]:
        met.append(f"Uric acid {uric_acid:.1f} ≥ {TLS_THRESHOLDS['uric_acid']} mg/dL")
    if potassium is not None and potassium >= TLS_THRESHOLDS["potassium"]:
        met.append(f"Potassium {potassium:.1f} ≥ {TLS_THRESHOLDS['potassium']} mEq/L")
    if phosphorus is not None and phosphorus >= TLS_THRESHOLDS["phosphorus"]:
        met.append(f"Phosphorus {phosphorus:.1f} ≥ {TLS_THRESHOLDS['phosphorus']} mg/dL")
    if calcium is not None and calcium <= TLS_THRESHOLDS["calcium"]:
        met.append(f"Corrected calcium {calcium:.1f} ≤ {TLS_THRESHOLDS['calcium']} mg/dL")
    return met


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
