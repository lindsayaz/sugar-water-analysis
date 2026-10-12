"""
Create a global 2018 sugar-water dataset and illustrative irrigation-withdrawal scenarios.

Purpose
-------
1. Read the country-level Excel file for 2018.
2. Keep all original columns.
3. Sum every column from "Total_pop_female" to the final column across all countries.
4. Create a one-row global dataset.
5. Estimate illustrative irrigation withdrawals from aggregated blue ET only:
       irrigation withdrawal = blue ET / irrigation efficiency
       non-consumptive irrigation flow = irrigation withdrawal - blue ET
6. Export a new Excel workbook with:
       - Global_2018_sum
       - Field_water_summary
       - Irrigation_scenarios
       - Method_notes

Important methodological note
-----------------------------
The main MFA should use GCWM country-level blue and green evapotranspiration (ET),
because these represent consumptive water use.

The irrigation-withdrawal calculation is only an illustrative Sankey scenario.
It is not a measured global hydrological water balance and does not quantify
rainfall runoff, groundwater recharge, canal losses, return-flow reuse, or changes
in soil-water storage.

Author: prepared for Mali
"""

from pathlib import Path
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------
# 1. USER PATHS
# ---------------------------------------------------------------------
# Input country-level data file
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "main data 2018 - by country.xlsx"

# Output folder requested
OUTPUT_DIR = BASE_DIR / "outputs"

# Output file name
OUTPUT_FILE = OUTPUT_DIR / "global_view_2018_with_irrigation_scenarios.xlsx"


# ---------------------------------------------------------------------
# 2. SETTINGS
# ---------------------------------------------------------------------
# The first column from which all columns should be summed.
# All columns before this column are treated as identifiers and filled manually
# for the global row.
START_SUM_COLUMN = "Total_pop_female"

# Irrigation-efficiency assumptions for the illustrative Sankey scenario.
# These are not measured global values. They are used only for sensitivity analysis.
IRRIGATION_EFFICIENCY_SCENARIOS = [
    {
        "Scenario": "Low efficiency",
        "Efficiency": 0.40,
        "Notes": "Lower-bound illustrative scenario; closer to inefficient surface/flood systems."
    },
    {
        "Scenario": "Central estimate",
        "Efficiency": 0.50,
        "Notes": "Central illustrative scenario for the Sankey diagram."
    },
    {
        "Scenario": "Higher efficiency",
        "Efficiency": 0.60,
        "Notes": "Upper sensitivity scenario; closer to better managed surface/sprinkler systems."
    },
]


# ---------------------------------------------------------------------
# 3. LOAD DATA
# ---------------------------------------------------------------------
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Input file was not found: {INPUT_FILE}")

df = pd.read_excel(INPUT_FILE, sheet_name=0)

if START_SUM_COLUMN not in df.columns:
    raise ValueError(
        f'The required start column "{START_SUM_COLUMN}" was not found. '
        f"Available columns are:\n{list(df.columns)}"
    )

# Make sure the output folder exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 4. CREATE GLOBAL ONE-ROW DATASET
# ---------------------------------------------------------------------
start_idx = df.columns.get_loc(START_SUM_COLUMN)

identifier_cols = list(df.columns[:start_idx])
sum_cols = list(df.columns[start_idx:])

# Convert all summed columns to numeric values.
# Non-numeric cells become NaN and are ignored in the sum.
df_numeric = df[sum_cols].apply(pd.to_numeric, errors="coerce")

# Build one global row with the same column structure as the input file.
global_row = {col: None for col in df.columns}

# Fill identifier columns.
# Adjust these labels if you prefer different wording.
identifier_values = {
    "Column1": "Global",
    "UN_country": "Global",
    "iso3": "WORLD",
    "Region": "Global",
    "Continent": "Global",
    "Year": 2018,
}

for col in identifier_cols:
    global_row[col] = identifier_values.get(col, "Global")

# Sum all requested columns.
for col in sum_cols:
    global_row[col] = df_numeric[col].sum(skipna=True)

global_df = pd.DataFrame([global_row], columns=df.columns)


# ---------------------------------------------------------------------
# 5. FIELD-WATER SUMMARY
# ---------------------------------------------------------------------
def get_global_value(column_name: str) -> float:
    """Return a numeric value from the global row. If the column does not exist, return 0."""
    if column_name not in global_df.columns:
        return 0.0
    value = global_df[column_name].iloc[0]
    if pd.isna(value):
        return 0.0
    return float(value)


# Sugarcane ET components
sc_blue = get_global_value("SC_blue_km3")
sc_green = get_global_value("SC_green_km3")
sc_total_et = get_global_value("SC_et_km3")

# Sugar beet ET components
sb_blue = get_global_value("SB_blue_km3")
sb_green = get_global_value("SB_green_km3")
sb_total_et = get_global_value("SB_et_km3")

# Aggregated sugar crops
blue_et = sc_blue + sb_blue
green_et = sc_green + sb_green
total_et_from_components = blue_et + green_et
total_et_from_dataset = sc_total_et + sb_total_et

field_water_summary = pd.DataFrame([
    {
        "Metric": "Global sugarcane blue ET",
        "Value_km3_per_year": sc_blue,
        "Explanation": "Irrigation-derived consumptive water use from SC_blue_km3, summed across countries."
    },
    {
        "Metric": "Global sugar beet blue ET",
        "Value_km3_per_year": sb_blue,
        "Explanation": "Irrigation-derived consumptive water use from SB_blue_km3, summed across countries."
    },
    {
        "Metric": "Aggregated blue ET: sugarcane + sugar beet",
        "Value_km3_per_year": blue_et,
        "Explanation": "This is the only value used to estimate irrigation withdrawals."
    },
    {
        "Metric": "Global sugarcane green ET",
        "Value_km3_per_year": sc_green,
        "Explanation": "Rainfall-derived consumptive water use from SC_green_km3, summed across countries."
    },
    {
        "Metric": "Global sugar beet green ET",
        "Value_km3_per_year": sb_green,
        "Explanation": "Rainfall-derived consumptive water use from SB_green_km3, summed across countries."
    },
    {
        "Metric": "Aggregated green ET: sugarcane + sugar beet",
        "Value_km3_per_year": green_et,
        "Explanation": "Rainfall-derived consumptive water use."
    },
    {
        "Metric": "Total consumptive ET from blue + green components",
        "Value_km3_per_year": total_et_from_components,
        "Explanation": "Blue ET + green ET. This is the main field-water value for the MFA."
    },
    {
        "Metric": "Total ET from dataset total columns",
        "Value_km3_per_year": total_et_from_dataset,
        "Explanation": "SC_et_km3 + SB_et_km3. This should be close to blue + green ET, depending on dataset definitions."
    },
])


# ---------------------------------------------------------------------
# 6. ILLUSTRATIVE IRRIGATION-WITHDRAWAL SCENARIOS
# ---------------------------------------------------------------------
scenario_rows = []

for item in IRRIGATION_EFFICIENCY_SCENARIOS:
    scenario = item["Scenario"]
    efficiency = item["Efficiency"]

    # Irrigation withdrawal applies only to blue ET.
    # It must not be applied to green ET.
    irrigation_withdrawal = blue_et / efficiency

    # This includes runoff, drainage, deep percolation, return flows, conveyance losses, etc.
    # We do not split it into sub-flows because those processes are highly location-specific.
    non_consumptive_irrigation_flow = irrigation_withdrawal - blue_et

    # This is useful for a conceptual Sankey:
    # rainfall-derived consumed water + total withdrawn irrigation water.
    # It is NOT the full rainfall input to the field.
    conceptual_field_input = green_et + irrigation_withdrawal

    scenario_rows.append({
        "Scenario": scenario,
        "Irrigation_efficiency_assumption": efficiency,
        "Global_blue_ET_used_for_calculation_km3_per_year": blue_et,
        "Estimated_blue_irrigation_withdrawal_km3_per_year": irrigation_withdrawal,
        "Non_consumptive_irrigation_flow_km3_per_year": non_consumptive_irrigation_flow,
        "Global_green_ET_km3_per_year": green_et,
        "Total_consumptive_ET_blue_plus_green_km3_per_year": total_et_from_components,
        "Conceptual_field_water_input_green_ET_plus_blue_withdrawal_km3_per_year": conceptual_field_input,
        "Notes": item["Notes"],
    })

irrigation_scenarios = pd.DataFrame(scenario_rows)


# ---------------------------------------------------------------------
# 7. METHOD NOTES FOR SUPPLEMENTARY INFORMATION
# ---------------------------------------------------------------------
method_notes = pd.DataFrame([
    {
        "Topic": "Main water boundary",
        "Text": (
            "The main MFA uses country-level blue and green ET from GCWM. "
            "ET represents consumptive water use: water removed from the local hydrological system "
            "through evaporation and plant transpiration."
        ),
    },
    {
        "Topic": "Purpose of withdrawal estimate",
        "Text": (
            "The irrigation-withdrawal estimate is included only as an illustrative scenario "
            "for a conceptual/global Sankey diagram. It is not used in the main country-level results."
        ),
    },
    {
        "Topic": "Blue ET",
        "Text": (
            "Blue ET is irrigation-derived water consumed by the crop. "
            "Only blue ET is converted into estimated irrigation withdrawal."
        ),
    },
    {
        "Topic": "Green ET",
        "Text": (
            "Green ET is precipitation-derived soil moisture consumed by the crop. "
            "It is not converted into irrigation withdrawal."
        ),
    },
    {
        "Topic": "Formula 1",
        "Text": "Irrigation withdrawal = Blue ET / irrigation efficiency.",
    },
    {
        "Topic": "Formula 2",
        "Text": "Non-consumptive irrigation flow = irrigation withdrawal - Blue ET.",
    },
    {
        "Topic": "Efficiency range",
        "Text": (
            "The 40%, 50%, and 60% assumptions are used as a sensitivity range. "
            "They should be justified using irrigation-performance literature and described as illustrative."
        ),
    },
    {
        "Topic": "Limitation",
        "Text": (
            "The non-consumptive irrigation flow is not separated into runoff, recharge, drainage, "
            "return flows, or conveyance losses. These processes depend on local climate, soil, slope, "
            "irrigation technology, and management."
        ),
    },
    {
        "Topic": "Suggested wording",
        "Text": (
            "Estimated irrigation withdrawals should be interpreted as order-of-magnitude values "
            "for visualization, not as measured global hydrological water balances."
        ),
    },
    {
        "Topic": "References to use in manuscript",
        "Text": (
            "Use Siebert & Döll (2010) for GCWM and blue/green consumptive ET definitions; "
            "Dingre & Gorantiwar (2020) for sugarcane ET and field water balance; "
            "Mortel & Madramootoo (2023) for site-specific irrigation-management limitations; "
            "Tayade et al. (2020) and other original irrigation-performance papers for efficiency ranges."
        ),
    },
])


# ---------------------------------------------------------------------
# 8. EXPORT EXCEL WORKBOOK
# ---------------------------------------------------------------------
with pd.ExcelWriter(OUTPUT_FILE, engine="xlsxwriter") as writer:
    global_df.to_excel(writer, sheet_name="Global_2018_sum", index=False)
    field_water_summary.to_excel(writer, sheet_name="Field_water_summary", index=False)
    irrigation_scenarios.to_excel(writer, sheet_name="Irrigation_scenarios", index=False)
    method_notes.to_excel(writer, sheet_name="Method_notes", index=False)

    workbook = writer.book

    # Basic formatting
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#D9EAF7",
        "border": 1,
        "text_wrap": True,
        "valign": "top",
    })

    number_fmt = workbook.add_format({"num_format": "#,##0.000"})
    percent_fmt = workbook.add_format({"num_format": "0%"})
    wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})

    sheets_and_data = {
        "Global_2018_sum": global_df,
        "Field_water_summary": field_water_summary,
        "Irrigation_scenarios": irrigation_scenarios,
        "Method_notes": method_notes,
    }

    for sheet_name, data in sheets_and_data.items():
        worksheet = writer.sheets[sheet_name]

        # Header formatting and column widths
        for col_num, col_name in enumerate(data.columns):
            worksheet.write(0, col_num, col_name, header_fmt)
            width = min(max(len(str(col_name)) + 2, 14), 45)
            worksheet.set_column(col_num, col_num, width, wrap_fmt)

        worksheet.freeze_panes(1, 0)

    # More specific formatting
    ws = writer.sheets["Field_water_summary"]
    ws.set_column(0, 0, 42, wrap_fmt)
    ws.set_column(1, 1, 18, number_fmt)
    ws.set_column(2, 2, 70, wrap_fmt)

    ws = writer.sheets["Irrigation_scenarios"]
    for col_num, col_name in enumerate(irrigation_scenarios.columns):
        if "efficiency" in col_name.lower():
            ws.set_column(col_num, col_num, 20, percent_fmt)
        elif "km3" in col_name.lower():
            ws.set_column(col_num, col_num, 24, number_fmt)
        elif col_name == "Notes":
            ws.set_column(col_num, col_num, 60, wrap_fmt)

    ws = writer.sheets["Method_notes"]
    ws.set_column(0, 0, 28, wrap_fmt)
    ws.set_column(1, 1, 100, wrap_fmt)


print(f"Done. File saved to:\n{OUTPUT_FILE}")
print("\nKey values:")
print(f"Aggregated blue ET = {blue_et:,.3f} km3/yr")
print(f"Aggregated green ET = {green_et:,.3f} km3/yr")
print(f"Total consumptive ET = {total_et_from_components:,.3f} km3/yr")
print("\nIrrigation scenarios:")
print(irrigation_scenarios[[
    "Scenario",
    "Irrigation_efficiency_assumption",
    "Estimated_blue_irrigation_withdrawal_km3_per_year",
    "Non_consumptive_irrigation_flow_km3_per_year",
]].to_string(index=False))
