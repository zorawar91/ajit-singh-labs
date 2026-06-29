# Papa's Lab Tracker — Streamlit + Neon Deployment

This folder hosts the same dashboard as the local HTML version, but built with **Streamlit** (Python web app) and backed by a **Neon Postgres** database. Deploy it to **Streamlit Community Cloud** (free) for a password-protected URL you can share.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit app (Overview / Trends / Compare Dates / Full Table) |
| `schema.sql` | Postgres schema for `parameters`, `readings`, `metadata` |
| `sync_to_neon.py` | Loads `../Lab Dashboard/data.json` and writes to Neon |
| `requirements.txt` | Python deps for Streamlit Cloud |
| `.streamlit/secrets.toml.example` | Template for local `secrets.toml` |
| `.gitignore` | Keeps `secrets.toml` out of git |

---

## Step 1 — Create the Neon database

1. Log in to https://console.neon.tech.
2. Create a new project (or pick an existing one). The free tier is fine.
3. From the project dashboard, copy the **connection string** — looks like:
   `postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
4. (Optional) Create a dedicated DB or schema if you don't want this to share with your other project. By default Neon gives you a `neondb` database — using it is fine.

## Step 2 — Configure local secrets

```bash
cd "Streamlit Dashboard/.streamlit"
cp secrets.toml.example secrets.toml
```

Edit `.streamlit/secrets.toml` with your real values:

```toml
neon_db = "postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require"
app_password = "K7r$mPe9-vBz!2x"   # what you'll share with doctor / family
```

> The `.gitignore` keeps this file out of git. Never commit it.

## Step 3 — Push data from Excel → Neon

```bash
cd "Streamlit Dashboard"
python3 sync_to_neon.py
```

This reads `../Lab Dashboard/data.json` (regenerate it first via `rebuild_data.command` in the Lab Dashboard folder if you've updated the Excel) and writes the schema + all parameters + readings into Neon. Safe to re-run; it truncates and rewrites.

## Step 4 — Test locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Visit `http://localhost:8501`. Enter the password from `secrets.toml`. You should see the full dashboard.

## Step 5 — Push to a private GitHub repo

```bash
# From the Streamlit Dashboard folder
git init
git add .
git commit -m "Initial Streamlit lab tracker"
# Create a private repo on GitHub, then:
git remote add origin git@github.com:YOUR-USERNAME/papa-lab-tracker.git
git branch -M main
git push -u origin main
```

> Use a **private** GitHub repo. `.gitignore` keeps `secrets.toml` out, but a private repo is safer.

## Step 6 — Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io
2. Click **New app** → connect your GitHub account if you haven't.
3. Pick the private repo, branch `main`, main file `app.py`.
4. Click **Advanced settings** → **Secrets** → paste the contents of your `secrets.toml`:
   ```toml
   neon_db = "postgresql://..."
   app_password = "K7r$mPe9-vBz!2x"
   ```
5. Click **Deploy**.

After ~2 minutes you'll get a URL like `https://papa-lab-tracker.streamlit.app`. Anyone visiting sees the password lock screen first.

## When labs are updated

1. Update the Excel tracker.
2. Run `rebuild_data.command` in the Lab Dashboard folder (regenerates `data.json`).
3. `cd "Streamlit Dashboard" && python3 sync_to_neon.py` (pushes new data to Neon).
4. Visit the Streamlit Cloud app — it'll show the new data within the cache TTL (5 min), or click "Rerun" to refresh immediately.

No code changes or re-deploy needed for data updates — only when you change `app.py` itself.

## Sharing access

Send the doctor / family member:
- The Streamlit URL (e.g. `https://papa-lab-tracker.streamlit.app`)
- The password (separately — different channel)

To revoke access: change `app_password` in the Streamlit Cloud Secrets UI and re-share.

## Security notes

- Password is checked server-side with constant-time comparison.
- Neon connection happens server-side; the connection string is never exposed to the browser.
- Streamlit Cloud serves over HTTPS by default.
- The data is in your Neon DB, behind Neon's auth + your own app password.
- Anyone with the GitHub repo URL (private) and the Streamlit Cloud secrets cannot access the data without the app password.
