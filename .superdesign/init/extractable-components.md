# Extractable components — Papa's Lab Tracker

Caveat: no reusable component files exist. All UI is inline HTML strings
composed from CSS classes in `app.py`'s inline stylesheet, plus two Python
render functions. Extractable units below are *patterns*, not files.

## Layout components

### AuthGate
- Source: `check_password()`, `app.py:222-245`
- Category: layout
- Description: Centered password form — the first (and currently only)
  screen a new doctor/family visitor sees. Bare `## 🔒 {APP_TITLE}` heading, a
  caption, password input, Unlock button. No branding, no patient name, no
  context about what the tool is.
- Extractable props: `appTitle` (string), `errorMessage` (string, optional)
- Hardcoded: 🔒 emoji, "Enter the password to view records." copy

### AppShell
- Source: `app.py` page config (`:102-107`) + `.block-container` (theme.md)
- Category: layout
- Description: max-width 1500px content column, light theme, default
  Streamlit chrome NOT hidden (unlike other apps in this ecosystem)
- Extractable props: none (static)

### TabBar
- Source: `st.tabs(...)`, `app.py:1643-1645`, styled `app.py:214-215`
- Category: layout
- Description: 5-tab navigation — Overview / Trends / Compare Trends /
  Compare Dates / Full Table. Minimal restyle (padding/gap only); no active-
  tab color treatment currently.
- Extractable props: `activeTab` (string, default: "Overview")
- Hardcoded: the 5 tab labels

## Basic components

### PatientBanner
- Source: `app.py:373-401`
- Category: basic
- Description: Header card — patient name, diagnosis (optional), total
  reports + latest date, and 3 colored count chips (Normal/Below Range/Above
  Range) for the latest report's status mix
- Extractable props: `patientName` (string), `diagnosis` (string, optional),
  `totalReports` (number), `latestDate` (string), `normalCount` (number),
  `lowCount` (number), `highCount` (number)
- Hardcoded: `linear-gradient(180deg,#fff,#fafbfd)`, the 3 chip colors
  (green/amber/red), "Normal"/"Below Range"/"Above Range" labels

### CriticalAlertBanner
- Source: `build_alerts()` + render, `app.py:406-433`
- Category: basic
- Description: Red left-border banner listing notable/critical values on
  the latest report (>2× or <0.5× reference bounds, or hardcoded critical
  thresholds for platelets/ANC)
- Extractable props: `date` (string), `items` (array of {name, detail})
- Hardcoded: ⚠ icon, red palette, "Notable values on latest report" copy

### StatusPill
- Source: `.pill-high`/`.pill-low`/`.pill-normal`, `theme.md`
- Category: basic
- Description: Loud uppercase status badge — high/low/normal
- Extractable props: `status` ("high"|"low"|"normal")
- Hardcoded: the 3 color pairs, 999px radius, 1.5px border

### ChartCard (render_chart)
- Source: `app.py:1581-1637` (+ `_build_figure`, `:1503-1549`)
- Category: basic — the single most-reused pattern in the app
- Description: Bordered card — param name + status pill + expand button
  header, plain-language description, Plotly line chart with shaded
  reference-range band, then a 5-metric row (Latest/Previous/Min/Max/Readings)
- Extractable props: `paramName` (string), `periodDays` (number, optional —
  this is exactly the field the new time-range slicer should drive),
  `status` ("high"|"low"|"normal")
- Hardcoded: 300px default height (480px in the expand modal), the metric
  row's 5 columns, chart color scheme (see theme.md)

### ClinicalWatchCard
- Source: `.watch-card` + call site `app.py:1660-1666`
- Category: basic
- Description: One of 4 buckets (Improving/Stable/Watching/Concern), colored
  top border, list of bolded-finding + explanation lines
- Extractable props: `bucket` ("improving"|"stable"|"watching"|"concern"),
  `title` (string), `items` (array of {name, detail})
- Hardcoded: the 4 border/heading colors, bucket icons (✓/○/◐/!)

### InsightCard (generic left-border finding line)
- Source: inline style pattern, call sites `app.py:1697-1701`, `:1741-1746`
- Category: basic
- Description: Small white card with a 3px colored left border keyed to
  improving/stable/watching/concern; used inside the "Clinical Insights" and
  "Unique Insights" expander grids (icon + bold headline + detail text)
- Extractable props: `colorClass` ("improving"|"stable"|"watching"|"concern"),
  `icon` (string, emoji), `text` (string, HTML)
- Hardcoded: the 4-color map (`#15803d`/`#475569`/`#b45309`/`#b91c1c`)

### LatestResultCard
- Source: call site `app.py:1779-1793`
- Category: basic
- Description: One parameter's most recent value as a big colored number,
  with description, reference range + date, and a small trend-vs-prior line
- Extractable props: `paramName` (string), `value` (string), `status`
  ("high"|"low"|"normal"), `referenceRange` (string), `date` (string),
  `trendDirection` ("up"|"down"|"flat", optional)
- Hardcoded: 28px big-value type scale, `.trend-line` up/down/flat colors

### OverlayLegendCard
- Source: call site `app.py:1953-1963` (Compare Trends tab)
- Category: basic
- Description: Small per-parameter card below the overlay chart — colored
  dot + name, current value, % of upper limit, reference range, description
- Extractable props: `paramName` (string), `color` (string, one of the
  5-item overlay palette), `value` (string), `pctOfLimit` (string)
- Hardcoded: the 5-color overlay palette (`#2563eb #dc2626 #16a34a #d97706 #7c3aed`)

### PeriodFilter (the control the redesign targets)
- Source: 3 near-duplicate call sites — `app.py:1812` (Trends),
  `:1867-1871` (Compare Trends), `:2018` (Full Table)
- Category: basic
- Description: A `st.selectbox` currently offering
  `All time / Last 30 days / Last 90 days / Last 6 months / Last 1 year`,
  independently re-declared per tab with its own `period_days` dict. Real,
  working filter over `readings.test_date` — not decorative. **Redesign
  target**: consolidate into one shared control with buckets
  `3 months / 6 months / 9 months / 1 year / All time`, applied consistently
  wherever a chart or table depends on a date range.
- Extractable props: `value` ("3m"|"6m"|"9m"|"1y"|"all", default: "all")
- Hardcoded: none — this is the one component that should NOT hardcode its
  option labels differently per tab, per the redesign brief

## Not extractable
Charts are Plotly figures (`_build_figure`), not markup — shared styling
lives in that function, not a component. Streamlit natives (`st.tabs`,
`st.expander`, `st.dataframe`, `st.metric`, `st.dialog`, `st.form`) are
restyled by CSS selectors only (or not restyled at all, e.g. `st.expander`,
`st.dataframe`) and can't be extracted as markup.
