# -*- coding: utf-8 -*-

"""
===============================================================================
SUGAR WATER SPAGHETTI PLOTS — FINAL VERSION (WITH DOMINANT HIGHLIGHT)
===============================================================================

Key features:
- One figure per continent
- 3 panels (A, B, C)
- Thin country lines
- Slightly thicker dominant country line + ISO3 label
- Fixed y-axis per continent (with South America special case)
- Clean publication style
- PDF + JPG (300 dpi)
===============================================================================
"""

# =============================================================================
# 1. IMPORT LIBRARIES
# =============================================================================

import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt


# =============================================================================
# 2. FILE PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
IN_FILE = BASE_DIR / "data" / "GCWM_FAOscaled_sugar_ALL_countryyear_AGG_WATER_km3_SCALEDONLY_1981_2021.xlsx"

OUT_DIR = BASE_DIR / "outputs"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 3. SETTINGS
# =============================================================================

YEAR_MIN, YEAR_MAX = 1981, 2021

BLUE_COL  = "blue_km3_total"
GREEN_COL = "green_km3_total"
ET_COL    = "et_km3_total"

CONTINENTS = [
    "Asia",
    "South America",
    "North America",
    "Africa",
    "Europe",
    "Central America",
    "Oceania",
]

# Colors by variable
COLOR_BLUE  = "#3f8fad"
COLOR_GREEN = "#4bb277"
COLOR_TOTAL = "#924848"

# Line styling
LINE_WIDTH = 1.0
LINE_ALPHA = 0.35

# Dominant line styling (slightly thicker only)
DOM_LINE_WIDTH = 1.8
DOM_ALPHA = 0.9

# Labels
PANEL_LABEL_SIZE = 14
ISO3_LABEL_SIZE = 10

FIGSIZE = (13, 4)

# Smoothing (OFF by default)
USE_SMOOTHING = False
ROLLING_WINDOW = 3


# =============================================================================
# 4. FIXED Y LIMITS
# =============================================================================

FIXED_YMAX = {
    "Africa": {"A": 7, "B": 7, "C": 7},
    "Asia": {"A": 90, "B": 90, "C": 90},
    "Central America": {"A": 4, "B": 4, "C": 4},
    "Europe": {"A": 7, "B": 7, "C": 7},
    "North America": {"A": 18, "B": 18, "C": 18},
    "Oceania": {"A": 5, "B": 5, "C": 5},
    "South America": {"A": 12, "B": 120, "C": 120},
}


# =============================================================================
# 5. LOAD DATA
# =============================================================================

df = pd.read_excel(IN_FILE)

# Clean string columns (remove spaces, standardize)
for col in ["iso3", "country", "Continent"]:
    df[col] = df[col].astype(str).str.strip()

# Convert year to numeric and filter study period
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df = df[df["year"].between(YEAR_MIN, YEAR_MAX)].copy()

# Convert water variables to numeric (keep NaN for missing values)
for c in [BLUE_COL, GREEN_COL, ET_COL]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# -------------------------------------------------------------------------
# Handle countries with missing historical data (e.g., Ukraine)
# -------------------------------------------------------------------------
# Ukraine (UKR) only has reliable national data after ~1991 (post-Soviet period).
# Earlier values may appear as zeros or missing, which can create artificial jumps.
# To avoid misleading visual artifacts, we remove pre-1991 Ukraine data,
# allowing the time series to start at the first valid observation.
df = df[~((df["iso3"] == "UKR") & (df["year"] < 1991))]


# =============================================================================
# 6. HELPERS
# =============================================================================

def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=9)

def nice_ymax(x):
    return np.ceil(x * 1.1)

def smooth_series(y):
    return pd.Series(y).rolling(ROLLING_WINDOW, center=True, min_periods=1).mean()

def get_dominant(df_c, col):
    tmp = df_c.groupby("iso3")[col].sum().sort_values(ascending=False)
    return tmp.index[0] if not tmp.empty else None

def set_integer_ticks(ax, ymax):
    if ymax <= 10:
        ax.set_yticks(np.arange(0, ymax + 1, 1))


# =============================================================================
# 7. PANELS
# =============================================================================

PANELS = [
    ("A", BLUE_COL,  COLOR_BLUE,  "Consumptive Blue water use (km³/year)"),
    ("B", GREEN_COL, COLOR_GREEN, "Consumptive Green water use (km³/year)"),
    ("C", ET_COL,    COLOR_TOTAL, "Total consumptive water use (km³/year)"),
]


# =============================================================================
# 8. MAIN LOOP
# =============================================================================

for cont in CONTINENTS:

    df_c = df[df["Continent"] == cont].copy()
    if df_c.empty:
        continue

    n_countries = df_c["iso3"].nunique()

    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE)

    for ax, (letter, col, color, ylabel) in zip(axes, PANELS):

        panel_max = 0

        # ---- plot all countries ----
        for iso3, g in df_c.groupby("iso3"):
            g = g.sort_values("year")
            x = g["year"].values
            y = g[col].values.astype(float)

            # For Europe, trim Ukraine (`UKR`) so the line starts
            # at the first year with real (non-zero, non-NaN) data.
            first_valid_idx = None
            if cont == "Europe" and iso3 == "UKR":
                valid = (~np.isnan(y)) & (y != 0)
                if valid.any():
                    first_valid_idx = int(np.where(valid)[0][0])
                    y[:first_valid_idx] = np.nan

            if USE_SMOOTHING:
                y = smooth_series(y)
                # Re-apply leading mask after smoothing so smoothing
                # doesn't reintroduce values before the first data point.
                if first_valid_idx is not None:
                    y = np.asarray(y)
                    y[:first_valid_idx] = np.nan

            # skip if nothing to plot
            if np.all(np.isnan(y)):
                continue

            panel_max = max(panel_max, np.nanmax(y))

            ax.plot(x, y, lw=LINE_WIDTH, alpha=LINE_ALPHA, color=color)

        # ---- dominant country ----
        dom = get_dominant(df_c, col)
        if dom:
            g_dom = df_c[df_c["iso3"] == dom].sort_values("year")
            x = g_dom["year"].values
            y = g_dom[col].values.astype(float)

            # Apply same leading-data trimming for the dominant line
            if cont == "Europe" and dom == "UKR":
                valid_dom = (~np.isnan(y)) & (y != 0)
                if valid_dom.any():
                    first_dom = int(np.where(valid_dom)[0][0])
                    y[:first_dom] = np.nan

            if USE_SMOOTHING:
                y = smooth_series(y)
                if cont == "Europe" and dom == "UKR" and valid_dom.any():
                    y = np.asarray(y)
                    y[:first_dom] = np.nan

            if not np.all(np.isnan(y)):
                ax.plot(x, y, lw=DOM_LINE_WIDTH, alpha=DOM_ALPHA, color=color)

                # label at last non-NaN point
                if np.any(~np.isnan(y)):
                    last_idx = int(np.where(~np.isnan(y))[0][-1])
                    ax.text(x[last_idx] + 0.3, y[last_idx], dom,
                            fontsize=ISO3_LABEL_SIZE,
                            ha="left", va="center", color=color)

        # ---- Y scaling ----
        if cont in FIXED_YMAX:
            val = FIXED_YMAX[cont][letter]
            ymax = nice_ymax(panel_max) if val is None else val
        else:
            ymax = nice_ymax(panel_max)

        ax.set_ylim(0, ymax)

        if cont in ["Africa", "Europe", "Central America", "Oceania"]:
            set_integer_ticks(ax, ymax)

        # ---- labels ----
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Year")
        ax.set_xlim(YEAR_MIN, YEAR_MAX)

        # panel letter
        ax.text(0.02, 0.99, letter,
                transform=ax.transAxes,
                fontsize=PANEL_LABEL_SIZE,
                fontweight="bold",
                va="top")

        style_axis(ax)

    fig.suptitle(f"{cont} ({n_countries} countries)", fontsize=13)

    plt.tight_layout()

    name = cont.replace(" ", "_")

    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.jpg", dpi=300, bbox_inches="tight")

    plt.close()

print("Done.")
