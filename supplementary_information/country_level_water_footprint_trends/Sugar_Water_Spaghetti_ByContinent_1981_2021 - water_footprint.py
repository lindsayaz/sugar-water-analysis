# -*- coding: utf-8 -*-

"""
===============================================================================
SUGAR WATER-FOOTPRINT SPAGHETTI PLOTS — BY CONTINENT
===============================================================================

Purpose
-------
This script creates one three-panel figure for each continent showing annual
country-level consumptive water footprints for combined sugarcane and sugar
beet production from 1981 to 2021.

Panels
------
A. Blue consumptive water footprint
B. Green consumptive water footprint
C. Total consumptive water footprint

Units
-----
All water-footprint indicators are expressed as:

    m³ of consumptive water per tonne of harvested crop

Interpretation
--------------
Higher values indicate that more water is consumed per tonne of crop:

    Higher water footprint = lower water-use efficiency
    Lower water footprint  = higher water-use efficiency

Visual design
-------------
The script retains the same visual structure as the previous absolute-water-use
spaghetti figures:

- one figure per continent;
- three horizontal panels;
- thin country lines;
- one highlighted country in each panel;
- ISO3 label for the highlighted country;
- identical panel colors and general publication style;
- PDF and JPG outputs.

Highlighted country
-------------------
For each panel, the highlighted country is the country with the highest mean
annual water footprint over the available study period.

The mean is used instead of the sum because water footprint is an intensity
indicator. Summing m³/t values over time has no useful physical meaning.
===============================================================================
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# 1. FILE PATHS
# =============================================================================

# Input file containing the calculated water-footprint columns.
BASE_DIR = Path(__file__).resolve().parent
IN_FILE = BASE_DIR / "data" / "S2_Country-level_GCWM_with_water_footprint_m3_per_t.xlsx"

# Output folder for the new water-footprint figures.
OUT_DIR = BASE_DIR / "outputs"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 2. SETTINGS
# =============================================================================

YEAR_MIN = 1981
YEAR_MAX = 2021

# Water-footprint columns created in the data-preparation script.
BLUE_COL = "blue_WF_m3_per_t_crop"
GREEN_COL = "green_WF_m3_per_t_crop"
TOTAL_COL = "total_WF_m3_per_t_crop"

CONTINENTS = [
    "Asia",
    "South America",
    "North America",
    "Africa",
    "Europe",
    "Central America",
    "Oceania",
]


# Colors retained from the original spaghetti figures.
COLOR_BLUE = "#3f8fad"
COLOR_GREEN = "#4bb277"
COLOR_TOTAL = "#924848"


# Thin country-line styling.
LINE_WIDTH = 1.0
LINE_ALPHA = 0.35


# Highlighted-country styling.
DOM_LINE_WIDTH = 1.8
DOM_ALPHA = 0.9


# Text and figure settings.
PANEL_LABEL_SIZE = 14
ISO3_LABEL_SIZE = 10
FIGSIZE = (13, 4)


# Smoothing is disabled by default.
USE_SMOOTHING = False
ROLLING_WINDOW = 3


# Add 10% space above the largest plotted value.
Y_AXIS_MARGIN = 1.10


# =============================================================================
# 3. LOAD DATA
# =============================================================================

df = pd.read_excel(IN_FILE)

print("=" * 79)
print("WATER-FOOTPRINT SPAGHETTI FIGURES")
print("=" * 79)

print(f"\nLoaded {len(df):,} rows.")
print(f"\nInput file:\n{IN_FILE}")


# =============================================================================
# 4. CHECK REQUIRED COLUMNS
# =============================================================================

required_columns = [
    "iso3",
    "country",
    "year",
    "Continent",
    BLUE_COL,
    GREEN_COL,
    TOTAL_COL,
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
# 5. CLEAN AND PREPARE DATA
# =============================================================================

# Remove leading and trailing spaces from text variables.
for column in ["iso3", "country", "Continent"]:
    df[column] = (
        df[column]
        .astype(str)
        .str.strip()
    )


# Convert year to numeric.
df["year"] = pd.to_numeric(
    df["year"],
    errors="coerce",
)


# Keep only the study period.
df = df[
    df["year"].between(YEAR_MIN, YEAR_MAX)
].copy()


# Convert water-footprint variables to numeric.
for column in [BLUE_COL, GREEN_COL, TOTAL_COL]:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce",
    )


# Replace infinite values with NaN.
df[[BLUE_COL, GREEN_COL, TOTAL_COL]] = (
    df[[BLUE_COL, GREEN_COL, TOTAL_COL]]
    .replace([np.inf, -np.inf], np.nan)
)


# Remove negative water-footprint values if any occur.
# Negative water consumption per unit of production is not physically meaningful.
for column in [BLUE_COL, GREEN_COL, TOTAL_COL]:
    negative_count = (df[column] < 0).sum()

    if negative_count > 0:
        print(
            f"Warning: {negative_count:,} negative values found in "
            f"{column}; these values were replaced by NaN."
        )

        df.loc[df[column] < 0, column] = np.nan


# -------------------------------------------------------------------------
# Handle Ukraine's historical data
# -------------------------------------------------------------------------
# Ukraine only has reliable country-level national data after approximately
# 1991. Earlier rows are removed to avoid artificial time-series jumps.

df = df[
    ~(
        (df["iso3"] == "UKR")
        & (df["year"] < 1991)
    )
].copy()


# -------------------------------------------------------------------------
# Exclude countries without complete coverage for the study period
# -------------------------------------------------------------------------
# BIH, PRI, BGR, PRT, IRQ, and BRN are omitted because they do not have
# observations for all years in the 1981-2021 analysis window, which would
# otherwise create incomplete time series in the spaghetti plots.

excluded_iso3 = {"BIH", "PRI", "BGR", "PRT", "IRQ", "BRN"}
df = df[~df["iso3"].isin(excluded_iso3)].copy()


# =============================================================================
# 6. HELPER FUNCTIONS
# =============================================================================

def style_axis(ax):
    """
    Apply the same clean publication style used in the original figures.
    """

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.tick_params(
        axis="both",
        labelsize=9,
    )


def smooth_series(values):
    """
    Apply a centred rolling mean when smoothing is enabled.
    """

    return (
        pd.Series(values)
        .rolling(
            window=ROLLING_WINDOW,
            center=True,
            min_periods=1,
        )
        .mean()
        .to_numpy()
    )


def get_highest_mean_country(df_continent, value_column):
    """
    Identify the country with the highest mean annual water footprint.

    The mean is used because water footprint is an intensity indicator.
    Summing annual m³/t values would not have a meaningful physical
    interpretation.
    """

    country_means = (
        df_continent
        .groupby("iso3")[value_column]
        .mean()
        .dropna()
        .sort_values(ascending=False)
    )

    if country_means.empty:
        return None

    return country_means.index[0]


def calculate_ymax(panel_max):
    """
    Calculate an automatic y-axis maximum with a 10% upper margin.
    """

    if not np.isfinite(panel_max) or panel_max <= 0:
        return 1

    ymax = panel_max * Y_AXIS_MARGIN

    # Round upward to a readable scale.
    magnitude = 10 ** np.floor(np.log10(ymax))
    normalized = ymax / magnitude

    if normalized <= 1:
        rounded = 1
    elif normalized <= 2:
        rounded = 2
    elif normalized <= 5:
        rounded = 5
    else:
        rounded = 10

    return rounded * magnitude


def trim_leading_invalid_values(years, values):
    """
    Remove leading zero or missing values from a country time series.

    This prevents an artificial line from zero when a country begins reporting
    later in the study period.
    """

    years = np.asarray(years)
    values = np.asarray(values, dtype=float)

    valid = np.isfinite(values) & (values != 0)

    if not valid.any():
        return years, values

    first_valid_index = int(np.where(valid)[0][0])

    values[:first_valid_index] = np.nan

    return years, values


# =============================================================================
# 7. PANEL DEFINITIONS
# =============================================================================

PANELS = [
    (
        "A",
        BLUE_COL,
        COLOR_BLUE,
        "Blue consumptive water footprint (m³/t crop)",
    ),
    (
        "B",
        GREEN_COL,
        COLOR_GREEN,
        "Green consumptive water footprint (m³/t crop)",
    ),
    (
        "C",
        TOTAL_COL,
        COLOR_TOTAL,
        "Total consumptive water footprint (m³/t crop)",
    ),
]


# =============================================================================
# 8. CREATE FIGURES
# =============================================================================

for continent in CONTINENTS:

    df_continent = df[
        df["Continent"] == continent
    ].copy()

    if df_continent.empty:
        print(f"No data found for {continent}; figure skipped.")
        continue

    number_of_countries = df_continent["iso3"].nunique()

    fig, axes = plt.subplots(
        nrows=1,
        ncols=3,
        figsize=FIGSIZE,
    )

    for ax, (letter, column, color, ylabel) in zip(
        axes,
        PANELS,
    ):

        panel_max = 0


        # =====================================================================
        # Plot all country time series
        # =====================================================================

        for iso3, country_group in df_continent.groupby("iso3"):

            country_group = country_group.sort_values("year")

            years = country_group["year"].to_numpy()
            values = (
                country_group[column]
                .to_numpy(dtype=float)
            )


            # Trim leading missing or zero values for Ukraine.
            if continent == "Europe" and iso3 == "UKR":
                years, values = trim_leading_invalid_values(
                    years,
                    values,
                )


            # Apply optional smoothing.
            if USE_SMOOTHING:
                original_nan_mask = np.isnan(values)

                values = smooth_series(values)

                # Preserve missing values at the beginning of the time series.
                values[original_nan_mask] = np.nan


            # Skip countries with no usable observations.
            if np.all(np.isnan(values)):
                continue


            finite_values = values[np.isfinite(values)]

            if finite_values.size > 0:
                panel_max = max(
                    panel_max,
                    finite_values.max(),
                )


            ax.plot(
                years,
                values,
                linewidth=LINE_WIDTH,
                alpha=LINE_ALPHA,
                color=color,
            )


        # =====================================================================
        # Highlight country with highest mean annual footprint
        # =====================================================================

        highlighted_iso3 = get_highest_mean_country(
            df_continent,
            column,
        )

        if highlighted_iso3 is not None:

            highlighted_group = (
                df_continent[
                    df_continent["iso3"] == highlighted_iso3
                ]
                .sort_values("year")
            )

            highlighted_years = (
                highlighted_group["year"]
                .to_numpy()
            )

            highlighted_values = (
                highlighted_group[column]
                .to_numpy(dtype=float)
            )


            if (
                continent == "Europe"
                and highlighted_iso3 == "UKR"
            ):
                (
                    highlighted_years,
                    highlighted_values,
                ) = trim_leading_invalid_values(
                    highlighted_years,
                    highlighted_values,
                )


            if USE_SMOOTHING:
                original_nan_mask = np.isnan(
                    highlighted_values
                )

                highlighted_values = smooth_series(
                    highlighted_values
                )

                highlighted_values[
                    original_nan_mask
                ] = np.nan


            if not np.all(np.isnan(highlighted_values)):

                ax.plot(
                    highlighted_years,
                    highlighted_values,
                    linewidth=DOM_LINE_WIDTH,
                    alpha=DOM_ALPHA,
                    color=color,
                )


                # Label the final non-missing observation.
                valid_indices = np.where(
                    np.isfinite(highlighted_values)
                )[0]

                if valid_indices.size > 0:

                    last_index = int(valid_indices[-1])

                    ax.text(
                        highlighted_years[last_index] + 0.3,
                        highlighted_values[last_index],
                        highlighted_iso3,
                        fontsize=ISO3_LABEL_SIZE,
                        horizontalalignment="left",
                        verticalalignment="center",
                        color=color,
                    )


        # =====================================================================
        # Axis scaling
        # =====================================================================

        ymax = calculate_ymax(panel_max)

        ax.set_ylim(
            bottom=0,
            top=ymax,
        )

        ax.set_xlim(
            YEAR_MIN,
            YEAR_MAX,
        )


        # =====================================================================
        # Labels and style
        # =====================================================================

        ax.set_ylabel(ylabel)
        ax.set_xlabel("Year")


        # Panel letter.
        ax.text(
            0.02,
            0.99,
            letter,
            transform=ax.transAxes,
            fontsize=PANEL_LABEL_SIZE,
            fontweight="bold",
            verticalalignment="top",
        )


        style_axis(ax)


    # =========================================================================
    # Figure title and layout
    # =========================================================================

    fig.suptitle(
        f"{continent} ({number_of_countries} countries)",
        fontsize=13,
    )

    plt.tight_layout()


    # =========================================================================
    # Save outputs
    # =========================================================================

    continent_file_name = continent.replace(" ", "_")

    pdf_file = OUT_DIR / (
        f"{continent_file_name}_water_footprint.pdf"
    )

    jpg_file = OUT_DIR / (
        f"{continent_file_name}_water_footprint.jpg"
    )

    fig.savefig(
        pdf_file,
        bbox_inches="tight",
    )

    fig.savefig(
        jpg_file,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        f"Saved water-footprint figures for {continent}: "
        f"{number_of_countries} countries."
    )


# =============================================================================
# 9. COMPLETION MESSAGE
# =============================================================================

print("\n" + "=" * 79)
print("ALL WATER-FOOTPRINT FIGURES COMPLETED")
print("=" * 79)

print(f"\nFigures saved to:\n{OUT_DIR}")
