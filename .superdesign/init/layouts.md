# Layouts — Papa's Lab Tracker

Streamlit app. There is no router and no layout component tree — the entire
app is **one file, `app.py`** (2063 lines): page config → CSS injection →
password gate → data load → patient banner → alerts → 5 tabs, each rendering
inline. There is no sidebar (`initial_sidebar_state="collapsed"`, and it's
never used) and no persistent nav beyond the tab bar itself. Streamlit's own
header/footer/menu are NOT hidden (unlike some other Streamlit apps) — default
Streamlit chrome is visible.

Shell structure on every screen (after auth):

```
.stApp                                background #ffffff (Streamlit theme)
└── .block-container                  max-width 1500px, padding-top 1.5rem, padding-bottom 3rem
    ├── ## {APP_TITLE} — {PATIENT_NAME}      st.markdown header (app.py:353)
    ├── st.caption(subtitle)
    ├── .patient-banner                       name, dx, report count/latest date, 3 status-count chips
    ├── .alert (conditional)                   critical-value banner, only if any exist
    └── st.tabs(["Overview","Trends","Compare Trends","Compare Dates","Full Table"])
        └── <one tab's content, all others hidden by Streamlit>
```

## `app.py` — the entire app (structure by section)

```
1-137    Imports, PARAM_INFO dict (60 lab parameters → plain-language descriptions),
         st.set_page_config(), <head> meta-tag injection via components.html()
140-217  Inline global stylesheet (see theme.md)
222-245  check_password() — single shared-password gate (HMAC compare), st.stop() if not authed
250-274  load_data() — cached (ttl=300) Postgres fetch: parameters, readings, metadata
277-348  Presentation helpers: display_info, fmt_num, fmt_range, status_of,
         get_readings, get_latest, get_previous
350-401  Header + patient banner (name, dx, report count, latest date, normal/low/high counts)
404-433  build_alerts() + critical-alert banner render
436-1199 build_watch() + 16 insight_*() functions — pure Python, return
         (icon, color_class, text) tuples consumed by the Overview tab.
         (See components.md for the ones that render distinct card patterns.)
1202-1499 More insight_*() functions, cancer/cholangiocarcinoma-specific
         (ALBI, MELD-Na, mGPS, PNI, CAR, SII, CIPI, NLR, PLR, CTCAE, etc.)
1503-1578 _build_figure() (shared Plotly chart builder) + expand_chart_dialog()
         (st.dialog modal for a full-size chart)
1581-1637 render_chart() — the reusable per-parameter chart card (title + status
         pill + expand button + Plotly chart + 5-stat metric row)
1643-2063 The 5 tabs (see routes.md for what each renders)
```

## Auth gate (`app.py:222-245`)
```python
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.markdown(f"## 🔒 {APP_TITLE}")
    st.caption("Enter the password to view records.")
    with st.form("login"):
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Unlock")
    if submit:
        expected = st.secrets.get("app_password", "")
        if not expected:
            st.error("Server misconfigured: app_password secret is missing.")
            return False
        if hmac.compare_digest(pwd, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False


if not check_password():
    st.stop()
```
This IS the app's only "landing page" for a first-time visitor (doctor or
family member following a shared link) — currently a bare centered form with
no branding, no explanation of what the tool is, no patient name. Worth
redesigning explicitly since it's the very first impression.

## Patient banner (`app.py:373-401`)
```python
banner_html = f"""
<div class="patient-banner">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
    <div>
      <div style="font-size:18px; font-weight:700;">{PATIENT_NAME}</div>
      {f'<div style="font-size:11px; color:#2563eb; font-weight:600; text-transform:uppercase; letter-spacing:.5px;">{PATIENT_DX}</div>' if PATIENT_DX else ''}
      <div style="font-size:12px; color:#64748b; margin-top:6px;">
        <b>Total reports:</b> {len(ALL_DATES)} dates &nbsp;·&nbsp;
        <b>Latest:</b> {latest_date.strftime('%d-%b-%Y') if latest_date else '—'}
      </div>
    </div>
    <div style="display:flex; gap:10px;">
      <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:8px 14px; min-width:90px; text-align:center;">
        <div style="font-size:22px; font-weight:700; color:#16a34a;">{norm_n}</div>
        <div style="font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:.5px;">Normal</div>
      </div>
      <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:8px 14px; min-width:90px; text-align:center;">
        <div style="font-size:22px; font-weight:700; color:#d97706;">{low_n}</div>
        <div style="font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:.5px;">Below Range</div>
      </div>
      <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:8px; padding:8px 14px; min-width:90px; text-align:center;">
        <div style="font-size:22px; font-weight:700; color:#dc2626;">{high_n}</div>
        <div style="font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:.5px;">Above Range</div>
      </div>
    </div>
  </div>
</div>
"""
```

## Tab bar (`app.py:1643-1645`)
```python
tab_overview, tab_trends, tab_overlay, tab_compare, tab_table = st.tabs(
    ["Overview", "Trends", "Compare Trends", "Compare Dates", "Full Table"]
)
```
Restyled only via `.stTabs [data-baseweb="tab-list"] { gap:4px; }` and
`.stTabs [data-baseweb="tab"] { padding:10px 18px; font-weight:500; }` — no
active/inactive color override, so tab styling is mostly Streamlit default.
