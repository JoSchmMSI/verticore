"""
Verticore — SMB Count Scraper
=============================
Pulls live Structural Business Statistics (SBS) enterprise counts from the
Eurostat API for the four seed verticals, per country, with size-class filter.

This is Verticore's market-BASE layer: the number of SMBs per vertical, per
country, per year. It reuses the proven ingestion pattern from MSI's
nace_scraper.py (chunked writes, retries, explicit timeouts, resize-before-write).

Fetches enterprise COUNTS (indicator ENT_NR) from dataset sbs_sc_ovw, which
carries the size-class dimension we need to isolate SMBs (< 250 employees).

Writes to Google Sheet tab: "SMB Base"
Reads vertical -> NACE config from Google Sheet tab: "Vertical Config"

Seed verticals:
  - Beauty          (NACE 96.02, 96.04)
  - Renovation      (NACE 43.x specialized construction)
  - Repair          (NACE 45.20, 95.x)
  - Fitness Clubs   (NACE 93.12, 93.13, 94.99)

Data source: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data
"""

import requests
import json
import os
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ── Sheet config — set via GitHub secret / env, no hardcoded ID ────────────────
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

# ── Geography: EU27 + Norway + UK (matches Verticore's coverage) ───────────────
# (alpha-2 API code, alpha-3 store code)
COUNTRIES = [
    ('AT','AUT'),('BE','BEL'),('BG','BGR'),('CY','CYP'),('CZ','CZE'),
    ('DE','DEU'),('DK','DNK'),('EE','EST'),('ES','ESP'),('FI','FIN'),
    ('FR','FRA'),('HR','HRV'),('HU','HUN'),('IE','IRL'),('IT','ITA'),
    ('LT','LTU'),('LU','LUX'),('LV','LVA'),('MT','MLT'),('NL','NLD'),
    ('PL','POL'),('PT','PRT'),('RO','ROU'),('SE','SWE'),('SI','SVN'),
    ('SK','SVK'),('NO','NOR'),
]
# UK left out of SBS by default (not in EU datasets post-Brexit for many series);
# handled gracefully — if a country returns nothing, it is simply skipped.

# ── Seed vertical -> NACE config (fallback if sheet config is empty) ────────────
# NACE codes use the Eurostat API format (letter prefix + digits, no dots).
DEFAULT_VERTICAL_CONFIG = {
    "Beauty": [
        {"code": "S9602", "label": "Hairdressing and other beauty treatment"},
    ],
    "Renovation": [
        {"code": "F4321", "label": "Electrical installation"},
        {"code": "F4322", "label": "Plumbing, heat and air-conditioning installation"},
        {"code": "F4329", "label": "Other construction installation"},
        {"code": "F4331", "label": "Plastering"},
        {"code": "F4332", "label": "Joinery installation"},
        {"code": "F4333", "label": "Floor and wall covering"},
        {"code": "F4334", "label": "Painting and glazing"},
        {"code": "F4339", "label": "Other building completion and finishing"},
    ],
    "Repair": [
        {"code": "G4520", "label": "Maintenance and repair of motor vehicles"},
        {"code": "S9521", "label": "Repair of consumer electronics"},
        {"code": "S9522", "label": "Repair of household appliances and home/garden equipment"},
        {"code": "S9529", "label": "Repair of other personal and household goods"},
    ],
    "Fitness Clubs": [
        {"code": "R9312", "label": "Activities of sport clubs"},
        {"code": "R9313", "label": "Fitness facilities"},
        {"code": "S9499", "label": "Activities of other membership organisations n.e.c."},
    ],
}

# ── Eurostat SBS API ───────────────────────────────────────────────────────────
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# sbs_sc_ovw = Enterprise statistics by size class and NACE Rev.2 (2021 onwards).
# indic_sbs = ENT_NR (number of enterprises).
# size_clas: we pull the SMB-relevant classes and the total, so the engine can
# isolate < 250-employee businesses. Eurostat size classes for SBS:
#   TOTAL, 0-1, 2-9, 10-19, 20-49, 50-249, GE250 (availability varies by country)
SBS_DATASET   = "sbs_sc_ovw"
SBS_INDICATOR = "ENT_NR"          # number of enterprises
# SMB = everything below 250 employees. We request TOTAL and GE250 so SMB can be
# derived as TOTAL - GE250 (robust even when granular bands are suppressed), and
# also request the granular SMB bands where available for transparency.
SIZE_CLASSES = ["TOTAL", "GE250"]

def fetch_sbs(nace_code, geo_api, size_class):
    """
    Fetch enterprise count from Eurostat SBS. Returns {year: value} or {}.
    Explicit timeout prevents infinite hang (proven pattern from MSI scraper).
    """
    url = (
        f"{EUROSTAT_BASE}/{SBS_DATASET}"
        f"?format=JSON&lang=EN"
        f"&nace_r2={nace_code}"
        f"&indic_sbs={SBS_INDICATOR}"
        f"&size_clas={size_class}"
        f"&geo={geo_api}"
        f"&sinceTimePeriod=2018"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 400:
            # retry without time filter — some cells reject sinceTimePeriod
            r = requests.get(url.replace("&sinceTimePeriod=2018", ""), timeout=30)
        if r.status_code != 200:
            return {}
        return r.json()
    except requests.exceptions.Timeout:
        print(f"      TIMEOUT {nace_code}/{geo_api}/{size_class} — skipping")
        return {}
    except Exception as e:
        print(f"      Error {nace_code}/{geo_api}/{size_class}: {e}")
        return {}

def parse_response(data):
    """Extract {year: value} from Eurostat JSON-stat. Proven MSI pattern."""
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

def compute_yoy(series, year):
    try:
        prev = str(int(year) - 1)
        if prev in series and series[prev] != 0:
            return round((series[year] - series[prev]) / abs(series[prev]) * 100, 2)
    except Exception:
        pass
    return ""

def load_vertical_config(client):
    """Load vertical->NACE config from sheet; fall back to defaults."""
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet("Vertical Config")
        rows = ws.get_all_records()
        if not rows:
            return None
        config = {}
        for row in rows:
            vertical = str(row.get("Vertical", "")).strip()
            codes    = str(row.get("NACE Codes", "")).strip()
            active   = str(row.get("Active", "yes")).strip().lower()
            if vertical and codes and active in ("yes", "true", "1"):
                for code in [c.strip() for c in codes.split(";") if c.strip()]:
                    code_clean = code.replace(".", "").upper()
                    config.setdefault(vertical, []).append(
                        {"code": code_clean, "label": ""}
                    )
        return config if config else None
    except Exception as e:
        print(f"  Warning: could not load Vertical Config: {e}")
        return None

def ensure_smb_base_tab(client):
    sh = client.open_by_key(SHEET_ID)
    try:
        sh.worksheet("SMB Base")
        print("  SMB Base tab exists.")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="SMB Base", rows=8000, cols=10)
        headers = ["Vertical", "NACE Code", "NACE Label", "Geo", "Year",
                   "Enterprise Count", "Size Class", "YoY %", "Updated"]
        ws.update("A1:I1", [headers])
        ws.format("A1:I1", {"textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.15, "green": 0.20, "blue": 0.28}})
        print("  Created SMB Base tab.")

def write_rows_chunked(ws, all_rows, last_col="I"):
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
    print("Verticore — SMB Count Scraper v1.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Verticals: Beauty | Renovation | Repair | Fitness Clubs")
    print("=" * 60)

    if not SHEET_ID:
        print("\nFATAL: VERTICORE_SHEET_ID env var not set. Aborting.")
        return

    print("\n[1/4] Connecting to Google Sheets...")
    client = get_sheet_client()
    ensure_smb_base_tab(client)
    print("  Connected.")

    print("\n[2/4] Loading vertical configuration...")
    config = load_vertical_config(client)
    if config:
        # merge sheet labels with default labels where sheet omits them
        for v, entries in config.items():
            defaults = {e["code"]: e["label"] for e in DEFAULT_VERTICAL_CONFIG.get(v, [])}
            for e in entries:
                if not e["label"]:
                    e["label"] = defaults.get(e["code"], e["code"])
        print(f"  Loaded from sheet: {sum(len(v) for v in config.values())} codes across {len(config)} verticals")
    else:
        config = DEFAULT_VERTICAL_CONFIG
        print(f"  Using defaults: {sum(len(v) for v in config.values())} codes across {len(config)} verticals")

    all_geos = list(COUNTRIES)
    est_calls = sum(len(v) for v in config.values()) * len(all_geos) * len(SIZE_CLASSES)
    print(f"\n  Estimated API calls: {est_calls}")
    print(f"  Estimated runtime:   ~{int(est_calls * 0.15 // 60)}m at 0.15s/call")

    print("\n[3/4] Fetching Eurostat SBS data...")
    all_rows   = []
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    for vertical, nace_list in config.items():
        print(f"\n  -- {vertical} ({len(nace_list)} codes) --")
        for entry in nace_list:
            code  = entry["code"]
            label = entry["label"]
            rows_before = len(all_rows)
            for gi, (geo_api, geo_store) in enumerate(all_geos):
                if gi % 5 == 1:
                    print(f"    {code}: processing {geo_store}... ({len(all_rows)} rows so far)")
                for size_class in SIZE_CLASSES:
                    data   = fetch_sbs(code, geo_api, size_class)
                    series = parse_response(data)
                    if not series:
                        continue
                    for year in sorted(series.keys())[-5:]:
                        all_rows.append([
                            vertical, code, label, geo_store, year,
                            series[year], size_class, compute_yoy(series, year),
                            updated_at,
                        ])
                time.sleep(0.15)
            print(f"    {code}: {len(all_rows) - rows_before} new rows")

    print(f"\n  Total rows collected: {len(all_rows)}")

    print(f"\n[4/4] Writing to SMB Base tab...")
    if all_rows:
        ws = client.open_by_key(SHEET_ID).worksheet("SMB Base")
        print("  Clearing existing data rows...")
        ws.batch_clear(["A2:I8000"])
        time.sleep(1)
        needed = len(all_rows) + 10
        if ws.row_count < needed:
            ws.add_rows(needed - ws.row_count + 100)
        written = write_rows_chunked(ws, all_rows)
        countries = len(set(r[3] for r in all_rows))
        print(f"\n  Countries with data: {countries}")
        print(f"  Total rows written:  {written}")
    else:
        print("  No data collected — sheet not updated.")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
