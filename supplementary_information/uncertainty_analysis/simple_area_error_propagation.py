"""
Simple harvested-area error propagation for scaled GCWM ET
===========================================================

PURPOSE
-------
This script performs a simple propagation of the variability associated with
the FAOSTAT harvested-area reference period used to scale country-level GCWM
evapotranspiration (ET) estimates.

The script does NOT estimate the full uncertainty of:
- the GCWM model;
- FAOSTAT statistics;
- climate inputs;
- crop parameters;
- model structure.

It evaluates only the additional variability associated with the
harvested-area scaling step used in this study.

CORE EQUATIONS
--------------

1. Harvested-area scaling:

       ET_scaled = ET_GCWM × (A_year / A_reference)

2. Relative variability of the harvested-area reference period:

       CV_i = SD(A_i,reference period) / mean(A_i,reference period)

3. Country-level propagated variability:

       u_i = ET_i,scaled × CV_i

4. Aggregation across countries using root-sum-of-squares:

       u_total = sqrt(sum(u_i²))

The final result is reported as:

       ET_scaled ± harvested-area scaling variability


REFERENCE-AREA RULE
-------------------
The script follows the same reference-area hierarchy used in the scaling work:

1. Mean harvested area for 1999–2001;
2. otherwise, mean harvested area for 1995–2005;
3. otherwise, the first non-zero harvested-area observation.

For a one-year baseline, a standard deviation cannot be calculated. In those
cases, the script uses the median valid CV of the same crop and flags the row
as imputed. This avoids incorrectly assigning zero variability.


INPUT FILES
-----------
All files must be stored in DATA_DIR:

1. Country-level blue and green ET.xlsx
2. SUGARCAN - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx
3. SUGAR_BEET - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx


OUTPUT
------
Simple_area_error_propagation_2021.xlsx

The workbook contains two sheets:

1. Method
   - purpose;
   - data inputs;
   - equations;
   - assumptions;
   - interpretation.

2. Results_2021
   - main crop-level and combined results;
   - compact diagnostics;
   - country-level calculations for transparency.


REQUIRED PYTHON PACKAGES
------------------------
Install once, if needed:

    pip install pandas numpy openpyxl xlsxwriter
"""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# 1. USER SETTINGS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ET_FILE = DATA_DIR / "Country-level blue and green ET.xlsx"

FAO_SUGARCANE_FILE = (
    DATA_DIR
    / "SUGARCAN - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx"
)

FAO_SUGARBEET_FILE = (
    DATA_DIR
    / "SUGAR_BEET - area_hravest_pro_FAOSTAT_data_en_12-22-2025.xlsx"
)

OUTPUT_FILE = OUTPUT_DIR / "Simple_area_error_propagation_2021.xlsx"

ANALYSIS_YEAR = 2021

# Relative tolerance used to compare the reconstructed FAOSTAT reference area
# with area_ref_final in the country-level ET workbook.
REFERENCE_AREA_TOLERANCE = 1e-6


# =============================================================================
# 2. BASIC VALIDATION AND TEXT HELPERS
# =============================================================================

def require_file(path: Path) -> None:
    """Stop with a clear message if an input file does not exist."""
    if not path.exists():
        raise FileNotFoundError(
            f"\nInput file not found:\n{path}\n\n"
            "Check DATA_DIR and the exact file name."
        )


def clean_text(value: object) -> str:
    """
    Convert text to a stable matching key.

    The function:
    - converts to lowercase;
    - removes accents;
    - removes punctuation;
    - collapses repeated spaces.
    """
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Common naming differences between FAOSTAT and the ET workbook.
COUNTRY_ALIASES = {
    "bolivia plurinational state of": "bolivia",
    "brunei darussalam": "brunei",
    "cabo verde": "cape verde",
    "china mainland": "china",
    "china taiwan province of": "taiwan",
    "cote d ivoire": "ivory coast",
    "czechia": "czech republic",
    "iran islamic republic of": "iran",
    "lao people s democratic republic": "laos",
    "republic of korea": "south korea",
    "republic of moldova": "moldova",
    "russian federation": "russia",
    "syrian arab republic": "syria",
    "tanzania united republic of": "tanzania",
    "turkiye": "turkey",
    "united states of america": "united states",
    "venezuela bolivarian republic of": "venezuela",
    "viet nam": "vietnam",
}


def country_key(value: object) -> str:
    """Create a normalized country key."""
    key = clean_text(value)
    return COUNTRY_ALIASES.get(key, key)


def crop_key(value: object) -> str:
    """Standardize sugarcane and sugar beet crop names."""
    key = clean_text(value)

    if key in {"sugarcane", "sugar cane"}:
        return "Sugarcane"

    if key in {"sugar beet", "sugarbeet"}:
        return "Sugar beet"

    return str(value).strip()


def baseline_key(value: object) -> str:
    """Standardize the reference-period labels."""
    key = clean_text(value)

    if "1999" in key and "2001" in key:
        return "1999-2001"

    if "1995" in key and "2005" in key:
        return "1995-2005"

    if "first" in key and ("nonzero" in key or "non zero" in key):
        return "first_nonzero"

    return key


# =============================================================================
# 3. READ THE COUNTRY-LEVEL ET WORKBOOK
# =============================================================================

def detect_et_table() -> tuple[str, int]:
    """
    Automatically detect the worksheet and header row containing the ET table.

    The earlier script failed because it assumed that the headers were always
    in Excel row 2. This function instead searches the first 30 rows of every
    worksheet for the required column names.

    Returns
    -------
    tuple
        (worksheet name, zero-based header-row number)
    """
    required_columns = {
        "country",
        "year",
        "area_ref_final",
        "baseline_used",
        "blue_m3_scaled",
        "green_total_m3_scaled",
        "et_m3_scaled",
        "crop",
    }

    workbook = pd.ExcelFile(ET_FILE)

    for sheet_name in workbook.sheet_names:
        preview = pd.read_excel(
            ET_FILE,
            sheet_name=sheet_name,
            header=None,
            nrows=30,
        )

        for row_number in range(len(preview)):
            row_values = {
                str(value).strip()
                for value in preview.iloc[row_number].tolist()
                if pd.notna(value)
            }

            if required_columns.issubset(row_values):
                return sheet_name, row_number

    raise ValueError(
        "\nCould not locate the country-level ET table automatically.\n\n"
        f"Workbook: {ET_FILE}\n"
        f"Worksheets found: {workbook.sheet_names}\n\n"
        "Expected columns:\n"
        f"{sorted(required_columns)}\n\n"
        "Check that 'Country-level blue and green ET.xlsx' is the correct "
        "scaled country-level workbook."
    )


def read_et_data() -> pd.DataFrame:
    """
    Read and prepare the country-level scaled ET data for ANALYSIS_YEAR.
    """
    sheet_name, header_row = detect_et_table()

    print(
        f"Detected ET table in worksheet '{sheet_name}', "
        f"Excel header row {header_row + 1}."
    )

    dataframe = pd.read_excel(
        ET_FILE,
        sheet_name=sheet_name,
        header=header_row,
    )

    # Remove accidental leading/trailing spaces in column headings.
    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    required_columns = [
        "country",
        "year",
        "area_ref_final",
        "baseline_used",
        "blue_m3_scaled",
        "green_total_m3_scaled",
        "et_m3_scaled",
        "crop",
    ]

    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            f"\nThe ET table was detected, but these columns are missing:\n"
            f"{missing}\n\n"
            f"Detected columns:\n{list(dataframe.columns)}"
        )

    dataframe["year"] = pd.to_numeric(
        dataframe["year"],
        errors="coerce",
    )

    dataframe = dataframe.loc[
        dataframe["year"].eq(ANALYSIS_YEAR)
    ].copy()

    if dataframe.empty:
        raise ValueError(
            f"\nThe ET table was found, but it contains no rows for "
            f"ANALYSIS_YEAR={ANALYSIS_YEAR}."
        )

    dataframe["country_key"] = dataframe["country"].map(country_key)
    dataframe["crop_standard"] = dataframe["crop"].map(crop_key)
    dataframe["baseline_standard"] = dataframe["baseline_used"].map(
        baseline_key
    )

    numeric_columns = [
        "area_ref_final",
        "blue_m3_scaled",
        "green_total_m3_scaled",
        "et_m3_scaled",
    ]

    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    return dataframe


# =============================================================================
# 4. READ THE FAOSTAT HARVESTED-AREA FILES
# =============================================================================

def read_faostat_area(
    path: Path,
    expected_crop: str,
) -> pd.DataFrame:
    """
    Read one FAOSTAT workbook and retain harvested area in hectares only.

    FAOSTAT files may contain harvested area, yield and production. Only:

        Element = Area harvested
        Unit    = ha

    are retained.
    """
    dataframe = pd.read_excel(path, sheet_name=0)

    required_columns = [
        "Area",
        "Element",
        "Item",
        "Year",
        "Unit",
        "Value",
    ]

    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            f"\nFAOSTAT file '{path.name}' is missing columns:\n"
            f"{missing}\n\n"
            f"Available columns:\n{list(dataframe.columns)}"
        )

    dataframe = dataframe.loc[
        dataframe["Element"].map(clean_text).eq("area harvested")
        & dataframe["Unit"].map(clean_text).eq("ha")
    ].copy()

    dataframe["crop_standard"] = dataframe["Item"].map(crop_key)

    dataframe = dataframe.loc[
        dataframe["crop_standard"].eq(expected_crop)
    ].copy()

    dataframe["Year"] = pd.to_numeric(
        dataframe["Year"],
        errors="coerce",
    )

    dataframe["Value"] = pd.to_numeric(
        dataframe["Value"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["Year", "Value"]
    ).copy()

    dataframe["country_key"] = dataframe["Area"].map(country_key)

    output_columns = [
        "Area",
        "country_key",
        "crop_standard",
        "Year",
        "Value",
    ]

    if "Flag" in dataframe.columns:
        output_columns.append("Flag")

    return dataframe[output_columns].copy()


# =============================================================================
# 5. RECONSTRUCT THE REFERENCE AREA AND CALCULATE CV
# =============================================================================

def select_reference_period(
    country_data: pd.DataFrame,
    baseline: str,
) -> pd.DataFrame:
    """
    Select the annual values used to construct the reference area.
    """
    if baseline == "1999-2001":
        return country_data.loc[
            country_data["Year"].between(1999, 2001)
        ].copy()

    if baseline == "1995-2005":
        return country_data.loc[
            country_data["Year"].between(1995, 2005)
        ].copy()

    if baseline == "first_nonzero":
        return (
            country_data.loc[country_data["Value"] > 0]
            .sort_values("Year")
            .head(1)
            .copy()
        )

    return country_data.iloc[0:0].copy()


def calculate_country_reference_statistics(
    et_data: pd.DataFrame,
    faostat_data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate reference-area mean, sample SD and CV for every ET row.

    Formula
    -------
        CV_i = SD(A_i,reference period) / mean(A_i,reference period)

    Sample standard deviation is used (ddof=1).

    A CV cannot be calculated from a single observation. Such cases remain
    blank at this stage and are treated transparently in the next function.
    """
    faostat_groups = {
        key: group.sort_values("Year").copy()
        for key, group in faostat_data.groupby(
            ["country_key", "crop_standard"]
        )
    }

    output_rows: list[dict[str, object]] = []

    for _, et_row in et_data.iterrows():
        record = et_row.to_dict()

        record.update(
            {
                "baseline_years": "",
                "baseline_n": 0,
                "reference_mean_calculated_ha": np.nan,
                "reference_sd_ha": np.nan,
                "reference_cv_raw": np.nan,
                "reference_area_relative_difference": np.nan,
                "reference_check": "NO_MATCH",
            }
        )

        match_key = (
            et_row["country_key"],
            et_row["crop_standard"],
        )

        country_faostat = faostat_groups.get(match_key)

        if country_faostat is None or country_faostat.empty:
            output_rows.append(record)
            continue

        selected = select_reference_period(
            country_faostat,
            et_row["baseline_standard"],
        )

        if selected.empty:
            record["reference_check"] = "NO_BASELINE_DATA"
            output_rows.append(record)
            continue

        values = selected["Value"].astype(float)

        number_of_years = len(values)
        mean_area = float(values.mean())

        sample_sd = (
            float(values.std(ddof=1))
            if number_of_years >= 2
            else np.nan
        )

        raw_cv = (
            sample_sd / mean_area
            if number_of_years >= 2 and mean_area > 0
            else np.nan
        )

        stored_reference_area = et_row["area_ref_final"]

        relative_difference = (
            abs(mean_area - stored_reference_area)
            / abs(stored_reference_area)
            if pd.notna(stored_reference_area)
            and stored_reference_area != 0
            else np.nan
        )

        if pd.isna(relative_difference):
            reference_check = "CANNOT_COMPARE"
        elif relative_difference <= REFERENCE_AREA_TOLERANCE:
            reference_check = "MATCH"
        else:
            reference_check = "MISMATCH"

        record.update(
            {
                "baseline_years": ", ".join(
                    str(int(year))
                    for year in selected["Year"].tolist()
                ),
                "baseline_n": number_of_years,
                "reference_mean_calculated_ha": mean_area,
                "reference_sd_ha": sample_sd,
                "reference_cv_raw": raw_cv,
                "reference_area_relative_difference": relative_difference,
                "reference_check": reference_check,
            }
        )

        output_rows.append(record)

    return pd.DataFrame(output_rows)


def assign_cv_to_single_year_cases(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Treat records for which a country-specific CV cannot be calculated.

    Problem
    -------
    A one-year baseline has no calculable standard deviation.

    Treatment
    ---------
    Use the median valid CV of the same crop and flag the record as imputed.

    This is preferable to assigning zero variability merely because only one
    baseline observation exists.
    """
    detail = detail.copy()

    valid_cv_rows = detail.loc[
        detail["reference_cv_raw"].notna()
        & detail["reference_cv_raw"].ge(0)
    ].copy()

    crop_median_cv = (
        valid_cv_rows
        .groupby("crop_standard")["reference_cv_raw"]
        .median()
        .to_dict()
    )

    detail["crop_median_cv"] = detail["crop_standard"].map(
        crop_median_cv
    )

    detail["cv_used"] = detail["reference_cv_raw"]

    missing_cv = detail["cv_used"].isna()

    detail.loc[missing_cv, "cv_used"] = detail.loc[
        missing_cv,
        "crop_median_cv",
    ]

    detail["cv_source"] = "Country reference-period CV"

    detail.loc[
        missing_cv,
        "cv_source",
    ] = "Crop median CV (imputed)"

    detail.loc[
        detail["cv_used"].isna(),
        "cv_source",
    ] = "No valid CV available"

    return detail


# =============================================================================
# 6. SIMPLE PROPAGATION TO BLUE, GREEN AND TOTAL ET
# =============================================================================

def propagate_country_variability(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply the same relative harvested-area variability to each scaled ET term.

    Formula
    -------
        u_i = ET_i,scaled × CV_i
    """
    detail = detail.copy()

    detail["blue_variability_m3"] = (
        detail["blue_m3_scaled"]
        * detail["cv_used"]
    )

    detail["green_variability_m3"] = (
        detail["green_total_m3_scaled"]
        * detail["cv_used"]
    )

    detail["total_variability_m3"] = (
        detail["et_m3_scaled"]
        * detail["cv_used"]
    )

    return detail


def summarize_metric(
    data: pd.DataFrame,
    crop_label: str,
    component_label: str,
    estimate_column: str,
    variability_column: str,
) -> dict[str, object]:
    """
    Aggregate country-level variability with root-sum-of-squares.

    Formula
    -------
        u_total = sqrt(sum(u_i²))

    This is the standard simple propagation for independent contributions.
    """
    estimate_m3 = float(
        data[estimate_column].sum()
    )

    valid_variability = data[
        variability_column
    ].dropna()

    variability_m3 = float(
        math.sqrt(
            np.square(valid_variability).sum()
        )
    )

    relative_variability_percent = (
        variability_m3 / estimate_m3 * 100
        if estimate_m3 != 0
        else np.nan
    )

    imputed_rows = data["cv_source"].eq(
        "Crop median CV (imputed)"
    )

    imputed_et_m3 = float(
        data.loc[
            imputed_rows,
            estimate_column,
        ].sum()
    )

    imputed_et_share_percent = (
        imputed_et_m3 / estimate_m3 * 100
        if estimate_m3 != 0
        else np.nan
    )

    return {
        "Crop": crop_label,
        "ET component": component_label,
        "Estimate (km3)": estimate_m3 / 1e9,
        "Absolute variability (km3)": variability_m3 / 1e9,
        "Relative variability (%)": relative_variability_percent,
        "Lower value (km3)": (
            estimate_m3 - variability_m3
        ) / 1e9,
        "Upper value (km3)": (
            estimate_m3 + variability_m3
        ) / 1e9,
        "Result": (
            f"{estimate_m3 / 1e9:.3f} ± "
            f"{variability_m3 / 1e9:.3f} km³"
        ),
        "Records": int(len(data)),
        "Imputed-CV records": int(imputed_rows.sum()),
        "ET using imputed CV (%)": imputed_et_share_percent,
        "Reference mismatches": int(
            data["reference_check"].eq("MISMATCH").sum()
        ),
        "Unmatched records": int(
            data["reference_check"].eq("NO_MATCH").sum()
        ),
    }


def build_main_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create results for:
    - sugarcane;
    - sugar beet;
    - all sugar crops;
    and for blue, green and total ET.
    """
    metrics = [
        (
            "Blue ET",
            "blue_m3_scaled",
            "blue_variability_m3",
        ),
        (
            "Green ET",
            "green_total_m3_scaled",
            "green_variability_m3",
        ),
        (
            "Total ET",
            "et_m3_scaled",
            "total_variability_m3",
        ),
    ]

    rows: list[dict[str, object]] = []

    for crop in ["Sugarcane", "Sugar beet"]:
        crop_data = detail.loc[
            detail["crop_standard"].eq(crop)
        ].copy()

        for (
            component_label,
            estimate_column,
            variability_column,
        ) in metrics:
            rows.append(
                summarize_metric(
                    crop_data,
                    crop,
                    component_label,
                    estimate_column,
                    variability_column,
                )
            )

    for (
        component_label,
        estimate_column,
        variability_column,
    ) in metrics:
        rows.append(
            summarize_metric(
                detail,
                "All sugar crops",
                component_label,
                estimate_column,
                variability_column,
            )
        )

    return pd.DataFrame(rows)


def build_diagnostics(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create a compact diagnostic table by crop and reference-period type.
    """
    rows: list[dict[str, object]] = []

    for (
        crop,
        baseline,
    ), group in detail.groupby(
        ["crop_standard", "baseline_standard"],
        dropna=False,
    ):
        crop_total_et = detail.loc[
            detail["crop_standard"].eq(crop),
            "et_m3_scaled",
        ].sum()

        baseline_et = group["et_m3_scaled"].sum()

        rows.append(
            {
                "Crop": crop,
                "Reference baseline": baseline,
                "Records": int(len(group)),
                "Valid country CVs": int(
                    group["reference_cv_raw"].notna().sum()
                ),
                "Imputed CVs": int(
                    group["cv_source"].eq(
                        "Crop median CV (imputed)"
                    ).sum()
                ),
                "Median valid CV (%)": (
                    group["reference_cv_raw"].median()
                    * 100
                ),
                "Baseline ET (km3)": baseline_et / 1e9,
                "Share of crop ET (%)": (
                    baseline_et / crop_total_et * 100
                    if crop_total_et != 0
                    else np.nan
                ),
                "Reference mismatches": int(
                    group["reference_check"].eq(
                        "MISMATCH"
                    ).sum()
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# 7. EXPORT A TWO-SHEET EXCEL WORKBOOK
# =============================================================================

def export_workbook(
    summary: pd.DataFrame,
    diagnostics: pd.DataFrame,
    detail: pd.DataFrame,
) -> None:
    """
    Export the analysis to a clear two-sheet Excel workbook.
    """
    method_rows = [
        [
            "Title",
            "Simple harvested-area error propagation for scaled GCWM ET",
        ],
        [
            "Purpose",
            "Evaluate only the variability introduced by the FAOSTAT "
            "harvested-area reference period used in the scaling step.",
        ],
        [
            "Not included",
            "The result is not a complete uncertainty estimate for GCWM, "
            "FAOSTAT, climate inputs, crop parameters or model structure.",
        ],
        [
            "Analysis year",
            ANALYSIS_YEAR,
        ],
        [
            "Input ET file",
            ET_FILE.name,
        ],
        [
            "Input FAOSTAT file 1",
            FAO_SUGARCANE_FILE.name,
        ],
        [
            "Input FAOSTAT file 2",
            FAO_SUGARBEET_FILE.name,
        ],
        [
            "",
            "",
        ],
        [
            "Equation 1: scaling",
            "ET_scaled = ET_GCWM × (A_year / A_reference)",
        ],
        [
            "Equation 2: area variability",
            "CV_i = SD(A_i,reference period) / "
            "mean(A_i,reference period)",
        ],
        [
            "Equation 3: country propagation",
            "u_i = ET_i,scaled × CV_i",
        ],
        [
            "Equation 4: aggregation",
            "u_total = sqrt(sum(u_i²))",
        ],
        [
            "",
            "",
        ],
        [
            "Reference-period hierarchy",
            "1999–2001; otherwise 1995–2005; otherwise first non-zero.",
        ],
        [
            "Single-year baseline",
            "A standard deviation cannot be calculated from one observation. "
            "The median valid CV of the same crop is used and flagged.",
        ],
        [
            "Validation",
            "The reconstructed FAOSTAT reference mean is compared with "
            "area_ref_final from the country-level ET workbook.",
        ],
        [
            "Recommended interpretation",
            "Harvested-area scaling variability or reference-period "
            "sensitivity.",
        ],
        [
            "Recommended result format",
            "Scaled ET estimate ± propagated harvested-area variability.",
        ],
    ]

    method = pd.DataFrame(
        method_rows,
        columns=["Item", "Explanation"],
    )

    detail_columns = [
        "iso3",
        "country",
        "crop_standard",
        "year",
        "baseline_used",
        "baseline_standard",
        "baseline_years",
        "baseline_n",
        "area_ref_final",
        "reference_mean_calculated_ha",
        "reference_sd_ha",
        "reference_cv_raw",
        "crop_median_cv",
        "cv_used",
        "cv_source",
        "reference_area_relative_difference",
        "reference_check",
        "blue_m3_scaled",
        "blue_variability_m3",
        "green_total_m3_scaled",
        "green_variability_m3",
        "et_m3_scaled",
        "total_variability_m3",
    ]

    detail_columns = [
        column
        for column in detail_columns
        if column in detail.columns
    ]

    detail_export = detail[
        detail_columns
    ].copy()

    detail_export = detail_export.rename(
        columns={
            "crop_standard": "crop",
            "reference_cv_raw": "reference_cv_raw_fraction",
            "crop_median_cv": "crop_median_cv_fraction",
            "cv_used": "cv_used_fraction",
        }
    )

    detail_export = detail_export.sort_values(
        ["crop", "country"]
    ).reset_index(drop=True)

    summary_start_row = 1
    diagnostics_start_row = (
        summary_start_row
        + len(summary)
        + 4
    )
    detail_start_row = (
        diagnostics_start_row
        + len(diagnostics)
        + 4
    )

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="xlsxwriter",
    ) as writer:
        method.to_excel(
            writer,
            sheet_name="Method",
            index=False,
        )

        summary.to_excel(
            writer,
            sheet_name="Results_2021",
            index=False,
            startrow=summary_start_row,
        )

        diagnostics.to_excel(
            writer,
            sheet_name="Results_2021",
            index=False,
            startrow=diagnostics_start_row,
        )

        detail_export.to_excel(
            writer,
            sheet_name="Results_2021",
            index=False,
            startrow=detail_start_row,
        )

        workbook = writer.book

        method_sheet = writer.sheets["Method"]
        results_sheet = writer.sheets["Results_2021"]

        title_format = workbook.add_format(
            {
                "bold": True,
                "font_size": 14,
                "font_color": "white",
                "bg_color": "#1F4E78",
                "valign": "vcenter",
            }
        )

        header_format = workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#4472C4",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )

        wrap_format = workbook.add_format(
            {
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )

        number_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "0.000",
            }
        )

        percent_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "0.00",
            }
        )

        fraction_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "0.0000",
            }
        )

        scientific_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "0.000E+00",
            }
        )

        # --------------------------
        # Method sheet formatting
        # --------------------------

        method_sheet.set_column("A:A", 31)
        method_sheet.set_column("B:B", 100)
        method_sheet.set_row(0, 28, header_format)
        method_sheet.freeze_panes(1, 0)
        method_sheet.hide_gridlines(2)

        for row_number in range(
            1,
            len(method) + 1,
        ):
            method_sheet.set_row(
                row_number,
                34,
            )

        method_sheet.set_column(
            0,
            1,
            None,
            wrap_format,
        )

        # --------------------------
        # Results sheet formatting
        # --------------------------

        results_sheet.write(
            0,
            0,
            "A. Main results",
            title_format,
        )

        results_sheet.write(
            diagnostics_start_row - 1,
            0,
            "B. Diagnostics",
            title_format,
        )

        results_sheet.write(
            detail_start_row - 1,
            0,
            "C. Country-level calculations",
            title_format,
        )

        results_sheet.set_row(
            summary_start_row,
            42,
            header_format,
        )

        results_sheet.set_row(
            diagnostics_start_row,
            42,
            header_format,
        )

        results_sheet.set_row(
            detail_start_row,
            48,
            header_format,
        )

        results_sheet.freeze_panes(
            summary_start_row + 1,
            2,
        )

        results_sheet.hide_gridlines(2)

        # Main summary column formatting
        summary_column_index = {
            column: index
            for index, column in enumerate(
                summary.columns
            )
        }

        results_sheet.set_column(
            0,
            1,
            18,
        )

        if "Result" in summary_column_index:
            index = summary_column_index["Result"]
            results_sheet.set_column(
                index,
                index,
                24,
            )

        for column in [
            "Estimate (km3)",
            "Absolute variability (km3)",
            "Lower value (km3)",
            "Upper value (km3)",
        ]:
            if column in summary_column_index:
                index = summary_column_index[column]
                results_sheet.set_column(
                    index,
                    index,
                    19,
                    number_format,
                )

        for column in [
            "Relative variability (%)",
            "ET using imputed CV (%)",
        ]:
            if column in summary_column_index:
                index = summary_column_index[column]
                results_sheet.set_column(
                    index,
                    index,
                    19,
                    percent_format,
                )

        # Country-level calculation formatting
        detail_column_index = {
            column: index
            for index, column in enumerate(
                detail_export.columns
            )
        }

        width_map = {
            "iso3": 8,
            "country": 24,
            "crop": 13,
            "year": 10,
            "baseline_used": 17,
            "baseline_standard": 16,
            "baseline_years": 25,
            "cv_source": 29,
            "reference_check": 18,
        }

        for column, width in width_map.items():
            if column in detail_column_index:
                index = detail_column_index[column]
                results_sheet.set_column(
                    index,
                    index,
                    width,
                )

        for column in [
            "reference_cv_raw_fraction",
            "crop_median_cv_fraction",
            "cv_used_fraction",
            "reference_area_relative_difference",
        ]:
            if column in detail_column_index:
                index = detail_column_index[column]
                results_sheet.set_column(
                    index,
                    index,
                    17,
                    fraction_format,
                )

        for column in [
            "area_ref_final",
            "reference_mean_calculated_ha",
            "reference_sd_ha",
            "blue_m3_scaled",
            "blue_variability_m3",
            "green_total_m3_scaled",
            "green_variability_m3",
            "et_m3_scaled",
            "total_variability_m3",
        ]:
            if column in detail_column_index:
                index = detail_column_index[column]
                results_sheet.set_column(
                    index,
                    index,
                    18,
                    scientific_format,
                )

        # Highlight imputed CV cases.
        if "cv_source" in detail_column_index:
            column_index = detail_column_index[
                "cv_source"
            ]

            results_sheet.conditional_format(
                detail_start_row + 1,
                column_index,
                detail_start_row + len(detail_export),
                column_index,
                {
                    "type": "text",
                    "criteria": "containing",
                    "value": "imputed",
                    "format": workbook.add_format(
                        {
                            "bg_color": "#FFF2CC",
                            "font_color": "#7F6000",
                        }
                    ),
                },
            )

        # Highlight reference-area mismatches.
        if "reference_check" in detail_column_index:
            column_index = detail_column_index[
                "reference_check"
            ]

            results_sheet.conditional_format(
                detail_start_row + 1,
                column_index,
                detail_start_row + len(detail_export),
                column_index,
                {
                    "type": "text",
                    "criteria": "containing",
                    "value": "MISMATCH",
                    "format": workbook.add_format(
                        {
                            "bg_color": "#F4CCCC",
                            "font_color": "#9C0006",
                        }
                    ),
                },
            )


# =============================================================================
# 8. RUN THE COMPLETE ANALYSIS
# =============================================================================

def main() -> None:
    """Execute the complete simple propagation."""
    print("=" * 78)
    print("Simple harvested-area error propagation")
    print("=" * 78)

    for input_file in [
        ET_FILE,
        FAO_SUGARCANE_FILE,
        FAO_SUGARBEET_FILE,
    ]:
        require_file(input_file)
        print(f"Found: {input_file.name}")

    print(
        f"\nReading country-level ET data "
        f"for {ANALYSIS_YEAR}..."
    )

    et_data = read_et_data()

    print(
        f"Country-level ET records: "
        f"{len(et_data):,}"
    )

    print(
        "\nReading FAOSTAT harvested-area data..."
    )

    sugarcane_area = read_faostat_area(
        FAO_SUGARCANE_FILE,
        expected_crop="Sugarcane",
    )

    sugarbeet_area = read_faostat_area(
        FAO_SUGARBEET_FILE,
        expected_crop="Sugar beet",
    )

    faostat_area = pd.concat(
        [
            sugarcane_area,
            sugarbeet_area,
        ],
        ignore_index=True,
    )

    print(
        f"FAOSTAT harvested-area observations: "
        f"{len(faostat_area):,}"
    )

    print(
        "\nReconstructing reference areas and "
        "calculating country CVs..."
    )

    detail = calculate_country_reference_statistics(
        et_data,
        faostat_area,
    )

    detail = assign_cv_to_single_year_cases(
        detail
    )

    detail = propagate_country_variability(
        detail
    )

    summary = build_main_summary(
        detail
    )

    diagnostics = build_diagnostics(
        detail
    )

    mismatch_count = int(
        detail["reference_check"]
        .eq("MISMATCH")
        .sum()
    )

    unmatched_count = int(
        detail["reference_check"]
        .eq("NO_MATCH")
        .sum()
    )

    imputed_count = int(
        detail["cv_source"]
        .eq("Crop median CV (imputed)")
        .sum()
    )

    print("\nQuality checks")
    print(
        f"Reference-area mismatches: "
        f"{mismatch_count}"
    )
    print(
        f"Unmatched country records: "
        f"{unmatched_count}"
    )
    print(
        f"Records using crop-median CV: "
        f"{imputed_count}"
    )

    print(
        f"\nWriting output workbook:\n"
        f"{OUTPUT_FILE}"
    )

    export_workbook(
        summary,
        diagnostics,
        detail,
    )

    combined_total = summary.loc[
        summary["Crop"].eq(
            "All sugar crops"
        )
        & summary["ET component"].eq(
            "Total ET"
        )
    ]

    if not combined_total.empty:
        result_row = combined_total.iloc[0]

        print("\nCombined 2021 result")
        print(result_row["Result"])
        print(
            "Relative harvested-area scaling "
            f"variability: "
            f"{result_row['Relative variability (%)']:.2f}%"
        )

    print("\nCompleted successfully.")
    print(
        "Recommended SI wording: "
        "'harvested-area scaling variability' "
        "or 'reference-period sensitivity'."
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print("\nERROR")
        print("-" * 78)
        print(error)
        print("-" * 78)
        sys.exit(1)
