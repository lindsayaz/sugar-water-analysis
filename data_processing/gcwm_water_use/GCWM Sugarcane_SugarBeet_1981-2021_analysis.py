# -*- coding: utf-8 -*-
"""
Created on Mon Aug 25 19:35:51 2025

@author: nisni
"""

import pandas as pd
from pathlib import Path

# =========================
# File paths
# =========================

base_dir = Path(__file__).resolve().parent
data_dir = base_dir / "data"

cane_file = data_dir / "GCWM_sugarcane_country_1981_2021.xlsx"
beet_file = data_dir / "GCWM_sugar_beet_country_1981_2021.xlsx"

region_file = data_dir / "countries list_by continent_region.xlsx"

# =========================
# Load files
# =========================

df_cane = pd.read_excel(cane_file)
df_beet = pd.read_excel(beet_file)
df_region = pd.read_excel(region_file)

# =========================
# Remove empty "Unnamed" columns (Excel artifacts)
# =========================

df_cane = df_cane.loc[:, ~df_cane.columns.str.contains("^Unnamed")]
df_beet = df_beet.loc[:, ~df_beet.columns.str.contains("^Unnamed")]

# =========================
# Drop rows with missing ISO3 (invalid rows)
# =========================

df_cane = df_cane[df_cane['iso3'].notna()]
df_beet = df_beet[df_beet['iso3'].notna()]

# =========================
# Merge Region + Continent
# =========================

df_cane = df_cane.merge(
    df_region[['iso3', 'Region', 'Continent']],
    on='iso3',
    how='left'
)

df_beet = df_beet.merge(
    df_region[['iso3', 'Region', 'Continent']],
    on='iso3',
    how='left'
)

# =========================
# Manual fixes for missing countries
# =========================

manual_regions = {
    "PRI": {"Continent": "North America", "Region": "Caribbean"},
    "SDS": {"Continent": "Africa", "Region": "Eastern Africa"},
    "SOL": {"Continent": "Africa", "Region": "Eastern Africa"},
    "KOS": {"Continent": "Europe", "Region": "Southern Europe"},
}

def apply_manual_fixes(df):
    for iso, vals in manual_regions.items():
        mask = df['iso3'] == iso
        df.loc[mask, 'Continent'] = vals["Continent"]
        df.loc[mask, 'Region'] = vals["Region"]
    return df

df_cane = apply_manual_fixes(df_cane)
df_beet = apply_manual_fixes(df_beet)

# =========================
# Final missing check
# =========================

def report_missing(df, label):
    missing = df[df['Region'].isna() | df['Continent'].isna()]
    print(f"\n--- Missing region/continent in {label} ---")
    if missing.empty:
        print("None ✅")
    else:
        cols = ['iso3']
        if 'country' in missing.columns:
            cols.append('country')
        print(missing[cols].drop_duplicates().sort_values('iso3'))

report_missing(df_cane, "Sugarcane")
report_missing(df_beet, "Sugar beet")

# =========================
# Save outputs
# =========================

cane_out = cane_file.with_name("GCWM_sugarcane_country_1981_2021_with_region.xlsx")
beet_out = beet_file.with_name("GCWM_sugar_beet_country_1981_2021_with_region.xlsx")

df_cane.to_excel(cane_out, index=False)
df_beet.to_excel(beet_out, index=False)

print("\nSaved files:")
print(cane_out)
print(beet_out)


# ------------------------------------------------------------
"""
FAOSTAT filter + ISO3 mapping for GCWM scaling

What this script does:
1) Reads FAOSTAT exports for Sugar cane and Sugar beet.
2) Filters to years 1981–2021.
3) Keeps only the Elements needed for:
   - land-use scaling: Area harvested (ha)
   - optional weighting later: Production (t)
4) Adds ISO3 codes (best-effort mapping from FAO country names).
5) Exports 2 cleaned Excel files for easy merging with GCWM country-year tables.

Why:
- GCWM outputs assume a static crop map (~year 2000). To approximate land-use change,
  we scale GCWM volumes using FAO harvested area time series (country x year).
- Joining by ISO3 is the most robust way to merge datasets.

Important:
- Some FAO "Area" names are historical aggregates (e.g., USSR) or special territories.
  These will not map automatically to ISO3 and will require manual handling.
"""

import os
import pandas as pd


# ============================================================
# 1) PATHS — EDIT THESE
# ============================================================

# Folder with your FAO source files (input)
IN_DIR = str(data_dir)

# FAO files you received/exported
FAO_CANE_FILE = os.path.join(IN_DIR, "SUGARCAN - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx")
FAO_BEET_FILE = os.path.join(IN_DIR, "SUGAR_BEET - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx")

# Output folder (same folder as requested)
OUT_DIR = IN_DIR

# Output file names
OUT_CANE = os.path.join(OUT_DIR, "FAO_sugarcane_area_production_1981_2021_iso3.xlsx")
OUT_BEET = os.path.join(OUT_DIR, "FAO_sugarbeet_area_production_1981_2021_iso3.xlsx")


# ============================================================
# 2) HELPER: ISO3 mapping from FAO country name
# ============================================================

def iso3_from_fao_area_name(name: str):
    """
    Convert FAO country name to ISO3.
    Uses country_converter if available (recommended),
    otherwise falls back to pycountry.

    Returns:
      ISO3 code (str) or None if not found.
    """
    if pd.isna(name):
        return None

    name = str(name).strip()

    # Common FAO/UN naming fixes (extend as needed)
    fixes = {
        "Bolivia (Plurinational State of)": "Bolivia",
        "Venezuela (Bolivarian Republic of)": "Venezuela",
        "Iran (Islamic Republic of)": "Iran",
        "Syrian Arab Republic": "Syria",
        "Lao People's Democratic Republic": "Laos",
        "Côte d'Ivoire": "Cote d'Ivoire",
        "Türkiye": "Turkey",
        "United Republic of Tanzania": "Tanzania",
        "Viet Nam": "Vietnam",
        "Russian Federation": "Russia",
        "Republic of Moldova": "Moldova",
        "Cabo Verde": "Cape Verde",
        "Eswatini": "Swaziland",
        "China, mainland": "China",
        "China, Taiwan Province of": "Taiwan",
        "China, Hong Kong SAR": "Hong Kong",
        "China, Macao SAR": "Macao",
        "United States of America": "United States",
        "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
        "Réunion": "Reunion",
    }

    name_fixed = fixes.get(name, name)

    # Try country_converter (best)
    try:
        import country_converter as coco
        iso = coco.convert(names=[name_fixed], to="ISO3", not_found=None)
        if isinstance(iso, list):
            iso = iso[0]
        if iso and iso != "not found":
            return iso
    except Exception:
        pass

    # Fallback: pycountry
    try:
        import pycountry
        c = pycountry.countries.lookup(name_fixed)
        return c.alpha_3
    except Exception:
        return None


# ============================================================
# 3) FILTER FUNCTION
# ============================================================

def filter_fao_file(path: str, item_name: str, year_min=1981, year_max=2021):
    """
    Filters a FAOSTAT Excel table to:
    - one Item (Sugar cane / Sugar beet)
    - years in [1981, 2021]
    - Elements: Area harvested + Production
    Adds iso3 column.

    Returns a cleaned dataframe.
    """
    df = pd.read_excel(path)

    # Ensure expected columns exist
    expected = {"Area", "Item", "Element", "Year", "Unit", "Value"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {os.path.basename(path)}: {missing}")

    # 1) Filter by item (crop)
    df["Item"] = df["Item"].astype(str).str.strip()
    df = df[df["Item"].str.lower() == item_name.lower()]

    # 2) Filter by element (only what we need)
    needed_elements = {"Area harvested", "Production"}
    df["Element"] = df["Element"].astype(str).str.strip()
    df = df[df["Element"].isin(needed_elements)]

    # 3) Filter by years
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df[df["Year"].between(year_min, year_max)]

    # 4) Add ISO3
    df["iso3"] = df["Area"].apply(iso3_from_fao_area_name)

    # 5) Keep only relevant columns (plus Area Code if available)
    keep_cols = ["iso3", "Area", "Area Code", "Item", "Element", "Year", "Unit", "Value"]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()

    # Sort for readability
    df = df.sort_values(["iso3", "Element", "Year"], na_position="last")

    return df


# ============================================================
# 4) RUN FOR BOTH CROPS + EXPORT
# ============================================================

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    # Sugar cane
    cane = filter_fao_file(FAO_CANE_FILE, item_name="Sugar cane")
    cane.to_excel(OUT_CANE, index=False)

    # Sugar beet
    beet = filter_fao_file(FAO_BEET_FILE, item_name="Sugar beet")
    beet.to_excel(OUT_BEET, index=False)

    # Diagnostics: list unmapped FAO "Area" names
    cane_unmapped = sorted(cane.loc[cane["iso3"].isna(), "Area"].dropna().unique().tolist())
    beet_unmapped = sorted(beet.loc[beet["iso3"].isna(), "Area"].dropna().unique().tolist())

    print("Saved:")
    print(" -", OUT_CANE)
    print(" -", OUT_BEET)

    print("\nUnmapped FAO country names (Sugar cane):", len(cane_unmapped))
    print(cane_unmapped[:50])  # show up to 50

    print("\nUnmapped FAO country names (Sugar beet):", len(beet_unmapped))
    print(beet_unmapped[:50])  # show up to 50

    print("\nNote: unmapped names are often historical aggregates (e.g., USSR) or special territories.")
    print("You can handle them by creating a manual mapping dictionary and re-running the ISO3 step.")
