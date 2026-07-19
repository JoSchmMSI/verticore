"""
Verticore — Computation Engine
==============================
Deterministic market-sizing plus the transparent micro-enterprise adjustment.

Core formula (per vertical x country x year):
    Obtainable Market (EUR) = SMB_count x Adoption_rate x ARPU

Everything here is computed from LIVE data pulled by the scrapers:
  - SMB_count      -> "SMB Base" tab (Eurostat SBS, per country, SMB size classes)
  - Adoption_rate  -> "Adoption" tab (Eurostat ICT website adoption, per country)
  - Size gradient  -> "Adoption Sizeclass" tab (per country, the AI-adjust anchor)
  - ARPU           -> user input (default from "ARPU Config")

The micro-enterprise adjustment is NOT invented. It is derived from the real
per-country size-class gradient in "Adoption Sizeclass": if a country's small
enterprises (10_49) adopt websites at, say, 0.82x the rate of the survey base
(GE10), that same 0.82 ratio is applied to bridge the headline sector figure
down toward micro-business reality. This keeps the adjustment anchored to live
Eurostat data, per country, and fully transparent/overridable in the UI.
"""

import pandas as pd


# ── SMB derivation ─────────────────────────────────────────────────────────────
def derive_smb_count(smb_base_df, vertical, geo, year):
    """
    SMB count derivation. Handles two data shapes:

    Shape A (sbs_sc_ovw with size classes): sum TOTAL - GE250 per NACE code.
    Shape B (sbs_ovw_act, total only): sbs_ovw_act has no size_emp dimension
      so all rows carry a TOTAL/proxy label. When no GE250 row exists, the
      total enterprise count IS the SMB proxy — these verticals (hairdressers,
      small builders, repair shops, sports clubs) are overwhelmingly micro/small.

    Returns (count, detail_dict).
    """
    if smb_base_df is None or smb_base_df.empty:
        return None, {}
    df = smb_base_df.copy()
    df["Enterprise Count"] = pd.to_numeric(
        df["Enterprise Count"].astype(str).str.replace(",", "."), errors="coerce"
    )
    df = df[(df["Vertical"] == vertical) & (df["Geo"] == geo) & (df["Year"].astype(str) == str(year))]
    if df.empty:
        return None, {}

    total = 0.0
    large = 0.0
    per_code = {}
    for code in df["NACE Code"].unique():
        sub   = df[df["NACE Code"] == code]
        # TOTAL row: any row whose Size Class starts with "TOTAL"
        t_rows = sub[sub["Size Class"].astype(str).str.startswith("TOTAL")]
        g_rows = sub[sub["Size Class"].astype(str) == "GE250"]
        t_val  = float(t_rows["Enterprise Count"].iloc[0]) if not t_rows.empty else 0.0
        g_val  = float(g_rows["Enterprise Count"].iloc[0]) if not g_rows.empty else 0.0
        # Shape B: no GE250 row → total IS the count (no large-enterprise deduction)
        smb_val = max(t_val - g_val, 0.0) if not g_rows.empty else t_val
        total  += t_val
        large  += g_val
        per_code[code] = smb_val

    # Shape B at aggregate level: no GE250 data → use total directly
    has_ge250 = not df[df["Size Class"].astype(str) == "GE250"].empty
    smb = max(total - large, 0.0) if has_ge250 else total
    return smb, {"total": total, "large": large, "per_code": per_code,
                 "size_class_available": has_ge250}


# ── Adoption + micro-enterprise adjustment ─────────────────────────────────────
def get_headline_adoption(adoption_df, vertical, geo, year):
    """Live sector adoption % for this vertical's NACE group, this country/year."""
    if adoption_df is None or adoption_df.empty:
        return None
    df = adoption_df[
        (adoption_df["Vertical"] == vertical)
        & (adoption_df["Geo"] == geo)
        & (adoption_df["Year"].astype(str) == str(year))
    ]
    if df.empty:
        # fall back to the most recent available year for this vertical/geo
        df2 = adoption_df[(adoption_df["Vertical"] == vertical) & (adoption_df["Geo"] == geo)]
        if df2.empty:
            return None
        latest = df2.sort_values("Year").iloc[-1]
        return float(latest["Adoption %"])
    return float(df.sort_values("Year").iloc[-1]["Adoption %"])


def compute_micro_ratio(sizeclass_df, nace_group, geo, year):
    """
    The AI-adjustment ANCHOR: from live per-country size-class data, compute how
    much less (or more) small enterprises adopt vs the survey base.

    ratio = adoption(10_49) / adoption(GE10)

    Returns (ratio, basis_dict). ratio < 1 means small firms lag the sector
    average (the usual case) -> headline is adjusted DOWN toward micro reality.
    If the data isn't available for a country, returns (None, {}) and the caller
    keeps the unadjusted headline (transparent: no adjustment claimed).
    """
    if sizeclass_df is None or sizeclass_df.empty:
        return None, {}
    df = sizeclass_df[
        (sizeclass_df["NACE Group"] == nace_group)
        & (sizeclass_df["Geo"] == geo)
    ]
    if df.empty:
        return None, {}
    # pick the most recent year that has both bands
    for yr in sorted(df["Year"].astype(str).unique(), reverse=True):
        d = df[df["Year"].astype(str) == yr]
        base  = d[d["Size Class"] == "GE10"]["Value %"]
        small = d[d["Size Class"] == "10_49"]["Value %"]
        if not base.empty and not small.empty and float(base.iloc[0]) > 0:
            ratio = float(small.iloc[0]) / float(base.iloc[0])
            return round(ratio, 4), {
                "year": yr,
                "base_ge10": float(base.iloc[0]),
                "small_10_49": float(small.iloc[0]),
            }
    return None, {}


def effective_adoption(headline_pct, micro_ratio, apply_micro_adjust):
    """
    Combine headline sector adoption with the per-country micro ratio.
    headline_pct is a percentage (e.g. 82.0). micro_ratio is a fraction (e.g. 0.82).
    Returns (effective_pct, was_adjusted).
    """
    if headline_pct is None:
        return None, False
    if apply_micro_adjust and micro_ratio is not None:
        return round(headline_pct * micro_ratio, 2), True
    return round(headline_pct, 2), False


# ── ARPU ───────────────────────────────────────────────────────────────────────
def get_default_arpu(arpu_df, vertical):
    if arpu_df is None or arpu_df.empty:
        return None
    df = arpu_df[arpu_df["Vertical"] == vertical]
    if df.empty:
        return None
    try:
        return float(df.iloc[0]["Default ARPU EUR"])
    except Exception:
        return None


# ── The core SOM computation ───────────────────────────────────────────────────
def compute_market(smb_base_df, adoption_df, sizeclass_df,
                   vertical, nace_group, geo, year, arpu,
                   apply_micro_adjust=True):
    """
    Returns a dict with the full computation and its provenance, or None inputs
    flagged transparently where live data is missing (never fabricated).
    """
    smb, smb_detail = derive_smb_count(smb_base_df, vertical, geo, year)
    headline = get_headline_adoption(adoption_df, vertical, geo, year)
    micro_ratio, micro_basis = compute_micro_ratio(sizeclass_df, nace_group, geo, year)
    eff_adopt, was_adjusted = effective_adoption(headline, micro_ratio, apply_micro_adjust)

    market = None
    adopting_smbs = None
    if smb is not None and eff_adopt is not None and arpu:
        adopting_smbs = smb * (eff_adopt / 100.0)
        market = adopting_smbs * float(arpu)

    return {
        "vertical": vertical,
        "geo": geo,
        "year": year,
        "smb_count": smb,
        "smb_detail": smb_detail,
        "headline_adoption_pct": headline,
        "micro_ratio": micro_ratio,
        "micro_basis": micro_basis,
        "effective_adoption_pct": eff_adopt,
        "adoption_was_adjusted": was_adjusted,
        "arpu": float(arpu) if arpu else None,
        "adopting_smbs": adopting_smbs,
        "obtainable_market_eur": market,
        "data_complete": all(x is not None for x in [smb, eff_adopt, arpu]),
    }


# ── Multi-year projection ──────────────────────────────────────────────────────
def project_forward(base_result, smb_growth_pct, adoption_growth_pp, years):
    """
    Simple, transparent, auditable projection.
      - SMB count grows at smb_growth_pct % per year (compound)
      - Adoption grows by adoption_growth_pp percentage-POINTS per year (linear,
        capped at 100%), mirroring the source model's linear adoption steps
      - ARPU held flat (user can model price growth separately)
    Returns list of per-year dicts.
    """
    out = []
    if not base_result or not base_result["data_complete"]:
        return out
    smb0   = base_result["smb_count"]
    adopt0 = base_result["effective_adoption_pct"]
    arpu   = base_result["arpu"]
    for i, yr in enumerate(years):
        smb   = smb0 * ((1 + smb_growth_pct / 100.0) ** i)
        adopt = min(adopt0 + adoption_growth_pp * i, 100.0)
        adopting = smb * (adopt / 100.0)
        out.append({
            "year": yr,
            "smb_count": round(smb),
            "adoption_pct": round(adopt, 2),
            "adopting_smbs": round(adopting),
            "market_eur": round(adopting * arpu),
        })
    return out


# ── Cross-vertical / cross-country ranking (for the opportunity matrix) ────────
def rank_opportunities(smb_base_df, adoption_df, sizeclass_df, arpu_df,
                       verticals_config, geos, year, apply_micro_adjust=True):
    """
    Compute obtainable market for every (vertical x geo) and return a ranked
    DataFrame — the ICP prioritisation view. verticals_config maps
    vertical -> nace_group.
    """
    rows = []
    for vertical, nace_group in verticals_config.items():
        arpu = get_default_arpu(arpu_df, vertical)
        for geo in geos:
            r = compute_market(smb_base_df, adoption_df, sizeclass_df,
                               vertical, nace_group, geo, year, arpu,
                               apply_micro_adjust)
            if r["obtainable_market_eur"] is not None:
                rows.append({
                    "Vertical": vertical,
                    "Geo": geo,
                    "SMBs": round(r["smb_count"]) if r["smb_count"] else 0,
                    "Adoption %": r["effective_adoption_pct"],
                    "ARPU": r["arpu"],
                    "Obtainable Market (EUR)": round(r["obtainable_market_eur"]),
                })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Obtainable Market (EUR)", ascending=False).reset_index(drop=True)
