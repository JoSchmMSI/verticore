"""
Verticore — Eurostat API Diagnostic Script
==========================================
ONE-TIME throwaway test. Run via GitHub Actions (which can reach ec.europa.eu).
No sheet writes. Just prints which parameter formats return real data.
Fixes two bugs confirmed from first scraper run:
  - SMB Base empty: used wrong dimension 'size_clas' (correct: 'size_emp')
  - Adoption Sizeclass empty: used wrong size codes with underscores
"""

import requests
import json

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
GEO  = "DE"   # Germany — large country, most likely to have data in all cells

def try_url(label, url):
    """Hit a URL, print whether it returned data and a sample of values."""
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  ✗ {label}: HTTP {r.status_code}")
            return False
        d = r.json()
        vals = {k: v for k, v in (d.get("value") or {}).items() if v is not None}
        if not vals:
            print(f"  ✗ {label}: 200 OK but zero non-null values")
            return False
        sample = list(vals.values())[:3]
        print(f"  ✓ {label}: {len(vals)} values — sample: {sample}")
        return True
    except Exception as e:
        print(f"  ✗ {label}: exception — {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 65)
print("BLOCK 1 — SBS enterprise counts (sbs_sc_ovw)")
print("Target: fill 'SMB Base' tab")
print("Dataset: sbs_sc_ovw | Indicator: ENT_NR | Geo: DE")
print("=" * 65)

# ── 1A: NACE code format for Beauty (96.02) ───────────────────────────────────
print()
print("1A — Which NACE code format does the API accept?")
for nace in ["S9602", "9602", "S96_02", "S9604"]:
    url = (f"{BASE}/sbs_sc_ovw?format=JSON&lang=EN"
           f"&nace_r2={nace}&indic_sbs=ENT_NR&size_emp=TOTAL&geo={GEO}")
    try_url(f"nace_r2={nace}", url)

# ── 1B: size_emp band codes (using whichever NACE worked above) ────────────────
print()
print("1B — Which size_emp band codes return data? (using S9602)")
for size in ["TOTAL", "0-9", "10-19", "20-49", "50-249", "250-999", "GE250", "GE10"]:
    url = (f"{BASE}/sbs_sc_ovw?format=JSON&lang=EN"
           f"&nace_r2=S9602&indic_sbs=ENT_NR&size_emp={size}&geo={GEO}")
    try_url(f"size_emp={size}", url)

# ── 1C: confirm indic_sbs name (vs older indic_sb without 's') ────────────────
print()
print("1C — Indicator dimension name: indic_sbs vs indic_sb?")
for ind_name, ind_val in [("indic_sbs", "ENT_NR"), ("indic_sb", "ENT_NR"),
                           ("indic_sbs", "V11110")]:
    url = (f"{BASE}/sbs_sc_ovw?format=JSON&lang=EN"
           f"&nace_r2=S9602&{ind_name}={ind_val}&size_emp=TOTAL&geo={GEO}")
    try_url(f"{ind_name}={ind_val}", url)

# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 65)
print("BLOCK 2 — ICT adoption by size class (isoc_ciweb)")
print("Target: fill 'Adoption Sizeclass' tab")
print("Dataset: isoc_ciweb | Indicator: E_WEB | Unit: PC_ENT | Geo: DE")
print("=" * 65)

# ── 2A: NACE group for the size-class dataset ─────────────────────────────────
print()
print("2A — Which NACE group works for isoc_ciweb?")
for nace in ["G-N_S951_X_K", "C10-S951_X_K", "C10-S951_XK",
             "G47", "F", "S96", "TOTAL"]:
    url = (f"{BASE}/isoc_ciweb?format=JSON&lang=EN"
           f"&indic_is=E_WEB&unit=PC_ENT&nace_r2={nace}"
           f"&size_emp=GE10&geo={GEO}&sinceTimePeriod=2021")
    try_url(f"nace_r2={nace}", url)

# ── 2B: size_emp codes — underscore vs hyphen vs other ────────────────────────
print()
print("2B — Which size_emp codes work for isoc_ciweb? (using best NACE from 2A)")
# Try both the NACE that worked for Adoption tab AND the broader aggregate
for nace in ["G-N_S951_X_K", "C10-S951_X_K"]:
    print(f"  [nace={nace}]")
    for size in ["GE10", "10-49", "50-249", "GE250",
                 "10_49", "50_249",           # underscore variants (current bug)
                 "TOTAL", "SM_MD", "LG"]:     # other possible codes
        url = (f"{BASE}/isoc_ciweb?format=JSON&lang=EN"
               f"&indic_is=E_WEB&unit=PC_ENT&nace_r2={nace}"
               f"&size_emp={size}&geo={GEO}&sinceTimePeriod=2021")
        try_url(f"  size_emp={size}", url)

# ── 2C: try isoc_e_dii as alternative for size-class gradient ────────────────
print()
print("2C — isoc_e_dii (Digital Intensity by size class) as alternative?")
for size in ["GE10", "10-49", "50-249", "GE250", "TOTAL", "0-9"]:
    url = (f"{BASE}/isoc_e_dii?format=JSON&lang=EN"
           f"&nace_r2=C10-S951_X_K&size_emp={size}&geo={GEO}"
           f"&sinceTimePeriod=2021")
    try_url(f"isoc_e_dii size_emp={size}", url)

# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 65)
print("DIAGNOSTIC COMPLETE")
print("Paste the full output above back to Claude to get the fixed scrapers.")
print("=" * 65)
