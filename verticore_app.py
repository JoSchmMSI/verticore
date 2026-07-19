"""
Verticore — SMB Market Opportunity & Build-Priority Intelligence
================================================================
Phase 1: live market-sizing core.

Tells a web-services company the obtainable market for a given SMB vertical,
per country, computed entirely from live Eurostat data (SBS enterprise counts +
ICT website-adoption), with a transparent, per-country micro-enterprise
adjustment anchored to Eurostat's live size-class gradient.

Reads from Google Sheet tabs: SMB Base | Adoption | Adoption Sizeclass |
Vertical Config | ARPU Config  (all populated by the Verticore scrapers).

Phase 3 will add the free-text vertical + AI build-priority engine.
"""

import streamlit as st
import pandas as pd
import gspread
import json
import os
from datetime import datetime
from google.oauth2.service_account import Credentials

import verticore_engine as ve

# ── Config ─────────────────────────────────────────────────────────────────────
SHEET_ID = os.environ.get("VERTICORE_SHEET_ID", "").strip() or st.secrets.get("VERTICORE_SHEET_ID", "")
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly"]

st.set_page_config(page_title="Verticore · Market Opportunity Intelligence",
                   page_icon="◧", layout="wide", initial_sidebar_state="collapsed")

# ── Country display ────────────────────────────────────────────────────────────
GEO_NAMES = {
    'AUT':'Austria','BEL':'Belgium','BGR':'Bulgaria','CYP':'Cyprus','CZE':'Czechia',
    'DEU':'Germany','DNK':'Denmark','EST':'Estonia','ESP':'Spain','FIN':'Finland',
    'FRA':'France','HRV':'Croatia','HUN':'Hungary','IRL':'Ireland','ITA':'Italy',
    'LTU':'Lithuania','LUX':'Luxembourg','LVA':'Latvia','MLT':'Malta','NLD':'Netherlands',
    'POL':'Poland','PRT':'Portugal','ROU':'Romania','SWE':'Sweden','SVN':'Slovenia',
    'SVK':'Slovakia','NOR':'Norway',
}
def geo_label(iso3): return GEO_NAMES.get(iso3, iso3)

# ── Styling — Verticore identity (MSI-grade visual system, own colours) ────────
CLR = "#2F5D50"  # deep verdant green — Verticore identity, distinct from MSI navy
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root{{--bg:#EDF0F2;--white:#FFFFFF;--border:#CDD2DB;--text:#0D1117;--muted:#52596B;--accent:{CLR};}}
html,body,[data-testid="stAppViewContainer"]{{background:var(--bg)!important;font-family:'Inter',sans-serif!important;}}
[data-testid="stSidebar"]{{display:none!important;}}
#MainMenu,footer,header{{visibility:hidden;}}
.block-container{{padding-top:0.5rem!important;padding-bottom:2rem!important;}}
.v-hdr{{background:#FFFFFF;border-radius:8px;padding:16px 24px;margin-bottom:20px;display:flex;
        align-items:center;justify-content:space-between;border:1px solid #CDD2DB;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.v-title{{font-size:1.3rem;font-weight:800;color:#14181F;letter-spacing:-0.02em;line-height:1;}}
.v-sub{{font-size:0.64rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#7A8499;margin-top:4px;}}
.section-hdr{{font-size:0.72rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:var(--muted);
        border-bottom:1px solid #C4CAD6;padding-bottom:7px;margin:26px 0 15px 0;}}
[data-testid="stSelectbox"] label,[data-testid="stNumberInput"] label{{font-size:0.68rem!important;font-weight:600!important;
        letter-spacing:0.08em!important;text-transform:uppercase!important;color:var(--muted)!important;}}
div[data-baseweb="select"]>div,[data-testid="stNumberInput"] input{{background:var(--white)!important;
        border-color:var(--border)!important;border-radius:5px!important;font-size:0.9rem!important;}}
.hero{{background:{CLR};border-radius:10px;padding:26px 32px;box-shadow:0 2px 12px rgba(0,0,0,0.15);}}
.hero-val{{font-family:'Inter';font-size:3rem;font-weight:800;line-height:1;color:#FFFFFF;letter-spacing:-0.02em;}}
.hero-lbl{{font-size:0.6rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.7);margin-bottom:6px;}}
.chip{{display:inline-block;background:rgba(255,255,255,0.14);color:#EAF2EF;font-size:0.72rem;font-weight:600;
        border-radius:4px;padding:4px 11px;margin-right:6px;}}
.note{{background:#FBF7EC;border-left:3px solid #C9A227;border-radius:0 6px 6px 0;padding:11px 15px;
        font-size:0.78rem;color:#5A4A15;margin-top:10px;}}
.prov{{font-size:0.68rem;color:#7A8499;margin-top:6px;line-height:1.5;}}
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_sheet(tab_name):
    try:
        creds_dict = dict(st.secrets["gcp_service_account"]) if "gcp_service_account" in st.secrets \
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
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
    return df

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="v-hdr">
  <div>
    <div class="v-title">◧ Verti<span style="color:{CLR};">core</span></div>
    <div class="v-sub">SMB Market Opportunity &amp; Build-Priority Intelligence</div>
  </div>
  <div style="font-size:0.72rem;color:#52596B;text-align:right;line-height:1.6;">
    Live data &nbsp;·&nbsp; <strong style="color:#0D1117;">{datetime.now().strftime('%d %b %Y, %H:%M')}</strong>
    <br><span style="font-size:0.64rem;color:#9BAEC8;">Eurostat SBS + ICT · auto-refreshed weekly</span>
  </div>
</div>
""", unsafe_allow_html=True)

if not SHEET_ID:
    st.error("VERTICORE_SHEET_ID is not configured. Set it as a secret / environment variable.")
    st.stop()

with st.spinner("Loading live market data…"):
    smb_df   = to_num(load_sheet("SMB Base"), ["Enterprise Count", "YoY %"])
    adopt_df = to_num(load_sheet("Adoption"), ["Adoption %"])
    size_df  = to_num(load_sheet("Adoption Sizeclass"), ["Value %"])
    vcfg_df  = load_sheet("Vertical Config")
    arpu_df  = to_num(load_sheet("ARPU Config"), ["Default ARPU EUR"])

if smb_df.empty:
    st.warning("No market data yet. Run the Verticore scrapers (SMB + Adoption) to populate the sheet, then refresh.")
    st.stop()

# vertical -> adoption NACE group map (from Vertical Config)
vgroup = {}
if not vcfg_df.empty and "Vertical" in vcfg_df.columns:
    for _, r in vcfg_df.iterrows():
        v = str(r.get("Vertical", "")).strip()
        g = str(r.get("NACE Adoption Group", "")).strip()
        if v:
            vgroup[v] = g

verticals = sorted(smb_df["Vertical"].dropna().unique().tolist())
geos_avail = sorted(smb_df["Geo"].dropna().unique().tolist())
years_avail = sorted(smb_df["Year"].dropna().astype(str).unique().tolist())
latest_year = years_avail[-1] if years_avail else "2022"

# ── Filters ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Select your market</div>', unsafe_allow_html=True)
f1, f2, f3 = st.columns(3)
with f1:
    vertical = st.selectbox("Vertical", verticals, key="v_vertical")
with f2:
    geo = st.selectbox("Country", geos_avail, format_func=geo_label, key="v_geo")
with f3:
    default_arpu = ve.get_default_arpu(arpu_df, vertical) or 150.0
    arpu = st.number_input("ARPU (EUR / year)", min_value=1.0, max_value=100000.0,
                           value=float(default_arpu), step=10.0, key="v_arpu")

adjust = st.toggle("Apply micro-enterprise adjustment (recommended)", value=True,
                   help="Bridges the sector website-adoption rate down to micro-business reality, "
                        "using the live per-country size-class gradient from Eurostat. Fully transparent.")

nace_group = vgroup.get(vertical, "")

# ── Compute ────────────────────────────────────────────────────────────────────
res = ve.compute_market(smb_df, adopt_df, size_df, vertical, nace_group, geo,
                        latest_year, arpu, apply_micro_adjust=adjust)

def fmt_eur(v):
    if v is None: return "—"
    if v >= 1e9:  return f"€{v/1e9:.2f}B"
    if v >= 1e6:  return f"€{v/1e6:.1f}M"
    if v >= 1e3:  return f"€{v/1e3:.0f}K"
    return f"€{v:.0f}"

def fmt_int(v):
    return f"{int(round(v)):,}" if v is not None else "—"

st.markdown('<div class="section-hdr">Obtainable market</div>', unsafe_allow_html=True)

if not res["data_complete"]:
    missing = []
    if res["smb_count"] is None: missing.append("SMB count")
    if res["effective_adoption_pct"] is None: missing.append("adoption rate")
    if not res["arpu"]: missing.append("ARPU")
    st.markdown(f"""<div class="note">Live data for <strong>{vertical} · {geo_label(geo)}</strong>
      is incomplete ({', '.join(missing)} unavailable at source for this combination).
      Eurostat suppresses low-sample cells for some countries. Try another country, or see the
      data-coverage note below. No figure is shown rather than an invented one.</div>""",
      unsafe_allow_html=True)
else:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown(f"""<div class="hero">
          <div class="hero-lbl">Obtainable Market · {geo_label(geo)} · {latest_year}</div>
          <div class="hero-val">{fmt_eur(res['obtainable_market_eur'])}</div>
          <div style="margin-top:14px;">
            <span class="chip">📍 {vertical}</span>
            <span class="chip">{fmt_int(res['adopting_smbs'])} adopting SMBs</span>
          </div>
          <div style="font-size:0.75rem;color:rgba(255,255,255,0.82);margin-top:14px;line-height:1.6;">
            {fmt_int(res['smb_count'])} SMBs in market &nbsp;·&nbsp;
            {res['effective_adoption_pct']}% adoption &nbsp;·&nbsp;
            €{res['arpu']:.0f} ARPU/yr
          </div>
        </div>""", unsafe_allow_html=True)
    with c2:
        adj_txt = ""
        if res["adoption_was_adjusted"] and res["micro_basis"]:
            b = res["micro_basis"]
            adj_txt = (f"Sector website-adoption <strong>{res['headline_adoption_pct']}%</strong> "
                       f"(live Eurostat, {geo_label(geo)}) adjusted to "
                       f"<strong>{res['effective_adoption_pct']}%</strong> for micro-enterprises, "
                       f"using this country's size gradient "
                       f"(small firms {b['small_10_49']}% vs base {b['base_ge10']}% in {b['year']} "
                       f"→ ratio {res['micro_ratio']}).")
        else:
            adj_txt = (f"Sector website-adoption <strong>{res['headline_adoption_pct']}%</strong> "
                       f"(live Eurostat, {geo_label(geo)}). No micro-adjustment applied "
                       f"(size-class gradient not published for this country/group, or toggle off).")
        st.markdown(f"""<div style="background:#FFFFFF;border:1px solid #CDD2DB;border-radius:10px;padding:18px 20px;height:100%;">
          <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:{CLR};margin-bottom:8px;">How this is computed</div>
          <div style="font-size:0.82rem;color:#0D1117;line-height:1.6;">
            Obtainable Market = SMBs × Adoption × ARPU<br><br>{adj_txt}
          </div>
          <div class="prov">SMB count: Eurostat SBS (sbs_sc_ovw), TOTAL − 250+ employees, {latest_year}.
            Adoption: Eurostat ICT (isoc_ciwebn2 / isoc_ciweb), per country. Every figure is live and source-traceable.</div>
        </div>""", unsafe_allow_html=True)

    # ── Projection ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">2025–2030 projection</div>', unsafe_allow_html=True)
    pc1, pc2 = st.columns(2)
    with pc1:
        smb_growth = st.slider("SMB base growth % / year", 0.0, 3.0, 0.5, 0.1)
    with pc2:
        adopt_growth = st.slider("Adoption growth (pp / year)", 0.0, 5.0, 2.4, 0.1)

    proj = ve.project_forward(res, smb_growth, adopt_growth, ["2025","2026","2027","2028","2029","2030"])
    if proj:
        pdf = pd.DataFrame(proj)
        pdf_disp = pdf.copy()
        pdf_disp["Obtainable Market"] = pdf_disp["market_eur"].apply(fmt_eur)
        pdf_disp["SMBs"] = pdf_disp["smb_count"].apply(fmt_int)
        pdf_disp["Adopting SMBs"] = pdf_disp["adopting_smbs"].apply(fmt_int)
        pdf_disp["Adoption %"] = pdf_disp["adoption_pct"].astype(str) + "%"
        pdf_disp = pdf_disp.rename(columns={"year":"Year"})[["Year","SMBs","Adoption %","Adopting SMBs","Obtainable Market"]]
        st.dataframe(pdf_disp, use_container_width=True, hide_index=True, height=250)
        st.markdown(f'<div class="prov">Projection: SMB base compounds at {smb_growth}%/yr; adoption rises '
                    f'{adopt_growth}pp/yr (capped 100%); ARPU held flat. Transparent and adjustable above.</div>',
                    unsafe_allow_html=True)

# ── Opportunity matrix — cross-country ranking for the selected vertical ───────
st.markdown('<div class="section-hdr">Where is the opportunity? — all countries, this vertical</div>', unsafe_allow_html=True)
single_vcfg = {vertical: nace_group}
rank_df = ve.rank_opportunities(smb_df, adopt_df, size_df, arpu_df, single_vcfg, geos_avail,
                                latest_year, apply_micro_adjust=adjust)
if not rank_df.empty:
    disp = rank_df.copy()
    disp["Country"] = disp["Geo"].apply(geo_label)
    disp["Obtainable Market"] = disp["Obtainable Market (EUR)"].apply(fmt_eur)
    disp["SMBs"] = disp["SMBs"].apply(fmt_int)
    disp["Adoption %"] = disp["Adoption %"].astype(str) + "%"
    disp = disp[["Country","SMBs","Adoption %","Obtainable Market"]]
    st.dataframe(disp, use_container_width=True, hide_index=True, height=340)
    st.markdown('<div class="prov">Ranked by obtainable market. This is the geographic ICP view — '
                'which countries represent the largest prize for this vertical. Countries with suppressed '
                'source data are omitted, not estimated.</div>', unsafe_allow_html=True)
else:
    st.info("No cross-country data available yet for this vertical.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""<div style="border-top:1px solid #DDE1E7;margin-top:36px;padding:12px 0;
    display:flex;justify-content:space-between;font-size:0.65rem;color:#9CA3AF;">
  <span>Obtainable Market = SMBs × Adoption × ARPU · all inputs live from Eurostat · micro-adjustment anchored to per-country size gradient</span>
  <span>© 2026 Joscha Schmidt · Verticore · Confidential</span>
</div>""", unsafe_allow_html=True)
