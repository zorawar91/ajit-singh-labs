# Precision Clinical Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `app.py`'s visual layer to match the approved "Precision Clinical" Superdesign drafts (dark navy header, left sidebar nav, unified 3M/6M/9M/1Y/ALL time-range control, Family/Clinical view toggle, Plus Jakarta Sans + Outfit + JetBrains Mono typography) while keeping every existing data query, scoring function, and the password auth gate working exactly as before.

**Architecture:** Single-file Streamlit app stays single-file (matches this repo's existing convention — no `tests/`, no package structure). New pure-logic helpers (period-bucket math, nav config, cluster grouping) are added as plain functions with no Streamlit calls, so they're unit-testable with plain pytest. All page rendering stays Streamlit-native: `st.tabs` is replaced by `st.sidebar` + `st.button`-based nav (tracked in `st.session_state["nav_page"]`), the dark header bar is a `st.container(key="app_header")` (Streamlit ≥1.31 gives every `key=`'d container a stable `st-key-<key>` CSS class, which is how we style it dark) wrapping real widgets — `st.segmented_control` (native since Streamlit 1.36, already pinned in `requirements.txt`) for both the period control and the Family/Clinical toggle. Iconify `<iconify-icon>` tags in the mockups require a `<script>` tag to register the custom element; Streamlit's `st.markdown(unsafe_allow_html=True)` strips `<script>` tags, so every icon is translated to an emoji instead (matching this app's existing convention of 🔒/🧪/📈 etc. — see Task 1's icon map). Google Fonts `<link>` tags are NOT stripped and load normally via `st.markdown`.

**Tech Stack:** Streamlit ≥1.36, psycopg[binary] ≥3.2, pandas ≥2.2, plotly ≥5.22 (all already pinned — no new dependencies).

## Global Constraints

- Never introduce a new Python dependency — the four packages in `requirements.txt` are sufficient for everything in this plan.
- Never touch `.streamlit/secrets.toml` or any real patient data — every code example in this plan uses fictional placeholder values, matching the Superdesign drafts.
- Keep every `insight_*()` / `build_watch()` scoring function's signature and return contract (`(icon, color_class, html_text)` tuples) exactly as-is — this plan re-groups their OUTPUT into new card layouts, it does not rewrite the scoring logic.
- Keep the password gate (`check_password()`, `app.py:222-245`) and `load_data()` (`app.py:250-274`) untouched — only their surrounding chrome changes.
- The Full Records page's table styling is intentionally left at its last-approved state (plain white table, `slate-200` header, only horizontal row separators, green/red value text, generous `py-4` row padding, no vertical borders, no monospace) — the user said to revisit its polish later; don't over-invest further this round.
- Every new hex color below is copied verbatim from the approved Superdesign draft HTML (`/tmp/overview.html`, `/tmp/trends.html`, `/tmp/compare.html`, `/tmp/fullrecords.html` fetched via `get-design` during design review) — don't invent new ones.

---

## File Structure

All changes are in one file:

- **Modify:** `app.py` — every section below names exact line ranges from the CURRENT file (2063 lines) being replaced or added to.
- **Create:** `labtracker_lib.py` — new, small, Streamlit-free module holding the pure-logic pieces (period bucket math, nav config, cluster grouping order) so they're unit-testable without spinning up Streamlit. `app.py` imports from it.
- **Create:** `tests/test_labtracker_lib.py` — pytest unit tests for `labtracker_lib.py`.
- **Create:** `tests/__init__.py` — empty, so pytest can discover the package.
- **Modify:** `.streamlit/config.toml` — `secondaryBackgroundColor` updated to match the new page background.
- **Modify:** `requirements.txt` — add `pytest>=8.0` (dev-only test dependency; everything else is unchanged).

---

### Task 1: `labtracker_lib.py` — period buckets, nav config, icon map (pure logic, TDD)

**Files:**
- Create: `labtracker_lib.py`
- Test: `tests/test_labtracker_lib.py`
- Create: `tests/__init__.py` (empty file)

**Interfaces:**
- Produces: `PERIOD_OPTIONS: list[str]`, `PERIOD_DAYS: dict[str, int | None]`, `period_days_for(label: str) -> int | None`, `NAV_ITEMS: list[NavItem]` (namedtuple: `slug, label, icon`), `ICONS: dict[str, str]` (lucide-icon-name → emoji)
- Consumed by: Task 2 (header), Task 3 (sidebar nav), Task 4 (chart period filtering), Task 6/7/8 (page filters)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_labtracker_lib.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs && python3 -m pytest tests/test_labtracker_lib.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'labtracker_lib'`

- [ ] **Step 3: Write the implementation**

```python
# labtracker_lib.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs && python3 -m pytest tests/test_labtracker_lib.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add labtracker_lib.py tests/test_labtracker_lib.py tests/__init__.py
git commit -m "feat: add pure-logic helpers for unified period control and sidebar nav"
```

---

### Task 2: Theme foundation — fonts, colors, page config

**Files:**
- Modify: `app.py:1-217` (imports, `PARAM_INFO`, page config, inline stylesheet)
- Modify: `.streamlit/config.toml`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing new yet (this task only replaces the stylesheet and imports)
- Produces: the `<style>` block every later task's markup relies on (`.clinical-card`, `.pill-*`, `.font-mono-lab`, `h1-h4` Outfit rule, `.val-normal`/`.val-alert`, `.simple-table`)

- [ ] **Step 1: Add `pytest` to `requirements.txt`**

```
streamlit>=1.36
psycopg[binary]>=3.2
pandas>=2.2
plotly>=5.22
pytest>=8.0
```

- [ ] **Step 2: Update `.streamlit/config.toml`**

The new design's page background is `#f8fafc` throughout (vs. the old `#f5f7fb`) — match it so Streamlit's own chrome (e.g. the sidebar) doesn't clash.

```toml
[theme]
base = "light"
primaryColor = "#2563eb"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f8fafc"
textColor = "#0f172a"
font = "sans serif"

[browser]
gatherUsageStats = false
```

- [ ] **Step 3: Replace the inline stylesheet at `app.py:140-217`**

Replace the entire `st.markdown("""<style>...</style>""", unsafe_allow_html=True)` block (currently `app.py:140-217`) with the block below. This keeps every existing class the rest of the file still needs (`.pill-*`, `.alert`, `.param-desc`, `.param-meta`, `.trend-line`) and adds the new ones needed by later tasks.

```python
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
  html, .stApp { background-color: #f8fafc; }
  body, [class*="css"] { font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; }
  h1, h2, h3, h4 { font-family: 'Outfit', sans-serif; letter-spacing: -0.02em; }
  .font-mono-lab { font-family: 'JetBrains Mono', monospace; }

  .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1500px; }

  /* Every bordered Streamlit container (st.container(border=True)) becomes
     a "clinical-card": white surface, light border, small radius+shadow. */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05) !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
  }
  div[data-testid="column"] { display: flex !important; flex-direction: column !important; }
  div[data-testid="column"] > div { flex: 1 1 auto; }
  div[data-testid="column"] > div > div[data-testid="stVerticalBlock"] { height: 100%; }

  .param-desc { min-height: 2.8em; font-size: 11px; color: #475569; font-style: italic; line-height: 1.4; margin-top: 2px; }
  .param-meta { min-height: 1.2em; font-size: 11px; color: #64748b; margin-top: 4px; }
  .trend-line { min-height: 1.4em; font-size: 12px; color: #475569; margin-top: 4px; }
  .trend-line .up   { color: #b91c1c; font-weight: 700; }
  .trend-line .down { color: #15803d; font-weight: 700; }
  .trend-line .flat { color: #64748b; font-weight: 700; }

  .pill-high  { background: #fee2e2; color: #b91c1c; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase; border: 1px solid #ef4444; }
  .pill-low   { background: #fef3c7; color: #b45309; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase; border: 1px solid #f59e0b; }
  .pill-normal{ background: #dcfce7; color: #15803d; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase; border: 1px solid #22c55e; }

  div[data-testid="stMetricValue"] { font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  div[data-testid="stMetricDelta"] { font-weight: 700; font-size: 13px; }

  .param-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 4px; }
  .param-name { font-weight: 700; font-size: 14px; color: #0f172a; }

  .alert {
    background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; font-size: 13px;
  }
  .alert .t { font-weight: 800; color: #991b1b; margin-bottom: 4px; }
  .alert .d { line-height: 1.7; }
  .alert .d b { color: #b91c1c; }

  /* Full Records table — plain, spacious, minimal color coding (approved
     in the last design round: no vertical borders, only row separators). */
  .simple-table { width: 100%; border-collapse: collapse; }
  .simple-table th {
    padding: 16px 24px; font-size: 14px; font-weight: 600; color: #334155;
    background: rgba(248,250,252,0.8); text-align: left; border-bottom: 1px solid #e2e8f0;
  }
  .simple-table td {
    padding: 16px 24px; font-size: 14px; border-bottom: 1px solid #f1f5f9;
    color: #0f172a; line-height: 1.6;
  }
  .simple-table tr:nth-child(odd) { background: rgba(248,250,252,0.3); }
  .val-normal { color: #059669; font-weight: 600; }
  .val-alert  { color: #dc2626; font-weight: 600; }

  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
```

- [ ] **Step 4: Verify the page still loads**

Run: `cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs && streamlit run app.py --server.headless true &`
Then check `curl -s http://localhost:8501 | head -c 500` returns HTML (not an error trace), then stop the server: `kill %1`.
Expected: no Python traceback in the terminal Streamlit was launched from.

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py .streamlit/config.toml requirements.txt
git commit -m "feat: apply Precision Clinical theme tokens (fonts, colors, card styling)"
```

---

### Task 3: Persistent dark header — brand, unified period control, view toggle, lock

**Files:**
- Modify: `app.py:1` (add `import labtracker_lib as lib` near the top, alongside existing imports)
- Modify: `app.py:222-245` (`check_password`, unchanged logic, called from the new header flow)
- Modify: `app.py:350-401` (replace old header/patient-banner render call site — the new header replaces the plain `st.markdown(f"## {APP_TITLE} — {PATIENT_NAME}")` + `st.caption(...)`; the patient banner itself moves into Task 5's Overview page)

**Interfaces:**
- Consumes: `lib.PERIOD_OPTIONS`, `lib.period_days_for` (Task 1)
- Produces: `render_header() -> None` (renders the dark bar); reads/writes `st.session_state["global_period"]` (str, one of `PERIOD_OPTIONS`) and `st.session_state["view_mode"]` (str, `"Family"` or `"Clinical View"`) — every later task reads these two session_state keys directly, no parameters needed.

- [ ] **Step 1: Add the import**

At the top of `app.py`, alongside the existing imports (`app.py:16-25`), add:

```python
import labtracker_lib as lib
```

- [ ] **Step 2: Write `render_header()`**

Insert this function right after `check_password()` (i.e. after `app.py:245`, before `load_data()`):

```python
def render_header():
    """Persistent dark header: brand, unified period control, Family/Clinical
    toggle, and Lock. Uses st.container(key=...) so the wrapping element gets
    a stable `st-key-app_header` CSS class we can style dark (see the CSS
    block below) — this is the standard way to give a Streamlit container a
    targetable class without relying on brittle structural selectors."""
    st.markdown("""
    <style>
      .st-key-app_header {
        background: #0f172a; border-radius: 10px; padding: 10px 20px; margin-bottom: 20px;
      }
      .st-key-app_header * { color: #f1f5f9 !important; }
      .st-key-app_header [data-testid="stMarkdownContainer"] p { margin: 0; }
      .st-key-app_header button {
        background: #1e293b !important; border-color: #334155 !important;
      }
      .st-key-app_header button:hover { background: #2563eb !important; border-color: #2563eb !important; }
    </style>
    """, unsafe_allow_html=True)

    st.session_state.setdefault("global_period", "ALL")
    st.session_state.setdefault("view_mode", "Clinical View")

    with st.container(key="app_header"):
        col_brand, col_period, col_view, col_lock = st.columns([4, 3, 2, 1], vertical_alignment="center")
        with col_brand:
            st.markdown(
                f"""<div style="display:flex; align-items:center; gap:10px;">
                  <span style="font-size:22px;">{lib.ICONS['lucide:test-tube-2']}</span>
                  <div>
                    <div style="font-size:13px; font-weight:700; letter-spacing:.02em; text-transform:uppercase;">{APP_TITLE}</div>
                    <div style="font-size:10px; opacity:.7;">Clinical Monitoring • {PATIENT_NAME}</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
        with col_period:
            st.segmented_control(
                "Period", lib.PERIOD_OPTIONS, default="ALL",
                key="global_period", label_visibility="collapsed",
            )
        with col_view:
            st.segmented_control(
                "View", ["Family", "Clinical View"], default="Clinical View",
                key="view_mode", label_visibility="collapsed",
            )
        with col_lock:
            if st.button(f"{lib.ICONS['lucide:log-out']} Lock", key="lock_btn", use_container_width=True):
                st.session_state["authenticated"] = False
                st.rerun()
```

- [ ] **Step 3: Call it from the entry point**

Replace the old plain header (currently `app.py:353-354`):

```python
st.markdown(f"## {APP_TITLE} — {PATIENT_NAME}")
st.caption(meta.get("subtitle", ""))
```

with:

```python
render_header()
```

(The old plain-text header/caption is superseded by the header's brand block; `meta.get("subtitle", "")` is still used later, on the Overview page's patient banner — see Task 5.)

- [ ] **Step 4: Manual check**

Run `streamlit run app.py`, log in, and confirm: a dark rounded bar appears with the 🧪 title on the left, a 3M/6M/9M/1Y/ALL segmented control, a Family/Clinical View segmented control (defaulting to "Clinical View"), and a "🔒 Lock" button that logs you out when clicked.

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: add persistent header with unified period control and view toggle"
```

---

### Task 4: Sidebar navigation — replace `st.tabs` with `st.sidebar` button nav

**Files:**
- Modify: `app.py:1643-1645` (remove the `st.tabs(...)` call entirely; replaced by sidebar nav below)
- Modify: `app.py:102-107` (`st.set_page_config`: change `initial_sidebar_state` from unset/default to `"expanded"`)

**Interfaces:**
- Consumes: `lib.NAV_ITEMS` (Task 1)
- Produces: `render_sidebar_nav() -> str` (returns the active page slug: `"overview" | "trends" | "compare" | "records"`); reads/writes `st.session_state["nav_page"]`.

- [ ] **Step 1: Set the sidebar to expanded by default**

In `st.set_page_config(...)` (`app.py:102-107`), change:

```python
st.set_page_config(
    page_title=f"{APP_TITLE} — {PATIENT_NAME}",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)
```

(This is the only change to that call — it currently already has all 4 keyword args, just flip `initial_sidebar_state` to `"expanded"`.)

- [ ] **Step 2: Write `render_sidebar_nav()`**

Insert right after `render_header()` (Task 3):

```python
def render_sidebar_nav() -> str:
    """Left sidebar nav replacing the old 5-tab bar. Buttons (not st.radio)
    because each button's active/inactive background is set with an exact
    hex value we already know in Python — no brittle :checked CSS needed."""
    st.session_state.setdefault("nav_page", "overview")

    with st.sidebar:
        st.markdown("""
        <style>
          [data-testid="stSidebar"] button {
            justify-content: flex-start !important; text-align: left !important;
            border: none !important; background: transparent !important;
            font-weight: 500 !important; padding: 10px 12px !important;
          }
          [data-testid="stSidebar"] button:hover { background: #f8fafc !important; }
        </style>
        """, unsafe_allow_html=True)

        for item in lib.NAV_ITEMS:
            is_active = st.session_state["nav_page"] == item.slug
            if is_active:
                st.markdown(f"""
                <style>
                .st-key-nav_{item.slug} button {{
                  background: #eff6ff !important; color: #2563eb !important;
                  border-right: 3px solid #2563eb !important; font-weight: 600 !important;
                }}
                </style>
                """, unsafe_allow_html=True)
            if st.button(f"{item.icon}  {item.label}", key=f"nav_{item.slug}", use_container_width=True):
                st.session_state["nav_page"] = item.slug
                st.rerun()

        st.markdown("---")
        st.markdown("""
        <div style="background:#f8fafc; border-radius:8px; padding:12px;">
          <div style="font-size:10px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px;">Alert Thresholds</div>
          <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:6px;">
            <span style="color:#64748b;">Platelets</span><span style="font-weight:700; color:#dc2626;">&lt; 50k</span>
          </div>
          <div style="display:flex; justify-content:space-between; font-size:11px;">
            <span style="color:#64748b;">Neutrophils</span><span style="font-weight:700; color:#dc2626;">&lt; 0.5k</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    return st.session_state["nav_page"]
```

These threshold values (`< 50k` platelets, `< 0.5k` neutrophils) are copied from the existing hardcoded critical-alert thresholds already in `build_alerts()` (`app.py:420,422`: `val < 50` for Platelet Count, `val < 0.5` for Absolute Neutrophil Count) — this panel is a read-only restatement of logic that already exists, not new business logic.

- [ ] **Step 3: Replace the tab dispatch**

Replace `app.py:1643-1645`:

```python
tab_overview, tab_trends, tab_overlay, tab_compare, tab_table = st.tabs(
    ["Overview", "Trends", "Compare Trends", "Compare Dates", "Full Table"]
)
```

with:

```python
active_page = render_sidebar_nav()
```

The five `with tab_xxx:` blocks that follow (`app.py:1648` onward) are restructured into plain `if active_page == "...":` blocks in Tasks 5-8 — don't leave the old `with tab_overview:` wrapper in place once those tasks land.

- [ ] **Step 4: Manual check**

Run the app, confirm the sidebar shows 4 buttons (📊 Overview, 📈 Trends Browser, 🗂️ Compare Data, 📋 Full Records) with 📊 Overview visibly highlighted (light blue background, blue text, blue right border) by default, and the "Alert Thresholds" box below them.

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: replace tab bar with sidebar navigation"
```

---

### Task 5: Re-theme `render_chart` / `_build_figure` and wire the global period control

**Files:**
- Modify: `app.py:1503-1549` (`_build_figure`) — font family only, no structural change
- Modify: `app.py:1581-1637` (`render_chart`) — drop the `period_days` parameter in favor of reading the global control, keep an optional override for callers that still want a fixed window

**Interfaces:**
- Consumes: `st.session_state["global_period"]` (Task 3), `lib.period_days_for` (Task 1)
- Produces: `render_chart(name, key_prefix="chart", period_days=None)` — `period_days=None` now means "use the global header control", not "no filter" (that's the behavior change: previously `None` meant all-time; now all-time is reached by the control being set to `"ALL"`, which resolves to `None` via `lib.period_days_for`).

- [ ] **Step 1: Update `_build_figure`'s font**

In `_build_figure` (`app.py:1503-1549`), change the `fig.update_layout(...)` call (`app.py:1540-1548`) — only the `font=dict(...)` line changes:

```python
    fig.update_layout(
        xaxis_title=None, yaxis_title=unit or None,
        margin=dict(l=10, r=20, t=20, b=10), height=height,
        showlegend=False, hovermode="x unified",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=12, color="#0f172a", family="Plus Jakarta Sans, -apple-system, sans-serif"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11), nticks=8),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=11), title_font=dict(size=12)),
    )
```

Everything else in `_build_figure` (the line color `#2563eb`, the red/amber/blue point coloring, the green reference-band shading) is UNCHANGED — it already matches the new design's chart colors exactly (confirmed against the SVG mockup paths in the approved drafts).

- [ ] **Step 2: Update `render_chart` to default to the global period**

Replace the signature and the period-filtering block at the top of `render_chart` (`app.py:1581-1589`):

```python
def render_chart(name, key_prefix="chart", period_days=None):
    if not (params_df["name"] == name).any():
        st.info(f"Parameter '{name}' not found")
        return
    p_row = params_df[params_df["name"] == name].iloc[0]
    df = get_readings(name)
    effective_period_days = period_days if period_days is not None else lib.period_days_for(
        st.session_state.get("global_period", "ALL")
    )
    if effective_period_days is not None and not df.empty:
        cutoff = max(df["test_date"]) - pd.Timedelta(days=effective_period_days)
        df = df[df["test_date"] >= cutoff]
```

The rest of `render_chart` (`app.py:1590-1637`) is unchanged — it already just uses `df` from this point on.

- [ ] **Step 3: Add a regression test for the wiring**

The pure logic being tested here is "which cutoff does a given global-period value produce" — already covered by `test_labtracker_lib.py`'s `period_days_for` tests (Task 1). No new test needed for this task; it's a direct call-site wiring change with no new branching logic of its own. (Documented here so a reviewer doesn't wonder why Task 5 has no new test file — the logic under test already has coverage.)

- [ ] **Step 4: Manual check**

Run the app, go to Overview's "Key Trends" section (or Trends Browser once Task 7 lands), change the header's period control from ALL to 3M, and confirm the charts' x-axis range visibly shrinks to the last ~90 days.

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: wire chart rendering to the unified header period control"
```

---

### Task 6: Overview page rebuild

**Files:**
- Modify: `app.py:350-433` (old header/patient-banner/alert render — folds into the new Overview page body)
- Modify: `app.py:1648-1803` (old `with tab_overview:` body — replaced entirely)

**Interfaces:**
- Consumes: `active_page` (Task 4), `st.session_state["view_mode"]` (Task 3), existing `build_watch()`, `insight_albi()`, `insight_meldna()`, `insight_bili_fraction()`, `insight_mgps()`, `insight_sii()`, `insight_ca199_trajectory()`, `insight_pni()`, `insight_streaks()`, `insight_cachexia()`, `insight_velocity()` (all unchanged, `app.py:439-1499`)
- Produces: the Overview page body, gated by `active_page == "overview"`

**Design decision (documented, not a silent deviation):** the mockup's "Clinical Prognostic Panels" cluster cards show bespoke one-line score chips (e.g. "ALBI Score -2.85 (G1)"). The real `insight_*()` functions return pre-formatted narrative HTML strings (e.g. `"<b>ALBI: Grade 1 (best...)</b> — score -2.85..."`), not bare (score, band) tuples — rewriting all 14 scoring functions' return contract to split narrative from raw score is a much bigger, riskier change than this redesign asked for. Instead, each cluster card shows up to 3 of the existing narrative lines, grouped by theme — same clustering the design calls for, without touching the scoring functions.

- [ ] **Step 1: Write `_cluster_insights()` and `_render_cluster_card()`**

Insert after `render_sidebar_nav()`:

```python
def _cluster_insights():
    """Group existing insight_*() output into the 4 themed clusters the
    Precision Clinical design calls for. Returns a dict of
    {cluster_title: (icon, [(icon, color_class, text), ...])}."""
    liver = (insight_albi() + insight_meldna() + insight_bili_fraction())[:3]
    tumor = (insight_mgps() + insight_sii() + insight_ca199_trajectory())[:3]
    nutrition = (insight_pni() + insight_cachexia())[:3]
    trajectory = (insight_streaks() + insight_velocity())[:3]
    return {
        "Liver Function": ("🫀", liver),
        "Tumor / Inflammation": ("🔬", tumor),
        "Nutrition & Status": ("🍽️", nutrition),
        "Recent Trajectory": ("📈", trajectory),
    }


def _render_cluster_card(title, icon, items):
    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:11px; font-weight:700; color:#94a3b8; "
            f"text-transform:uppercase; letter-spacing:.05em; margin-bottom:12px;'>"
            f"{icon} {title}</div>",
            unsafe_allow_html=True,
        )
        if not items:
            st.markdown("<span style='font-size:12px; color:#94a3b8;'>Not enough data yet.</span>", unsafe_allow_html=True)
            return
        color_map = {"improving": "#15803d", "stable": "#475569", "watching": "#b45309", "concern": "#b91c1c"}
        for line_icon, color_class, text in items:
            border_color = color_map.get(color_class, "#94a3b8")
            st.markdown(
                f"<div style='font-size:12px; line-height:1.5; padding:6px 0 6px 10px; "
                f"margin:6px 0; border-left:3px solid {border_color};'>"
                f"<span style='margin-right:6px;'>{line_icon}</span>{text}</div>",
                unsafe_allow_html=True,
            )
```

- [ ] **Step 2: Write the Overview page body**

Replace `app.py:1648-1803` (the entire old `with tab_overview:` block, along with the header/banner/alert render that used to precede it at `app.py:350-433`) with:

```python
if active_page == "overview":
    latest_date = ALL_DATES[0] if ALL_DATES else None
    high_n = low_n = norm_n = 0
    if latest_date:
        day_readings = readings_df[readings_df["test_date"] == latest_date]
        for _, r in day_readings.iterrows():
            if pd.isna(r["value"]):
                continue
            p_row = params_df[params_df["name"] == r["parameter"]].iloc[0]
            s = status_of(p_row, float(r["value"]))
            if s == "high":
                high_n += 1
            elif s == "low":
                low_n += 1
            else:
                norm_n += 1

    # Patient quick-info banner
    col_info, col_counts = st.columns([3, 2])
    with col_info:
        dx_pill = (
            f'<span style="background:#eff6ff; color:#1d4ed8; font-size:11px; '
            f'font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #dbeafe; '
            f'text-transform:uppercase;">{PATIENT_DX}</span>' if PATIENT_DX else ""
        )
        st.markdown(
            f"""<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
              <h2 style="margin:0; font-size:28px;">{PATIENT_NAME}</h2>{dx_pill}
            </div>
            <p style="color:#64748b; font-size:14px; margin:0;">
              Last updated: <b style="color:#334155;">{latest_date.strftime('%d-%b-%Y') if latest_date else '—'}</b>
              (Report #{len(ALL_DATES)}) &nbsp;•&nbsp; <i>{meta.get('subtitle', 'Discuss results with your oncology team.')}</i>
            </p>""",
            unsafe_allow_html=True,
        )
    with col_counts:
        c1, c2, c3 = st.columns(3)
        for col, label, count, color in [
            (c1, "Normal", norm_n, "#059669"), (c2, "Warning", low_n, "#d97706"), (c3, "Critical", high_n, "#dc2626"),
        ]:
            with col:
                with st.container(border=True):
                    st.markdown(
                        f"<div style='font-size:10px; font-weight:700; color:#94a3b8; "
                        f"text-transform:uppercase;'>{label}</div>"
                        f"<div class='font-mono-lab' style='font-size:24px; font-weight:700; color:{color};'>{count:02d}</div>",
                        unsafe_allow_html=True,
                    )

    # Critical alerts (existing build_alerts(), unchanged)
    alerts = build_alerts()
    if alerts:
        html_items = " &nbsp;·&nbsp; ".join(f"<b>{n}:</b> {r}" for n, r in alerts)
        st.markdown(
            f'<div class="alert"><div class="t">⚠ Priority Clinical Findings (Latest Report — {latest_date.strftime("%d-%b-%Y")})</div>'
            f'<div class="d">{html_items}</div></div>',
            unsafe_allow_html=True,
        )

    # Clinical Prognostic Panels — Clinical View only
    if st.session_state.get("view_mode") == "Clinical View":
        st.markdown("### 🩺 Clinical Prognostic Panels")
        clusters = _cluster_insights()
        cols = st.columns(4)
        for col, (title, (icon, items)) in zip(cols, clusters.items()):
            with col:
                _render_cluster_card(title, icon, items)

    # Latest Laboratory Results
    st.markdown("### 📋 Latest Laboratory Results")
    KEY_PARAMS = ['Hemoglobin (Hb)', 'Platelet Count', 'WBC / Total Leukocyte Count',
                  'Bilirubin - Total', 'ALT (SGPT)', 'AST (SGOT)', 'GGT',
                  'Alkaline Phosphatase (ALP)', 'Albumin', 'CRP', 'Creatinine', 'CA 19-9']
    rows = [KEY_PARAMS[i:i+4] for i in range(0, len(KEY_PARAMS), 4)]
    for row in rows:
        cols = st.columns(len(row))
        for col, name in zip(cols, row):
            if not (params_df["name"] == name).any():
                continue
            p_row = params_df[params_df["name"] == name].iloc[0]
            latest = get_latest(name)
            if not latest:
                continue
            prev = get_previous(name, latest["date"])
            mult, unit = display_info(p_row)
            s = status_of(p_row, latest["value"])
            desc = PARAM_INFO.get(name, "")
            trend_html = ""
            if prev:
                diff = latest["value"] - prev["value"]
                if abs(diff) >= 0.005:
                    arrow = "↑" if diff > 0 else "↓"
                    cls = "up" if diff > 0 else "down"
                    trend_html = f'<div class="trend-line"><span class="{cls}">{arrow} {fmt_num(abs(diff), mult)}</span> vs prior</div>'
                else:
                    trend_html = '<div class="trend-line"><span class="flat">→ no change</span> vs prior</div>'
            with col:
                with st.container(border=True):
                    st.markdown(
                        f"""<div class="param-head"><span class="param-name">{name}</span>
                          <span class="pill-{s}">{s.upper()}</span></div>
                        {f'<div class="param-desc">{desc}</div>' if desc else ''}
                        <div class="big-value {s} font-mono-lab" style="font-size:26px; font-weight:800; margin:6px 0;">{fmt_num(latest['value'], mult)}
                          <span style="font-size:11px; color:#94a3b8; font-family:'Plus Jakarta Sans',sans-serif;">{unit}</span></div>
                        <div class="param-meta">Ref: {fmt_range(p_row)}</div>
                        {trend_html}""",
                        unsafe_allow_html=True,
                    )

    # Key Trajectories — respects the header's global period control
    st.markdown("### 📈 Key Trajectories (locked to selected period)")
    chart_cols = st.columns(2)
    for i, name in enumerate(CHARTED):
        if not (params_df["name"] == name).any():
            continue
        with chart_cols[i % 2]:
            render_chart(name, key_prefix="ov")
```

Note: `.big-value.high/.low/.normal` color classes already exist from the original stylesheet (kept in Task 2's replacement CSS under the same names via the `.pill-*` colors — if you removed them in Task 2, add these three lines to the Task 2 stylesheet block before this task: `.big-value.high{color:#b91c1c;} .big-value.low{color:#b45309;} .big-value.normal{color:#15803d;}`).

- [ ] **Step 3: Manual check**

Log in, land on Overview (the default `nav_page`), confirm: patient name + dx pill + last-updated line on the left, 3 count tiles (Normal/Warning/Critical) on the right, the critical-alerts red box if any critical values exist in the fixture data, a 4-column "Clinical Prognostic Panels" row (only when the header's view toggle is "Clinical View" — toggle to "Family" and confirm that row disappears), the Latest Laboratory Results grid, and the Key Trajectories chart grid whose date range shrinks/grows when you change the header's period control.

- [ ] **Step 4: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: rebuild Overview page in Precision Clinical style"
```

---

### Task 7: Trends Browser page

**Files:**
- Modify: `app.py:1807-1836` (old `with tab_trends:` body — replaced)

**Interfaces:**
- Consumes: `active_page` (Task 4), `render_chart` (Task 5, now reading the global period automatically)

- [ ] **Step 1: Replace the Trends tab body**

Replace `app.py:1807-1836` with:

```python
if active_page == "trends":
    st.markdown("## Trends Browser")
    st.caption("Visualize parameter trajectories over the selected timeframe.")

    col1, col2 = st.columns(2)
    panel_filter = col1.selectbox("Panel", ["All panels"] + PANELS, key="tr_panel")
    param_options = ["All charted parameters"] + sorted(params_df["name"].tolist())
    param_filter = col2.selectbox("Parameter", param_options, key="tr_param")

    sel_params = params_df.copy()
    if panel_filter != "All panels":
        sel_params = sel_params[sel_params["panel"] == panel_filter]
    if param_filter != "All charted parameters":
        sel_params = sel_params[sel_params["name"] == param_filter]
    sel_params = sel_params[sel_params["name"].isin(
        readings_df[readings_df["value"].notna()]["parameter"].unique()
    )]
    counts = readings_df[readings_df["value"].notna()].groupby("parameter").size()
    sel_params["n"] = sel_params["name"].map(counts).fillna(0)
    sel_params = sel_params.sort_values("n", ascending=False)

    if sel_params.empty:
        st.info("No data for this selection.")
    else:
        chart_cols = st.columns(2)
        for i, (_, p_row) in enumerate(sel_params.iterrows()):
            with chart_cols[i % 2]:
                render_chart(p_row["name"], key_prefix="tr")
```

This drops the old per-tab `period` selectbox (`app.py:1812`) and `period_days` dict (`app.py:1831-1832`) entirely — `render_chart` now reads `st.session_state["global_period"]` on its own (Task 5).

- [ ] **Step 2: Manual check**

Go to Trends Browser, confirm Panel/Parameter filters work, the chart grid updates, and changing the header's period control (not a page-local one — there should be no period dropdown on this page anymore) changes every chart's date range.

- [ ] **Step 3: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: rebuild Trends Browser page, drop redundant per-tab period control"
```

---

### Task 8: Compare Data page (Overlay Trends + By Date sub-toggle)

**Files:**
- Modify: `app.py:1839-2010` (old `with tab_overlay:` AND `with tab_compare:` bodies — merged into one page with an internal sub-toggle, per the approved design and the earlier user-confirmed page mapping)

**Interfaces:**
- Consumes: `active_page` (Task 4), `st.session_state["global_period"]` (Task 3)
- Produces: `st.session_state["compare_mode"]` (`"Overlay Trends" | "By Date"`)

- [ ] **Step 1: Replace both old tab bodies with one page**

Replace the combined `app.py:1839` (start of `with tab_overlay:`) through `app.py:2010` (end of `with tab_compare:`) with:

```python
if active_page == "compare":
    col_title, col_toggle = st.columns([3, 1])
    with col_title:
        st.markdown("## Compare Analytical Data")
        st.caption("Cross-parameter normalization and longitudinal comparison.")
    with col_toggle:
        st.segmented_control(
            "Mode", ["Overlay Trends", "By Date"], default="Overlay Trends",
            key="compare_mode", label_visibility="collapsed",
        )

    if st.session_state.get("compare_mode", "Overlay Trends") == "Overlay Trends":
        default_set = ["Bilirubin - Total", "Alkaline Phosphatase (ALP)", "GGT", "CRP", "CA 19-9"]
        available = sorted([p for p in params_df["name"].tolist()
                            if pd.notna(params_df.loc[params_df["name"] == p, "hi"].iloc[0])])
        default_in_available = [p for p in default_set if p in available]

        with st.container(border=True):
            selected = st.multiselect(
                "Select parameters (max 5)", options=available,
                default=default_in_available, max_selections=5,
                help="Only parameters with a defined upper reference limit can be normalized.",
            )
            st.caption("All values normalized to **% of Upper Reference Limit**.")

            if not selected:
                st.info("Pick at least one parameter from the dropdown.")
            else:
                palette = ["#2563eb", "#6366f1", "#10b981", "#f59e0b", "#f43f5e"]
                period_days = lib.period_days_for(st.session_state.get("global_period", "ALL"))

                fig = go.Figure()
                for i, name in enumerate(selected):
                    p_row = params_df[params_df["name"] == name].iloc[0]
                    df_p = get_readings(name)
                    if period_days is not None and not df_p.empty:
                        cutoff = max(df_p["test_date"]) - pd.Timedelta(days=period_days)
                        df_p = df_p[df_p["test_date"] >= cutoff]
                    if df_p.empty:
                        continue
                    hi = float(p_row["hi"])
                    unit = p_row["unit"] or ""
                    df_p = df_p.copy()
                    df_p["normalized"] = df_p["value"].astype(float) / hi * 100
                    fig.add_trace(go.Scatter(
                        x=df_p["test_date"], y=df_p["normalized"],
                        mode="lines+markers", name=name,
                        line=dict(color=palette[i], width=2.5),
                        marker=dict(size=8, color=palette[i], line=dict(width=1, color="#fff")),
                        customdata=list(zip(df_p["value"].astype(float), [unit] * len(df_p), [hi] * len(df_p))),
                        hovertemplate=(f"<b>{name}</b><br>%{{x|%d-%b-%Y}}<br>"
                                       "Value: %{customdata[0]:,.2f} %{customdata[1]}<br>"
                                       "Upper limit: %{customdata[2]:,.2f} %{customdata[1]}<br>"
                                       "<b>%{y:.0f}%</b> of upper limit<extra></extra>"),
                    ))
                fig.add_hline(y=100, line_dash="dash", line_color="rgba(220,38,38,0.55)",
                              annotation_text="upper limit (100%)", annotation_position="top right")
                fig.add_hrect(y0=0, y1=100, fillcolor="rgba(34,197,94,0.05)", line_width=0, layer="below")
                fig.update_layout(
                    height=420, margin=dict(l=20, r=20, t=30, b=60),
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(size=12, color="#0f172a", family="Plus Jakarta Sans, -apple-system, sans-serif"),
                    xaxis=dict(showgrid=False, tickfont=dict(size=11), nticks=10),
                    yaxis=dict(title=dict(text="% of upper reference limit"), gridcolor="rgba(0,0,0,0.06)",
                               tickfont=dict(size=11), tickformat=".0f", ticksuffix="%"),
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="overlay_chart")

                st.divider()
                leg_cols = st.columns(len(selected))
                for i, name in enumerate(selected):
                    p_row = params_df[params_df["name"] == name].iloc[0]
                    mult, unit = display_info(p_row)
                    latest = get_latest(name)
                    if latest:
                        pct_of_hi = latest["value"] / float(p_row["hi"]) * 100 if pd.notna(p_row["hi"]) else None
                        pct_str = f"{pct_of_hi:.0f}% of limit" if pct_of_hi is not None else ""
                        with leg_cols[i]:
                            st.markdown(
                                f"""<div style="background:#f8fafc; border:1px solid #f1f5f9; border-radius:8px; padding:10px;">
                                  <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                                    <span style="width:8px; height:8px; border-radius:50%; background:{palette[i]}; display:inline-block;"></span>
                                    <span style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;">{name}</span>
                                  </div>
                                  <div class="font-mono-lab" style="font-size:16px; font-weight:700;">{fmt_num(latest['value'], mult)} <span style="font-size:10px; color:#94a3b8;">{unit}</span></div>
                                  <div style="font-size:10px; color:#94a3b8; margin-top:2px;">{pct_str} • Ref: {fmt_range(p_row)}</div>
                                </div>""",
                                unsafe_allow_html=True,
                            )
    else:  # By Date
        date_options = [d.strftime("%d-%b-%Y") for d in ALL_DATES]
        iso_map = {d.strftime("%d-%b-%Y"): d for d in ALL_DATES}
        col1, col2, col3 = st.columns(3)
        dA_str = col1.selectbox("Date A", date_options, index=1 if len(date_options) > 1 else 0)
        dB_str = col2.selectbox("Date B", date_options, index=0)
        panel_cmp = col3.selectbox("Panel filter", ["All panels"] + PANELS, key="cmp_panel")
        dA, dB = iso_map[dA_str], iso_map[dB_str]
        st.caption("Δ shows B − A · red = higher · green = lower")

        sel = params_df.copy()
        if panel_cmp != "All panels":
            sel = sel[sel["panel"] == panel_cmp]

        for panel in PANELS:
            panel_params = sel[sel["panel"] == panel]
            if panel_params.empty:
                continue
            rows = []
            for _, p in panel_params.iterrows():
                mult, unit = display_info(p)
                vA = readings_df[(readings_df["parameter"] == p["name"]) & (readings_df["test_date"] == dA)]["value"]
                vB = readings_df[(readings_df["parameter"] == p["name"]) & (readings_df["test_date"] == dB)]["value"]
                vA = float(vA.iloc[0]) if not vA.empty and pd.notna(vA.iloc[0]) else None
                vB = float(vB.iloc[0]) if not vB.empty and pd.notna(vB.iloc[0]) else None
                if vA is None and vB is None:
                    continue
                stA = status_of(p, vA) if vA is not None else "—"
                stB = status_of(p, vB) if vB is not None else "—"
                delta = ""
                if vA is not None and vB is not None and abs(vA - vB) > 0.005:
                    diff = vB - vA
                    arrow = "↑" if diff > 0 else "↓"
                    delta = f"{arrow} {fmt_num(abs(diff), mult)}"
                rows.append({
                    "Parameter": p["name"],
                    f"{dA_str}": (fmt_num(vA, mult) if vA is not None else "—") + ("" if stA in ("normal", "—") else f" ({stA.upper()})"),
                    f"{dB_str}": (fmt_num(vB, mult) if vB is not None else "—") + ("" if stB in ("normal", "—") else f" ({stB.upper()})"),
                    "Δ (B − A)": delta,
                    "Reference": f"{fmt_range(p)} {unit}",
                })
            if rows:
                st.markdown(f"**{panel}**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
```

- [ ] **Step 2: Manual check**

Go to Compare Data, confirm the "Overlay Trends / By Date" segmented toggle appears top-right, Overlay Trends shows the multi-param normalized chart + legend cards (respecting the header period control), and switching to "By Date" shows the Date A/B/Panel diff tables.

- [ ] **Step 3: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: merge Compare Trends and Compare Dates into one Compare Data page"
```

---

### Task 9: Full Records page (kept at last-approved plain/spacious styling)

**Files:**
- Modify: `app.py:2013-2058` (old `with tab_table:` body — replaced)

**Interfaces:**
- Consumes: `active_page` (Task 4), `st.session_state["global_period"]` (Task 3), `.simple-table`/`.val-normal`/`.val-alert` CSS (Task 2)

- [ ] **Step 1: Replace the Full Table tab body**

Replace `app.py:2013-2058` with:

```python
if active_page == "records":
    col_title, col_export = st.columns([4, 1])
    with col_title:
        st.markdown("## Full Laboratory Records")
        st.caption("Historical view of all validated clinical parameters over the selected monitoring period.")

    col1, col2, col3 = st.columns([2, 2, 2])
    panel_t = col1.selectbox("Panel", ["All"] + PANELS, key="tbl_panel")
    search = col2.text_input("Search parameter", "", key="tbl_search")
    order_t = col3.selectbox("Date order", ["Newest → Oldest", "Oldest → Newest"], key="tbl_order")

    sel = params_df.copy()
    if panel_t != "All":
        sel = sel[sel["panel"] == panel_t]
    if search:
        sel = sel[sel["name"].str.lower().str.contains(search.lower())]

    dates = sorted(ALL_DATES)
    period_days = lib.period_days_for(st.session_state.get("global_period", "ALL"))
    if period_days is not None and dates:
        cutoff = max(dates) - pd.Timedelta(days=period_days)
        dates = [d for d in dates if d >= cutoff]
    if order_t == "Newest → Oldest":
        dates = list(reversed(dates))

    if not sel.empty and dates:
        header_cells = "".join(f"<th>{d.strftime('%d %b')}</th>" for d in dates)
        body_rows = []
        for panel in ([panel_t] if panel_t != "All" else PANELS):
            panel_rows = sel[sel["panel"] == panel]
            if panel_rows.empty:
                continue
            body_rows.append(
                f'<tr style="background:rgba(248,250,252,0.5);"><td colspan="{3+len(dates)}" '
                f'style="padding:12px 24px; font-size:11px; font-weight:700; color:#94a3b8; '
                f'text-transform:uppercase; letter-spacing:.05em; border-bottom:1px solid #e2e8f0;">{panel}</td></tr>'
            )
            for _, p in panel_rows.iterrows():
                mult, unit = display_info(p)
                cells = f'<td style="font-weight:600; color:#334155;">{p["name"]}</td>'
                cells += f'<td style="color:#64748b;">{unit}</td>'
                cells += f'<td style="color:#64748b; font-style:italic;">{fmt_range(p)}</td>'
                for d in dates:
                    v = readings_df[(readings_df["parameter"] == p["name"]) & (readings_df["test_date"] == d)]["value"]
                    if v.empty or pd.isna(v.iloc[0]):
                        cells += "<td>—</td>"
                    else:
                        val = float(v.iloc[0])
                        s = status_of(p, val)
                        cls = "val-alert" if s in ("high", "low") else "val-normal"
                        cells += f'<td class="{cls}">{fmt_num(val, mult)}</td>'
                body_rows.append(f"<tr>{cells}</tr>")

        st.markdown(
            f"""<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; overflow:hidden;">
              <table class="simple-table">
                <thead><tr><th>Parameter</th><th>Unit</th><th>Ref Range</th>{header_cells}</tr></thead>
                <tbody>{''.join(body_rows)}</tbody>
              </table>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="margin-top:16px; display:flex; gap:32px; font-size:11px; color:#64748b; text-transform:uppercase;">'
            '<span><span class="val-normal">12.5</span> Within reference range</span>'
            '<span><span class="val-alert">48.2</span> Outside reference range</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No data to display.")
```

- [ ] **Step 2: Manual check**

Go to Full Records, confirm: no vertical column borders, only horizontal row separators, generous row padding, green/red value coloring, and that changing the header's period control changes which date columns appear.

- [ ] **Step 3: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "feat: rebuild Full Records page, wire to unified period control"
```

---

### Task 10: Final integration pass — remove dead code, footer, full manual QA

**Files:**
- Modify: `app.py` (remove now-unused old tab variable assignments if any remain, remove the old footer's outdated copy if desired)
- Modify: `app.py:2061-2063` (footer — update wording to match the new design's status bar copy, optional but included here for completeness)

- [ ] **Step 1: Replace the footer**

Replace `app.py:2061-2063`:

```python
# Footer
st.divider()
st.caption(f"Built on Streamlit + Neon Postgres · Data refreshes on each browser reload (cached 5 min) · {len(ALL_DATES)} dates, {len(params_df)} parameters")
```

with:

```python
st.divider()
st.caption(
    f"🟢 DB: Connected · {len(ALL_DATES)} dates, {len(params_df)} parameters · "
    "Visual analytics only — decisions must be made by a board-certified oncologist."
)
```

- [ ] **Step 2: Grep for orphaned references**

Run: `cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs && grep -n "tab_overview\|tab_trends\|tab_overlay\|tab_compare\|tab_table" app.py`
Expected: no output (all `st.tabs`-era variable names removed in Tasks 4/6/7/8/9). If anything prints, remove that leftover reference.

- [ ] **Step 3: Full pytest run**

Run: `cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs && python3 -m pytest tests/ -v`
Expected: all tests from Task 1 pass, 0 failures.

- [ ] **Step 4: Full manual QA pass**

Run `streamlit run app.py`, log in, and walk through: Overview (patient banner, alerts, Clinical Prognostic Panels toggle, Latest Results, Key Trajectories), Trends Browser (Panel/Parameter filters + charts), Compare Data (Overlay Trends multiselect + chart + legend, and By Date diff tables), Full Records (Panel/search/date-order filters + table). For each, change the header's period control (3M/6M/9M/1Y/ALL) and confirm the relevant charts/table columns respond. Toggle Family/Clinical View on Overview and confirm the Clinical Prognostic Panels section shows/hides. Click Lock and confirm it returns to the password screen.

- [ ] **Step 5: Commit**

```bash
cd /Users/zorawarsinghnandwal/Documents/GitHub/ajit-singh-labs
git add app.py
git commit -m "chore: final integration pass — footer copy, dead-code cleanup"
```

---

## Known follow-ups (explicitly out of scope for this plan)

- **Full Records visual polish**: the user said its exact styling ("neater") is being revisited later — this plan intentionally keeps it at the last-approved plain/spacious state (Task 9) rather than iterating further.
- **Sidebar nav active-state CSS** (Task 4) uses a `key`-based CSS hook that is solid for Streamlit ≥1.31, but if a future Streamlit upgrade changes how `st-key-*` classes are emitted, re-verify the active highlight still renders.
- **Plotly font rendering**: `Plus Jakarta Sans` is requested via `font.family` in `_build_figure` (Task 5); if the browser hasn't loaded the webfont yet on first paint, Plotly falls back to its default sans-serif silently — no error, just a font mismatch on a slow connection. Not worth guarding against for a 2-person-audience app.
