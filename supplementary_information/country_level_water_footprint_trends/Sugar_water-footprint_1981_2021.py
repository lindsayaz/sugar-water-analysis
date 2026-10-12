# -*- coding: utf-8 -*-

"""
===============================================================================
CALCULATE COUNTRY-LEVEL CONSUMPTIVE WATER FOOTPRINT
===============================================================================

Purpose
-------
This script calculates annual country-level water-footprint indicators for
combined sugarcane and sugar-beet production.

The reviewer requested an analysis of the water footprint per unit of crop
production.

Input variables
---------------
production_t_total
    Total harvested sugarcane and sugar-beet production, in tonnes.

blue_km3_total
    Consumptive blue water use, in km³.

green_km3_total
    Consumptive green water use, in km³.

et_km3_total
    Total consumptive evapotranspiration, in km³.

Calculation
-----------
The water footprint is calculated as:

    water footprint = consumptive water use / crop production

The original water variables are reported in km³, while production is
reported in tonnes.

Because:

    1 km³ = 1,000,000,000 m³

the calculation is:

    water footprint (m³/t)
        = water use (km³) × 1,000,000,000 / production (t)

Resulting indicators
--------------------
blue_WF_m3_per_t_crop
    Consumptive blue water footprint, in m³/t crop.

green_WF_m3_per_t_crop
    Consumptive green water footprint, in m³/t crop.

total_WF_m3_per_t_crop
    Total blue-plus-green consumptive water footprint, in m³/t crop.

Interpretation
--------------
A higher value means that more consumptive water is associated with producing
one tonne of harvested crop.

    Higher water footprint = lower water-use efficiency
    Lower water footprint  = higher water-use efficiency

The calculation includes only consumptive blue and green water.
It does not include the grey water footprint associated with pollution.

Unit equivalence
----------------
The following units are numerically equivalent:

    1 m³/t = 1 L/kg

For example:

    2,116.8 m³/t = 2,116.8 L/kg
===============================================================================
"""

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# 1. FILE PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
IN_FILE = BASE_DIR / "data" / "S2_Country-level GCWM- new.xlsx"

# Save the expanded dataset as a new file.
# The original Excel file will remain unchanged.
OUT_FILE = IN_FILE.with_name(
    "S2_Country-level_GCWM_with_water_footprint_m3_per_t.xlsx"
)


# =============================================================================
# 2. ORIGINAL COLUMN NAMES
# =============================================================================

PRODUCTION_COL = "production_t_total"

BLUE_WATER_COL = "blue_km3_total"
GREEN_WATER_COL = "green_km3_total"
TOTAL_WATER_COL = "et_km3_total"


# =============================================================================
# 3. NEW WATER-FOOTPRINT COLUMN NAMES
# =============================================================================

BLUE_WF_COL = "blue_WF_m3_per_t_crop"
GREEN_WF_COL = "green_WF_m3_per_t_crop"
TOTAL_WF_COL = "total_WF_m3_per_t_crop"


# =============================================================================
# 4. UNIT-CONVERSION CONSTANT
# =============================================================================

# 1 km³ = 1,000,000,000 m³
KM3_TO_M3 = 1_000_000_000


# =============================================================================
# 5. LOAD THE DATASET
# =============================================================================

df = pd.read_excel(IN_FILE)

print("=" * 79)
print("COUNTRY-LEVEL WATER-FOOTPRINT CALCULATION")
print("=" * 79)
print(f"\nLoaded {len(df):,} rows.")
print(f"\nInput file:\n{IN_FILE}")


# =============================================================================
# 6. CHECK THAT ALL REQUIRED COLUMNS EXIST
# =============================================================================

required_columns = [
    PRODUCTION_COL,
    BLUE_WATER_COL,
    GREEN_WATER_COL,
    TOTAL_WATER_COL,
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise KeyError(
        "The following required columns are missing from the input file:\n"
        + "\n".join(f"- {column}" for column in missing_columns)
    )


# =============================================================================
# 7. CONVERT THE REQUIRED COLUMNS TO NUMERIC VALUES
# =============================================================================

# Any invalid text values are converted to NaN.
for column in required_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce",
    )


# =============================================================================
# 8. PREPARE A VALID PRODUCTION DENOMINATOR
# =============================================================================

# Water footprint cannot be calculated when production is:
# - missing,
# - zero, or
# - negative.
#
# Such values are replaced by NaN in the denominator so that the resulting
# water-footprint values are also NaN rather than infinite or misleading.

valid_production_t = df[PRODUCTION_COL].where(
    df[PRODUCTION_COL] > 0,
    np.nan,
)


# =============================================================================
# 9. CALCULATE THE BLUE CONSUMPTIVE WATER FOOTPRINT
# =============================================================================

# Formula:
#
#     blue water footprint (m³/t)
#         = blue water use (km³) × 10⁹ / crop production (t)

df[BLUE_WF_COL] = (
    df[BLUE_WATER_COL] * KM3_TO_M3
) / valid_production_t


# =============================================================================
# 10. CALCULATE THE GREEN CONSUMPTIVE WATER FOOTPRINT
# =============================================================================

# Formula:
#
#     green water footprint (m³/t)
#         = green water use (km³) × 10⁹ / crop production (t)

df[GREEN_WF_COL] = (
    df[GREEN_WATER_COL] * KM3_TO_M3
) / valid_production_t


# =============================================================================
# 11. CALCULATE THE TOTAL CONSUMPTIVE WATER FOOTPRINT
# =============================================================================

# The total consumptive water footprint is calculated using et_km3_total.
#
# Formula:
#
#     total water footprint (m³/t)
#         = total consumptive ET (km³) × 10⁹ / crop production (t)

df[TOTAL_WF_COL] = (
    df[TOTAL_WATER_COL] * KM3_TO_M3
) / valid_production_t


# =============================================================================
# 12. CHECK WHETHER TOTAL ET EQUALS BLUE PLUS GREEN WATER
# =============================================================================

# This quality-control check tests whether:
#
#     et_km3_total ≈ blue_km3_total + green_km3_total
#
# A very small difference may occur because of numerical precision or rounding.

df["blue_plus_green_km3_check"] = (
    df[BLUE_WATER_COL] + df[GREEN_WATER_COL]
)

df["et_balance_difference_km3_check"] = (
    df[TOTAL_WATER_COL]
    - df["blue_plus_green_km3_check"]
)

maximum_balance_difference = (
    df["et_balance_difference_km3_check"]
    .abs()
    .max()
)

TOLERANCE = 1e-9

rows_exceeding_tolerance = (
    df["et_balance_difference_km3_check"]
    .abs()
    .gt(TOLERANCE)
    .sum()
)

print("\n" + "-" * 79)
print("WATER-BALANCE CHECK")
print("-" * 79)

print(
    "Maximum absolute difference between et_km3_total and "
    f"blue + green water: {maximum_balance_difference}"
)

print(
    f"Rows where the difference exceeds {TOLERANCE}: "
    f"{rows_exceeding_tolerance:,}"
)


# =============================================================================
# 13. CHECK FOR MISSING OR NON-POSITIVE PRODUCTION
# =============================================================================

invalid_production_mask = (
    df[PRODUCTION_COL].isna()
    | (df[PRODUCTION_COL] <= 0)
)

invalid_production_count = invalid_production_mask.sum()

print("\n" + "-" * 79)
print("PRODUCTION-DATA CHECK")
print("-" * 79)

print(
    "Rows with missing, zero, or negative production for which the "
    f"water footprint could not be calculated: {invalid_production_count:,}"
)


# =============================================================================
# 14. CHECK FOR INFINITE RESULTS
# =============================================================================

water_footprint_columns = [
    BLUE_WF_COL,
    GREEN_WF_COL,
    TOTAL_WF_COL,
]

infinite_values_count = np.isinf(
    df[water_footprint_columns].to_numpy(dtype=float)
).sum()

print(
    f"Infinite water-footprint values found: "
    f"{infinite_values_count:,}"
)

if infinite_values_count > 0:
    raise ValueError(
        "Infinite values were found in the calculated water footprints. "
        "Please inspect the production denominator."
    )


# =============================================================================
# 15. DISPLAY A SAMPLE OF THE RESULTS
# =============================================================================

sample_columns = [
    "iso3",
    "country",
    "year",
    PRODUCTION_COL,
    BLUE_WATER_COL,
    GREEN_WATER_COL,
    TOTAL_WATER_COL,
    BLUE_WF_COL,
    GREEN_WF_COL,
    TOTAL_WF_COL,
]

# Keep only columns that actually exist in the dataset.
sample_columns = [
    column
    for column in sample_columns
    if column in df.columns
]

print("\n" + "-" * 79)
print("SAMPLE OF CALCULATED RESULTS")
print("-" * 79)

print(
    df[sample_columns]
    .head(10)
    .to_string(index=False)
)


# =============================================================================
# 16. DISPLAY SUMMARY STATISTICS
# =============================================================================

print("\n" + "-" * 79)
print("WATER-FOOTPRINT SUMMARY STATISTICS — m³/t CROP")
print("-" * 79)

print(
    df[water_footprint_columns]
    .describe()
    .transpose()
    .to_string()
)


# =============================================================================
# 17. SAVE THE EXPANDED DATASET
# =============================================================================

df.to_excel(
    OUT_FILE,
    sheet_name="Country-level water footprint",
    index=False,
)

print("\n" + "=" * 79)
print("CALCULATION COMPLETED SUCCESSFULLY")
print("=" * 79)

print(f"\nOutput file saved to:\n{OUT_FILE}")

print("\nNew water-footprint columns:")
print(f"- {BLUE_WF_COL}")
print(f"- {GREEN_WF_COL}")
print(f"- {TOTAL_WF_COL}")

print("\nUnits: m³ of consumptive water per tonne of harvested crop.")
