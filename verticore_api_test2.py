"""
Verticore — API Diagnostic Round 2
====================================
Tests which dataset + NACE format returns ENTERPRISE COUNTS for Verticore's
four specific verticals. sbs_sc_ovw confirmed to NOT carry fine NACE.
Testing: sbs_na_1a_se_r2, sbs_na_ind_r2, sbs_ovw_act with ENT_NR / V16110.
Also confirms adoption scraper NACE groups per vertical with the corrected
C10-S951_X_K aggregate.
"""

import requests

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
GEO  = "DE"

def try_url(label, url):
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

# ── NACE codes to test per vertical ───────────────────────────────────────────
# Format without prefix letter first, then with S/F/R prefix
VERTICALS = {
    "Beauty":        ["9602", "9604", "S9602", "S9604"],
    "Renovation":    ["4321", "4322", "4329", "4331", "F4321", "F43"],
    "Repair":        ["4520", "9521", "9522", "9529", "G4520", "S9521"],
    "FitnessClubs":  ["9312", "9313", "R9312", "R9313", "9499"],
}

# ── BLOCK 1: Which dataset carries fine NACE enterprise counts? ────────────────
print()
print("=" * 65)
print("BLOCK 1 — Finding the right dataset for enterprise counts")
print("Testing datasets: sbs_na_1a_se_r2, sbs_na_ind_r2, sbs_ovw_act")
print("=" * 65)

DATASETS = ["sbs_na_1a_se_r2", "sbs_na_ind_r2", "sbs_ovw_act"]
# Test with a single representative NACE per vertical
TEST_NACES = [
    ("Beauty_9602",       "9602"),
    ("Beauty_S9602",      "S9602"),
    ("Renovation_F43",    "F43"),
    ("Renovation_4321",   "4321"),
    ("Repair_9521",       "9521"),
    ("Repair_G4520",      "G4520"),
    ("FitnessClubs_9312", "9312"),
    ("FitnessClubs_R9312","R9312"),
]

for ds in DATASETS:
    print(f"\n  -- Dataset: {ds} --")
    for label, nace in TEST_NACES[:4]:  # test a subset per dataset to save time
        # Try with indic_sbs=ENT_NR (enterprise count)
        url = (f"{BASE}/{ds}?format=JSON&lang=EN"
               f"&nace_r2={nace}&indic_sbs=ENT_NR&geo={GEO}")
        worked = try_url(f"{label} ENT_NR", url)
        if not worked:
            # Try with V16110 (persons employed — proxy for business presence)
            url2 = (f"{BASE}/{ds}?format=JSON&lang=EN"
                    f"&nace_r2={nace}&indic_sb=V16110&geo={GEO}")
            try_url(f"{label} V16110", url2)

# ── BLOCK 2: sbs_ovw_act specifically — it claims detailed NACE ───────────────
print()
print("=" * 65)
print("BLOCK 2 — sbs_ovw_act with INDIC_SBS dimension (uppercase)")
print("=" * 65)
for label, nace in TEST_NACES:
    url = (f"{BASE}/sbs_ovw_act?format=JSON&lang=EN"
           f"&nace_r2={nace}&INDIC_SBS=ENT_NR&geo={GEO}")
    try_url(f"sbs_ovw_act {label} INDIC_SBS", url)

# ── BLOCK 3: Confirm adoption NACE groups per vertical ────────────────────────
print()
print("=" * 65)
print("BLOCK 3 — Adoption NACE groups per vertical (isoc_ciwebn2)")
print("Confirmed working: C10-S951_X_K (broad). Testing finer groups.")
print("=" * 65)
ADOPTION_GROUPS = [
    "C10-S951_X_K",   # confirmed working — broad aggregate
    "F",              # construction → Renovation
    "G-S_X_K",       # alternative services notation
    "S",              # personal services section
    "R",              # arts/recreation section
    "N",              # admin/support
    "G47",            # retail
    "S96",            # other personal services (beauty is here)
]
for grp in ADOPTION_GROUPS:
    url = (f"{BASE}/isoc_ciwebn2?format=JSON&lang=EN"
           f"&indic_is=E_WEB&unit=PC_ENT&nace_r2={grp}&geo={GEO}"
           f"&sinceTimePeriod=2021")
    try_url(f"isoc_ciwebn2 nace={grp}", url)

# ── BLOCK 4: Confirm the isoc_ciweb sizeclass fix ─────────────────────────────
print()
print("=" * 65)
print("BLOCK 4 — Confirming isoc_ciweb sizeclass with C10-S951_X_K")
print("(Already confirmed in round 1 — re-verifying the 4 working codes)")
print("=" * 65)
for size in ["GE10", "10-49", "50-249", "GE250"]:
    url = (f"{BASE}/isoc_ciweb?format=JSON&lang=EN"
           f"&indic_is=E_WEB&unit=PC_ENT&nace_r2=C10-S951_X_K"
           f"&size_emp={size}&geo={GEO}&sinceTimePeriod=2021")
    try_url(f"isoc_ciweb C10-S951_X_K size={size}", url)

print()
print("=" * 65)
print("DIAGNOSTIC ROUND 2 COMPLETE")
print("Paste the full output back to Claude.")
print("=" * 65)
