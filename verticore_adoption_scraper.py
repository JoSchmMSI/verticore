"""
Verticore — Adoption Scraper
============================
Pulls live web-adoption data from Eurostat's ICT-usage-in-enterprises survey,
per country, for the NACE groups mapped to each vertical.

Writes TWO tabs, because the AI micro-enterprise adjustment must be anchored to
real Eurostat data, not invented:

  1. "Adoption"           — headline web-adoption % per (vertical NACE group x
                            country x year). The base adoption figure.
  2. "Adoption Sizeclass" — the SAME indicator broken down BY SIZE CLASS per
                            country. This is the empirical size gradient the AI
                            layer uses to bridge the sector figure down to
                            micro-enterprise reality. Because it is real, live,
                            per-country data, the micro-adjustment is grounded,
                            not guessed.

Datasets used (all live, per-country, updated end of each survey year):
  isoc_ciwebn2 — "Enterprises having a website" by NACE Rev.2 activity
  isoc_ciweb   — same indicator by SIZE CLASS of enterprise (the gradient)

Indicator code: E_WEB  (enterprises with a website)

Data source: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data
"""

import requests
import json
import os
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("VERTICORE_SHEET_ID", "").strip()
SCOPES   = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
WRITE_CHUNK_SIZE = 200

def get_sheet_client():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "{}")
    creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return gspread.authorize(creds)

COUNTRIES = [
    ('AT','AUT'),('BE','BEL'),('BG','BGR'),('CY','CYP'),('CZ','CZE'),
    ('DE','DEU'),('DK','DNK'),('EE','EST'),('ES','ESP'),('FI','FIN'),
    ('FR','FRA'),('HR','HRV'),('HU','HUN'),('IE','IRL'),('IT','ITA'),
    ('LT','LTU'),('LU','LUX'),('LV','LVA'),('MT','MLT'),('NL','NLD'),
    ('PL','POL'),('PT','PRT'),('RO','ROU'),('SE','SWE'),('SI','SVN'),
    ('SK','SVK'),('NO','NOR'),
]

# ── Vertical -> best-available NACE adoption group ─────────────────────────────
# Eurostat's ICT survey publishes adoption at AGGREGATED NACE groupings, not at
# the fine SBS code level. Each vertical is mapped to the closest published
# group. This mapping is transparent and lives in "Vertical Config" (column
# "NACE Adoption Group") so it is visible and editable; these are the fallbacks.
#
# Published ICT-survey NACE groups relevant here (isoc_ciwebn2 breakdowns):
#   G-N_S951_X_K  Services (broad, the widest SMB-services aggregate)
#   F             Construction  -> Renovation
#   G47           Retail trade
#   I             Accommodation & food
#   Note: very fine service verticals (hairdressing, sport clubs) are NOT
#   separately published; they fall under broad service aggregates. The app is
#   transparent that these are sector proxies (see engine + UI).
DEFAULT_ADOPTION_GROUP = {
    "Beauty":        "G-N_S951_X_K",   # services aggregate (no finer beauty cell published)
    "Renovation":    "F",              # construction — a real, direct match
    "Repair":        "G-N_S951_X_K",   # services aggregate (auto+goods repair spread across G/S)
    "Fitness Clubs": "G-N_S951_X_K",   # services aggregate (no sport-club cell published)
}

# ── Eurostat ICT API ───────────────────────────────────────────────────────────
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

ADOPTION_DATASET_BYNACE = "isoc_ciwebn2"   # website adoption by NACE activity
ADOPTION_DATASET_BYSIZE = "isoc_ciweb"     # website adoption by size class
ADOPTION_INDICATOR      = "E_WEB"          # enterprises having a website

# Size classes for the gradient. Eurostat ICT size classes:
#   GE10 (10+, the survey base), 10_49 (small), 50_249 (medium), GE250 (large)
# Micro (0-9) is optional/patchy in the survey; where a country lacks small-band
# data the engine falls back gracefully. We store every band that returns data.
SIZE_CLASSES = ["GE10", "10_49", "50_249", "GE250"]

def fetch_eurostat(dataset, extra_params, geo_api):
    """Generic Eurostat fetch with proven timeout/retry pattern."""
    base = (
        f"{EUROSTAT_BASE}/{dataset}"
        f"?format=JSON&lang=EN"
        f"&indic_is={ADOPTION_INDICATOR}"
        f"&unit=PC_ENT"
        f"&geo={geo_api}"
        f"{extra_params}"
        f"&sinceTimePeriod=2019"
    )
    try:
        r = requests.get(base, timeout=30)
        if r.status_code == 400:
            r = requests.get(base.replace("&sinceTimePeriod=2019", ""), timeout=30)
        if r.status_code != 200:
            return {}
        return r.json()
    except requests.exceptions.Timeout:
        print(f"      TIMEOUT {dataset}/{geo_api} — skipping")
        return {}
    except Exception as e:
        print(f"      Error {dataset}/{geo_api}: {e}")
        return {}

def parse_response(data):
    if not data or "value" not in data:
        return {}
    try:
        time_cats = list(data["dimension"]["time"]["category"]["index"].keys())
        values    = data["value"]
        result    = {}
        for i, t in enumerate(time_cats):
            v = values.get(str(i))
            if v is not None:
                result[t] = round(float(v), 2)
        return result
    except Exception as e:
        print(f"      Parse error: {e}")
        return {}

def load_adoption_groups(client):
    """Read vertical -> adoption NACE group from Vertical Config; fall back."""
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet("Vertical Config")
        rows = ws.get_all_records()
        groups = {}
        for row in rows:
            v     = str(row.get("Vertical", "")).strip()
            grp   = str(row.get("NACE Adoption Group", "")).strip()
            active = str(row.get("Active", "yes")).strip().lower()
            if v and grp and active in ("yes", "true", "1"):
                groups[v] = grp
        return groups if groups else None
    except Exception as e:
        print(f"  Warning: could not load adoption groups: {e}")
        return None

def ensure_tabs(client):
    sh = client.open_by_key(SHEET_ID)
    for title, headers, cols in [
        ("Adoption",
         ["Vertical", "NACE Group", "Geo", "Year", "Indicator", "Adoption %", "Updated"], 8),
        ("Adoption Sizeclass",
         ["Geo", "NACE Group", "Size Class", "Year", "Indicator", "Value %", "Updated"], 8),
    ]:
        try:
            sh.worksheet(title)
            print(f"  {title} tab exists.")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=title, rows=6000, cols=cols)
            last = chr(ord("A") + len(headers) - 1)
            ws.update(f"A1:{last}1", [headers])
            ws.format(f"A1:{last}1", {"textFormat": {"bold": True},
                      "backgroundColor": {"red": 0.15, "green": 0.20, "blue": 0.28}})
            print(f"  Created {title} tab.")

def write_rows_chunked(ws, all_rows, last_col):
    total = len(all_rows)
    print(f"  Writing {total} rows in chunks of {WRITE_CHUNK_SIZE}...")
    written = 0
    for i in range(0, total, WRITE_CHUNK_SIZE):
        chunk     = all_rows[i:i + WRITE_CHUNK_SIZE]
        start_row = i + 2
        end_row   = start_row + len(chunk) - 1
        for attempt in range(3):
            try:
                ws.update(chunk, f"A{start_row}:{last_col}{end_row}")
                written += len(chunk)
                print(f"    Wrote rows {start_row}-{end_row} ({written}/{total})")
                time.sleep(0.3)
                break
            except Exception as e:
                print(f"    Write attempt {attempt+1} failed: {e} — retrying...")
                time.sleep(2)
    return written

def run_scraper():
    print("=" * 60)
    print("Verticore — Adoption Scraper v1.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not SHEET_ID:
        print("\nFATAL: VERTICORE_SHEET_ID env var not set. Aborting.")
        return

    print("\n[1/5] Connecting to Google Sheets...")
    client = get_sheet_client()
    ensure_tabs(client)
    print("  Connected.")

    print("\n[2/5] Loading adoption group mapping...")
    groups = load_adoption_groups(client) or DEFAULT_ADOPTION_GROUP
    for v, g in groups.items():
        print(f"  {v} -> {g}")

    # Distinct NACE groups we actually need (dedupe so we don't refetch the same
    # group for multiple verticals — the sizeclass gradient is per-group).
    distinct_groups = sorted(set(groups.values()))

    all_geos = list(COUNTRIES)

    # ── Pass 1: headline adoption per (vertical group x country) ────────────────
    print("\n[3/5] Fetching headline adoption (by NACE group)...")
    adoption_rows = []
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    for vertical, grp in groups.items():
        print(f"\n  -- {vertical} (group {grp}) --")
        for gi, (geo_api, geo_store) in enumerate(all_geos):
            if gi % 6 == 1:
                print(f"    processing {geo_store}... ({len(adoption_rows)} rows)")
            data   = fetch_eurostat(ADOPTION_DATASET_BYNACE, f"&nace_r2={grp}", geo_api)
            series = parse_response(data)
            for year in sorted(series.keys())[-4:]:
                adoption_rows.append([
                    vertical, grp, geo_store, year,
                    ADOPTION_INDICATOR, series[year], updated_at,
                ])
            time.sleep(0.15)

    # ── Pass 2: size-class gradient per (distinct group x country x size) ───────
    print("\n[4/5] Fetching size-class gradient (the AI-adjustment foundation)...")
    sizeclass_rows = []
    for grp in distinct_groups:
        print(f"\n  -- group {grp} --")
        for gi, (geo_api, geo_store) in enumerate(all_geos):
            if gi % 6 == 1:
                print(f"    processing {geo_store}... ({len(sizeclass_rows)} rows)")
            for size_class in SIZE_CLASSES:
                data   = fetch_eurostat(
                    ADOPTION_DATASET_BYSIZE,
                    f"&nace_r2={grp}&size_emp={size_class}",
                    geo_api,
                )
                series = parse_response(data)
                for year in sorted(series.keys())[-4:]:
                    sizeclass_rows.append([
                        geo_store, grp, size_class, year,
                        ADOPTION_INDICATOR, series[year], updated_at,
                    ])
            time.sleep(0.15)

    print(f"\n  Adoption rows:  {len(adoption_rows)}")
    print(f"  Sizeclass rows: {len(sizeclass_rows)}")

    print("\n[5/5] Writing to sheet...")
    sh = client.open_by_key(SHEET_ID)
    if adoption_rows:
        ws = sh.worksheet("Adoption")
        ws.batch_clear(["A2:G6000"]); time.sleep(1)
        if ws.row_count < len(adoption_rows) + 10:
            ws.add_rows(len(adoption_rows) + 100)
        write_rows_chunked(ws, adoption_rows, "G")
    if sizeclass_rows:
        ws = sh.worksheet("Adoption Sizeclass")
        ws.batch_clear(["A2:G6000"]); time.sleep(1)
        if ws.row_count < len(sizeclass_rows) + 10:
            ws.add_rows(len(sizeclass_rows) + 100)
        write_rows_chunked(ws, sizeclass_rows, "G")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
