"""
Verticore — SMB Market Opportunity & Build-Priority Intelligence
================================================================
Full production app. AI layer included from day one.

Two paths for vertical selection:
  A) Seed verticals (Beauty/Renovation/Repair/Fitness Clubs) — reads from
     Google Sheet, fast, pre-populated with live Eurostat data.
  B) Any free-text vertical — AI validates, resolves to NACE + adoption group,
     queries Eurostat live at runtime, returns market size + build-priority
     ranking. No Sheet prep required for new verticals.

AI layer (Claude API):
  1. validate_vertical()   — confirms real SMB web-services vertical, returns
                             canonical name + NACE code + adoption group
  2. generate_build_priority() — returns ranked list of features to build,
                             scored by (Pain Frequency x WTP) / Self-Solve

Data: Eurostat SBS (sbs_ovw_act) + ICT (isoc_ciwebn2 / isoc_ciweb)
"""

import streamlit as st
import pandas as pd
import gspread
import json
import os
import time
import requests as req
from datetime import datetime
from google.oauth2.service_account import Credentials
import verticore_engine as ve

# ── Config ─────────────────────────────────────────────────────────────────────
def _secret(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

SHEET_ID    = _secret("VERTICORE_SHEET_ID")
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")
SCOPES      = ["https://www.googleapis.com/auth/spreadsheets.readonly",
               "https://www.googleapis.com/auth/drive.readonly"]
CLR         = "#2F5D50"
EUROSTAT    = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

GEO_NAMES = {
    'AUT':'Austria','BEL':'Belgium','BGR':'Bulgaria','CYP':'Cyprus','CZE':'Czechia',
    'DEU':'Germany','DNK':'Denmark','EST':'Estonia','ESP':'Spain','FIN':'Finland',
    'FRA':'France','HRV':'Croatia','HUN':'Hungary','IRL':'Ireland','ITA':'Italy',
    'LTU':'Lithuania','LUX':'Luxembourg','LVA':'Latvia','MLT':'Malta','NLD':'Netherlands',
    'POL':'Poland','PRT':'Portugal','ROU':'Romania','SWE':'Sweden','SVN':'Slovenia',
    'SVK':'Slovakia','NOR':'Norway',
}
GEO_API = {v: k for k, v in {  # display name → alpha-2 for live API calls
    'AT':'Austria','BE':'Belgium','BG':'Bulgaria','CY':'Cyprus','CZ':'Czechia',
    'DE':'Germany','DK':'Denmark','EE':'Estonia','ES':'Spain','FI':'Finland',
    'FR':'France','HR':'Croatia','HU':'Hungary','IE':'Ireland','IT':'Italy',
    'LT':'Lithuania','LU':'Luxembourg','LV':'Latvia','MT':'Malta','NL':'Netherlands',
    'PL':'Poland','PT':'Portugal','RO':'Romania','SE':'Sweden','SI':'Slovenia',
    'SK':'Slovakia','NO':'Norway',
}.items()}
def geo_label(iso3): return GEO_NAMES.get(iso3, iso3)
def geo_to_api(iso3):
    # alpha-3 → alpha-2 for Eurostat API
    _map = {
        'AUT':'AT','BEL':'BE','BGR':'BG','CYP':'CY','CZE':'CZ','DEU':'DE',
        'DNK':'DK','EST':'EE','ESP':'ES','FIN':'FI','FRA':'FR','HRV':'HR',
        'HUN':'HU','IRL':'IE','ITA':'IT','LTU':'LT','LUX':'LU','LVA':'LV',
        'MLT':'MT','NLD':'NL','POL':'PL','PRT':'PT','ROU':'RO','SWE':'SE',
        'SVN':'SI','SVK':'SK','NOR':'NO',
    }
    return _map.get(iso3, iso3)

# ── Page config + Styling ───────────────────────────────────────────────────────
st.set_page_config(page_title="Verticore · Market Opportunity Intelligence",
                   page_icon="◧", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root{{--bg:#EDF0F2;--white:#FFFFFF;--border:#CDD2DB;--text:#0D1117;
      --muted:#52596B;--accent:{CLR};--amber:#C9A227;}}
html,body,[data-testid="stAppViewContainer"]{{background:var(--bg)!important;
  font-family:'Inter',sans-serif!important;}}
[data-testid="stSidebar"]{{display:none!important;}}
#MainMenu,footer,header{{visibility:hidden;}}
.block-container{{padding-top:0.5rem!important;padding-bottom:2rem!important;}}
.v-hdr{{background:#FFFFFF;border-radius:8px;padding:16px 24px;margin-bottom:20px;
  display:flex;align-items:center;justify-content:space-between;
  border:1px solid #CDD2DB;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.v-title{{font-size:1.3rem;font-weight:800;color:#14181F;letter-spacing:-0.02em;}}
.v-sub{{font-size:0.64rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;
  color:#7A8499;margin-top:4px;}}
.sec{{font-size:0.72rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid #C4CAD6;padding-bottom:7px;margin:26px 0 15px 0;}}
[data-testid="stSelectbox"] label,[data-testid="stNumberInput"] label,
[data-testid="stTextInput"] label{{font-size:0.68rem!important;font-weight:600!important;
  letter-spacing:0.08em!important;text-transform:uppercase!important;color:var(--muted)!important;}}
div[data-baseweb="select"]>div,[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input{{background:var(--white)!important;
  border-color:var(--border)!important;border-radius:5px!important;font-size:0.9rem!important;}}
.hero{{background:{CLR};border-radius:10px;padding:26px 32px;
  box-shadow:0 2px 12px rgba(0,0,0,0.15);}}
.hero-val{{font-size:3rem;font-weight:800;line-height:1;color:#FFFFFF;letter-spacing:-0.02em;}}
.hero-lbl{{font-size:0.6rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;
  color:rgba(255,255,255,0.7);margin-bottom:6px;}}
.chip{{display:inline-block;background:rgba(255,255,255,0.14);color:#EAF2EF;
  font-size:0.72rem;font-weight:600;border-radius:4px;padding:4px 11px;margin-right:6px;}}
.note{{background:#FBF7EC;border-left:3px solid #C9A227;border-radius:0 6px 6px 0;
  padding:11px 15px;font-size:0.78rem;color:#5A4A15;margin-top:10px;}}
.prov{{font-size:0.68rem;color:#7A8499;margin-top:6px;line-height:1.5;}}
.build-card{{background:#FFFFFF;border:1px solid #CDD2DB;border-radius:8px;
  padding:16px 20px;margin-bottom:10px;}}
.build-rank{{font-size:2rem;font-weight:800;color:{CLR};line-height:1;}}
.build-feature{{font-size:1rem;font-weight:700;color:#0D1117;margin:4px 0;}}
.build-pain{{font-size:0.8rem;color:#52596B;}}
.build-why{{font-size:0.75rem;color:{CLR};font-weight:600;margin-top:6px;}}
.ai-badge{{display:inline-block;background:#EAF2EF;color:{CLR};font-size:0.6rem;
  font-weight:700;letter-spacing:0.1em;text-transform:uppercase;border-radius:3px;
  padding:2px 8px;margin-left:8px;}}
.validated{{background:#EAF2EF;border:1px solid #A8C4BB;border-radius:6px;
  padding:10px 14px;font-size:0.82rem;color:#1A3A30;margin-bottom:12px;}}
</style>
""", unsafe_allow_html=True)

# ── Data loading ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_sheet(tab_name):
    try:
        creds_dict = dict(st.secrets["gcp_service_account"]) \
            if "gcp_service_account" in st.secrets \
            else json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON", "{}"))
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        ws    = gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(tab_name)
        rows  = ws.get_all_values()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows[1:], columns=[h.strip() for h in rows[0]])
        return df
    except Exception as e:
        st.error(f"Could not load **{tab_name}**: {e}")
        return pd.DataFrame()

def to_num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "."), errors="coerce")
    return df

# ── AI layer — Claude API calls ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"

def claude_call(system_prompt, user_prompt, max_tokens=800):
    """Call the Claude API. Returns text or None on failure."""
    if not ANTHROPIC_KEY:
        return None
    try:
        r = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            return None
        blocks = r.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    except Exception:
        return None

def validate_vertical(raw_input):
    """
    Step 1: Validate and resolve a free-text vertical.
    Returns dict with keys: valid, canonical_name, nace_code,
    adoption_group, arpu_eur, reason.
    """
    system = """You are a strict validator for a market-intelligence tool targeting
SMB web-services buyers (Shopify, Wix, IONOS, GoDaddy, group.one).

Your ONLY job: determine if the user's input is a real, coherent SMB vertical
that a web-services company might target, and if so, return the correct
Eurostat NACE Rev.2 code and ICT-survey adoption group.

Respond ONLY with a JSON object, no markdown, no explanation, no preamble:
{
  "valid": true or false,
  "canonical_name": "Clean display name e.g. Hairdressers & Beauty Salons",
  "nace_code": "Eurostat API format e.g. S9602 or F43 — letter prefix + digits",
  "adoption_group": "Eurostat ICT NACE group — use C10-S951_X_K for services,
                     F for construction/trades, G47 for retail",
  "arpu_eur": estimated annual SaaS ARPU in EUR as integer,
  "reason": "one sentence — why valid or why not"
}

Rules:
- If valid: return the most specific NACE code available in sbs_ovw_act.
  Always include the letter prefix (S9602 not 9602, F43 not 4321).
- If typo: correct it and return valid=true with the corrected vertical.
- If nonsense/gibberish: return valid=false.
- If out of domain (e.g. aircraft manufacturing, nuclear energy): valid=false,
  reason must explain this is not an SMB web-services vertical.
- Never invent NACE codes — use standard Eurostat Rev.2 codes only."""

    result = claude_call(system, f'Validate this vertical: "{raw_input}"', max_tokens=300)
    if not result:
        return {"valid": False, "reason": "AI validation unavailable — check API key."}
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception:
        return {"valid": False, "reason": "Could not parse AI response."}

def fetch_live_smb(nace_code, geo_api):
    """Fetch enterprise count from Eurostat live for a custom vertical."""
    url = (f"{EUROSTAT}/sbs_ovw_act?format=JSON&lang=EN"
           f"&nace_r2={nace_code}&INDIC_SBS=ENT_NR&geo={geo_api}"
           f"&sinceTimePeriod=2020")
    try:
        r = req.get(url, timeout=20)
        if r.status_code != 200:
            return {}
        d = r.json()
        if "value" not in d:
            return {}
        time_cats = list(d["dimension"]["time"]["category"]["index"].keys())
        vals = {}
        for i, t in enumerate(time_cats):
            v = d["value"].get(str(i))
            if v is not None:
                vals[t] = round(float(v), 2)
        return vals
    except Exception:
        return {}

def fetch_live_adoption(nace_group, geo_api):
    """Fetch website-adoption % from Eurostat live for a custom vertical."""
    url = (f"{EUROSTAT}/isoc_ciwebn2?format=JSON&lang=EN"
           f"&indic_is=E_WEB&unit=PC_ENT&nace_r2={nace_group}&geo={geo_api}"
           f"&sinceTimePeriod=2020")
    try:
        r = req.get(url, timeout=20)
        if r.status_code != 200:
            return None
        d = r.json()
        if "value" not in d:
            return None
        time_cats = list(d["dimension"]["time"]["category"]["index"].keys())
        vals = {t: float(d["value"][str(i)])
                for i, t in enumerate(time_cats)
                if d["value"].get(str(i)) is not None}
        if not vals:
            return None
        return vals[max(vals.keys())]
    except Exception:
        return None

def generate_build_priority(canonical_name, smb_count, adoption_pct,
                             arpu, market_eur, country_name):
    """
    Step 2: Generate ranked build-priority features for the validated vertical.
    The AI proposes; the product scores. Returns list of dicts.
    """
    system = """You are a product-intelligence engine for web-services companies
(Shopify, Wix, IONOS, GoDaddy, group.one). You analyse SMB verticals and
identify the highest-value web features to build.

Respond ONLY with a JSON array of exactly 5 features, no markdown, no preamble:
[
  {
    "rank": 1,
    "feature": "Short feature name e.g. Online Booking & Scheduling",
    "pain_point": "The specific pain this solves in 1 sentence",
    "self_solve_ability": "low|medium|high",
    "willingness_to_pay": "low|medium|high",
    "pain_frequency": "low|medium|high",
    "why_it_wins": "One sentence commercial rationale"
  },
  ...
]

Rules:
- Think from the perspective of the SMB owner, not the platform
- low self_solve_ability means businesses CAN'T easily build this themselves
  → higher build-priority
- Rank 1 = highest build-priority
- Suggest features a web-services platform could realistically build
- Do NOT suggest enterprise software, complex ERP, or things requiring
  deep industry-specific hardware"""

    numeric_market = f"€{market_eur/1e6:.1f}M" if market_eur > 1e6 else f"€{market_eur:,.0f}"
    prompt = (
        f"Vertical: {canonical_name}\n"
        f"Country: {country_name}\n"
        f"SMB count: {smb_count:,.0f}\n"
        f"Website adoption: {adoption_pct:.1f}%\n"
        f"ARPU: €{arpu}/year\n"
        f"Obtainable market: {numeric_market}\n\n"
        f"Generate the 5 highest-priority web features to build for this vertical."
    )
    result = claude_call(system, prompt, max_tokens=800)
    if not result:
        return []
    try:
        clean = result.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception:
        return []

def score_build_priority(features):
    """
    Apply the transparent scoring formula IN THE PRODUCT, not in the AI.
    Build Priority = (Pain Frequency × Willingness-to-Pay) ÷ Self-Solve Ability
    """
    SCALE = {"low": 1, "medium": 2, "high": 3}
    for f in features:
        pf  = SCALE.get(str(f.get("pain_frequency",  "medium")).lower(), 2)
        wtp = SCALE.get(str(f.get("willingness_to_pay", "medium")).lower(), 2)
        ssa = SCALE.get(str(f.get("self_solve_ability", "medium")).lower(), 2)
        f["priority_score"] = round((pf * wtp) / ssa, 2)
    return sorted(features, key=lambda x: -x.get("priority_score", 0))

# ── Helper formatters ───────────────────────────────────────────────────────────
def fmt_eur(v):
    if v is None: return "—"
    if v >= 1e9:  return f"€{v/1e9:.2f}B"
    if v >= 1e6:  return f"€{v/1e6:.1f}M"
    if v >= 1e3:  return f"€{v/1e3:.0f}K"
    return f"€{v:.0f}"

def fmt_int(v):
    return f"{int(round(v)):,}" if v is not None else "—"

# ── Header ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="v-hdr">
  <div>
    <div class="v-title">◧ Verti<span style="color:{CLR};">core</span></div>
    <div class="v-sub">SMB Market Opportunity &amp; Build-Priority Intelligence</div>
  </div>
  <div style="font-size:0.72rem;color:#52596B;text-align:right;line-height:1.6;">
    Live data &nbsp;·&nbsp;
    <strong style="color:#0D1117;">{datetime.now().strftime('%d %b %Y, %H:%M')}</strong>
    <br><span style="font-size:0.64rem;color:#9BAEC8;">
    Eurostat SBS + ICT · AI-powered vertical resolution</span>
  </div>
</div>
""", unsafe_allow_html=True)

if not SHEET_ID:
    st.error("VERTICORE_SHEET_ID is not configured.")
    st.stop()

# ── Load sheet data ─────────────────────────────────────────────────────────────
with st.spinner("Loading market data…"):
    smb_df   = to_num(load_sheet("SMB Base"),   ["Enterprise Count", "YoY %"])
    adopt_df = to_num(load_sheet("Adoption"),    ["Adoption %"])
    size_df  = to_num(load_sheet("Adoption Sizeclass"), ["Value %"])
    vcfg_df  = load_sheet("Vertical Config")
    arpu_df  = to_num(load_sheet("ARPU Config"), ["Default ARPU EUR"])

seed_verticals = sorted(smb_df["Vertical"].dropna().unique().tolist()) \
    if not smb_df.empty else []
geos_avail = sorted(smb_df["Geo"].dropna().unique().tolist()) \
    if not smb_df.empty else list(GEO_NAMES.keys())
years_avail = sorted(smb_df["Year"].dropna().astype(str).unique().tolist()) \
    if not smb_df.empty else []
latest_year = years_avail[-1] if years_avail else "2022"

vgroup = {}
if not vcfg_df.empty and "Vertical" in vcfg_df.columns:
    for _, row in vcfg_df.iterrows():
        v = str(row.get("Vertical", "")).strip()
        g = str(row.get("NACE Adoption Group", "")).strip()
        if v: vgroup[v] = g

# ── Vertical selection ──────────────────────────────────────────────────────────
st.markdown('<div class="sec">Select or enter your target vertical</div>',
            unsafe_allow_html=True)

col_mode, col_v, col_geo, col_arpu = st.columns([1.2, 2, 2, 1.5])
with col_mode:
    _mode_opts = ["Seed vertical", "Enter any vertical"]
    _mode_help = ("Seed = instant pre-loaded data. "
                  "Enter any vertical = AI resolves + live Eurostat query "
                  + ("(API key not configured — coming soon)."
                     if not ANTHROPIC_KEY else "(AI enabled)."))
    mode = st.selectbox("Mode", _mode_opts, key="v_mode", help=_mode_help)

use_ai = (mode == "Enter any vertical")

with col_v:
    if not use_ai:
        vertical_sel = st.selectbox(
            "Vertical", seed_verticals or ["No data yet — run scrapers first"],
            key="v_seed")
    else:
        vertical_raw = st.text_input(
            "Type any SMB vertical",
            placeholder="e.g. artisan bakeries, veterinary clinics, yoga studios…",
            key="v_raw")

with col_geo:
    geo = st.selectbox("Country", geos_avail or list(GEO_NAMES.keys()),
                       format_func=geo_label, key="v_geo")

with col_arpu:
    arpu_default = 150.0
    if not use_ai and seed_verticals:
        arpu_default = ve.get_default_arpu(arpu_df, vertical_sel) or 150.0
    arpu = st.number_input("ARPU (EUR / year)", min_value=1.0, max_value=100000.0,
                           value=float(arpu_default), step=10.0, key="v_arpu")

adjust = st.toggle("Apply micro-enterprise adjustment", value=True,
    help="Bridges sector adoption down to micro-business reality using "
         "Eurostat's per-country size-class gradient. Recommended.")

# ── AI validation flow ──────────────────────────────────────────────────────────
validated = None
ai_smb    = None
ai_adopt  = None

if use_ai:
    raw = (vertical_raw or "").strip()
    if not raw:
        st.info("Type a vertical above to get started. Examples: yoga studios, "
                "artisan bakeries, dog grooming, independent pharmacies.")
        st.stop()

    if not ANTHROPIC_KEY:
        st.markdown(f"""<div class="note">
          <strong>AI vertical analysis coming soon.</strong>
          The market-sizing engine is fully live for the four seed verticals below.
          Free-text vertical entry and build-priority ranking will be enabled shortly.
          <br><span style="font-size:0.75rem;">Switch mode to <em>Seed vertical</em>
          to explore live market data now.</span>
        </div>""", unsafe_allow_html=True)
        st.stop()

    # Cache validation per (raw_input, geo) so it doesn't re-fire on every rerender
    cache_key = f"val_{raw}_{geo}"
    if cache_key not in st.session_state:
        with st.spinner(f"Validating '{raw}'…"):
            result = validate_vertical(raw)
            st.session_state[cache_key] = result
    validated = st.session_state[cache_key]

    if not validated.get("valid"):
        st.markdown(f"""<div class="note">
          <strong>Not recognised:</strong> {validated.get('reason',
          'This does not appear to be a valid SMB web-services vertical.')}<br>
          <span style="font-size:0.75rem;">Try: beauty salons, yoga studios,
          independent pharmacies, artisan bakeries, dog grooming, auto repair…</span>
        </div>""", unsafe_allow_html=True)
        st.stop()

    # Show confirmation
    nace      = validated.get("nace_code", "")
    adp_group = validated.get("adoption_group", "C10-S951_X_K")
    cname     = validated.get("canonical_name", raw)
    ai_arpu   = validated.get("arpu_eur", arpu)
    # Update ARPU field to AI suggestion if user hasn't changed it
    if arpu == 150.0 and ai_arpu:
        arpu = float(ai_arpu)

    st.markdown(f"""<div class="validated">
      ✓ <strong>{cname}</strong> &nbsp;·&nbsp; NACE {nace}
      &nbsp;·&nbsp; {validated.get('reason','')}
    </div>""", unsafe_allow_html=True)

    # Fetch live Eurostat data for this custom vertical
    geo_api_code = geo_to_api(geo)
    lk_smb  = f"smb_{nace}_{geo}"
    lk_adpt = f"adpt_{adp_group}_{geo}"
    if lk_smb not in st.session_state:
        with st.spinner("Fetching live Eurostat enterprise count…"):
            st.session_state[lk_smb] = fetch_live_smb(nace, geo_api_code)
    if lk_adpt not in st.session_state:
        with st.spinner("Fetching live adoption rate…"):
            st.session_state[lk_adpt] = fetch_live_adoption(adp_group, geo_api_code)

    smb_series  = st.session_state[lk_smb]
    adopt_pct   = st.session_state[lk_adpt]
    ai_smb      = smb_series.get(max(smb_series.keys())) if smb_series else None
    ai_adopt    = adopt_pct

# ── Compute market ──────────────────────────────────────────────────────────────
if use_ai:
    # Build a synthetic single-row DataFrame for the engine
    if ai_smb is not None and ai_adopt is not None:
        synth_smb = pd.DataFrame([{
            "Vertical": cname, "NACE Code": nace, "Geo": geo,
            "Year": latest_year, "Enterprise Count": ai_smb,
            "Size Class": "TOTAL (SMB proxy)",
        }])
        synth_adpt = pd.DataFrame([{
            "Vertical": cname, "NACE Group": adp_group, "Geo": geo,
            "Year": latest_year, "Adoption %": ai_adopt,
        }])
        res = ve.compute_market(synth_smb, synth_adpt, size_df, cname,
                                adp_group, geo, latest_year, arpu,
                                apply_micro_adjust=adjust)
    else:
        res = {"data_complete": False, "smb_count": ai_smb,
               "effective_adoption_pct": ai_adopt, "arpu": arpu}
    display_vertical = cname
    nace_group_used  = validated.get("nace_code", "") if validated else ""
else:
    nace_group_used = vgroup.get(vertical_sel, "")
    res = ve.compute_market(smb_df, adopt_df, size_df, vertical_sel,
                            nace_group_used, geo, latest_year, arpu,
                            apply_micro_adjust=adjust)
    display_vertical = vertical_sel

# ── Output ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Obtainable market</div>', unsafe_allow_html=True)

if not res.get("data_complete"):
    missing = []
    if res.get("smb_count") is None:    missing.append("SMB count (no Eurostat data for this NACE)")
    if res.get("effective_adoption_pct") is None: missing.append("adoption rate")
    st.markdown(f"""<div class="note">
      Live data for <strong>{display_vertical} · {geo_label(geo)}</strong>
      is incomplete ({', '.join(missing)}).
      Eurostat suppresses low-sample cells for some countries or NACE codes.
      No figure is shown rather than an invented one. Try another country.
    </div>""", unsafe_allow_html=True)
else:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        ai_tag     = '<span class="ai-badge">AI + Live Eurostat</span>' if use_ai else ""
        hero_mkt   = fmt_eur(res["obtainable_market_eur"])
        hero_geo   = geo_label(geo)
        hero_adopt = str(res["effective_adoption_pct"]) + "% adoption"
        hero_smbs  = fmt_int(res["smb_count"]) + " SMBs"
        hero_arpu  = "\u20ac" + str(int(res["arpu"])) + " ARPU/yr"
        hero_chips = fmt_int(res["adopting_smbs"]) + " adopting SMBs"
        hero_stats = hero_smbs + " &nbsp;·&nbsp; " + hero_adopt + " &nbsp;·&nbsp; " + hero_arpu
        hero_html  = (
            '<div class="hero">'
            + '<div class="hero-lbl">Obtainable Market &middot; ' + hero_geo + ' &middot; ' + str(latest_year) + '</div>'
            + '<div class="hero-val">' + hero_mkt + '</div>'
            + '<div style="margin-top:14px;">'
            + '<span class="chip">&#128205; ' + display_vertical + '</span>'
            + '<span class="chip">' + hero_chips + ' adopting SMBs</span>'
            + ai_tag
            + '</div>'
            + '<div style="font-size:0.75rem;color:rgba(255,255,255,0.82);margin-top:14px;line-height:1.6;">' 
            + hero_stats
            + '</div>'
            + '</div>'
        )
        st.markdown(hero_html, unsafe_allow_html=True)

    with c2:
        if res.get("adoption_was_adjusted") and res.get("micro_basis"):
            b = res["micro_basis"]
            adj = (f"Sector adoption <strong>{res['headline_adoption_pct']}%</strong> "
                   f"adjusted to <strong>{res['effective_adoption_pct']}%</strong> "
                   f"for micro-enterprises using {geo_label(geo)}'s size gradient "
                   f"({b['small_10_49']}% small vs {b['base_ge10']}% base in {b['year']}, "
                   f"ratio {res['micro_ratio']}).")
        else:
            adj = (f"Sector website-adoption <strong>{res['headline_adoption_pct']}%</strong> "
                   f"({geo_label(geo)}, live Eurostat). "
                   f"{'Size gradient not available for this country — unadjusted.' if adjust else 'Micro-adjustment off.'}")
        nace_note = f"NACE {nace_group_used} · " if nace_group_used else ""
        st.markdown(f"""<div style="background:#FFFFFF;border:1px solid #CDD2DB;
          border-radius:10px;padding:18px 20px;height:100%;">
          <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;
            text-transform:uppercase;color:{CLR};margin-bottom:8px;">How this is computed</div>
          <div style="font-size:0.82rem;color:#0D1117;line-height:1.6;">
            Obtainable Market = SMBs × Adoption × ARPU<br><br>{adj}
          </div>
          <div class="prov">{nace_note}Enterprise count: Eurostat sbs_ovw_act.
            Adoption: Eurostat isoc_ciwebn2 / isoc_ciweb. All live data.</div>
        </div>""", unsafe_allow_html=True)

    # ── Projection ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">2025–2030 projection</div>', unsafe_allow_html=True)
    pc1, pc2 = st.columns(2)
    with pc1:
        smb_growth   = st.slider("SMB base growth % / year", 0.0, 3.0, 0.5, 0.1)
    with pc2:
        adopt_growth = st.slider("Adoption growth (pp / year)", 0.0, 5.0, 2.4, 0.1)
    proj = ve.project_forward(res, smb_growth, adopt_growth,
                              ["2025","2026","2027","2028","2029","2030"])
    if proj:
        pdf = pd.DataFrame(proj)
        pdf["Obtainable Market"] = pdf["market_eur"].apply(fmt_eur)
        pdf["SMBs"]              = pdf["smb_count"].apply(fmt_int)
        pdf["Adopting SMBs"]     = pdf["adopting_smbs"].apply(fmt_int)
        pdf["Adoption %"]        = pdf["adoption_pct"].astype(str) + "%"
        st.dataframe(pdf.rename(columns={"year":"Year"})
                     [["Year","SMBs","Adoption %","Adopting SMBs","Obtainable Market"]],
                     use_container_width=True, hide_index=True, height=250)
        st.markdown(f'<div class="prov">SMB base +{smb_growth}%/yr compound; '
                    f'adoption +{adopt_growth}pp/yr linear (capped 100%); ARPU flat.</div>',
                    unsafe_allow_html=True)

    # ── Build-priority ranking ────────────────────────────────────────────────────
    st.markdown('<div class="sec">What to build — ranked build-priority'
                '<span class="ai-badge" style="vertical-align:middle;margin-left:8px;">'
                'AI-scored</span></div>', unsafe_allow_html=True)

    bp_key = f"bp_{display_vertical}_{geo}_{arpu}"
    if bp_key not in st.session_state:
        if not ANTHROPIC_KEY:
            pass  # no-key: teaser card shown below via `if not ANTHROPIC_KEY and not features`
        else:
            with st.spinner("Generating build-priority analysis…"):
                raw_features = generate_build_priority(
                    display_vertical,
                    res["smb_count"] or 0,
                    res["effective_adoption_pct"] or 0,
                    arpu,
                    res["obtainable_market_eur"] or 0,
                    geo_label(geo),
                )
                st.session_state[bp_key] = score_build_priority(raw_features)

    features = st.session_state.get(bp_key, [])
    if not ANTHROPIC_KEY and not features:
        st.markdown(f"""<div style="background:#F8FFFE;border:1px solid #A8C4BB;
          border-radius:8px;padding:20px 24px;text-align:center;">
          <div style="font-size:1.1rem;font-weight:700;color:{CLR};margin-bottom:8px;">
            ◧ AI Build-Priority Ranking</div>
          <div style="font-size:0.85rem;color:#52596B;line-height:1.7;">
            The engine analyses <strong>{display_vertical}</strong> pain points,
            scores each buildable feature by commercial opportunity, and returns
            a ranked list of what to build next — with the euro prize attached.<br><br>
            <strong>Available shortly.</strong> The market-sizing data above is
            fully live and ready to present today.
          </div>
        </div>""", unsafe_allow_html=True)
    elif features:
        for i, f in enumerate(features):
            score = f.get("priority_score", 0)
            ssa   = f.get("self_solve_ability", "?")
            wtp   = f.get("willingness_to_pay", "?")
            pf    = f.get("pain_frequency", "?")
            market_per_feature = fmt_eur(
                (res["obtainable_market_eur"] or 0) * (1 / max(len(features), 1))
            )
            st.markdown(f"""<div class="build-card">
              <div style="display:flex;align-items:flex-start;gap:16px;">
                <div class="build-rank">#{i+1}</div>
                <div style="flex:1;">
                  <div class="build-feature">{f.get('feature','')}</div>
                  <div class="build-pain">{f.get('pain_point','')}</div>
                  <div class="build-why">{f.get('why_it_wins','')}</div>
                  <div style="margin-top:8px;font-size:0.68rem;color:#7A8499;">
                    Pain freq: <strong>{pf}</strong> &nbsp;·&nbsp;
                    WTP: <strong>{wtp}</strong> &nbsp;·&nbsp;
                    Self-solve: <strong>{ssa}</strong> &nbsp;·&nbsp;
                    Priority score: <strong>{score}</strong>
                    &nbsp;·&nbsp; ~{market_per_feature} opportunity slice
                  </div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="prov" style="margin-top:8px;">
          Scoring formula: Build Priority = (Pain Frequency × Willingness-to-Pay) ÷ Self-Solve Ability.
          AI proposes features; this product scores and ranks them.
          Context: {fmt_int(res['smb_count'])} {display_vertical} in {geo_label(geo)},
          {res['effective_adoption_pct']}% website adoption,
          €{arpu:.0f} ARPU → {fmt_eur(res['obtainable_market_eur'])} obtainable market.
        </div>""", unsafe_allow_html=True)
    else:
        if ANTHROPIC_KEY:
            st.info("Build-priority analysis will appear here. "
                    "Data may be insufficient for ranking.")

    # ── Cross-country ranking (seed verticals only) ───────────────────────────────
    if not use_ai:
        st.markdown('<div class="sec">Where is the opportunity? — all countries</div>',
                    unsafe_allow_html=True)
        rank_df = ve.rank_opportunities(
            smb_df, adopt_df, size_df, arpu_df,
            {vertical_sel: nace_group_used}, geos_avail,
            latest_year, apply_micro_adjust=adjust)
        if not rank_df.empty:
            disp = rank_df.copy()
            disp["Country"]          = disp["Geo"].apply(geo_label)
            disp["Obtainable Market"]= disp["Obtainable Market (EUR)"].apply(fmt_eur)
            disp["SMBs"]             = disp["SMBs"].apply(fmt_int)
            disp["Adoption %"]       = disp["Adoption %"].astype(str) + "%"
            st.dataframe(disp[["Country","SMBs","Adoption %","Obtainable Market"]],
                         use_container_width=True, hide_index=True, height=340)
            st.markdown('<div class="prov">Ranked by obtainable market. '
                        'Countries with suppressed source data are omitted.</div>',
                        unsafe_allow_html=True)

# ── Footer ───────────────────────────────────────────────────────────────────────
st.markdown(f"""<div style="border-top:1px solid #DDE1E7;margin-top:36px;
  padding:12px 0;display:flex;justify-content:space-between;
  font-size:0.65rem;color:#9CA3AF;">
  <span>Obtainable Market = SMBs × Adoption × ARPU · Eurostat SBS + ICT ·
    AI build-priority: (Pain Freq × WTP) ÷ Self-Solve</span>
  <span>© 2026 Joscha Schmidt · Verticore · Confidential</span>
</div>""", unsafe_allow_html=True)
