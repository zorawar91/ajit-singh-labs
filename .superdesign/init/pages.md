# Pages — dependency trees

Streamlit app, single file (`app.py`, 2063 lines) — so there are no separate
page files to trace imports across. Every "page" (tab) shares the same
in-file dependencies. Listed once instead of repeated per tab:

```
Shell (all tabs):
- app.py:1-137        page config, PARAM_INFO dict, <head> meta injection
- app.py:140-217       inject_css() equivalent — inline stylesheet (theme.md)
- app.py:222-245       check_password() — auth gate every session hits first
- app.py:250-274       load_data() — cached Postgres fetch (parameters, readings, metadata)
- app.py:277-348       display_info, fmt_num, fmt_range, status_of,
                       get_readings, get_latest, get_previous
- app.py:350-433       header + patient banner + critical-alerts banner
- app.py:1503-1578     _build_figure, expand_chart_dialog (shared by every chart)
- app.py:1581-1637     render_chart (shared ChartCard)
```

**Context-file recipe for any tab's design**: since it's one 2063-line file,
per the PAYLOAD BUDGET rule (~900+ lines → line-range to the render section),
pass `app.py` in slices — the shell (`:1-433`), the shared helpers/chart
builder (`:1503-1637`), and the specific tab's render block — rather than the
whole file. Do NOT pass the ~700 lines of `insight_*()`/`build_watch()` pure-
logic functions (`app.py:436-1499`) for tabs other than Overview; they are
scoring logic, not layout, and just consume budget. Note: `_build_figure`,
`render_chart`, and the CSS are used by BOTH Overview (Key Trends section)
and Trends — always include them together.

---

## Overview (default landing tab)
Entry: `app.py:1648-1803` (inside `with tab_overview:`)
```
- app.py:1-433          shell (see above) — banner, alerts
- app.py:436-1199       build_watch() + first ~8 insight_*() functions
                        (needed for real content in the Clinical Watch /
                        Clinical Insights expanders — but these are LOGIC,
                        pass only if the draft needs real sample text; a
                        structural reproduction can use placeholder text)
- app.py:1202-1499      remaining insight_*() functions (Unique Insights)
- app.py:1503-1637      _build_figure, expand_chart_dialog, render_chart
                        (used by the "Key Trends" section, 14 charts, 2/row)
- app.py:1648-1803      the tab's own render code — 5 stacked st.expander
                        blocks: Clinical Watch, Clinical Insights, Unique
                        Insights, Latest Results (12-card grid), Key Trends
```

## Trends
Entry: `app.py:1807-1836`
```
- app.py:1-433          shell
- app.py:1503-1637      _build_figure, render_chart (this tab is almost
                        entirely render_chart calls)
- app.py:1807-1836      the tab's own render code — 3 filter selectboxes
                        (Panel, Parameter, Period) + chart grid, 2/row
```

## Compare Trends (overlay)
Entry: `app.py:1840-1963`
```
- app.py:1-433          shell
- app.py:277-348        display_info, fmt_num, fmt_range, get_readings,
                        get_latest (used directly, NOT via render_chart —
                        this tab builds its own Plotly figure inline)
- app.py:1840-1963      the tab's own render code — multiselect (≤5 params)
                        + Period selectbox, one normalized overlay chart,
                        per-param legend-card row below
```

## Compare Dates
Entry: `app.py:1967-2010`
```
- app.py:1-433          shell
- app.py:277-348        display_info, fmt_num, fmt_range, status_of
- app.py:1967-2010      the tab's own render code — Date A / Date B / Panel
                        selectboxes, then one st.dataframe per panel
```

## Full Table
Entry: `app.py:2014-2058`
```
- app.py:1-433          shell
- app.py:277-348        display_info, fmt_num, status_of, fmt_range
- app.py:2014-2058      the tab's own render code — Panel / search / Period /
                        Date-order filters, one wide st.dataframe
```
