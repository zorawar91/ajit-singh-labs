# Routes — Papa's Lab Tracker

**No URL router.** Single-page Streamlit app, one URL, password-gated. After
auth, "routing" is Streamlit's native `st.tabs()` — all 5 tabs render in the
same script run; the browser shows/hides via Streamlit's own tab JS, so there
are no deep links to a specific tab (opening the shared URL always lands on
"Overview"). No path params.

Launch: `streamlit run app.py`.

## The 5 tabs (`app.py:1643-2063`)

| Tab | Lines | Sidebar/in-tab filters | What it renders |
|---|---|---|---|
| **Overview** (default) | 1648-1803 | none | 5 stacked expanders: Clinical Watch, Clinical Insights, Unique Insights (cancer-specific), Latest Results (12 key params as cards), Key Trends (14 pre-selected charted parameters, 2/row) |
| **Trends** | 1807-1836 | Panel · Parameter · Period (`All time / Last 30 days / Last 90 days / Last 6 months / Last 1 year`) | Every parameter matching the filters as a `render_chart()` card, 2/row, sorted by reading count desc |
| **Compare Trends** | 1840-1963 | multiselect (up to 5 params) · Period (same 5 buckets as Trends) | One overlay Plotly chart normalizing all selected params to `% of upper reference limit` (so differently-scaled labs are visually comparable), plus a per-param legend-card row below |
| **Compare Dates** | 1967-2010 | Date A · Date B · Panel | Per-panel table: value on A, value on B, Δ (B−A), reference range — a point-in-time diff view, not a time series |
| **Full Table** | 2014-2058 | Panel · search text · Period (same 5 buckets) · Date order | One big wide table: rows = parameters, columns = dates, cells = value with ⚠/↓ markers for out-of-range |

**Existing time-range control**: Trends, Compare Trends, and Full Table
already each have their own independent `Period` selectbox with buckets
`All time / Last 30 days / Last 90 days / Last 6 months / Last 1 year`
(`app.py:1812`, `:1867-1871`, `:2018`, applied via `period_days` cutoff on
`test_date` — `app.py:1587-1589`, `:1878-1889`, `:2028-2031`). This is real,
working, dated data (`readings.test_date` in Postgres) — not decorative. The
requested redesign is to **standardize the bucket set to 3 / 6 / 9 months /
1 year / all time** (currently missing 9-months and has 30/90-day buckets
instead of 3-month) and likely **unify it into one consistent, prominent
control** rather than three near-duplicate small selectboxes reinvented per tab.

## What each key view renders (detail)

**Overview** — the default landing tab a doctor/family member sees first.
Auto-derived clinical narrative in plain + technical language: a 4-bucket
"Clinical Watch" (Improving / Stable / Watching / Concerns) built from
`build_watch()`; ~8 categories of "Clinical Insights" (streaks, liver
injury pattern, velocity, time-since-peak, clusters, anemia classification,
fatigue driver, electrolytes); ~10 categories of "Unique Insights" — validated
oncology composite scores (ALBI, MELD-Na, mGPS, PNI, CAR, SII, CIPI, NLR, PLR,
CTCAE toxicity grade, chemo-readiness, cholangitis watch, cachexia risk) each
rendered as a colored left-border card; a 12-card "Latest Results" grid; a
"Key Trends" section of 14 pre-picked charts. This tab is dense with clinical
jargon (MELD-Na, R-factor, ALBI grade) alongside plain descriptions — the
core "doctor-friendly vs. family-friendly" tension to resolve in the redesign.

**Trends** — self-service chart browser: pick a panel/parameter/period,
get every matching parameter as a chart card (line + shaded reference band +
5-stat row: Latest/Previous/Min/Max/Readings).

**Compare Trends** — up to 5 parameters overlaid on one normalized chart
(% of upper limit) so a family member/doctor can see co-movement (e.g. do
bilirubin, ALP, GGT and CRP rise together = cholangitis signal) without
needing to mentally rescale different units.

**Compare Dates** — snapshot diff between any two report dates, grouped by
panel, Δ colored by direction.

**Full Table** — the "audit trail" tab: every parameter × every date in one
wide table, for a doctor who wants the raw numbers rather than the narrative.
