"""
Verticore — Adoption Scraper  v2.0  (fixed 19 Jul 2026)
========================================================
Pulls live website-adoption data from Eurostat ICT surveys.

Key fixes from v1.0 (confirmed via live API diagnostic):
  Adoption tab   (isoc_ciwebn2):
    - NACE group per vertical updated:
        Renovation  → F            (direct match, confirmed ✓)
        others      → C10-S951_X_K (broad aggregate, only one that works)
  Adoption Sizeclass tab (isoc_ciweb):
    - NACE group:  G-N_S951_X_K → C10-S951_X_K  (only one that works)
    - Size codes:  underscores   → hyphens
        10_49  → 10-49  ✓
        50_249 → 50-249 ✓
        GE10   stays   ✓
        GE250  stays   ✓

Writes:
  "Adoption"           — headline % per (vertical × country × year)
  "Adoption Sizeclass" — size-class gradient (the micro-adjustment anchor)
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
    raw   = os.environ.get("GOOGLE_CREDENTIALS_JSON", "{}")
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

# ── Confirmed working NACE adoption groups (from live diagnostic) ──────────────
# Renovation → F  (construction, direct match, confirmed ✓)
# All others → C10-S951_X_K (broad services aggregate, only one that returns data)
# S96 (personal services — ideal for beauty) returns zero values on isoc_ciwebn2
DEFAULT_ADOPTION_GROUP = {
    "Beauty":        "C10-S951_X_K",
    "Renovation":    "F",
    "Repair":        "C10-S951_X_K",
    "Fitness Clubs": "C10-S951_X_K",
}

EUROSTAT_BASE      = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ADOPTION_BY_NACE   = "isoc_ciwebn2"   # website adoption by NACE
ADOPTION_BY_SIZE   = "isoc_ciweb"     # website adoption by size class
ADOPTION_INDICATOR = "E_WEB"
ADOPTION_UNIT      = "PC_ENT"

# Confirmed working size codes — hyphens required, NOT underscores:
SIZE_CLASSES = ["GE10", "10-49", "50-249", "GE250"]

def fetch_eurostat(dataset, extra_params, geo_api):
    url = (
        f"{EUROSTAT_BASE}/{dataset}"
        f"?format=JSON&lang=EN"
        f"&indic_is={ADOPTION_INDICATOR}"
        f"&unit={ADOPTION_UNIT}"
        f"&geo={geo_api}"
        f"{extra_params}"
        f"&sinceTimePeriod=2019"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 400:
            r = requests.get(url.replace("&sinceTimePeriod=2019", ""), timeout=30)
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
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet("Vertical Config")
        rows = ws.get_all_records()
        groups = {}
        for row in rows:
            v      = str(row.get("Vertical", "")).strip()
            grp    = str(row.get("NACE Adoption Group", "")).strip()
            active = str(row.get("Active", "yes")).strip().lower()
            if v and grp and active in ("yes", "true", "1"):
                groups[v] = grp
        return groups if groups else None
    except Exception as e:
        print(f"  Warning: could not load adoption groups: {e}")
        return None

def ensure_tabs(client):
    sh = client.open_by_key(SHEET_ID)
    for title, headers in [
        ("Adoption",
         ["Vertical","NACE Group","Geo","Year","Indicator","Adoption %","Updated"]),
        ("Adoption Sizeclass",
         ["Geo","NACE Group","Size Class","Year","Indicator","Value %","Updated"]),
    ]:
        try:
            sh.worksheet(title)
            print(f"  {title}: exists.")
        except gspread.WorksheetNotFound:
            last = chr(ord("A") + len(headers) - 1)
            ws   = sh.add_worksheet(title=title, rows=6000, cols=len(headers))
            ws.update(f"A1:{last}1", [headers])
            ws.format(f"A1:{last}1", {"textFormat": {"bold": True}})
            print(f"  {title}: created.")

def write_rows_chunked(ws, all_rows, last_col):
    total   = len(all_rows)
    written = 0
    for i in range(0, total, WRITE_CHUNK_SIZE):
        chunk     = all_rows[i:i + WRITE_CHUNK_SIZE]
        start_row = i + 2
        end_row   = start_row + len(chunk) - 1
        for attempt in range(3):
            try:
                ws.update(chunk, f"A{start_row}:{last_col}{end_row}")
                written += len(chunk)
                time.sleep(0.3)
                break
            except Exception as e:
                print(f"    Attempt {attempt+1} failed: {e}")
                time.sleep(2)
    return written

def run_scraper():
    print("=" * 60)
    print("Verticore — Adoption Scraper v2.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not SHEET_ID:
        print("\nFATAL: VERTICORE_SHEET_ID not set. Aborting.")
        return

    print("\n[1/5] Connecting...")
    client = get_sheet_client()
    ensure_tabs(client)

    print("\n[2/5] Loading adoption group mapping...")
    groups = load_adoption_groups(client) or DEFAULT_ADOPTION_GROUP
    for v, g in groups.items():
        print(f"  {v} → {g}")

    distinct_groups = sorted(set(groups.values()))
    all_geos        = list(COUNTRIES)
    updated_at      = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Pass 1: headline adoption per (vertical × country) ────────────────────
    print("\n[3/5] Fetching headline adoption (isoc_ciwebn2 by NACE group)...")
    adoption_rows = []
    for vertical, grp in groups.items():
        print(f"\n  -- {vertical} (group={grp}) --")
        for gi, (geo_api, geo_store) in enumerate(all_geos):
            if gi % 6 == 1:
                print(f"    {geo_store}... ({len(adoption_rows)} rows)")
            data   = fetch_eurostat(ADOPTION_BY_NACE, f"&nace_r2={grp}", geo_api)
            series = parse_response(data)
            for year in sorted(series.keys())[-4:]:
                adoption_rows.append([
                    vertical, grp, geo_store, year,
                    ADOPTION_INDICATOR, series[year], updated_at,
                ])
            time.sleep(0.15)

    # ── Pass 2: size-class gradient (C10-S951_X_K confirmed only working NACE) –
    print("\n[4/5] Fetching size-class gradient (isoc_ciweb by size)...")
    print("      NACE: C10-S951_X_K | Sizes: GE10, 10-49, 50-249, GE250")
    sizeclass_rows = []
    grp = "C10-S951_X_K"   # only NACE group confirmed working for isoc_ciweb
    for gi, (geo_api, geo_store) in enumerate(all_geos):
        if gi % 6 == 1:
            print(f"    {geo_store}... ({len(sizeclass_rows)} rows)")
        for size_class in SIZE_CLASSES:
            data   = fetch_eurostat(
                ADOPTION_BY_SIZE,
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

    print(f"\n  Adoption rows:       {len(adoption_rows)}")
    print(f"  Sizeclass rows:      {len(sizeclass_rows)}")

    print("\n[5/5] Writing to sheet...")
    sh = client.open_by_key(SHEET_ID)

    if adoption_rows:
        ws = sh.worksheet("Adoption")
        ws.batch_clear(["A2:G6000"])
        time.sleep(1)
        if ws.row_count < len(adoption_rows) + 10:
            ws.add_rows(len(adoption_rows) + 100)
        n = write_rows_chunked(ws, adoption_rows, "G")
        print(f"  Adoption: {n} rows written")

    if sizeclass_rows:
        ws = sh.worksheet("Adoption Sizeclass")
        ws.batch_clear(["A2:G6000"])
        time.sleep(1)
        if ws.row_count < len(sizeclass_rows) + 10:
            ws.add_rows(len(sizeclass_rows) + 100)
        n = write_rows_chunked(ws, sizeclass_rows, "G")
        print(f"  Sizeclass: {n} rows written")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
