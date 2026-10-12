# -*- coding: utf-8 -*-

"""
===============================================================================
PREPARE 2021 COUNTRY-LEVEL SUGAR WATER DATA FOR THE SANKEY DIAGRAM
===============================================================================

Purpose
-------
This script prepares a country-level table for the 2021 sugar-water Sankey
diagram.

The original dataset contains separate rows for sugarcane and sugar beet.
Therefore, some countries appear twice:

    - one row for Sugarcane
    - one row for Sugar beet

The script reshapes the data so that each country appears only once, with
separate water-use columns for sugarcane and sugar beet.

Main steps
----------
1. Read the country-level GCWM dataset.
2. Filter the dataset to the year 2021.
3. Keep only the required columns.
4. Check the crop labels.
5. Check for duplicate country-crop records.
6. Reshape crop rows into separate sugarcane and sugar-beet columns.
7. Convert blue and green evapotranspiration from m³ to km³.
8. Calculate total blue + green evapotranspiration for each crop.
9. Verify that there is one row per country.
10. Display the resulting table in Python without exporting it.

Important
---------
Countries that produce only one crop will initially have missing values for
the other crop. These missing crop-specific values are replaced with zero for
the Sankey input table.
===============================================================================
"""

from pathlib import Path

import pandas as pd


# =============================================================================
# 1. DEFINE THE INPUT FILE
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "S1_Country-level blue and green GCWM by sugarcane and sugar beet production.xlsx"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 2. READ THE EXCEL FILE
# =============================================================================

df = pd.read_excel(INPUT_FILE)

print("=" * 79)
print("PREPARING 2021 COUNTRY-LEVEL SUGAR-WATER DATA")
print("=" * 79)

print(f"\nOriginal dataset: {len(df):,} rows")
print(f"\nInput file:\n{INPUT_FILE}")


# =============================================================================
# 3. CHECK THAT THE REQUIRED COLUMNS EXIST
# =============================================================================

required_columns = [
    "iso3",
    "country",
    "year",
    "crop",
    "blue_m3_scaled",
    "green_total_m3_scaled",
    "production_t",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise KeyError(
        "The following required columns are missing from the dataset:\n"
        + "\n".join(f"- {column}" for column in missing_columns)
    )


# =============================================================================
# 4. CLEAN THE VARIABLES USED IN THE ANALYSIS
# =============================================================================

# Remove leading and trailing spaces from text columns.
for column in ["iso3", "country", "crop"]:
    df[column] = (
        df[column]
        .astype(str)
        .str.strip()
    )


# Convert year and water variables to numeric.
# Any invalid text values are converted to NaN.
df["year"] = pd.to_numeric(
    df["year"],
    errors="coerce",
)

df["blue_m3_scaled"] = pd.to_numeric(
    df["blue_m3_scaled"],
    errors="coerce",
)

df["green_total_m3_scaled"] = pd.to_numeric(
    df["green_total_m3_scaled"],
    errors="coerce",
)

df["production_t"] = pd.to_numeric(
    df["production_t"],
    errors="coerce",
)


# =============================================================================
# 5. FILTER THE DATASET TO 2021
# =============================================================================

df_2021 = df[
    df["year"] == 2021
].copy()

print(f"\nRows after filtering to 2021: {len(df_2021):,}")


# =============================================================================
# 6. KEEP ONLY THE REQUIRED COLUMNS
# =============================================================================

df_2021 = df_2021[
    [
        "iso3",
        "country",
        "year",
        "crop",
        "blue_m3_scaled",
        "green_total_m3_scaled",
        "production_t",
    ]
].copy()


# =============================================================================
# 7. CHECK THE CROP LABELS
# =============================================================================

print("\nCrop labels found in the 2021 data:")
print(df_2021["crop"].value_counts(dropna=False))


expected_crops = {
    "Sugarcane",
    "Sugar beet",
}

unexpected_crops = (
    set(df_2021["crop"].dropna().unique())
    - expected_crops
)

if unexpected_crops:
    raise ValueError(
        "Unexpected crop labels were found:\n"
        + "\n".join(
            f"- {crop}"
            for crop in sorted(unexpected_crops)
        )
    )


# =============================================================================
# 8. CHECK FOR DUPLICATE COUNTRY-CROP RECORDS
# =============================================================================

# Each country should have no more than one row for each crop in 2021.
#
# Example:
#     Brazil + Sugarcane = one row
#     Brazil + Sugar beet = one row

duplicate_mask = df_2021.duplicated(
    subset=["iso3", "year", "crop"],
    keep=False,
)

duplicate_rows = df_2021.loc[
    duplicate_mask,
    [
        "iso3",
        "country",
        "year",
        "crop",
        "blue_m3_scaled",
        "green_total_m3_scaled",
    ],
]

if not duplicate_rows.empty:
    print("\nDuplicate country-crop records found:")
    print(
        duplicate_rows
        .sort_values(["iso3", "crop"])
        .to_string(index=False)
    )

    raise ValueError(
        "The 2021 dataset contains more than one row for at least one "
        "country-crop combination. These duplicates should be checked "
        "before reshaping the data."
    )


# =============================================================================
# 9. RESHAPE THE DATA TO ONE ROW PER COUNTRY
# =============================================================================

# In the original dataset, crop type is stored in rows:
#
# iso3   country   year   crop          blue_m3_scaled
# BRA    Brazil    2021   Sugarcane     ...
# BRA    Brazil    2021   Sugar beet    ...
#
# We reshape the table so that crop type is stored in separate columns.

df_wide = df_2021.pivot_table(
    index=[
        "iso3",
        "country",
        "year",
    ],
    columns="crop",
    values=[
        "blue_m3_scaled",
        "green_total_m3_scaled",
        "production_t",
    ],
    aggfunc="first",
)


# =============================================================================
# 10. FLATTEN AND RENAME THE PIVOTED COLUMNS
# =============================================================================

# The pivot creates two-level column names such as:
#
#     ("blue_m3_scaled", "Sugarcane")
#     ("green_total_m3_scaled", "Sugar beet")
#
# We convert these into clear, ordinary one-level column names.

column_name_map = {
    (
        "blue_m3_scaled",
        "Sugarcane",
    ): "blue_ET_m3_Sugarcane",

    (
        "green_total_m3_scaled",
        "Sugarcane",
    ): "green_ET_m3_Sugarcane",

    (
        "blue_m3_scaled",
        "Sugar beet",
    ): "blue_ET_m3_Sugarbeet",

    (
        "green_total_m3_scaled",
        "Sugar beet",
    ): "green_ET_m3_Sugarbeet",
    (
        "production_t",
        "Sugarcane",
    ): "production_t_Sugarcane",
    (
        "production_t",
        "Sugar beet",
    ): "production_t_Sugarbeet",
}


df_wide.columns = [
    column_name_map.get(
        column,
        "_".join(
            str(part)
            for part in column
            if str(part)
        ),
    )
    for column in df_wide.columns
]


# Convert iso3, country, and year from index fields back into normal columns.
df_wide = df_wide.reset_index()


print("\nColumns after reshaping:")
print(df_wide.columns.tolist())


# =============================================================================
# 11. ENSURE THAT ALL FOUR WATER COLUMNS EXIST
# =============================================================================

# A crop-specific column could theoretically be absent if no country had that
# crop in the filtered year. This ensures that the expected structure exists.

water_columns_m3 = [
    "blue_ET_m3_Sugarcane",
    "green_ET_m3_Sugarcane",
    "blue_ET_m3_Sugarbeet",
    "green_ET_m3_Sugarbeet",
]

production_columns_t = [
    "production_t_Sugarcane",
    "production_t_Sugarbeet",
]

for column in water_columns_m3 + production_columns_t:
    if column not in df_wide.columns:
        df_wide[column] = 0.0


# =============================================================================
# 12. REPLACE MISSING CROP-SPECIFIC VALUES WITH ZERO
# =============================================================================

# A country that produces only sugarcane will have NaN in the sugar-beet
# columns, and vice versa.
#
# For the Sankey input table, these crop-specific missing values are treated
# as zero.

df_wide[water_columns_m3 + production_columns_t] = (
    df_wide[water_columns_m3 + production_columns_t]
    .fillna(0)
)


# =============================================================================
# 13. CONVERT WATER VALUES FROM m³ TO km³
# =============================================================================

# Unit conversion:
#
#     1 km³ = 1,000,000,000 m³
#
# Therefore:
#
#     value in km³ = value in m³ / 1,000,000,000

M3_PER_KM3 = 1_000_000_000


df_wide["blue_ET_km3_Sugarcane"] = (
    df_wide["blue_ET_m3_Sugarcane"]
    / M3_PER_KM3
)

df_wide["green_ET_km3_Sugarcane"] = (
    df_wide["green_ET_m3_Sugarcane"]
    / M3_PER_KM3
)

df_wide["blue_ET_km3_Sugarbeet"] = (
    df_wide["blue_ET_m3_Sugarbeet"]
    / M3_PER_KM3
)

df_wide["green_ET_km3_Sugarbeet"] = (
    df_wide["green_ET_m3_Sugarbeet"]
    / M3_PER_KM3
)


# =============================================================================
# 14. CONVERT PRODUCTION VALUES FROM TONNES TO GIGATONNES
# =============================================================================

TONNES_PER_GT = 1_000_000_000

df_wide["production_Gt_Sugarcane"] = (
    df_wide["production_t_Sugarcane"]
    / TONNES_PER_GT
)

df_wide["production_Gt_Sugarbeet"] = (
    df_wide["production_t_Sugarbeet"]
    / TONNES_PER_GT
)


# =============================================================================
# 15. FIELD LOSSES AND TO-MILL MASS
# =============================================================================

# Calculate field losses from harvested sugarcane production based on the: https://doi.org/10.1016/j.resconrec.2026.109000
# 8% field-loss share estimated in the previous global sugar MFA study
# then derive the mass delivered to the mill

df_wide["Stalk_losses_in_field_Gt"] = (
    df_wide["production_Gt_Sugarcane"]
    * 0.08
)

df_wide["Stalk_losses_in_field_water_km^3"] = (
    df_wide["Stalk_losses_in_field_Gt"]
    * 0.70
)

df_wide["Stalk_to_mill_Gt"] = (
    df_wide["production_Gt_Sugarcane"]
    - df_wide["Stalk_losses_in_field_Gt"]
)

df_wide["Taproot_losses_in_field_Gt"] = (
    df_wide["production_Gt_Sugarbeet"]
    * 0.10
)

df_wide["Taproot_losses_in_field_water_km^3"] = (
    df_wide["Taproot_losses_in_field_Gt"]
    * 0.80
)

df_wide["Taproot_to_mill_Gt"] = (
    df_wide["production_Gt_Sugarbeet"]
    - df_wide["Taproot_losses_in_field_Gt"]
)


# =============================================================================
# 16. SUGARCANE TO THE MILL
# =============================================================================

# The following columns estimate how much water and straw are associated
# with sugarcane mass delivered to the mill.
#
# Source for stalk water fraction:
#   DOI: 10.1007/s12355-019-00735-8
#   This uses 70% of sugarcane production mass as the water content of the
#   harvested stalk material.
#
# Sources for straw mass and straw water fraction:
#   DOI: 10.1016/j.indcrop.2023.117112
#   DOI: 10.1016/j.rser.2023.113647
#   We assume straw mass is 24% of sugarcane production (stalk) mass,
#   and that 15% of that straw mass is water.
#
# Source for bagasse fraction:
#   FAO commodity tree methodology
#   https://www.fao.org/fileadmin/templates/ess/documents/methodology/tcf.pdf
#   We assume 25% of sugarcane production mass becomes bagasse.
#
# Sources for bagasse water content:
#   DOI: 10.1016/j.biortech.2020.122929
#   DOI: 10.1016/j.rser.2023.113647
#   We assume 48% of bagasse mass is water.
#
# Source for filter cake and filter cake water:
#   DOI: 10.1016/j.rser.2023.113647
#   Filter cake is assumed to be 4% of sugarcane production mass and
#   69% of the filter cake mass is water.
#
# Source for filter mud and filter mud water:
#   DOI: 10.1016/j.biortech.2020.122929
#   Filter mud is assumed to be 3% of sugarcane production mass and
#   58% of the filter mud mass is water.
#
# Source for molasses and molasses water:
#   DOI: 10.1016/j.biortech.2016.09.074
#   FAO commodity tree methodology
#   https://www.fao.org/fileadmin/templates/ess/documents/methodology/tcf.pdf
#   Molasses is assumed to be 5% of sugarcane production mass and
#   20% of molasses mass is water.

# Estimate the water content of harvested sugarcane stalks delivered to the mill.
# This is expressed in cubic kilometres of water contained in the stalk.
# Estimate the water contained in the sugarcane production mass itself.
# Source: https://doi.org/10.1016/j.envdev.2015.03.004
# We assume the production mass is 70% water.
df_wide["Stalk_to_mill_water_km^3"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.70
)



# Straw share of the total plant mass on a wet basis (20–28% range; midpoint 24%).
# The dataset contains stalk mass (the portion delivered to the mill), which
# represents approximately 76% of the total plant mass when straw is 24%.
# Therefore, to compute straw mass from stalk mass we use:
#     straw = stalk * (STRAW_SHARE_TOTAL_PLANT / (1 - STRAW_SHARE_TOTAL_PLANT))
# This yields straw ≈ 0.315789 × stalk for a 24% straw share of total plant mass.
STRAW_SHARE_TOTAL_PLANT = 0.24

df_wide["Straw_Sugarcane_Gt"] = (
    df_wide["Stalk_to_mill_Gt"]
    * STRAW_SHARE_TOTAL_PLANT
    / (1 - STRAW_SHARE_TOTAL_PLANT)
)

# Estimate water contained in the straw.
df_wide["Straw_Sugarcane_water_km^3"] = (
    df_wide["Straw_Sugarcane_Gt"]
    * 0.15
)

# Estimate bagasse produced from sugarcane.
df_wide["Bagasse_Sugarcane_Gt"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.25
)

# Estimate water content of the bagasse.
df_wide["Bagasse_Sugarcane_water_km^3"] = (
    df_wide["Bagasse_Sugarcane_Gt"]
    * 0.48
)

# Estimate sugarcane filter cake mass.
df_wide["Filter_cake_Sugarcane_Gt"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.04
)

# Estimate water in sugarcane filter cake.
df_wide["Filter_cake_Sugarcane_water_km^3"] = (
    df_wide["Filter_cake_Sugarcane_Gt"]
    * 0.69
)

# Estimate sugarcane filter mud mass.
df_wide["Filter_mud_Sugarcane_Gt"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.03
)

# Estimate water in sugarcane filter mud.
df_wide["Filter_mud_Sugarcane_water_km^3"] = (
    df_wide["Filter_mud_Sugarcane_Gt"]
    * 0.58
)

# Estimate molasses produced from sugarcane.
df_wide["Molasses_Sugarcane_Gt"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.05
)

# Estimate water content of the molasses.
df_wide["Molasses_Sugarcane_water_km^3"] = (
    df_wide["Molasses_Sugarcane_Gt"]
    * 0.20
)

# Estimate refined sugar produced from sugarcane.
# Source: FAO commodity tree methodology
# chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://www.fao.org/fileadmin/templates/ess/documents/methodology/tcf.pdf
# We assume 11% of sugarcane production mass is refined sugar.
df_wide["refined_sugar_cane_GT"] = (
    df_wide["Stalk_to_mill_Gt"]
    * 0.11
)

# Estimate water content of the refined sugar (very small fraction).
# We assume 0.04% of refined sugar mass is water.
df_wide["refined_sugar_cane_water_km^3"] = (
    df_wide["refined_sugar_cane_GT"]
    * 0.0004
)

# =============================================================================
# 17. SUGAR BEET TO THE MILL
# =============================================================================
# Estimate leaves mass for sugar beet based on total-plant shares.
# Source: FAO commodity tree methodology and DOI: 10.3390/agronomy13020346
#
# Context: the dataset contains sugar beet production = taproot mass, which
# represents ~75% of the total plant mass. Leaves constitute ~25% of the
# total plant mass (range 20–30%, midpoint 25%). To compute leaves mass from
# the reported taproot (production) mass we use:
#     leaves = taproot * (LEAVES_SHARE_TOTAL_PLANT / TAPROOT_SHARE_TOTAL_PLANT)
# and then estimate leaf water content as 80% of leaf mass.
LEAVES_SHARE_TOTAL_PLANT = 0.25

df_wide["leaves_Sugarbeet_GT"] = (
    df_wide["Taproot_to_mill_Gt"]
    * LEAVES_SHARE_TOTAL_PLANT
    / (1-LEAVES_SHARE_TOTAL_PLANT)
)

# Estimate water content of the leaves (80% water).
df_wide["leaves_Sugarbeet_water_km^3"] = (
    df_wide["leaves_Sugarbeet_GT"]
    * 0.80
)

# Estimate sugarbeet pulp mass and water content.
# Sources: DOI 10.1016/j.biombioe.2008.02.012 and FAO commodity tree methodology.
df_wide["Sugarbeet_pulp_Gt"] = (
    df_wide["Taproot_to_mill_Gt"]
    * 0.10
)

df_wide["Sugarbeet_pulp_water_km^3"] = (
    df_wide["Sugarbeet_pulp_Gt"]
    * 0.80
)

# Estimate lime cake from sugarbeet processing.
# Source: FAO commodity tree methodology.
df_wide["Lime_cake_Sugarbeet_GT"] = (
    df_wide["Taproot_to_mill_Gt"]
    * 0.045
)

df_wide["Lime_cake_Sugarbeet_water_km^3"] = (
    df_wide["Lime_cake_Sugarbeet_GT"]
    * 0.50
)

# Estimate the water contained in sugarbeet production mass.
# Source: same FAO tree and processing water assumptions.
df_wide["Taproot_to_mill_water_km^3"] = (
    df_wide["Taproot_to_mill_Gt"]
    * 0.80
)

# Estimate sugarbeet molasses and its water content.
# Source: FAO commodity tree methodology.
df_wide["Molasses_Sugarbeet_GT"] = (
    df_wide["Taproot_to_mill_Gt"]
    * 0.04
)

df_wide["Molasses_Sugarbeet_water_km^3"] = (
    df_wide["Molasses_Sugarbeet_GT"]
    * 0.20
)

# Estimate refined sugar from sugarbeet.
# Source: FAO commodity tree methodology.
df_wide["refined_sugar_beet_GT"] = (
    df_wide["Taproot_to_mill_Gt"]
    * 0.14
)

df_wide["refined_sugar_beet_water_km^3"] = (
    df_wide["refined_sugar_beet_GT"]
    * 0.0004
)

print("\nSample Sugarcane-to-the-mill calculations:")
print(
    df_wide[
        [
            "production_Gt_Sugarcane",
            "Stalk_losses_in_field_Gt",
            "Stalk_losses_in_field_water_km^3",
            "Stalk_to_mill_Gt",
            "Stalk_to_mill_water_km^3",
            "Straw_Sugarcane_Gt",
            "Straw_Sugarcane_water_km^3",
            "Bagasse_Sugarcane_Gt",
            "Bagasse_Sugarcane_water_km^3",
            "Filter_cake_Sugarcane_Gt",
            "Filter_cake_Sugarcane_water_km^3",
            "Filter_mud_Sugarcane_Gt",
            "Filter_mud_Sugarcane_water_km^3",
            "Molasses_Sugarcane_Gt",
            "Molasses_Sugarcane_water_km^3",
            "refined_sugar_cane_GT",
            "refined_sugar_cane_water_km^3",
            "production_Gt_Sugarbeet",
            "Taproot_losses_in_field_Gt",
            "Taproot_losses_in_field_water_km^3",
            "Taproot_to_mill_Gt",
            "Taproot_to_mill_water_km^3",
            "leaves_Sugarbeet_GT",
            "leaves_Sugarbeet_water_km^3",
            "Sugarbeet_pulp_Gt",
            "Sugarbeet_pulp_water_km^3",
            "Lime_cake_Sugarbeet_GT",
            "Lime_cake_Sugarbeet_water_km^3",
            "Molasses_Sugarbeet_GT",
            "Molasses_Sugarbeet_water_km^3",
            "refined_sugar_beet_GT",
            "refined_sugar_beet_water_km^3",
        ]
    ]
    .head(10)
    .to_string(index=False)
)


# =============================================================================
# 16. CALCULATE TOTAL ET FOR EACH CROP
# =============================================================================

# Total consumptive evapotranspiration is the sum of blue and green ET.
df_wide["Total_ET_km3_Sugarcane"] = (
    df_wide["blue_ET_km3_Sugarcane"]
    + df_wide["green_ET_km3_Sugarcane"]
)

df_wide["Total_ET_km3_Sugarbeet"] = (
    df_wide["blue_ET_km3_Sugarbeet"]
    + df_wide["green_ET_km3_Sugarbeet"]
)


# =============================================================================
# 15. ARRANGE THE COLUMNS IN A LOGICAL ORDER
# =============================================================================

df_2021_country = df_wide[
    [
        "iso3",
        "country",
        "year",

        "blue_ET_m3_Sugarcane",
        "green_ET_m3_Sugarcane",
        "production_t_Sugarcane",

        "blue_ET_m3_Sugarbeet",
        "green_ET_m3_Sugarbeet",
        "production_t_Sugarbeet",

        "blue_ET_km3_Sugarcane",
        "green_ET_km3_Sugarcane",
        "Total_ET_km3_Sugarcane",
        "production_Gt_Sugarcane",
        "Stalk_losses_in_field_Gt",
        "Stalk_losses_in_field_water_km^3",
        "Stalk_to_mill_Gt",
        "Stalk_to_mill_water_km^3",
        "Straw_Sugarcane_Gt",
        "Straw_Sugarcane_water_km^3",
        "Bagasse_Sugarcane_Gt",
        "Bagasse_Sugarcane_water_km^3",
        "Filter_cake_Sugarcane_Gt",
        "Filter_cake_Sugarcane_water_km^3",
        "Filter_mud_Sugarcane_Gt",
        "Filter_mud_Sugarcane_water_km^3",
        "Molasses_Sugarcane_Gt",
        "Molasses_Sugarcane_water_km^3",
        "refined_sugar_cane_GT",
        "refined_sugar_cane_water_km^3",
        "blue_ET_km3_Sugarbeet",
        "green_ET_km3_Sugarbeet",
        "Total_ET_km3_Sugarbeet",
        "production_Gt_Sugarbeet",
        "Taproot_losses_in_field_Gt",
        "Taproot_losses_in_field_water_km^3",
        "Taproot_to_mill_Gt",
        "Taproot_to_mill_water_km^3",
        "leaves_Sugarbeet_GT",
        "leaves_Sugarbeet_water_km^3",
        "Sugarbeet_pulp_Gt",
        "Sugarbeet_pulp_water_km^3",
        "Lime_cake_Sugarbeet_GT",
        "Lime_cake_Sugarbeet_water_km^3",
        "Taproot_to_mill_water_km^3",
        "Molasses_Sugarbeet_GT",
        "Molasses_Sugarbeet_water_km^3",
        "refined_sugar_beet_GT",
        "refined_sugar_beet_water_km^3",
    ]
].copy()


# =============================================================================
# 16. SORT THE TABLE
# =============================================================================

df_2021_country = (
    df_2021_country
    .sort_values(
        by=[
            "country",
            "iso3",
        ]
    )
    .reset_index(drop=True)
)


# =============================================================================
# 17. VERIFY THAT THERE IS ONE ROW PER COUNTRY
# =============================================================================

duplicate_country_mask = df_2021_country.duplicated(
    subset=[
        "iso3",
        "year",
    ],
    keep=False,
)

duplicate_country_rows = df_2021_country.loc[
    duplicate_country_mask,
    [
        "iso3",
        "country",
        "year",
    ],
]

if not duplicate_country_rows.empty:
    print("\nDuplicate country-year rows remain after reshaping:")
    print(
        duplicate_country_rows
        .sort_values(["iso3", "year"])
        .to_string(index=False)
    )

    raise ValueError(
        "Duplicate country-year rows remain after reshaping."
    )


print(
    f"\nFinal country-level table: "
    f"{len(df_2021_country):,} rows"
)

print(
    "Unique ISO3 country codes: "
    f"{df_2021_country['iso3'].nunique():,}"
)


# =============================================================================
# 18. DISPLAY THE TABLE IN PYTHON
# =============================================================================

# In Spyder:
# Open the Variable Explorer and double-click df_2021_country.
#
# In Jupyter:
# Put df_2021_country as the last line of a notebook cell.
#
# In VS Code or a normal Python console:
# Print a selected number of rows as shown below.

print("\nFirst 20 rows of the resulting table:")
print(
    df_2021_country
    .head(20)
    .to_string(index=False)
)


# Display all column names.
print("\nFinal column names:")
for column in df_2021_country.columns:
    print(f"- {column}")


# Display data types.
print("\nFinal columns and data types:")
print(df_2021_country.dtypes)


# Display summary statistics for the km³ variables.
km3_columns = [
    "blue_ET_km3_Sugarcane",
    "green_ET_km3_Sugarcane",
    "Total_ET_km3_Sugarcane",
    "blue_ET_km3_Sugarbeet",
    "green_ET_km3_Sugarbeet",
    "Total_ET_km3_Sugarbeet",
]

print("\nSummary of the 2021 water variables in km³:")
print(
    df_2021_country[km3_columns]
    .describe()
    .transpose()
    .to_string()
)


# =============================================================================
# 19. KEEP THE DATAFRAME AVAILABLE FOR THE NEXT STEPS
# =============================================================================

# This line does not export anything.
# It keeps the final dataframe available under the name df_2021_country.

df_2021_country


# =============================================================================
# EXPORT THE TABLE FOR INSPECTION
# =============================================================================

OUTPUT_FILE = OUTPUT_DIR / "DEBUG_2021_country_table.xlsx"

df_2021_country.to_excel(
    OUTPUT_FILE,
    index=False
)

print(f"\nTable exported successfully to:\n{OUTPUT_FILE}")
print(OUTPUT_FILE)

# =============================================================================
# EXPORT GLOBAL TOTALS SUMMARY
# =============================================================================
# Create a one-row global summary table with the sum of every numeric column.
numeric_columns = [
    column
    for column in df_2021_country.select_dtypes(include="number").columns
    if column != "year"
]

global_totals = (
    df_2021_country[numeric_columns]
    .sum()
    .to_frame()
    .T
)

global_totals["iso3"] = ""
global_totals["country"] = "Global"
global_totals["year"] = 2021

# Use the same column order as the country-level file.
global_totals = global_totals[df_2021_country.columns]

OUTPUT_GLOBAL_TOTALS_FILE = OUTPUT_DIR / "DEBUG_2021_country_table_global_totals.xlsx"

global_totals.to_excel(
    OUTPUT_GLOBAL_TOTALS_FILE,
    index=False
)

print(f"\nGlobal totals exported successfully to:\n{OUTPUT_GLOBAL_TOTALS_FILE}")
print(OUTPUT_GLOBAL_TOTALS_FILE)
