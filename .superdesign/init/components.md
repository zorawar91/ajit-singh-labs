# Components — Papa's Lab Tracker

**No component library and no component directory.** Streamlit app, single
file. Shared UI primitives exist as:
1. **Python helpers** in `app.py` that format values / classify status.
2. **CSS classes** in the inline stylesheet (`app.py:140-217`, full source in
   `theme.md`) that views compose by writing inline HTML into
   `st.markdown(..., unsafe_allow_html=True)`.
3. **Two render functions** (`render_chart`, `_build_figure`) that are the
   closest thing to a reusable "ChartCard" component — every chart in the app
   (Overview's Key Trends, all of Trends, the modal expand) goes through them.

## 1. Status/formatting helpers (full source, `app.py:277-348`)

```python
def display_info(p_row):
    u = (p_row["unit"] or "").strip().lower()
    if u in ("thou/µl", "thousand/µl", "x10^9/l", "10^3/µl"):
        return 1000, "/µL"
    return 1, p_row["unit"] or ""


def fmt_num(v, mult):
    if v is None or pd.isna(v):
        return "—"
    scaled = v * (mult or 1)
    if mult > 1 and abs(scaled) >= 100:
        return f"{round(scaled):,}"
    return f"{scaled:,.2f}".rstrip("0").rstrip(".") or "0"


def fmt_range(p_row):
    mult, _ = display_info(p_row)
    if mult == 1:
        return p_row["reference_range"] or ""
    lo, hi = p_row["lo"], p_row["hi"]
    if pd.notna(lo) and pd.notna(hi):
        return f"{fmt_num(lo, mult)} – {fmt_num(hi, mult)}"
    if pd.notna(hi):
        return f"≤ {fmt_num(hi, mult)}"
    if pd.notna(lo):
        return f"≥ {fmt_num(lo, mult)}"
    return p_row["reference_range"] or ""


def status_of(p_row, v):
    if v is None or pd.isna(v):
        return "normal"
    if pd.notna(p_row["hi"]) and v > float(p_row["hi"]):
        return "high"
    if pd.notna(p_row["lo"]) and v < float(p_row["lo"]):
        return "low"
    return "normal"


def get_readings(param_name, n=None):
    """Return DataFrame of numeric readings (date, value) ordered oldest→newest."""
    pid = params_df.loc[params_df["name"] == param_name, "id"]
    if pid.empty:
        return pd.DataFrame()
    df = readings_df[(readings_df["parameter"] == param_name) & (readings_df["value"].notna())].copy()
    df = df.sort_values("test_date")
    return df.tail(n) if n else df


def get_latest(param_name):
    df = get_readings(param_name)
    if df.empty:
        return None
    row = df.iloc[-1]
    return {"date": row["test_date"], "value": float(row["value"])}


def get_previous(param_name, before_date):
    df = get_readings(param_name)
    df = df[df["test_date"] < before_date]
    if df.empty:
        return None
    row = df.iloc[-1]
    return {"date": row["test_date"], "value": float(row["value"])}
```

## 2. `render_chart(name, period_days=None, key_prefix="chart")` — the ChartCard (`app.py:1581-1637`)

The single most-reused piece of UI in the app — every chart on Overview and
Trends is one of these.

```python
def render_chart(name, period_days=None, key_prefix="chart"):
    if not (params_df["name"] == name).any():
        st.info(f"Parameter '{name}' not found")
        return
    p_row = params_df[params_df["name"] == name].iloc[0]
    df = get_readings(name)
    if period_days is not None and not df.empty:
        cutoff = max(df["test_date"]) - pd.Timedelta(days=period_days)
        df = df[df["test_date"] >= cutoff]
    if df.empty:
        with st.container(border=True):
            st.markdown(f"**{name}** — no readings in selected period")
        return
    mult, unit = display_info(p_row)
    df = df.copy(); df["disp"] = df["value"].astype(float) * mult
    desc = PARAM_INFO.get(name, "")
    latest_v = float(df.iloc[-1]["value"])
    s_status = status_of(p_row, latest_v)

    with st.container(border=True):
        # Title row: name + status pill + expand button
        title_col, btn_col = st.columns([8, 1])
        with title_col:
            st.markdown(
                f"""
                <div class="param-head">
                  <span class="param-name" style="font-size:15px;">{name}</span>
                  <span class="pill-{s_status}">{s_status}</span>
                </div>
                {f'<div class="param-desc">{desc}</div>' if desc else ''}
                <div class="param-meta">{unit or ""} &nbsp;·&nbsp; ref {fmt_range(p_row)} &nbsp;·&nbsp; {p_row["panel"]}</div>
                """,
                unsafe_allow_html=True,
            )
        with btn_col:
            if st.button("⛶", key=f"exp_{key_prefix}_{name}", help="Expand chart"):
                expand_chart_dialog(name)

        # Chart
        fig = _build_figure(name, p_row, df, mult, unit, height=300)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"{key_prefix}_chart_{name}")

        # Stat row
        prev_v = float(df.iloc[-2]["value"]) if len(df) >= 2 else None
        min_v = float(df["value"].min())
        max_v = float(df["value"].max())
        delta_str = None
        if prev_v is not None and abs(latest_v - prev_v) > 0.005:
            arrow = "↑" if latest_v > prev_v else "↓"
            delta_str = f"{arrow} {fmt_num(abs(latest_v - prev_v), mult)}"
        cols = st.columns(5)
        cols[0].metric("Latest", fmt_num(latest_v, mult), delta=delta_str,
                       delta_color="inverse" if s_status == "high" else "normal")
        cols[1].metric("Previous", fmt_num(prev_v, mult) if prev_v is not None else "—")
        cols[2].metric("Min", fmt_num(min_v, mult))
        cols[3].metric("Max", fmt_num(max_v, mult))
        cols[4].metric("Readings", len(df))
```

## 3. `_build_figure(...)` — shared Plotly builder (`app.py:1503-1549`)

```python
def _build_figure(name, p_row, df, mult, unit, height=320, label_textsize=10):
    """Build the Plotly figure (shared between inline render and modal expand).
    Hides per-point text labels when the series gets dense, for clarity."""
    def col_for(v):
        s = status_of(p_row, float(v))
        return "#ef4444" if s == "high" else "#f59e0b" if s == "low" else "#2563eb"
    point_colors = [col_for(v) for v in df["value"]]

    n = len(df)
    show_labels = n <= 12  # hide labels on dense series
    mode = "lines+markers+text" if show_labels else "lines+markers"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["test_date"], y=df["disp"],
        mode=mode,
        line=dict(color="#2563eb", width=2.5),
        marker=dict(color=point_colors, size=10, line=dict(width=1, color="#fff")),
        text=[fmt_num(float(v), mult) for v in df["value"]] if show_labels else None,
        textposition="top center",
        textfont=dict(size=label_textsize, color="#334155"),
        name=name,
        hovertemplate=f"<b>{name}</b><br>%{{x|%d-%b-%Y}}<br>%{{y:,.2f}} {unit}<extra></extra>",
    ))
    if pd.notna(p_row["hi"]) and pd.notna(p_row["lo"]):
        hi_d = float(p_row["hi"]) * mult
        lo_d = float(p_row["lo"]) * mult
        fig.add_hrect(y0=lo_d, y1=hi_d, fillcolor="rgba(34,197,94,0.10)", line_width=0, layer="below")
        fig.add_hline(y=hi_d, line_dash="dash", line_color="rgba(34,197,94,0.5)")
        fig.add_hline(y=lo_d, line_dash="dash", line_color="rgba(34,197,94,0.5)")
    elif pd.notna(p_row["hi"]):
        fig.add_hline(y=float(p_row["hi"]) * mult, line_dash="dash", line_color="rgba(239,68,68,0.65)",
                      annotation_text=f"max {fmt_num(float(p_row['hi']), mult)}", annotation_position="top right")
    elif pd.notna(p_row["lo"]):
        fig.add_hline(y=float(p_row["lo"]) * mult, line_dash="dash", line_color="rgba(245,158,11,0.65)",
                      annotation_text=f"min {fmt_num(float(p_row['lo']), mult)}", annotation_position="bottom right")

    fig.update_layout(
        xaxis_title=None, yaxis_title=unit or None,
        margin=dict(l=10, r=20, t=20, b=10), height=height,
        showlegend=False, hovermode="x unified",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=12, color="#0f172a"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11), nticks=8),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=11), title_font=dict(size=12)),
    )
    return fig
```

## 4. CSS primitives (see `theme.md` for full stylesheet)

- `.param-head` / `.param-name` / `.param-desc` / `.param-meta` — the header
  block atop every chart card and every "Latest Results" card.
- `.pill-high` / `.pill-low` / `.pill-normal` — status pill, loud uppercase badge.
- `.big-value` (+ `.high`/`.low`/`.normal` modifiers) — the large colored
  numeral on "Latest Results" cards.
- `.trend-line` (+ `.up`/`.down`/`.flat`) — small vs-prior delta line.
- `.watch-card` (+ `.improving`/`.stable`/`.watching`/`.concern`) — the
  4-bucket Clinical Watch cards, colored top border.
- `.patient-banner` — the header banner (name, dx, counts).
- `.alert` — critical-value red banner.
- Generic insight-card pattern (inline styles, not a class): white bg,
  colored 3px left border keyed to improving/stable/watching/concern, used for
  Clinical Insights and Unique Insights entries (`app.py:1697-1701`, `:1741-1746`).

## 5. Streamlit widgets in use (native, lightly restyled)
`st.tabs` (only padding/gap restyled — no active-state color) · `st.columns`
(layout grid, height-equalized via CSS) · `st.expander` (Overview's 5
sections; default Streamlit chrome, not restyled) · `st.selectbox` /
`st.multiselect` / `st.text_input` (filters) · `st.plotly_chart` (always via
`_build_figure`) · `st.metric` (5-stat row under each chart — used directly,
unlike other dashboards in this codebase's ecosystem that hand-build KPI
cards) · `st.dialog` (chart expand modal) · `st.dataframe` (Compare Dates,
Full Table) · `st.form` (password gate).
