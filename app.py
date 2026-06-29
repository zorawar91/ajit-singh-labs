"""
Lab Tracker — Streamlit app.

Loads data from a Neon Postgres database, password-protected.
Mirrors the HTML dashboard: Overview / Trends / Compare / Full Table.

Required Streamlit secrets:
    neon_db        = "postgresql://user:pwd@host/db?sslmode=require"
    app_password   = "your-strong-shared-password"

Optional Streamlit secrets (UI display only — no PII in this code by default):
    patient_name   = "Patient name to show on the dashboard"
    patient_dx     = "Diagnosis or condition shown under the name"
    app_title      = "Lab Tracker"
"""
import json
import hmac
from datetime import date, datetime
from collections import defaultdict

import streamlit as st
import streamlit.components.v1 as components
import psycopg
import pandas as pd
import plotly.graph_objects as go

# ============================================================================
# Page config
# ============================================================================
# Patient info pulled from secrets so this code stays generic / safe to publish.
PATIENT_NAME = st.secrets.get("patient_name", "Patient")
PATIENT_DX = st.secrets.get("patient_dx", "")
APP_TITLE = st.secrets.get("app_title", "Lab Tracker")

# Plain-language clinical context for each parameter (displayed under cards and charts)
PARAM_INFO = {
    'CA 19-9': 'Tumor marker for biliary & pancreatic cancers. Trends matter more than single values.',
    'CEA': 'General tumor marker, useful for tracking cancer activity over time.',
    'AFP (Alpha Fetoprotein)': 'Tumor marker; elevated in some liver cancers.',
    'Bilirubin - Total': 'Total bile pigment in blood. High = jaundice, bile duct or liver issue.',
    'Bilirubin - Direct': 'Conjugated bilirubin; high suggests bile duct obstruction or liver damage.',
    'Bilirubin - Indirect': 'Unconjugated bilirubin; high suggests excess red cell breakdown.',
    'ALT (SGPT)': 'Liver enzyme. Elevated = active liver cell injury.',
    'AST (SGOT)': 'Liver/muscle enzyme. Elevated alongside ALT suggests liver injury.',
    'GGT': 'Bile duct enzyme. Elevated with biliary obstruction or alcohol use.',
    'Alkaline Phosphatase (ALP)': 'Bile duct / bone enzyme. High = bile duct issue or bone turnover.',
    'Total Protein': 'Total serum proteins (albumin + globulin).',
    'Albumin': 'Main blood protein, made by liver. Low = poor liver synthesis or malnutrition.',
    'Globulin': 'Antibody / inflammation-related proteins.',
    'A/G Ratio': 'Albumin to Globulin ratio. Low suggests chronic disease or liver issue.',
    'LDH': 'Tissue damage marker; non-specific.',
    'Hemoglobin (Hb)': 'Oxygen-carrying protein in red blood cells. Low = anemia.',
    'RBC Count': 'Red blood cell count. Low with low Hb = anemia.',
    'WBC / Total Leukocyte Count': 'Total white cell count. High = infection/inflammation; low = bone marrow suppression.',
    'Platelet Count': 'Clotting cells. Low (<150k) = bleeding risk; very low (<50k) is dangerous.',
    'Hematocrit (PCV)': 'Fraction of blood that is red cells. Tracks with hemoglobin.',
    'MCV': 'Average red cell size. High = vit B12/folate issue; low = iron deficiency.',
    'MCH': 'Average hemoglobin per red cell.',
    'MCHC': 'Hemoglobin concentration within red cells.',
    'RDW': 'Red cell size variation. High = mixed cell populations, often early anemia.',
    'MPV': 'Average platelet size.',
    'Neutrophils (%)': 'Most abundant white cell; rises with bacterial infection.',
    'Lymphocytes (%)': 'Immune cells; rise with viral infection or chronic immune activity.',
    'Monocytes (%)': 'Cleanup white cells; rise in chronic inflammation.',
    'Eosinophils (%)': 'Allergy/parasite-related white cells.',
    'Basophils (%)': 'Rare white cells; allergy-related.',
    'Absolute Neutrophil Count': 'Critical for infection risk. <1,500 = neutropenia; <500 = severe.',
    'Absolute Lymphocyte Count': 'Total lymphocytes. Low = immunosuppression.',
    'Absolute Monocyte Count': 'Total monocytes.',
    'Absolute Eosinophil Count': 'Total eosinophils.',
    'Absolute Basophil Count': 'Total basophils.',
    'ESR': 'Inflammation marker; rises slowly with chronic inflammation.',
    'CRP': 'Acute inflammation marker; rises fast with infection or active inflammation.',
    'Procalcitonin': 'Bacterial infection marker; sharp rise suggests bacterial sepsis.',
    'Blood Urea Nitrogen (BUN)': 'Kidney waste product. High = dehydration or kidney issue.',
    'Urea': 'Same as BUN × 2.14 (different unit).',
    'Creatinine': 'Kidney filtration marker. Rising = worsening kidney function.',
    'Uric Acid': 'Purine breakdown product. High = gout risk or rapid cell turnover.',
    'eGFR': 'Estimated kidney filtration rate. <60 = chronic kidney disease.',
    'Sodium': 'Main blood electrolyte; tight regulation.',
    'Potassium': 'Critical for heart rhythm; both high and low are dangerous.',
    'Chloride': 'Tracks with sodium.',
    'Calcium': 'Bone & nerve mineral.',
    'Phosphorus': 'Bone mineral; rises in kidney disease.',
    'Magnesium': 'Co-factor mineral; often low in chronic illness.',
    'Bicarbonate': 'Blood pH buffer.',
    'Prothrombin Time (PT)': 'Clotting time. High = bleeding risk; affected by liver and warfarin.',
    'INR': 'Standardized PT. Therapeutic on warfarin is usually 2–3.',
    'Ferritin': 'Iron storage. High = inflammation or iron overload; low = iron deficiency.',
    'Transferrin': 'Iron transport protein. Low with high ferritin = inflammation pattern.',
    'TSH': 'Thyroid-stimulating hormone. High = underactive thyroid; low = overactive.',
    'Total T3': 'Total triiodothyronine (thyroid hormone).',
    'Total T4': 'Total thyroxine (thyroid hormone).',
    'Free T3': 'Free (active) T3.',
    'Free T4': 'Free (active) T4.',
    'Cortisol (AM)': 'Morning stress hormone. High = stress, steroid use; low = adrenal issue.',
    'ACTH': 'Pituitary hormone driving cortisol production.',
    'Random Glucose': 'Random blood sugar.',
    'HbA1c': 'Average blood sugar over ~3 months. <5.7% = normal.',
}

st.set_page_config(
    page_title=f"{APP_TITLE} — {PATIENT_NAME}",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject meta description + Open Graph tags into the document <head>.
# Streamlit doesn't expose these via set_page_config, so we use a tiny
# components.html() snippet that runs JS against parent.document.
import json as _json
_META_DESC = st.secrets.get("meta_description", "Private lab tracker. Sign-in required.")
_PAGE_TITLE = f"{APP_TITLE} — {PATIENT_NAME}"
components.html(f"""
<script>
  try {{
    const head = parent.document.head;
    const setMeta = (name, content, attr = 'name') => {{
      let el = head.querySelector(`meta[${{attr}}="${{name}}"]`);
      if (!el) {{
        el = parent.document.createElement('meta');
        el.setAttribute(attr, name);
        head.appendChild(el);
      }}
      el.setAttribute('content', content);
    }};
    setMeta('description', {_json.dumps(_META_DESC)});
    setMeta('og:title', {_json.dumps(_PAGE_TITLE)}, 'property');
    setMeta('og:description', {_json.dumps(_META_DESC)}, 'property');
    setMeta('og:type', 'website', 'property');
    setMeta('twitter:card', 'summary');
    setMeta('twitter:title', {_json.dumps(_PAGE_TITLE)});
    setMeta('twitter:description', {_json.dumps(_META_DESC)});
  }} catch (e) {{ /* sandboxed contexts can't reach parent; ignore */ }}
</script>
""", height=0)

# Tighter spacing + louder status colors
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

# ============================================================================
# Auth — single shared password
# ============================================================================
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

# ============================================================================
# Data loading — cached
# ============================================================================
@st.cache_data(ttl=300, show_spinner="Loading lab data…")
def load_data():
    cs = st.secrets["neon_db"]

    def fetch_df(cur, sql):
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)

    with psycopg.connect(cs) as conn, conn.cursor() as cur:
        params_df = fetch_df(cur, "SELECT id, name, unit, reference_range, panel, lo, hi FROM parameters ORDER BY id")
        readings_df = fetch_df(cur, """SELECT p.name AS parameter, r.test_date, r.value, r.text_value
                                       FROM readings r JOIN parameters p ON p.id = r.parameter_id""")
        meta_df = fetch_df(cur, "SELECT key, value FROM metadata")

    # Normalize types
    if not readings_df.empty:
        readings_df["test_date"] = pd.to_datetime(readings_df["test_date"]).dt.date
        readings_df["value"] = pd.to_numeric(readings_df["value"], errors="coerce")
    # Numeric columns on params_df come back as Decimal — convert to float
    for col in ("lo", "hi"):
        if col in params_df.columns:
            params_df[col] = pd.to_numeric(params_df[col], errors="coerce")
    meta = dict(zip(meta_df["key"], meta_df["value"]))
    return params_df, readings_df, meta


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


params_df, readings_df, meta = load_data()
ALL_DATES = sorted(readings_df["test_date"].unique(), reverse=True)
PANELS = sorted(params_df["panel"].dropna().unique().tolist())
CHARTED = json.loads(meta.get("charted_json", "[]"))

# Quick lookups
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


# ============================================================================
# Header
# ============================================================================
st.markdown(f"## {APP_TITLE} — {PATIENT_NAME}")
st.caption(meta.get("subtitle", ""))

# Patient banner
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
st.markdown(banner_html, unsafe_allow_html=True)

# ============================================================================
# Critical alerts
# ============================================================================
def build_alerts():
    critical = []
    if not latest_date:
        return critical
    for _, p in params_df.iterrows():
        v = readings_df[(readings_df["parameter"] == p["name"]) & (readings_df["test_date"] == latest_date)]["value"]
        if v.empty or pd.isna(v.iloc[0]):
            continue
        val = float(v.iloc[0])
        mult, unit = display_info(p)
        if pd.notna(p["hi"]) and val > float(p["hi"]) * 2:
            critical.append((p["name"], f"{fmt_num(val, mult)} {unit} (ref ≤ {fmt_num(float(p['hi']), mult)})"))
        elif pd.notna(p["lo"]) and val < float(p["lo"]) * 0.5:
            critical.append((p["name"], f"{fmt_num(val, mult)} {unit} (ref ≥ {fmt_num(float(p['lo']), mult)})"))
        if p["name"] == "Platelet Count" and val < 50:
            critical.append((p["name"], f"{fmt_num(val, mult)} /µL — bleeding risk"))
        if p["name"] == "Absolute Neutrophil Count" and val < 0.5:
            critical.append((p["name"], f"{fmt_num(val, mult)} /µL — severe neutropenia"))
    return critical


alerts = build_alerts()
if alerts:
    html_items = " &nbsp;·&nbsp; ".join(f"<b>{n}:</b> {r}" for n, r in alerts)
    st.markdown(
        f'<div class="alert"><div class="t">⚠ Notable values on latest report ({latest_date.strftime("%d-%b-%Y")})</div><div class="d">{html_items}</div></div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# Clinical Watch
# ============================================================================
def build_watch():
    findings = {"improving": [], "stable": [], "watching": [], "concern": []}

    def pct(a, b):
        return 0 if b == 0 else (a - b) / b * 100

    # CA 19-9
    df = get_readings("CA 19-9")
    if len(df) >= 2:
        latest = float(df.iloc[-1]["value"]); prev = float(df.iloc[-2]["value"])
        peak = float(df["value"].max())
        peak_date = df.loc[df["value"].idxmax(), "test_date"]
        drop_pk = pct(latest, peak)
        recent = pct(latest, prev)
        if drop_pk < -50 and recent < 25:
            findings["improving"].append(("CA 19-9 (primary tumor marker)",
                f"Major long-term response: {abs(drop_pk):.0f}% below peak ({peak:,.1f} on {peak_date.strftime('%d-%b-%Y')})."))
        elif recent > 50:
            findings["concern"].append(("CA 19-9",
                f"Recent rise of {recent:.0f}% vs prior reading ({prev:,.1f} → {latest:,.1f}). Worth confirming on next draw."))
        elif latest < 100 and len(df) >= 3:
            findings["improving"].append(("CA 19-9",
                f"Trending low at {latest:,.1f} (peak was {peak:,.1f})."))

    # Biliary markers
    for n in ["Bilirubin - Total", "Alkaline Phosphatase (ALP)", "GGT"]:
        if not (params_df["name"] == n).any():
            continue
        p_row = params_df[params_df["name"] == n].iloc[0]
        mult, unit = display_info(p_row)
        df = get_readings(n, 5)
        if len(df) < 2:
            continue
        latest = float(df.iloc[-1]["value"]); prev = float(df.iloc[-2]["value"])
        s = status_of(p_row, latest)
        trend = pct(latest, prev)
        all_vals = readings_df[(readings_df["parameter"] == n) & (readings_df["value"].notna())]["value"]
        peak_high = pd.notna(p_row["hi"]) and (all_vals > float(p_row["hi"]) * 1.5).any()
        if s == "normal" and peak_high:
            findings["improving"].append((f"{n}: normalized",
                f"Now {fmt_num(latest, mult)} {unit} (within {fmt_range(p_row)}). Previously elevated — biliary drainage looks effective."))
        elif s != "normal" and trend < -15:
            findings["improving"].append((f"{n}: improving",
                f"Down {abs(trend):.0f}% from prior ({fmt_num(prev, mult)} → {fmt_num(latest, mult)} {unit}). Ref {fmt_range(p_row)}."))
        elif s != "normal" and trend > 20:
            findings["watching"].append((f"{n}: rising",
                f"Up {trend:.0f}% to {fmt_num(latest, mult)} {unit} (ref {fmt_range(p_row)}). Watch next reading."))
        elif s != "normal":
            findings["watching"].append((f"{n}: still above range",
                f"Currently {fmt_num(latest, mult)} {unit} (ref {fmt_range(p_row)})."))
        else:
            findings["stable"].append((f"{n}: within range",
                f"{fmt_num(latest, mult)} {unit} (ref {fmt_range(p_row)})."))

    # Albumin
    if (params_df["name"] == "Albumin").any():
        p_row = params_df[params_df["name"] == "Albumin"].iloc[0]
        df = get_readings("Albumin", 4)
        if len(df) >= 2:
            latest = float(df.iloc[-1]["value"]); prev = float(df.iloc[-2]["value"])
            s = status_of(p_row, latest); mult, _ = display_info(p_row)
            if s == "normal" and latest > prev:
                findings["improving"].append(("Albumin: recovered",
                    f"Now {fmt_num(latest, mult)} g/dL (within {fmt_range(p_row)}), up from {fmt_num(prev, mult)}. Reflects improved liver synthesis and nutrition."))
            elif s == "low":
                findings["watching"].append(("Albumin: low",
                    f"{fmt_num(latest, mult)} g/dL (ref {fmt_range(p_row)}). Suggests reduced liver synthesis or nutrition shortfall."))

    # CRP persistence
    if (params_df["name"] == "CRP").any():
        p_row = params_df[params_df["name"] == "CRP"].iloc[0]
        df = get_readings("CRP", 5)
        if len(df) >= 3:
            recent3 = df.tail(3)
            if all(float(v) > (float(p_row["hi"]) if pd.notna(p_row["hi"]) else 0.5) for v in recent3["value"]):
                mult, _ = display_info(p_row)
                trail = " → ".join(fmt_num(float(v), mult) for v in recent3["value"])
                findings["watching"].append(("CRP persistently elevated",
                    f"{trail} mg/L across last 3 readings (normal <0.5). In a stented patient, worth evaluating for low-grade biliary infection (cholangitis)."))

    # ESR
    df = get_readings("ESR", 4)
    if len(df) >= 2:
        latest = float(df.iloc[-1]["value"]); prev = float(df.iloc[-2]["value"])
        if latest < prev * 0.5 and latest < 50:
            findings["improving"].append(("ESR dropping",
                f"Down to {latest:.0f} mm/hr from {prev:.0f} — chronic inflammation easing."))

    # Platelets
    if (params_df["name"] == "Platelet Count").any():
        p_row = params_df[params_df["name"] == "Platelet Count"].iloc[0]
        df = get_readings("Platelet Count", 4)
        if not df.empty:
            latest = float(df.iloc[-1]["value"]); mult, _ = display_info(p_row)
            if latest < 50:
                findings["concern"].append(("Platelets critically low",
                    f"{fmt_num(latest, mult)} /µL — bleeding risk; needs urgent attention."))
            elif latest < float(p_row["lo"]):
                findings["watching"].append(("Platelets below range",
                    f"{fmt_num(latest, mult)} /µL on {df.iloc[-1]['test_date'].strftime('%d-%b-%Y')} (ref {fmt_range(p_row)}). Common with chemo cycles — track next reading."))

    # ANC
    if (params_df["name"] == "Absolute Neutrophil Count").any():
        p_row = params_df[params_df["name"] == "Absolute Neutrophil Count"].iloc[0]
        df = get_readings("Absolute Neutrophil Count", 4)
        if not df.empty:
            latest = float(df.iloc[-1]["value"]); mult, _ = display_info(p_row)
            if latest < 0.5:
                findings["concern"].append(("Severe neutropenia",
                    f"ANC {fmt_num(latest, mult)} /µL on {df.iloc[-1]['test_date'].strftime('%d-%b-%Y')} — verify with lab if recent reports were inconsistent; if real, urgent infection-risk precautions warranted."))
            elif latest >= float(p_row["lo"]):
                findings["stable"].append(("ANC normal",
                    f"{fmt_num(latest, mult)} /µL (ref {fmt_range(p_row)}) — infection-fighting capacity preserved."))

    # Hb stability
    if (params_df["name"] == "Hemoglobin (Hb)").any():
        p_row = params_df[params_df["name"] == "Hemoglobin (Hb)"].iloc[0]
        df = get_readings("Hemoglobin (Hb)", 6)
        if len(df) >= 3:
            latest = float(df.iloc[-1]["value"])
            last3 = df.tail(3)["value"].astype(float)
            if (last3 - latest).abs().max() < 0.5 and latest < float(p_row["lo"]):
                findings["watching"].append(("Stable anemia",
                    f"Hb hovering at {latest} g/dL across recent readings (ref {fmt_range(p_row)}). Common in chronic illness + chemo. Not worsening, but worth discussing iron studies if symptomatic."))

    return findings


# ============================================================================
# Helpers — defined BEFORE tabs so they're available when overview renders
# ============================================================================
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


@st.dialog("Chart Detail", width="large")
def expand_chart_dialog(name):
    """Modal dialog showing a full-size chart for one parameter."""
    if not (params_df["name"] == name).any():
        st.info("Parameter not found"); return
    p_row = params_df[params_df["name"] == name].iloc[0]
    df = get_readings(name)
    if df.empty:
        st.info("No data"); return
    mult, unit = display_info(p_row)
    df = df.copy(); df["disp"] = df["value"].astype(float) * mult
    s = status_of(p_row, float(df.iloc[-1]["value"]))
    desc = PARAM_INFO.get(name, "")

    st.markdown(
        f"""
        <div class="param-head">
          <span class="param-name" style="font-size:18px;">{name}</span>
          <span class="pill-{s}">{s}</span>
        </div>
        {f'<div class="param-desc" style="font-size:13px; margin-bottom:8px;">{desc}</div>' if desc else ''}
        <div class="param-meta">{unit} &nbsp;·&nbsp; reference range {fmt_range(p_row)} &nbsp;·&nbsp; {len(df)} readings</div>
        """,
        unsafe_allow_html=True,
    )
    fig = _build_figure(name, p_row, df, mult, unit, height=480, label_textsize=11)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"modal_chart_{name}")


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


# ============================================================================
# Tabs
# ============================================================================
tab_overview, tab_trends, tab_overlay, tab_compare, tab_table = st.tabs(
    ["Overview", "Trends", "Multi-Param", "Compare Dates", "Full Table"]
)

# -------- Overview tab --------
with tab_overview:
    st.markdown("### Clinical Watch")
    st.caption("Automated summary across recent readings — discuss specifics with the treating oncologist.")
    findings = build_watch()
    buckets = [
        ("improving", "✓ Improving"),
        ("stable", "○ Stable / In Range"),
        ("watching", "◐ Watching"),
        ("concern", "! Concerns"),
    ]
    non_empty = [(k, t) for k, t in buckets if findings[k]]
    if non_empty:
        cols = st.columns(len(non_empty))
        for col, (k, title) in zip(cols, non_empty):
            items = findings[k]
            with col:
                items_html = "".join(f'<div class="watch-item"><b>{n}</b><span>{d}</span></div>' for n, d in items)
                st.markdown(f'<div class="watch-card {k}"><h4>{title} ({len(items)})</h4>{items_html}</div>', unsafe_allow_html=True)
    else:
        st.info("Not enough data points yet for trend assessment.")

    st.divider()
    st.markdown(f"### Latest Results &nbsp;<small style='color:#64748b'>as of {latest_date.strftime('%d-%b-%Y') if latest_date else '—'}</small>", unsafe_allow_html=True)

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
            value_str = f"{fmt_num(latest['value'], mult)} {unit}"
            desc = PARAM_INFO.get(name, "")
            # Trend line
            trend_html = ""
            if prev:
                diff = latest["value"] - prev["value"]
                if abs(diff) >= 0.005:
                    arrow = "↑" if diff > 0 else "↓"
                    cls = "up" if diff > 0 else "down"
                    trend_html = f'<div class="trend-line"><span class="{cls}">{arrow} {fmt_num(abs(diff), mult)}</span> vs prior ({fmt_num(prev["value"], mult)})</div>'
                else:
                    trend_html = '<div class="trend-line"><span class="flat">→ no change</span> vs prior</div>'
            with col:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="param-head">
                          <span class="param-name">{name}</span>
                          <span class="pill-{s}">{s}</span>
                        </div>
                        {f'<div class="param-desc">{desc}</div>' if desc else ''}
                        <div class="big-value {s}">{value_str}</div>
                        <div class="param-meta">ref {fmt_range(p_row)} {unit} &nbsp;·&nbsp; {latest["date"].strftime("%d-%b-%Y")}</div>
                        {trend_html}
                        """,
                        unsafe_allow_html=True,
                    )

    st.divider()
    st.markdown("### Key Trends")
    st.caption("14 most relevant parameters · click ⛶ on any chart to expand")
    chart_cols = st.columns(2)
    for i, name in enumerate(CHARTED):
        if not (params_df["name"] == name).any():
            continue
        with chart_cols[i % 2]:
            render_chart(name, key_prefix="ov")


# -------- Trends tab --------
with tab_trends:
    col1, col2, col3 = st.columns([2, 2, 1])
    panel_filter = col1.selectbox("Panel", ["All panels"] + PANELS, key="tr_panel")
    param_options = ["All charted parameters"] + sorted(params_df["name"].tolist())
    param_filter = col2.selectbox("Parameter", param_options, key="tr_param")
    period = col3.selectbox("Period", ["All time", "Last 30 days", "Last 90 days", "Last 6 months", "Last 1 year"], key="tr_period")

    sel_params = params_df.copy()
    if panel_filter != "All panels":
        sel_params = sel_params[sel_params["panel"] == panel_filter]
    if param_filter != "All charted parameters":
        sel_params = sel_params[sel_params["name"] == param_filter]
    # Only params with ≥1 numeric reading
    sel_params = sel_params[sel_params["name"].isin(
        readings_df[readings_df["value"].notna()]["parameter"].unique()
    )]
    # Sort by # readings desc
    counts = readings_df[readings_df["value"].notna()].groupby("parameter").size()
    sel_params["n"] = sel_params["name"].map(counts).fillna(0)
    sel_params = sel_params.sort_values("n", ascending=False)

    if sel_params.empty:
        st.info("No data for this selection.")
    else:
        period_days = {"All time": None, "Last 30 days": 30, "Last 90 days": 90,
                       "Last 6 months": 180, "Last 1 year": 365}[period]
        chart_cols = st.columns(2)
        for i, (_, p_row) in enumerate(sel_params.iterrows()):
            with chart_cols[i % 2]:
                render_chart(p_row["name"], period_days=period_days, key_prefix="tr")


# -------- Multi-Param overlay tab --------
with tab_overlay:
    st.markdown("### Compare Multiple Parameters")
    st.caption(
        "Overlay up to 5 lab parameters on one chart. "
        "Because parameters have different scales (mg/dL, U/L, /µL, etc.), values are normalized "
        "to **percent of the upper reference limit** so trends across markers are visually comparable. "
        "A horizontal line at 100% marks the upper limit; values above the line are out of range."
    )

    # Pre-selected medically meaningful set for cholangiocarcinoma — adjust freely
    default_set = [
        "Bilirubin - Total", "Alkaline Phosphatase (ALP)", "GGT", "CRP", "CA 19-9"
    ]
    available = sorted([p for p in params_df["name"].tolist()
                        if pd.notna(params_df.loc[params_df["name"] == p, "hi"].iloc[0])])
    default_in_available = [p for p in default_set if p in available]

    col_a, col_b = st.columns([3, 1])
    with col_a:
        selected = st.multiselect(
            "Choose up to 5 parameters",
            options=available,
            default=default_in_available,
            max_selections=5,
            help="Only parameters with a defined upper reference limit can be normalized.",
        )
    with col_b:
        period_overlay = st.selectbox(
            "Period",
            ["All time", "Last 30 days", "Last 90 days", "Last 6 months", "Last 1 year"],
            key="overlay_period",
        )

    if not selected:
        st.info("Pick at least one parameter from the dropdown.")
    else:
        # Color palette — distinct, colorblind-friendly
        palette = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed"]
        period_days = {
            "All time": None, "Last 30 days": 30, "Last 90 days": 90,
            "Last 6 months": 180, "Last 1 year": 365,
        }[period_overlay]

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
                mode="lines+markers",
                name=f"{name}",
                line=dict(color=palette[i], width=2.5),
                marker=dict(size=8, color=palette[i], line=dict(width=1, color="#fff")),
                customdata=list(zip(df_p["value"].astype(float), [unit] * len(df_p), [hi] * len(df_p))),
                hovertemplate=(
                    f"<b>{name}</b><br>"
                    "%{x|%d-%b-%Y}<br>"
                    "Value: %{customdata[0]:,.2f} %{customdata[1]}<br>"
                    "Upper limit: %{customdata[2]:,.2f} %{customdata[1]}<br>"
                    "<b>%{y:.0f}%</b> of upper limit"
                    "<extra></extra>"
                ),
            ))

        # Upper limit reference
        fig.add_hline(
            y=100, line_dash="dash", line_color="rgba(220,38,38,0.55)",
            annotation_text="upper limit (100%)", annotation_position="top right",
            annotation_font_size=11,
        )
        # Shaded "normal zone" below 100%
        fig.add_hrect(y0=0, y1=100, fillcolor="rgba(34,197,94,0.05)", line_width=0, layer="below")

        fig.update_layout(
            height=520,
            margin=dict(l=20, r=20, t=30, b=80),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(size=12, color="#0f172a"),
            xaxis=dict(showgrid=False, tickfont=dict(size=11), nticks=10),
            yaxis=dict(
                title=dict(text="% of upper reference limit", font=dict(size=12)),
                gridcolor="rgba(0,0,0,0.06)", tickfont=dict(size=11),
                tickformat=".0f", ticksuffix="%",
            ),
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="overlay_chart")

        # Quick clinical-context legend below the chart
        st.divider()
        st.markdown("##### What you're seeing")
        leg_cols = st.columns(len(selected))
        for i, name in enumerate(selected):
            p_row = params_df[params_df["name"] == name].iloc[0]
            mult, unit = display_info(p_row)
            latest = get_latest(name)
            if latest:
                pct_of_hi = latest["value"] / float(p_row["hi"]) * 100 if pd.notna(p_row["hi"]) else None
                pct_str = f"{pct_of_hi:.0f}% of limit" if pct_of_hi is not None else ""
                desc = PARAM_INFO.get(name, "")
                with leg_cols[i]:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div style="font-weight:700; color:{palette[i]}; font-size:13px;">● {name}</div>
                            <div style="font-size:18px; font-weight:700; margin:4px 0;">{fmt_num(latest['value'], mult)} {unit}</div>
                            <div style="font-size:11px; color:#64748b;">{pct_str} · ref {fmt_range(p_row)}</div>
                            {f'<div style="font-size:11px; color:#475569; font-style:italic; margin-top:6px; line-height:1.4;">{desc}</div>' if desc else ''}
                            """,
                            unsafe_allow_html=True,
                        )


# -------- Compare Dates tab --------
with tab_compare:
    date_options = [d.strftime("%d-%b-%Y") for d in ALL_DATES]
    iso_map = {d.strftime("%d-%b-%Y"): d for d in ALL_DATES}
    col1, col2, col3 = st.columns([2, 2, 2])
    dA_str = col1.selectbox("Date A", date_options, index=1 if len(date_options) > 1 else 0)
    dB_str = col2.selectbox("Date B", date_options, index=0)
    panel_cmp = col3.selectbox("Panel filter", ["All panels"] + PANELS, key="cmp_panel")
    dA, dB = iso_map[dA_str], iso_map[dB_str]
    st.caption(f"Δ shows B – A · red = higher · green = lower")

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
                f"{dA_str}": (fmt_num(vA, mult) if vA is not None else "—") + ("" if stA == "normal" or stA == "—" else f" ({stA.upper()})"),
                f"{dB_str}": (fmt_num(vB, mult) if vB is not None else "—") + ("" if stB == "normal" or stB == "—" else f" ({stB.upper()})"),
                "Δ (B − A)": delta,
                "Reference": f"{fmt_range(p)} {unit}",
            })
        if rows:
            st.markdown(f"**{panel}**")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# -------- Full Table tab --------
with tab_table:
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    panel_t = col1.selectbox("Panel", ["All"] + PANELS, key="tbl_panel")
    search = col2.text_input("Search parameter", "", key="tbl_search")
    period_t = col3.selectbox("Period", ["All time", "Last 30 days", "Last 90 days", "Last 6 months", "Last 1 year"], key="tbl_period")
    order_t = col4.selectbox("Date order", ["Newest → Oldest", "Oldest → Newest"], key="tbl_order")

    sel = params_df.copy()
    if panel_t != "All":
        sel = sel[sel["panel"] == panel_t]
    if search:
        sel = sel[sel["name"].str.lower().str.contains(search.lower())]

    dates = sorted(ALL_DATES)
    if period_t != "All time":
        cutoff = max(dates) - pd.Timedelta(days={"Last 30 days": 30, "Last 90 days": 90,
                                                  "Last 6 months": 180, "Last 1 year": 365}[period_t])
        dates = [d for d in dates if d >= cutoff]
    if order_t == "Newest → Oldest":
        dates = list(reversed(dates))

    if not sel.empty and dates:
        table_rows = []
        for _, p in sel.iterrows():
            mult, unit = display_info(p)
            row = {"Parameter": p["name"], "Unit": unit, "Reference": fmt_range(p)}
            for d in dates:
                v = readings_df[(readings_df["parameter"] == p["name"]) & (readings_df["test_date"] == d)]["value"]
                if v.empty or pd.isna(v.iloc[0]):
                    row[d.strftime("%d-%b-%Y")] = ""
                else:
                    val = float(v.iloc[0])
                    s = status_of(p, val)
                    formatted = fmt_num(val, mult)
                    if s == "high":
                        formatted = f"⚠ {formatted}"
                    elif s == "low":
                        formatted = f"↓ {formatted}"
                    row[d.strftime("%d-%b-%Y")] = formatted
            table_rows.append(row)
        df_out = pd.DataFrame(table_rows)
        st.dataframe(df_out, use_container_width=True, hide_index=True, height=600)
        st.caption("⚠ = above range · ↓ = below range")
    else:
        st.info("No data to display.")


# Footer
st.divider()
st.caption(f"Built on Streamlit + Neon Postgres · Data refreshes on each browser reload (cached 5 min) · {len(ALL_DATES)} dates, {len(params_df)} parameters")
