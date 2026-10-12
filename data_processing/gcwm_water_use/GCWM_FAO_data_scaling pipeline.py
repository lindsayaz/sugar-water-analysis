# -*- coding: utf-8 -*-
"""
GCWM × FAO scaling pipeline (Sugarcane + Sugar beet)
Analysis-ready for spaghetti charts and Nature-style burden estimates

Created on Fri Feb 6, 2026
@author: nisni

====================================================================
WHY THIS SCRIPT EXISTS
====================================================================
GCWM country-year crop water use (ET, blue/green components) is driven by
*climate variability*, but is based on a fixed crop-area map around the
year ~2000 (e.g., MIRCA2000).

This means:
- Interannual variability in GCWM reflects climate/weather (good).
- Cultivated area does NOT change year-to-year inside GCWM (problem for
  “real burden” trends).
- For publication-grade (e.g., Nature-style) time series of water burden,
  GCWM water volumes should be scaled using FAO harvested area.

====================================================================
WHAT THIS SCRIPT DOES
====================================================================
For each crop (sugarcane, sugar beet):
1) Load GCWM country-year results (already extracted) including Continent.
2) Load FAO country-year harvested area + production.
3) Merge on iso3 + year.
4) Compute a hierarchical baseline harvested area per country:
   A) mean area in 1999–2001 (preferred)
   B) mean area in 1995–2005 (fallback)
   C) first non-zero area in the full time series (last resort)
5) Scale GCWM water volumes by FAO area.
6) Flag rows where scaling is impossible (transparent).
7) Build continent-year aggregates for thick-line plots:
   - total burden (km3)
   - area-weighted intensity (m3/ha)
   - production-weighted intensity (m3/t)
8) Report FAO area coverage (%) for SI transparency.

====================================================================
OUTPUT FILES
====================================================================
Saved into OUT_DIR:
- GCWM_FAOscaled_sugarcane_country_1981_2021.xlsx
- GCWM_FAOscaled_sugarbeet_country_1981_2021.xlsx
- GCWM_FAOscaled_ALL_country_1981_2021.xlsx
- GCWM_FAOscaled_continent_aggregates_SCALEDONLY_with_area_coverage_1981_2021.xlsx
"""

import pandas as pd
import numpy as np
from pathlib import Path


# =============================================================================
# 1) USER PATHS (EDIT ONLY THIS SECTION)
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GCWM_CANE = DATA_DIR / "GCWM_sugarcane_country_1981_2021_with_region.xlsx"
GCWM_BEET = DATA_DIR / "GCWM_sugar_beet_country_1981_2021_with_region.xlsx"

FAO_CANE = DATA_DIR / "FAO_sugarcane_area_production_1981_2021_iso3.xlsx"
FAO_BEET = DATA_DIR / "FAO_sugarbeet_area_production_1981_2021_iso3.xlsx"

OUT_DIR = BASE_DIR / "outputs"


# =============================================================================
# 2) KEY DESIGN CHOICES
# =============================================================================

BASELINE_YEARS_TIGHT = [1999, 2000, 2001]
BASELINE_YEARS_WIDE_START = 1995
BASELINE_YEARS_WIDE_END = 2005


# =============================================================================
# 3) SMALL HELPERS
# =============================================================================

def remove_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove Excel index columns like 'Unnamed: 7'."""
    return df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed")].copy()


def prep_fao_area_production(fao_path: Path) -> pd.DataFrame:
    """
    Convert FAO long format to wide:
    iso3 | year | area_ha | production_t
    """
    df = pd.read_excel(fao_path)
    df = remove_unnamed_columns(df)

    df = df.rename(columns={"Year": "year"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["iso3"] = df["iso3"].astype(str).str.strip()

    df = df[df["Element"].isin({"Area harvested", "Production"})]

    wide = (
        df.pivot_table(
            index=["iso3", "year"],
            columns="Element",
            values="Value",
            aggfunc="sum"
        )
        .reset_index()
        .rename(columns={
            "Area harvested": "area_ha",
            "Production": "production_t"
        })
    )

    for col in ["area_ha", "production_t"]:
        wide[col] = pd.to_numeric(wide[col], errors="coerce")

    return wide


# =============================================================================
# 4) CORE FUNCTION: SCALE GCWM WITH FAO AREA
# =============================================================================

def scale_gcwm_volumes_with_fao_area(gcwm_path: Path, fao_path: Path, crop_label: str) -> pd.DataFrame:

    g = remove_unnamed_columns(pd.read_excel(gcwm_path))
    g["year"] = pd.to_numeric(g["year"], errors="coerce").astype("Int64")
    g["iso3"] = g["iso3"].astype(str).str.strip()

    f = prep_fao_area_production(fao_path)
    df = g.merge(f, on=["iso3", "year"], how="left")

    # --- Baselines ---
    base1 = (
        df[df["year"].isin(BASELINE_YEARS_TIGHT)]
        .groupby("iso3", as_index=False)["area_ha"]
        .mean()
        .rename(columns={"area_ha": "area_ref_1999_2001"})
    )

    base2 = (
        df[df["year"].between(BASELINE_YEARS_WIDE_START, BASELINE_YEARS_WIDE_END)]
        .groupby("iso3", as_index=False)["area_ha"]
        .mean()
        .rename(columns={"area_ha": "area_ref_1995_2005"})
    )

    base3 = (
        df[df["area_ha"].fillna(0) > 0]
        .sort_values(["iso3", "year"])
        .groupby("iso3", as_index=False)
        .first()[["iso3", "area_ha"]]
        .rename(columns={"area_ha": "area_ref_first_nonzero"})
    )

    df = df.merge(base1, on="iso3", how="left")
    df = df.merge(base2, on="iso3", how="left")
    df = df.merge(base3, on="iso3", how="left")

    df["area_ref_final"] = df["area_ref_1999_2001"]
    df.loc[df["area_ref_final"].isna(), "area_ref_final"] = df["area_ref_1995_2005"]
    df.loc[df["area_ref_final"].isna(), "area_ref_final"] = df["area_ref_first_nonzero"]

    df["baseline_used"] = np.select(
        [
            df["area_ref_1999_2001"].fillna(0) > 0,
            df["area_ref_1995_2005"].fillna(0) > 0,
            df["area_ref_first_nonzero"].fillna(0) > 0,
        ],
        ["1999-2001", "1995-2005", "first_nonzero"],
        default="none"
    )

    df["scale_factor_area"] = df["area_ha"] / df["area_ref_final"]

    invalid = (
        df["scale_factor_area"].isna()
        | ~np.isfinite(df["scale_factor_area"])
        | (df["area_ha"] <= 0)
        | (df["area_ref_final"] <= 0)
    )
    df["scale_flag"] = np.where(invalid, "NO_SCALE", "SCALED")

    # --- Scale volumes ---
    for col in ["blue_m3", "green_total_m3", "total_m3"]:
        if col in df.columns:
            df[col + "_scaled"] = np.where(
                df["scale_flag"] == "SCALED",
                df[col] * df["scale_factor_area"],
                df[col]
            )

    if "blue_m3_scaled" in df.columns and "green_total_m3_scaled" in df.columns:
        df["et_m3_scaled"] = df["blue_m3_scaled"] + df["green_total_m3_scaled"]
    elif "total_m3_scaled" in df.columns:
        df["et_m3_scaled"] = df["total_m3_scaled"]
    else:
        df["et_m3_scaled"] = np.nan

    df["et_km3_scaled"] = df["et_m3_scaled"] / 1e9
    df["crop"] = crop_label

    return df


# =============================================================================
# 5) MAIN PIPELINE
# =============================================================================

def main():

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("OUT_DIR =", OUT_DIR.resolve())

    cane_scaled = scale_gcwm_volumes_with_fao_area(GCWM_CANE, FAO_CANE, "Sugarcane")
    beet_scaled = scale_gcwm_volumes_with_fao_area(GCWM_BEET, FAO_BEET, "Sugar beet")

    all_scaled = pd.concat([cane_scaled, beet_scaled], ignore_index=True)

    # --- Continent aggregates (SCALED ONLY) ---
    df_scaled = all_scaled[all_scaled["scale_flag"] == "SCALED"].copy()

    cont = (
        df_scaled.groupby(["crop", "Continent", "year"], as_index=False)
        .agg(
            et_m3=("et_m3_scaled", "sum"),
            area_ha=("area_ha", "sum"),
            production_t=("production_t", "sum")
        )
    )

    cont["et_km3"] = cont["et_m3"] / 1e9
    cont["et_m3_per_ha"] = cont["et_m3"] / cont["area_ha"]
    cont["et_m3_per_t"] = cont["et_m3"] / cont["production_t"]

    # --- FAO area coverage ---
    df_area_exists = all_scaled.copy()
    df_area_exists["area_exists"] = np.where(df_area_exists["area_ha"] > 0, df_area_exists["area_ha"], np.nan)

    area_total = (
        df_area_exists.groupby(["crop", "Continent", "year"], as_index=False)
        .agg(total_area_ha=("area_exists", "sum"))
    )

    cont = cont.merge(area_total, on=["crop", "Continent", "year"], how="left")
    cont["area_coverage_pct"] = 100 * cont["area_ha"] / cont["total_area_ha"]

    # --- Export ---
    cane_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarcane_country_1981_2021.xlsx", index=False)
    beet_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarbeet_country_1981_2021.xlsx", index=False)
    all_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_ALL_country_1981_2021.xlsx", index=False)
    cont.to_excel(
        OUT_DIR / "GCWM_FAOscaled_continent_aggregates_SCALEDONLY_with_area_coverage_1981_2021.xlsx",
        index=False
    )

    # --- Diagnostics ---
    print("\nScale flag counts:")
    print(all_scaled["scale_flag"].value_counts())

    print("\nBaseline used:")
    print(all_scaled["baseline_used"].value_counts())


if __name__ == "__main__":
    main()


#####################################################################################3
# -*- coding: utf-8 -*-
"""
GCWM × FAO scaling pipeline (Sugarcane + Sugar beet)
Analysis-ready for spaghetti charts and Nature-style burden estimates

Created on Fri Feb 11, 2026
@author: nisni

====================================================================
WHY THIS SCRIPT EXISTS
====================================================================
GCWM country-year crop water use (ET, blue/green components) is driven by
*climate variability*, but is based on a fixed crop-area map around the
year ~2000 (e.g., MIRCA2000).

This means:
- Interannual variability in GCWM reflects climate/weather (good).
- Cultivated area does NOT change year-to-year inside GCWM (problem for
  “real burden” trends).
- For publication-grade (e.g., Nature-style) time series of water burden,
  GCWM water volumes should be scaled using FAO harvested area.

====================================================================
WHAT THIS SCRIPT DOES
====================================================================
For each crop (sugarcane, sugar beet):
1) Load GCWM country-year results (already extracted) including Continent.
2) Load FAO country-year harvested area + production.
3) Merge on iso3 + year.
4) Compute a hierarchical baseline harvested area per country:
   A) mean area in 1999–2001 (preferred)
   B) mean area in 1995–2005 (fallback)
   C) first non-zero area in the full time series (last resort)
5) Scale GCWM water volumes by FAO area.
6) Flag rows where scaling is impossible (transparent).
7) Build continent-year aggregates for thick-line plots:
   - total burden (km3)
   - area-weighted intensity (m3/ha)
   - production-weighted intensity (m3/t)
8) Report FAO area coverage (%) for SI transparency.

====================================================================
OUTPUT FILES
====================================================================
Saved into OUT_DIR (original):
- GCWM_FAOscaled_sugarcane_country_1981_2021.xlsx
- GCWM_FAOscaled_sugarbeet_country_1981_2021.xlsx
- GCWM_FAOscaled_ALL_country_1981_2021.xlsx
- GCWM_FAOscaled_continent_aggregates_SCALEDONLY_with_area_coverage_1981_2021.xlsx

NEW (clean + aggregate):
- GCWM_FAOscaled_sugarcane_country_CLEAN_SCALEDONLY_1981_2021.xlsx
- GCWM_FAOscaled_sugarbeet_country_CLEAN_SCALEDONLY_1981_2021.xlsx
- GCWM_FAOscaled_sugar_ALL_countryyear_AGG_WATER_km3_SCALEDONLY_1981_2021.xlsx
"""

import pandas as pd
import numpy as np
from pathlib import Path


# =============================================================================
# 1) USER PATHS (EDIT ONLY THIS SECTION)
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GCWM_CANE = DATA_DIR / "GCWM_sugarcane_country_1981_2021_with_region.xlsx"
GCWM_BEET = DATA_DIR / "GCWM_sugar_beet_country_1981_2021_with_region.xlsx"

FAO_CANE = DATA_DIR / "FAO_sugarcane_area_production_1981_2021_iso3.xlsx"
FAO_BEET = DATA_DIR / "FAO_sugarbeet_area_production_1981_2021_iso3.xlsx"

OUT_DIR = BASE_DIR / "outputs"


# =============================================================================
# 2) KEY DESIGN CHOICES
# =============================================================================

BASELINE_YEARS_TIGHT = [1999, 2000, 2001]
BASELINE_YEARS_WIDE_START = 1995
BASELINE_YEARS_WIDE_END = 2005


# =============================================================================
# 3) SMALL HELPERS
# =============================================================================

def remove_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove Excel index columns like 'Unnamed: 7'."""
    return df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed")].copy()


def prep_fao_area_production(fao_path: Path) -> pd.DataFrame:
    """
    Convert FAO long format to wide:
    iso3 | year | area_ha | production_t
    """
    df = pd.read_excel(fao_path)
    df = remove_unnamed_columns(df)

    df = df.rename(columns={"Year": "year"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["iso3"] = df["iso3"].astype(str).str.strip()

    df = df[df["Element"].isin({"Area harvested", "Production"})]

    wide = (
        df.pivot_table(
            index=["iso3", "year"],
            columns="Element",
            values="Value",
            aggfunc="sum"
        )
        .reset_index()
        .rename(columns={
            "Area harvested": "area_ha",
            "Production": "production_t"
        })
    )

    for col in ["area_ha", "production_t"]:
        wide[col] = pd.to_numeric(wide[col], errors="coerce")

    return wide


def _to_km3(series: pd.Series) -> pd.Series:
    """Convert m3 to km3 (1 km3 = 1e9 m3)."""
    return pd.to_numeric(series, errors="coerce") / 1e9


# =============================================================================
# 4) CORE FUNCTION: SCALE GCWM WITH FAO AREA
# =============================================================================

def scale_gcwm_volumes_with_fao_area(gcwm_path: Path, fao_path: Path, crop_label: str) -> pd.DataFrame:

    g = remove_unnamed_columns(pd.read_excel(gcwm_path))
    g["year"] = pd.to_numeric(g["year"], errors="coerce").astype("Int64")
    g["iso3"] = g["iso3"].astype(str).str.strip()

    f = prep_fao_area_production(fao_path)
    df = g.merge(f, on=["iso3", "year"], how="left")

    # --- Baselines ---
    base1 = (
        df[df["year"].isin(BASELINE_YEARS_TIGHT)]
        .groupby("iso3", as_index=False)["area_ha"]
        .mean()
        .rename(columns={"area_ha": "area_ref_1999_2001"})
    )

    base2 = (
        df[df["year"].between(BASELINE_YEARS_WIDE_START, BASELINE_YEARS_WIDE_END)]
        .groupby("iso3", as_index=False)["area_ha"]
        .mean()
        .rename(columns={"area_ha": "area_ref_1995_2005"})
    )

    base3 = (
        df[df["area_ha"].fillna(0) > 0]
        .sort_values(["iso3", "year"])
        .groupby("iso3", as_index=False)
        .first()[["iso3", "area_ha"]]
        .rename(columns={"area_ha": "area_ref_first_nonzero"})
    )

    df = df.merge(base1, on="iso3", how="left")
    df = df.merge(base2, on="iso3", how="left")
    df = df.merge(base3, on="iso3", how="left")

    df["area_ref_final"] = df["area_ref_1999_2001"]
    df.loc[df["area_ref_final"].isna(), "area_ref_final"] = df["area_ref_1995_2005"]
    df.loc[df["area_ref_final"].isna(), "area_ref_final"] = df["area_ref_first_nonzero"]

    df["baseline_used"] = np.select(
        [
            df["area_ref_1999_2001"].fillna(0) > 0,
            df["area_ref_1995_2005"].fillna(0) > 0,
            df["area_ref_first_nonzero"].fillna(0) > 0,
        ],
        ["1999-2001", "1995-2005", "first_nonzero"],
        default="none"
    )

    df["scale_factor_area"] = df["area_ha"] / df["area_ref_final"]

    invalid = (
        df["scale_factor_area"].isna()
        | ~np.isfinite(df["scale_factor_area"])
        | (df["area_ha"] <= 0)
        | (df["area_ref_final"] <= 0)
    )
    df["scale_flag"] = np.where(invalid, "NO_SCALE", "SCALED")

    # --- Scale volumes ---
    for col in ["blue_m3", "green_total_m3", "total_m3"]:
        if col in df.columns:
            df[col + "_scaled"] = np.where(
                df["scale_flag"] == "SCALED",
                df[col] * df["scale_factor_area"],
                df[col]
            )

    if "blue_m3_scaled" in df.columns and "green_total_m3_scaled" in df.columns:
        df["et_m3_scaled"] = df["blue_m3_scaled"] + df["green_total_m3_scaled"]
    elif "total_m3_scaled" in df.columns:
        df["et_m3_scaled"] = df["total_m3_scaled"]
    else:
        df["et_m3_scaled"] = np.nan

    df["et_km3_scaled"] = df["et_m3_scaled"] / 1e9
    df["crop"] = crop_label

    return df


# =============================================================================
# 5) NEW: CLEAN EXPORTS (SCALED ONLY) + AGGREGATE (BALANCED PANEL)
# =============================================================================

def make_clean_scaled_export(df: pd.DataFrame, crop_label: str) -> pd.DataFrame:
    """
    Keep only requested columns + create km3 versions for blue/green.
    Filter to scale_flag == 'SCALED'.
    """
    d = df.copy()
    d = d[d["scale_flag"] == "SCALED"].copy()

    d["crop"] = crop_label

    # km3 columns derived from scaled m3
    d["blue_km3_scaled"] = _to_km3(d["blue_m3_scaled"])
    d["green_total_km3_scaled"] = _to_km3(d["green_total_m3_scaled"])

    keep_cols = [
        "iso3", "country", "year", "Region", "Continent",
        "area_ha", "production_t",
        "blue_m3_scaled", "green_total_m3_scaled",
        "blue_km3_scaled", "green_total_km3_scaled",
        "et_km3_scaled",
        "crop",
    ]
    keep_cols = [c for c in keep_cols if c in d.columns]

    return d[keep_cols].sort_values(["iso3", "year"]).reset_index(drop=True)


def make_country_year_aggregate_balanced(cane_clean: pd.DataFrame, beet_clean: pd.DataFrame) -> pd.DataFrame:
    """
    Country-year aggregate (1981–2021) across both crops:
    - totals in km3: blue, green, et
    - flags: Sugarcane / Sugar_beet (Yes/No)
    - balanced panel: every iso3 gets every year 1981–2021 (missing -> 0)
    """
    c = cane_clean.copy()
    b = beet_clean.copy()

    # flags
    c["Sugarcane"] = "Yes"
    c["Sugar_beet"] = "No"
    b["Sugarcane"] = "No"
    b["Sugar_beet"] = "Yes"

    # combine
    comb = pd.concat([c, b], ignore_index=True)

    # lookups (for filling after balancing)
    country_lu = comb[["iso3", "country"]].dropna(subset=["iso3"]).drop_duplicates("iso3")
    region_lu = comb[["iso3", "Region"]].dropna(subset=["iso3"]).drop_duplicates("iso3")
    cont_lu = comb[["iso3", "Continent"]].dropna(subset=["iso3"]).drop_duplicates("iso3")

    # aggregate by iso3+year
    agg = (
        comb.groupby(["iso3", "year"], as_index=False)
        .agg(
            # keep first available for labels
            Region=("Region", "first"),
            Continent=("Continent", "first"),
            # totals across crops
            area_ha_total=("area_ha", "sum"),
            production_t_total=("production_t", "sum"),
            blue_km3_total=("blue_km3_scaled", "sum"),
            green_km3_total=("green_total_km3_scaled", "sum"),
            et_km3_total=("et_km3_scaled", "sum"),
            Sugarcane=("Sugarcane", lambda s: "Yes" if (s == "Yes").any() else "No"),
            Sugar_beet=("Sugar_beet", lambda s: "Yes" if (s == "Yes").any() else "No"),
        )
    )

    # ---- force balanced panel ----
    years = list(range(1981, 2022))  # inclusive 1981–2021 (41 years)
    iso3_list = sorted(agg["iso3"].dropna().unique())

    full_index = pd.MultiIndex.from_product([iso3_list, years], names=["iso3", "year"])
    agg = agg.set_index(["iso3", "year"]).reindex(full_index).reset_index()

    # reattach labels
    agg = agg.merge(country_lu, on="iso3", how="left")
    agg = agg.merge(region_lu, on="iso3", how="left", suffixes=("", "_lu"))
    agg = agg.merge(cont_lu, on="iso3", how="left", suffixes=("", "_lu2"))

    # if Region/Continent were missing due to reindex, fill from lookup
    if "Region_lu" in agg.columns:
        agg["Region"] = agg["Region"].fillna(agg["Region_lu"])
        agg = agg.drop(columns=["Region_lu"])
    if "Continent_lu2" in agg.columns:
        agg["Continent"] = agg["Continent"].fillna(agg["Continent_lu2"])
        agg = agg.drop(columns=["Continent_lu2"])

    # fill numeric totals with 0 (meaning: no sugar water that year)
    numeric_cols = [
        "area_ha_total", "production_t_total",
        "blue_km3_total", "green_km3_total", "et_km3_total"
    ]
    for col in numeric_cols:
        if col in agg.columns:
            agg[col] = pd.to_numeric(agg[col], errors="coerce").fillna(0.0)

    # fill flags with No
    for flag in ["Sugarcane", "Sugar_beet"]:
        if flag in agg.columns:
            agg[flag] = agg[flag].fillna("No")

    # final ordering
    col_order = [
        "iso3", "country", "year", "Region", "Continent",
        "Sugarcane", "Sugar_beet",
        "area_ha_total", "production_t_total",
        "blue_km3_total", "green_km3_total", "et_km3_total",
    ]
    col_order = [c for c in col_order if c in agg.columns]

    return agg[col_order].sort_values(["iso3", "year"]).reset_index(drop=True)


# =============================================================================
# 6) MAIN PIPELINE
# =============================================================================

def main():

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("OUT_DIR =", OUT_DIR.resolve())

    cane_scaled = scale_gcwm_volumes_with_fao_area(GCWM_CANE, FAO_CANE, "Sugarcane")
    beet_scaled = scale_gcwm_volumes_with_fao_area(GCWM_BEET, FAO_BEET, "Sugar beet")

    all_scaled = pd.concat([cane_scaled, beet_scaled], ignore_index=True)

    # --- Continent aggregates (SCALED ONLY) ---
    df_scaled = all_scaled[all_scaled["scale_flag"] == "SCALED"].copy()

    cont = (
        df_scaled.groupby(["crop", "Continent", "year"], as_index=False)
        .agg(
            et_m3=("et_m3_scaled", "sum"),
            area_ha=("area_ha", "sum"),
            production_t=("production_t", "sum")
        )
    )

    cont["et_km3"] = cont["et_m3"] / 1e9
    cont["et_m3_per_ha"] = cont["et_m3"] / cont["area_ha"]
    cont["et_m3_per_t"] = cont["et_m3"] / cont["production_t"]

    # --- FAO area coverage ---
    df_area_exists = all_scaled.copy()
    df_area_exists["area_exists"] = np.where(df_area_exists["area_ha"] > 0, df_area_exists["area_ha"], np.nan)

    area_total = (
        df_area_exists.groupby(["crop", "Continent", "year"], as_index=False)
        .agg(total_area_ha=("area_exists", "sum"))
    )

    cont = cont.merge(area_total, on=["crop", "Continent", "year"], how="left")
    cont["area_coverage_pct"] = 100 * cont["area_ha"] / cont["total_area_ha"]

    # --- Export original full outputs ---
    cane_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarcane_country_1981_2021.xlsx", index=False)
    beet_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarbeet_country_1981_2021.xlsx", index=False)
    all_scaled.to_excel(OUT_DIR / "GCWM_FAOscaled_ALL_country_1981_2021.xlsx", index=False)
    cont.to_excel(
        OUT_DIR / "GCWM_FAOscaled_continent_aggregates_SCALEDONLY_with_area_coverage_1981_2021.xlsx",
        index=False
    )

    # --- NEW: clean SCALED-only files ---
    cane_clean = make_clean_scaled_export(cane_scaled, "Sugarcane")
    beet_clean = make_clean_scaled_export(beet_scaled, "Sugar beet")

    cane_clean.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarcane_country_CLEAN_SCALEDONLY_1981_2021.xlsx", index=False)
    beet_clean.to_excel(OUT_DIR / "GCWM_FAOscaled_sugarbeet_country_CLEAN_SCALEDONLY_1981_2021.xlsx", index=False)

    # --- NEW: aggregate country-year (balanced panel, zeros) ---
    agg_country_year = make_country_year_aggregate_balanced(cane_clean, beet_clean)
    agg_country_year.to_excel(
        OUT_DIR / "GCWM_FAOscaled_sugar_ALL_countryyear_AGG_WATER_km3_SCALEDONLY_1981_2021.xlsx",
        index=False
    )

    # --- Diagnostics ---
    print("\nScale flag counts:")
    print(all_scaled["scale_flag"].value_counts())

    print("\nBaseline used:")
    print(all_scaled["baseline_used"].value_counts())

    # quick sanity check: should be 41 rows per iso3 in aggregate
    check = agg_country_year.groupby("iso3").size()
    print("\nAggregate panel rows per iso3 (min/max):", int(check.min()), int(check.max()))


if __name__ == "__main__":
    main()
