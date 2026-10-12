from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
src = BASE_DIR / "data" / "Pasted code.py"
text = src.read_text(encoding="utf-8")

# 1) Update purpose/output commentary and method wording conservatively.
text = text.replace(
"""# STEP C — Treatment of "Others"
#
# DES reports several minor states collectively as "Others".
#
# The total "Others" share is therefore allocated among the remaining
# states/UTs according to their relative MIRCA sugarcane harvested area:
#
#       A_target,s =
#           A_DES_Others ×
#           A_MIRCA,s / sum(A_MIRCA,Other_states)
#""",
"""# STEP C — Treatment of "Others"
#
# DES reports several minor states collectively as "Others".
#
# For the spatial scaling grid only, the total "Others" share is distributed
# among the remaining states/UTs according to their relative MIRCA sugarcane
# harvested area:
#
#       A_target,s =
#           A_DES_Others ×
#           A_MIRCA,s / sum(A_MIRCA,Other_states)
#
# IMPORTANT:
# These internally allocated state values are diagnostic/model-allocation
# quantities. They are NOT reported as observed 2021 state statistics.
# The manuscript/SI reporting table retains "Others" as one DES category.
#"""
)

text = text.replace(
"""# Main state table includes:
#   State
#   MIRCA reference harvested area
#   2021 target harvested area
#   Scaling factor
#   Blue water
#   Irrigated green water
#   Rainfed green water
#   Total green water
#   Total consumptive ET
#   Blue share
#   Green share
#""",
"""# Excel contains:
#   Reporting_results
#       - 11 DES-reported states + one collective "Others" category
#       - recommended table for manuscript/SI and sharing
#
#   State_diagnostic
#       - all 36 state/UT model-allocation units
#       - retained for spatial diagnostics, not as observed 2021 state statistics
#
#   National_comparison
#       - original country-level FAOSTAT scaling vs state-constrained scaling
#
# Additional sheets contain scaling details, DES inputs, national summary,
# and validation checks.
#"""
)

# 2) Add effective raster CRS handling after ah_nodata line.
needle = """    ah_nodata = src.nodata


print(
"""
insert = """    ah_nodata = src.nodata


# GCWM ASCII rasters use geographic longitude/latitude coordinates on the
# global 5 arc-minute grid. Some ASCII readers return no CRS metadata.
# Keep the original raster geometry, but explicitly use EPSG:4326 for
# geospatial operations and GeoTIFF export when CRS metadata are absent.
if ah_crs is None:
    EFFECTIVE_AH_CRS = "EPSG:4326"
    print("WARNING: AH raster does not contain CRS metadata. Using EPSG:4326.")
else:
    EFFECTIVE_AH_CRS = ah_crs


print(
"""
text = text.replace(needle, insert)

# 3) Reproject state boundaries to effective raster CRS rather than hard-coded EPSG.
text = text.replace(
"""states = states.to_crs(
    "EPSG:4326"
)
""",
"""states = states.to_crs(
    EFFECTIVE_AH_CRS
)
"""
)

# 4) Replace section 23 onward through just before raster export with expanded reporting.
start_marker = "# =============================================================================\n# 23. PREPARE FINAL STATE TABLE"
end_marker = "# =============================================================================\n# 28. EXPORT SCALED 5' RASTERS"
start = text.index(start_marker)
end = text.index(end_marker)

replacement = r'''# =============================================================================
# 23. PREPARE 36-STATE/UT DIAGNOSTIC TABLE
# =============================================================================
#
# This table preserves the internal state/UT allocations used to construct the
# spatial scaling grid. For DES "Others", these individual state values are
# model allocations based on MIRCA shares and must NOT be interpreted as
# observed 2021 state harvested-area statistics.
# =============================================================================

state_diagnostic = states[
    [
        "state_id",
        "state",
        "mirca_reference_area_ha",
        "target_area_2021_ha",
        "harmonized_area_share_percent",
        "target_area_source",
        "scaling_factor_area",
        "scaling_flag",
        "blue_km3",
        "green_irr_km3",
        "green_rain_km3",
        "green_total_km3",
        "total_et_km3",
        "blue_share_percent",
        "green_share_percent",
    ]
].copy()


state_diagnostic = (
    state_diagnostic
    .sort_values(
        "total_et_km3",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =============================================================================
# 24. PREPARE DES-SUPPORTED REPORTING TABLE: 11 STATES + OTHERS
# =============================================================================
#
# This is the recommended table for the manuscript/SI and for sharing.
#
# The 11 states explicitly reported by DES are retained individually.
# All other states/UTs are aggregated back to one "Others" category so that
# the reporting resolution matches the observational source.
#
# The spatial calculation still uses all 36 state/UT polygons internally.
# =============================================================================

report_rows = []


# Explicit DES states
for state_name in explicit_des_states:

    row = states.loc[
        states["state"] == state_name
    ].iloc[0]

    report_rows.append(
        {
            "DES_category": state_name,
            "DES_area_share_percent":
                DES_AREA_SHARE_PERCENT[state_name],
            "mirca_reference_area_ha":
                row["mirca_reference_area_ha"],
            "harmonized_target_area_2021_ha":
                row["target_area_2021_ha"],
            "spatial_scaling_factor":
                row["scaling_factor_area"],
            "blue_km3":
                row["blue_km3"],
            "green_irr_km3":
                row["green_irr_km3"],
            "green_rain_km3":
                row["green_rain_km3"],
            "green_total_km3":
                row["green_total_km3"],
            "total_et_km3":
                row["total_et_km3"],
            "reporting_note":
                "DES 2020-21 explicit state category",
        }
    )


# Collective DES "Others"
others_blue = states.loc[
    others_mask,
    "blue_km3"
].sum()

others_green_irr = states.loc[
    others_mask,
    "green_irr_km3"
].sum()

others_green_rain = states.loc[
    others_mask,
    "green_rain_km3"
].sum()

others_green_total = states.loc[
    others_mask,
    "green_total_km3"
].sum()

others_total_et = states.loc[
    others_mask,
    "total_et_km3"
].sum()


# Because the DES Others target was distributed in direct proportion to MIRCA
# reference area, every state in the Others group has the same scaling factor.
others_spatial_scaling_factor = (
    others_target_area
    / others_mirca_area
)


report_rows.append(
    {
        "DES_category": "Others",
        "DES_area_share_percent":
            DES_AREA_SHARE_PERCENT["Others"],
        "mirca_reference_area_ha":
            others_mirca_area,
        "harmonized_target_area_2021_ha":
            others_target_area,
        "spatial_scaling_factor":
            others_spatial_scaling_factor,
        "blue_km3":
            others_blue,
        "green_irr_km3":
            others_green_irr,
        "green_rain_km3":
            others_green_rain,
        "green_total_km3":
            others_green_total,
        "total_et_km3":
            others_total_et,
        "reporting_note":
            "DES 2020-21 collective Others category; "
            "spatially distributed by MIRCA shares only for raster scaling",
    }
)


reporting_results = pd.DataFrame(
    report_rows
)


reporting_results[
    "blue_share_percent"
] = np.where(
    reporting_results[
        "total_et_km3"
    ] > 0,
    reporting_results[
        "blue_km3"
    ]
    / reporting_results[
        "total_et_km3"
    ]
    * 100,
    np.nan,
)


reporting_results[
    "green_share_percent"
] = np.where(
    reporting_results[
        "total_et_km3"
    ] > 0,
    reporting_results[
        "green_total_km3"
    ]
    / reporting_results[
        "total_et_km3"
    ]
    * 100,
    np.nan,
)


reporting_results = (
    reporting_results
    .sort_values(
        "total_et_km3",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =============================================================================
# 25. NATIONAL SUMMARY
# =============================================================================

national_blue_km3 = states[
    "blue_km3"
].sum()

national_green_irr_km3 = states[
    "green_irr_km3"
].sum()

national_green_rain_km3 = states[
    "green_rain_km3"
].sum()

national_green_total_km3 = states[
    "green_total_km3"
].sum()

national_total_et_km3 = states[
    "total_et_km3"
].sum()


national_summary = pd.DataFrame(
    {
        "Parameter": [
            "Target year",
            "FAOSTAT India harvested area",
            "Sum of harmonized state target areas",
            "MIRCA reference sugarcane area within India",
            "Scaled blue water use",
            "Scaled irrigated green water use",
            "Scaled rainfed green water use",
            "Scaled total green water use",
            "Scaled total consumptive ET",
        ],

        "Value": [
            TARGET_YEAR,
            FAOSTAT_INDIA_AREA_2021_HA,
            national_target_sum,
            india_mirca_area,
            national_blue_km3,
            national_green_irr_km3,
            national_green_rain_km3,
            national_green_total_km3,
            national_total_et_km3,
        ],

        "Unit": [
            "year",
            "ha",
            "ha",
            "ha",
            "km³",
            "km³",
            "km³",
            "km³",
            "km³",
        ]
    }
)


# =============================================================================
# 26. NATIONAL COMPARISON WITH ORIGINAL COUNTRY-LEVEL SCALING
# =============================================================================
#
# Original values are the India 2021 results from the existing global workbook:
#
#   blue  = 34.580227043 km³
#   green = 35.284319844 km³
#   total = 69.864546887 km³
#
# The comparison quantifies the effect of replacing one national scaling factor
# with state-constrained harvested-area scaling while preserving the same exact
# FAOSTAT 2021 national harvested-area target.
# =============================================================================

ORIGINAL_NATIONAL_BLUE_KM3 = 34.580227043
ORIGINAL_NATIONAL_GREEN_KM3 = 35.284319844
ORIGINAL_NATIONAL_TOTAL_ET_KM3 = 69.864546887


national_comparison = pd.DataFrame(
    {
        "Water_component": [
            "Blue water",
            "Green water",
            "Total consumptive ET",
        ],

        "Original_country_level_scaling_km3": [
            ORIGINAL_NATIONAL_BLUE_KM3,
            ORIGINAL_NATIONAL_GREEN_KM3,
            ORIGINAL_NATIONAL_TOTAL_ET_KM3,
        ],

        "State_constrained_scaling_km3": [
            national_blue_km3,
            national_green_total_km3,
            national_total_et_km3,
        ],
    }
)


national_comparison[
    "Difference_km3"
] = (
    national_comparison[
        "State_constrained_scaling_km3"
    ]
    - national_comparison[
        "Original_country_level_scaling_km3"
    ]
)


national_comparison[
    "Difference_percent"
] = (
    national_comparison[
        "Difference_km3"
    ]
    / national_comparison[
        "Original_country_level_scaling_km3"
    ]
    * 100
)


# =============================================================================
# 27. DES INPUT TABLE
# =============================================================================

des_input_table = pd.DataFrame(
    {
        "DES_category":
        list(
            DES_AREA_SHARE_PERCENT.keys()
        ),

        "Area_share_percent":
        list(
            DES_AREA_SHARE_PERCENT.values()
        ),
    }
)


des_input_table[
    "Harmonized_area_ha"
] = (
    des_input_table[
        "Area_share_percent"
    ]
    / 100
    * FAOSTAT_INDIA_AREA_2021_HA
)


# =============================================================================
# 28. VALIDATION TABLE
# =============================================================================

reporting_target_sum = reporting_results[
    "harmonized_target_area_2021_ha"
].sum()

reporting_blue_sum = reporting_results[
    "blue_km3"
].sum()

reporting_green_sum = reporting_results[
    "green_total_km3"
].sum()

reporting_total_et_sum = reporting_results[
    "total_et_km3"
].sum()


validation = pd.DataFrame(
    {
        "Check": [
            "DES shares sum",
            "FAOSTAT national target",
            "Sum of 36-state/UT target areas",
            "36-state/UT target-area difference",
            "Sum of 11+Others reporting target areas",
            "Reporting target-area difference",
            "Number of retained state/UT polygons",
            "Explicit DES states matched",
            "DES reporting categories",
            "States requiring scaling review",
            "Reporting blue equals state-grid blue",
            "Reporting green equals state-grid green",
            "Reporting total ET equals state-grid total ET",
        ],

        "Value": [
            des_share_sum,
            FAOSTAT_INDIA_AREA_2021_HA,
            national_target_sum,
            target_difference,
            reporting_target_sum,
            reporting_target_sum
            - FAOSTAT_INDIA_AREA_2021_HA,
            len(states),
            len(explicit_des_states),
            len(reporting_results),
            int(
                (
                    states[
                        "scaling_flag"
                    ]
                    != "OK"
                ).sum()
            ),
            reporting_blue_sum
            - national_blue_km3,
            reporting_green_sum
            - national_green_total_km3,
            reporting_total_et_sum
            - national_total_et_km3,
        ],

        "Unit": [
            "%",
            "ha",
            "ha",
            "ha",
            "ha",
            "ha",
            "states/UTs",
            "states",
            "categories",
            "states",
            "km³ difference",
            "km³ difference",
            "km³ difference",
        ]
    }
)


# =============================================================================
# 29. EXPORT EXCEL
# =============================================================================

print(
    "\nWriting Excel output..."
)


with pd.ExcelWriter(
    OUTPUT_XLSX,
    engine="openpyxl",
) as writer:

    reporting_results.to_excel(
        writer,
        sheet_name="Reporting_results",
        index=False,
    )

    state_diagnostic.to_excel(
        writer,
        sheet_name="State_diagnostic",
        index=False,
    )

    states.drop(
        columns="geometry"
    ).to_excel(
        writer,
        sheet_name="Scaling_details",
        index=False,
    )

    des_input_table.to_excel(
        writer,
        sheet_name="DES_inputs",
        index=False,
    )

    national_summary.to_excel(
        writer,
        sheet_name="National_summary",
        index=False,
    )

    national_comparison.to_excel(
        writer,
        sheet_name="National_comparison",
        index=False,
    )

    validation.to_excel(
        writer,
        sheet_name="Validation",
        index=False,
    )


'''

text = text[:start] + replacement + text[end:]

# 5) Update section numbering after insertion and raster CRS.
text = text.replace("# 28. EXPORT SCALED 5' RASTERS", "# 30. EXPORT SCALED 5' RASTERS")
text = text.replace('"crs": ah_crs,', '"crs": EFFECTIVE_AH_CRS,')
text = text.replace("# 29. STATE-LEVEL CHOROPLETH MAP — BLUE WATER", "# 31. STATE-LEVEL CHOROPLETH MAP — BLUE WATER")
text = text.replace("# 30. STATE-LEVEL CHOROPLETH MAP — GREEN WATER", "# 32. STATE-LEVEL CHOROPLETH MAP — GREEN WATER")
text = text.replace("# 31. COMPARISON FIGURE — BLUE VS GREEN", "# 33. COMPARISON FIGURE — BLUE VS GREEN")
text = text.replace("# 32. PRINT FINAL RESULTS", "# 34. PRINT FINAL RESULTS")

# 6) Update final printing: state_results -> state_diagnostic, and use national variables.
text = text.replace("f\"{states['blue_km3'].sum():.3f} km³\"", "f\"{national_blue_km3:.3f} km³\"")
text = text.replace("f\"{states['green_total_km3'].sum():.3f} km³\"", "f\"{national_green_total_km3:.3f} km³\"")
text = text.replace("f\"{states['total_et_km3'].sum():.3f} km³\"", "f\"{national_total_et_km3:.3f} km³\"")
text = text.replace("state_results[", "state_diagnostic[")

# 7) Insert reporting-table and comparison printout before the final separator.
needle = """print()
print(
    "=" * 78
)


print(
    "\\nExcel:"
)
"""
insert = """print(
    "\\nDES-supported reporting categories "
    "(11 explicit states + Others):"
)

print(
    reporting_results[
        [
            "DES_category",
            "blue_km3",
            "green_total_km3",
            "total_et_km3",
        ]
    ]
    .to_string(
        index=False
    )
)

print(
    "\\nComparison with original country-level scaling:"
)

print(
    national_comparison.to_string(
        index=False
    )
)

print()
print(
    "=" * 78
)


print(
    "\\nExcel:"
)
"""
text = text.replace(needle, insert)

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
out = OUTPUT_DIR / "02_India_GCWM_sugarcane_subnational_2021_FINAL.py"
out.write_text(text, encoding="utf-8")

print(f"Created: {out}")
print(f"Lines: {len(text.splitlines())}")
