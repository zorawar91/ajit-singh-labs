"""
Pure-logic helpers for the Lab Tracker redesign — no Streamlit imports here
on purpose, so this module can be unit-tested directly with pytest instead
of spinning up a Streamlit script run.
"""
from __future__ import annotations
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
