# Design System — Papa's Lab Tracker

## Product context
A private, password-protected Streamlit dashboard that tracks one cancer
patient's (cholangiocarcinoma) blood-test results over time from a Neon
Postgres database. Built by a family member, shared with the treating doctor
and other family via a Streamlit Cloud URL + shared password. No PHI lives in
the git repo — only in the DB behind the app password.

## Audiences & JTBD (this drives every layout decision)
1. **Family member (non-clinical)** — opens the link anxious, wants a fast
   plain-language read: "is he better or worse since last time?" Needs calm,
   non-alarming visual language, minimal jargon up front, and confidence the
   number they're looking at is good/bad without decoding units.
2. **Treating doctor** — opens it during or before a consult, wants to scan
   real values, trends, and validated clinical scores (MELD-Na, ALBI, mGPS,
   CA 19-9 trajectory) quickly, cross-check against reference ranges, and
   drill into the raw table if needed. Needs density and precision, not
   simplification — but easy to navigate under time pressure.
3. Both audiences currently get the **same undifferentiated wall of content**
   on the Overview tab (16+ insight categories, jargon like "R-factor" and
   "CIPI" sitting next to plain descriptions). The redesign's central tension
   to resolve: serve both without dumbing down for the doctor or overwhelming
   the family member — progressive disclosure (plain summary first,
   technical detail one click away) rather than one flat wall of cards.

## Key pages / tabs
- **Auth gate** — currently a bare password form, no branding, no context.
  First impression for every visitor; worth a deliberate redesign.
- **Overview** (default landing) — Clinical Watch, Clinical Insights, Unique
  (oncology-specific) Insights, Latest Results grid, Key Trends charts.
- **Trends** — self-service chart browser (Panel/Parameter/Period filters).
- **Compare Trends** — up to 5 parameters overlaid, normalized to % of upper
  reference limit.
- **Compare Dates** — point-in-time diff between any two report dates.
- **Full Table** — every parameter × every date, doctor's audit view.

## Feature requirement for this pass: unified time-range control
Three tabs (Trends, Compare Trends, Full Table) each currently reimplement
their own `Period` selectbox with inconsistent buckets
(`All time / Last 30 days / Last 90 days / Last 6 months / Last 1 year`).
Standardize to **3 months / 6 months / 9 months / 1 year / All time**, backed
by real `readings.test_date` data (already dated, real historical readings —
this is NOT decorative). Treat it as one first-class, prominent, consistently
placed control — not three near-duplicate small dropdowns. See
`extractable-components.md` → PeriodFilter for the current 3 call sites.

## Current baseline tokens (ground truth for the Step 3a reproduction)
Full detail in `.superdesign/init/theme.md`. Summary: primary blue `#2563eb`,
white/`#f8fafc` card surfaces, `#e2e8f0` borders, status triad red `#ef4444`
(high) / amber `#f59e0b` (low) / green `#22c55e` (normal), flat cards (no
shadows), 10-12px radii, Streamlit-default sans-serif, pinned light theme.

## Direction for the new visual style (this pass explores away from baseline)
The user explicitly wants to move past the current look (flat, dense,
spreadsheet-adjacent), while staying appropriate for a sensitive medical
context shared with an oncologist. Constraints for ANY new direction explored:
- **Calm, trustworthy, clinical — not clinical-cold or consumer-flashy.**
  Avoid alarming saturated reds/greens as decoration; reserve strong color
  for genuine status signal (out-of-range values), not chrome.
- **Colorblind-safe status encoding** — status must not rely on hue alone
  (pair color with icon/label/position, as the current pill text already
  does — keep that principle).
- **Legible for an older, non-technical reader** at arm's length (a family
  member on a phone) AND scannable at a glance by a doctor. Generous type
  scale, high contrast, no dense unlabeled walls of cards.
- **Progressive disclosure**: a plain-language summary layer for family,
  full clinical detail (scores, ranges, jargon) available but not forced on
  first view — e.g. collapse/expand, tabs, or a role toggle.
- **Trust and provenance cues**: reference ranges, dates, and "not medical
  advice / discuss with your oncologist" framing must stay visible, not
  buried — this is a clinical-adjacent tool, not a lifestyle app.
- Two variations should each commit to ONE coherent point of view rather
  than blend directions (e.g. "warm/human editorial calm" vs. "precise
  clinical-grade dashboard") — per Superdesign's variant rules, do not mix.

## Motion
None currently. Subtle, purposeful only (e.g. a value transition, an expand/
collapse) — never decorative animation in a medical context.
