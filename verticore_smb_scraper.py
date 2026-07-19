"""
Verticore — SMB Count Scraper  v2.0  (fixed 19 Jul 2026)
=========================================================
Pulls enterprise counts from Eurostat's sbs_ovw_act dataset
(Enterprises by detailed NACE Rev.2 activity).

Key fixes from v1.0:
  - Dataset: sbs_sc_ovw → sbs_ovw_act  (confirmed via live API diagnostic)
  - Indicator param: indic_sbs → INDIC_SBS  (confirmed)
  - NACE format: letter-prefix required (S9602 not 9602, F43 not 4321)
  - sbs_ovw_act has no size_emp dimension → pulls total enterprise count.
    These verticals are overwhelmingly SMB (hairdressers, small builders,
    repair shops, sports clubs) so total count = SMB proxy. App labels
    this transparently.

Writes to Google Sheet tab: "SMB Base"
Reads vertical config from tab: "Vertical Config"
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

# ── Confirmed working NACE codes (letter-prefix required, division-level) ──────
# Confirmed live: S9602✓ F43✓ G4520✓ R9312✓
# sbs_ovw_act publishes at division/group level, not fine sub-class.
DEFAULT_VERTICAL_CONFIG = {
    "Beauty": [
        {"code": "S9602", "label": "Hairdressing and other beauty treatment"},
    ],
    "Renovation": [
        {"code": "F43",   "label": "Specialised construction activities"},
    ],
    "Repair": [
        {"code": "G4520", "label": "Maintenance and repair of motor vehicles"},
        {"code": "S9521", "label": "Repair of consumer electronics"},
        {"code": "S9522", "label": "Repair of household appliances"},
        {"code": "S9529", "label": "Repair of other personal and household goods"},
    ],
    "Fitness Clubs": [
        {"code": "R9312", "label": "Activities of sport clubs"},
        {"code": "R9313", "label": "Fitness facilities"},
    ],
}

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
SBS_DATASET   = "sbs_ovw_act"   # confirmed: carries fine NACE + ENT_NR
SBS_INDICATOR = "ENT_NR"        # number of enterprises

def fetch_sbs(nace_code, geo_api):
    """
    Fetch enterprise count from sbs_ovw_act.
    No size_emp dimension on this dataset — returns total enterprise count.
    INDIC_SBS (uppercase) confirmed correct from diagnostic.
    """
    url = (
        f"{EUROSTAT_BASE}/{SBS_DATASET}"
        f"?format=JSON&lang=EN"
        f"&nace_r2={nace_code}"
        f"&INDIC_SBS={SBS_INDICATOR}"
        f"&geo={geo_api}"
        f"&sinceTimePeriod=2018"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 400:
            r = requests.get(url.replace("&sinceTimePeriod=2018", ""), timeout=30)
        if r.status_code != 200:
            return {}
        return r.json()
    except requests.exceptions.Timeout:
        print(f"      TIMEOUT {nace_code}/{geo_api} — skipping")
        return {}
    except Exception as e:
        print(f"      Error {nace_code}/{geo_api}: {e}")
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
                    config.setdefault(vertical, []).append(
                        {"code": code, "label": ""}
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
        ws = sh.add_worksheet(title="SMB Base", rows=8000, cols=9)
        headers = ["Vertical", "NACE Code", "NACE Label", "Geo", "Year",
                   "Enterprise Count", "Count Type", "YoY %", "Updated"]
        ws.update("A1:I1", [headers])
        ws.format("A1:I1", {"textFormat": {"bold": True}})
        print("  Created SMB Base tab.")

def write_rows_chunked(ws, all_rows, last_col="I"):
    total   = len(all_rows)
    written = 0
    print(f"  Writing {total} rows in chunks of {WRITE_CHUNK_SIZE}...")
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
                print(f"    Attempt {attempt+1} failed: {e} — retrying...")
                time.sleep(2)
    return written

def run_scraper():
    print("=" * 60)
    print("Verticore — SMB Count Scraper v2.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Dataset: sbs_ovw_act | Indicator: ENT_NR")
    print("=" * 60)

    if not SHEET_ID:
        print("\nFATAL: VERTICORE_SHEET_ID not set. Aborting.")
        return

    print("\n[1/4] Connecting to Google Sheets...")
    client = get_sheet_client()
    ensure_smb_base_tab(client)
    print("  Connected.")

    print("\n[2/4] Loading vertical configuration...")
    config = load_vertical_config(client)
    if config:
        for v, entries in config.items():
            defaults = {e["code"]: e["label"]
                        for e in DEFAULT_VERTICAL_CONFIG.get(v, [])}
            for e in entries:
                if not e["label"]:
                    e["label"] = defaults.get(e["code"], e["code"])
        print(f"  Loaded from sheet: {sum(len(v) for v in config.values())} codes")
    else:
        config = DEFAULT_VERTICAL_CONFIG
        print(f"  Using defaults: {sum(len(v) for v in config.values())} codes")

    all_geos   = list(COUNTRIES)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_rows   = []

    print(f"\n[3/4] Fetching enterprise counts...")
    for vertical, nace_list in config.items():
        print(f"\n  -- {vertical} ({len(nace_list)} code(s)) --")
        for entry in nace_list:
            code  = entry["code"]
            label = entry["label"]
            rows_before = len(all_rows)
            for gi, (geo_api, geo_store) in enumerate(all_geos):
                if gi % 6 == 1:
                    print(f"    {code}: {geo_store}... ({len(all_rows)} rows)")
                data   = fetch_sbs(code, geo_api)
                series = parse_response(data)
                for year in sorted(series.keys())[-5:]:
                    all_rows.append([
                        vertical, code, label, geo_store, year,
                        series[year],
                        "TOTAL (SMB proxy — sbs_ovw_act has no size class)",
                        compute_yoy(series, year),
                        updated_at,
                    ])
                time.sleep(0.15)
            print(f"    {code}: {len(all_rows) - rows_before} rows added")

    print(f"\n  Total rows: {len(all_rows)}")

    print(f"\n[4/4] Writing to SMB Base tab...")
    if all_rows:
        ws = client.open_by_key(SHEET_ID).worksheet("SMB Base")
        ws.batch_clear(["A2:I8000"])
        time.sleep(1)
        if ws.row_count < len(all_rows) + 10:
            ws.add_rows(len(all_rows) + 100)
        written = write_rows_chunked(ws, all_rows)
        print(f"  Written: {written} rows across "
              f"{len(set(r[3] for r in all_rows))} countries")
    else:
        print("  No data — sheet not updated.")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
