#!/usr/bin/env python3
"""Sync data.json (from Lab Dashboard folder) into a Neon Postgres database.

Usage:
    NEON_CONNECTION_STRING="postgresql://..." python3 sync_to_neon.py
  OR (if you have .streamlit/secrets.toml with neon_db = "postgresql://..."):
    python3 sync_to_neon.py
"""
import json
import os
import sys
import re
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("Installing psycopg (Postgres driver)…")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--quiet", "psycopg[binary]"])
    import psycopg

HERE = Path(__file__).parent
DATA_JSON = HERE.parent / "Lab Dashboard" / "data.json"
SCHEMA_SQL = HERE / "schema.sql"


def load_conn_string():
    # 1. Environment variable
    cs = os.environ.get("NEON_CONNECTION_STRING")
    if cs:
        return cs
    # 2. Streamlit secrets file
    secrets = HERE / ".streamlit" / "secrets.toml"
    if secrets.exists():
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                # Auto-install the toml backport for older Pythons
                print("Installing tomli (TOML parser for older Python)…")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--quiet", "tomli"])
                import tomli as tomllib
        with open(secrets, "rb") as f:
            data = tomllib.load(f)
        cs = data.get("neon_db") or data.get("NEON_CONNECTION_STRING")
        if cs:
            return cs
    raise SystemExit(
        "ERROR: No Neon connection string found.\n"
        "Set NEON_CONNECTION_STRING env var, or add neon_db = \"...\" to .streamlit/secrets.toml"
    )


def main():
    if not DATA_JSON.exists():
        raise SystemExit(f"ERROR: {DATA_JSON} not found. Run rebuild_data.command in Lab Dashboard first.")
    print(f"Loading: {DATA_JSON}")
    payload = json.loads(DATA_JSON.read_text())
    print(f"  {len(payload['dates'])} dates × {len(payload['parameters'])} parameters")

    cs = load_conn_string()
    print(f"Connecting to Neon…")
    with psycopg.connect(cs) as conn:
        with conn.cursor() as cur:
            # Schema
            print("Ensuring schema…")
            cur.execute(SCHEMA_SQL.read_text())

            # Wipe & rewrite (small dataset, easier than diffing)
            cur.execute("TRUNCATE readings, parameters RESTART IDENTITY CASCADE")

            # Upsert parameters
            print("Inserting parameters…")
            param_ids = {}
            for p in payload["parameters"]:
                cur.execute(
                    """INSERT INTO parameters (name, unit, reference_range, panel, lo, hi)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (p["name"], p.get("unit"), p.get("range"), p.get("panel"), p.get("lo"), p.get("hi")),
                )
                param_ids[p["name"]] = cur.fetchone()[0]

            # Insert readings
            print("Inserting readings…")
            n_readings = 0
            for p in payload["parameters"]:
                pid = param_ids[p["name"]]
                rows = []
                for date_iso, v in p.get("values", {}).items():
                    # Validate date
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_iso):
                        continue
                    if isinstance(v, (int, float)):
                        rows.append((pid, date_iso, v, None))
                    else:
                        rows.append((pid, date_iso, None, str(v)))
                if rows:
                    cur.executemany(
                        "INSERT INTO readings (parameter_id, test_date, value, text_value) VALUES (%s, %s, %s, %s)",
                        rows,
                    )
                    n_readings += len(rows)
            print(f"  inserted {n_readings} readings")

            # Metadata
            print("Updating metadata…")
            meta = {
                "title": payload.get("title", ""),
                "subtitle": payload.get("subtitle", ""),
                "charted_json": json.dumps(payload.get("charted", [])),
                "panels_json": json.dumps(payload.get("panels", [])),
            }
            cur.execute("TRUNCATE metadata")
            for k, v in meta.items():
                cur.execute("INSERT INTO metadata (key, value) VALUES (%s, %s)", (k, v))

        conn.commit()
    print("✓ Sync complete.")


if __name__ == "__main__":
    main()
