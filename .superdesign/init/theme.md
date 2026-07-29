# Theme — Papa's Lab Tracker

Framework: **Streamlit** (Python), no JS build. CSS approach: a single global
stylesheet string injected once via `st.markdown(..., unsafe_allow_html=True)`
inline in `app.py:140-217`. There is no Tailwind, no CSS modules. Design tokens
are hardcoded hex values repeated inline (no Python constants, unlike a typical
theme.py pattern) — see raw source below for the exact values as used.

## Part 1 — Compact token summary

### Color palette
| Token (informal) | Value | Role |
|---|---|---|
| Primary blue | `#2563eb` | Streamlit `primaryColor`, chart lines, links, param names, patient-banner accents |
| Page background | `#ffffff` | Streamlit `backgroundColor` |
| Secondary background | `#f5f7fb` | Streamlit `secondaryBackgroundColor` |
| Text | `#0f172a` | Streamlit `textColor`, card titles, big values |
| Muted text | `#475569` / `#64748b` | descriptions, meta lines, captions |
| Card surface | `#f8fafc` | bordered-container fill, watch-card fill |
| Card border | `#e2e8f0` | bordered-container border, watch-card border |
| **Status: high/critical** | bg `#fee2e2` text `#b91c1c` border `#ef4444` | pill-high, alert box, watch-card.concern |
| **Status: low/warning** | bg `#fef3c7` text `#b45309` border `#f59e0b` | pill-low, watch-card.watching |
| **Status: normal/good** | bg `#dcfce7` text `#15803d` border `#22c55e` | pill-normal, watch-card.improving |
| **Status: stable/neutral** | `#94a3b8` / `#475569` | watch-card.stable |
| Chart normal-range band | `rgba(34,197,94,0.10)` fill, `rgba(34,197,94,0.5)` dashed line | `_build_figure` hrect/hline |
| Chart out-of-range markers | red `#ef4444` / amber `#f59e0b` / blue `#2563eb` (normal) | point colors in `_build_figure` |
| Overlay chart palette (5 series) | `#2563eb #dc2626 #16a34a #d97706 #7c3aed` | Compare Trends tab |
| Unique-Insights section accent | `#7c3aed` (purple) | vs. `#2563eb` (blue) for Clinical Insights |

### Streamlit base theme (`.streamlit/config.toml`) — pinned light
`base="light"`, `primaryColor="#2563eb"`, `backgroundColor="#ffffff"`,
`secondaryBackgroundColor="#f5f7fb"`, `textColor="#0f172a"`, `font="sans serif"`.

### Typography
Family: Streamlit default sans-serif stack (`font="sans serif"` in config.toml).
Type scale actually used (all inline in `app.py`):
- `.big-value` 28px/800 (status-colored: red/amber/green)
- card headline `param-name` 14px/700 (18px in the expand-modal variant)
- patient name in banner 18px/700
- `div[data-testid="stMetricValue"]` 26px/700 (Streamlit metric override)
- `.param-desc` 11px italic — clinical one-liner under every param
- `.param-meta`, `.trend-line` 11–12px
- `.watch-card h4` 12px/800, uppercase, letter-spacing .5px
- status pills (`.pill-*`) 11px/800, uppercase, letter-spacing .5px

### Spacing / layout
- `.block-container`: `padding-top:1.5rem; padding-bottom:3rem; max-width:1500px`
- bordered containers (`stVerticalBlockBorderWrapper`): `padding:14px 16px`, `border-radius:12px`
- `.patient-banner`: `padding:16px 20px; border-radius:12px`
- `.alert`: `padding:12px 16px; border-radius:8px; border-left:4px solid #ef4444`
- initial sidebar state: **collapsed** (no persistent sidebar nav — unlike a typical dashboard)

### Radii & elevation
- Card / bordered-container / patient-banner / watch-card: `10–12px`
- pills: `999px` (full round)
- No box-shadows used anywhere — flat card look, borders only (`1px #e2e8f0`, `1.5px` on status pills)

### Gradients
- `.patient-banner`: `linear-gradient(180deg, #fff, #fafbfd)` — the only gradient in the app (subtle, near-white)

### Layout mechanics (important for redesign — see `layouts.md`)
- Every bordered container is forced to `display:flex; flex-direction:column; height:100%` so grid cards in a row stretch to the tallest sibling — this is a manual fix for Streamlit's default (columns don't auto-equalize height).
- Charts are 2-per-row (`st.columns(2)`) throughout Overview/Trends.
- No dark mode — pinned light theme deliberately (same reasoning pattern as other Streamlit dashboards in this user's other projects: custom CSS assumes light base).

## Part 2 — Raw source

### `.streamlit/config.toml`
```toml
[theme]
base = "light"
primaryColor = "#2563eb"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f5f7fb"
textColor = "#0f172a"
font = "sans serif"

[browser]
gatherUsageStats = false
```

### Inline stylesheet (`app.py:140-217`)
```python
st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px; }
  h1, h2, h3 { font-weight: 600; }
  /* All Streamlit bordered containers get a soft light-grey look */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
    height: 100% !important;  /* stretch to fill the column height */
    display: flex !important;
    flex-direction: column !important;
  }
  /* Make every column stretch its child to the row's tallest sibling */
  div[data-testid="column"] {
    display: flex !important;
    flex-direction: column !important;
  }
  div[data-testid="column"] > div { flex: 1 1 auto; }
  div[data-testid="column"] > div > div[data-testid="stVerticalBlock"] {
    height: 100%;
  }
  /* Reserve consistent space for the description so cards align */
  .param-desc { min-height: 2.8em; }
  .param-meta { min-height: 1.2em; }
  .trend-line { min-height: 1.4em; }
  /* LOUDER status colors */
  .pill-high  { background: #fee2e2; color: #b91c1c; font-weight: 800; padding: 3px 10px; border-radius: 999px; font-size: 11px; letter-spacing: 0.5px; text-transform: uppercase; border: 1.5px solid #ef4444; }
  .pill-low   { background: #fef3c7; color: #b45309; font-weight: 800; padding: 3px 10px; border-radius: 999px; font-size: 11px; letter-spacing: 0.5px; text-transform: uppercase; border: 1.5px solid #f59e0b; }
  .pill-normal{ background: #dcfce7; color: #15803d; font-weight: 800; padding: 3px 10px; border-radius: 999px; font-size: 11px; letter-spacing: 0.5px; text-transform: uppercase; border: 1.5px solid #22c55e; }
  /* Stronger metric value colors when red/green */
  div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; }
  div[data-testid="stMetricDelta"] { font-weight: 700; font-size: 13px; }
  /* Card header row */
  .param-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 4px; }
  .param-name { font-weight: 700; font-size: 14px; color: #0f172a; }
  .param-help-icon { color: #64748b; font-size: 13px; cursor: help; }
  .param-desc { font-size: 11px; color: #475569; font-style: italic; line-height: 1.4; margin-top: 2px; }
  .param-meta { font-size: 11px; color: #64748b; margin-top: 4px; }
  .big-value { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; margin: 4px 0; }
  .big-value.high   { color: #b91c1c; }
  .big-value.low    { color: #b45309; }
  .big-value.normal { color: #15803d; }
  .trend-line { font-size: 12px; color: #475569; margin-top: 4px; }
  .trend-line .up   { color: #b91c1c; font-weight: 700; }
  .trend-line .down { color: #15803d; font-weight: 700; }
  .trend-line .flat { color: #64748b; font-weight: 700; }
  /* Watch cards */
  .watch-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; border-top: 4px solid #cbd5e1; height: 100%; }
  .watch-card.improving { border-top-color: #22c55e; }
  .watch-card.stable    { border-top-color: #94a3b8; }
  .watch-card.watching  { border-top-color: #f59e0b; }
  .watch-card.concern   { border-top-color: #ef4444; }
  .watch-card h4 { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; font-weight: 800; }
  .watch-card.improving h4 { color: #15803d; }
  .watch-card.stable    h4 { color: #475569; }
  .watch-card.watching  h4 { color: #b45309; }
  .watch-card.concern   h4 { color: #b91c1c; }
  .watch-item { font-size: 13px; line-height: 1.45; margin: 6px 0; padding-left: 6px; border-left: 2px solid #e2e8f0; }
  .watch-item b { font-weight: 700; }
  .watch-item span { color: #475569; display: block; font-size: 12px; margin-top: 2px; }
  .patient-banner {
    background: linear-gradient(180deg, #fff, #fafbfd);
    border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 14px;
  }
  .alert {
    background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; font-size: 13px;
  }
  .alert .t { font-weight: 800; color: #991b1b; margin-bottom: 4px; }
  .alert .d { line-height: 1.7; }
  .alert .d b { color: #b91c1c; }
  .stTabs [data-baseweb="tab-list"] { gap: 4px; }
  .stTabs [data-baseweb="tab"] { padding: 10px 18px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)
```

### Plotly chart theming (`_build_figure`, `app.py:1503-1549`)
```python
fig.update_layout(
    xaxis_title=None, yaxis_title=unit or None,
    margin=dict(l=10, r=20, t=20, b=10), height=height,
    showlegend=False, hovermode="x unified",
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(size=12, color="#0f172a"),
    xaxis=dict(showgrid=False, tickfont=dict(size=11), nticks=8),
    yaxis=dict(gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=11), title_font=dict(size=12)),
)
```
Reference-range band: `add_hrect` green fill `rgba(34,197,94,0.10)` between lo/hi,
dashed green hlines at the boundaries. Point markers colored red/amber/blue by
`status_of()`. Line color always `#2563eb`.
