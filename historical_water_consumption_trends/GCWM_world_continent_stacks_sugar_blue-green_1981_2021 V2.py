# -*- coding: utf-8 -*-
"""
===============================================================================
WORLD STACKED WATER BURDENS BY CONTINENT — CONTINENT PAIRS (BLUE + GREEN)
===============================================================================

WHAT THIS SCRIPT DOES
--------------------
This script creates a stacked-area figure for global sugar-production water use
(1981–2021), using a continent-pair structure.

For EACH continent, the stack is built as:
    1. Blue water layer
    2. Green water layer directly above it

Then the next continent starts:
    3. Next continent blue
    4. Next continent green
    ...

So the final order is:
    Asia blue → Asia green → South America blue → South America green → ...

WHY THIS VERSION IS BETTER
--------------------------
This design makes each continent visible as one "unit":
- blue contribution first
- green contribution on top of it
- then a white boundary before the next continent

This is cleaner and easier to interpret than:
- all blue layers first
- then all green layers

DESIGN CHOICES
--------------
- Only 2 fill colors are used:
    Blue water  = same blue as spaghetti chart
    Green water = same green as spaghetti chart
- White separator lines appear ONLY between continents
- No black total boundary line is drawn
- Continent names appear on the right in black

OUTPUT
------
The script exports:
- PNG (300 dpi)
- PDF (vector)

INPUT FILE
----------
GCWM_FAOscaled_sugar_ALL_countryyear_AGG_WATER_km3_SCALEDONLY_1981_2021.xlsx
===============================================================================
"""

# =============================================================================
# 1. IMPORT LIBRARIES
# =============================================================================

import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


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
YEARS_FULL = np.arange(YEAR_MIN, YEAR_MAX + 1)

# Column names in the Excel file
BLUE_COL  = "blue_km3_total"
GREEN_COL = "green_km3_total"
ET_COL    = "et_km3_total"

# Standardize continent naming if needed
CONTINENT_REMAP = {"Eurasia": "Europe"}

# Desired continent order in the stack
CONTINENT_ORDER = [
    "Asia",
    "South America",
    "North America",
    "Africa",
    "Europe",
    "Central America",
    "Oceania",
]

# Same colors as in the spaghetti chart
COLOR_BLUE = "#3f8fad"
COLOR_GREEN = "#4bb277"

# Visual settings
BLUE_ALPHA = 0.80
GREEN_ALPHA = 0.75
BOUNDARY_LW = 1.2        # white separator lines between continent pairs only
LABEL_SIZE = 11

FIG_TITLE = ""
Y_LABEL = "Consumptive water use (km³/year)"

# Label positioning (axis coordinates; >1 moves further right)
LABEL_BASE_X = 1.03   # base x-position for continent labels (axis coords)
LABEL_STAGGER = 0.02  # horizontal offset per nearby neighbor (axis coords)


# =============================================================================
# 4. LOAD AND PREPARE DATA
# =============================================================================

# Read the Excel file
df = pd.read_excel(IN_FILE)

# Clean continent names and apply remap
df["Continent"] = (
    df["Continent"]
    .astype(str)
    .str.strip()
    .replace(CONTINENT_REMAP)
)

# Convert year to numeric and keep only study period
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df = df[df["year"].between(YEAR_MIN, YEAR_MAX)].copy()

# Convert water columns to numeric
for c in [BLUE_COL, GREEN_COL, ET_COL]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

# Aggregate yearly totals by continent
df_cont = (
    df.groupby(["Continent", "year"], as_index=False)
      .agg(
          blue_km3=(BLUE_COL, "sum"),
          green_km3=(GREEN_COL, "sum"),
          et_km3=(ET_COL, "sum"),
      )
)

# Keep only continents actually present in the data
present = sorted(df_cont["Continent"].unique().tolist())
continents = [c for c in CONTINENT_ORDER if c in present] + [c for c in present if c not in CONTINENT_ORDER]


# =============================================================================
# 5. BUILD WIDE TABLES
# =============================================================================

def build_wide(value_col: str) -> pd.DataFrame:
    """
    Convert long continent-year data into a wide table:
    - rows    = years
    - columns = continents
    - values  = selected metric
    """
    wide = (
        df_cont.pivot_table(index="year", columns="Continent", values=value_col, aggfunc="sum")
        .reindex(YEARS_FULL)
        .fillna(0.0)
        .reindex(columns=continents, fill_value=0.0)
    )
    return wide

wide_blue = build_wide("blue_km3")
wide_green = build_wide("green_km3")


# =============================================================================
# 6. CREATE FIGURE
# =============================================================================

fig, ax = plt.subplots(figsize=(9.2, 6.6))


# =============================================================================
# 7. BUILD STACK IN CONTINENT PAIRS
# =============================================================================

"""
For each continent:
    lower boundary starts at current stack height
    add BLUE layer
    add GREEN layer directly above it
    draw ONE white separator at the top of the green layer only

So each continent appears as one visual pair:
    blue + green
without an internal white divider.
"""

# Start from zero baseline
running_base = np.zeros(len(YEARS_FULL))

# Store final-year midpoint of each continent pair for right-side labels
continent_pair_midpoints = []

for cont in continents:

    # -------------------------------------------------------------------------
    # 7a. BLUE layer for this continent
    # -------------------------------------------------------------------------
    lower_blue = running_base.copy()
    upper_blue = running_base + wide_blue[cont].values

    ax.fill_between(
        YEARS_FULL,
        lower_blue,
        upper_blue,
        color=COLOR_BLUE,
        alpha=BLUE_ALPHA,
        linewidth=0
    )

    # Update running base after blue layer
    running_base = upper_blue

    # -------------------------------------------------------------------------
    # 7b. GREEN layer for this continent
    # -------------------------------------------------------------------------
    lower_green = running_base.copy()
    upper_green = running_base + wide_green[cont].values

    ax.fill_between(
        YEARS_FULL,
        lower_green,
        upper_green,
        color=COLOR_GREEN,
        alpha=GREEN_ALPHA,
        linewidth=0
    )

    # Draw black separator ONLY at the top of the continent pair and extend it
    # external extension reduced by 50%
    x_sep = np.concatenate([YEARS_FULL, [YEAR_MAX + 1.0]])
    y_sep = np.concatenate([upper_green, [upper_green[-1]]])
    ax.plot(
        x_sep,
        y_sep,
        color="black",
        lw=BOUNDARY_LW,
        clip_on=False
    )

    # -------------------------------------------------------------------------
    # 7c. Save label position for this continent pair
    # -------------------------------------------------------------------------
    final_lower = lower_blue[-1]
    final_upper = upper_green[-1]
    final_mid = (final_lower + final_upper) / 2
    continent_pair_midpoints.append(final_mid)

    # Update running base for next continent
    running_base = upper_green


# =============================================================================
# 8. STYLE AXES
# =============================================================================

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_linewidth(0.8)
ax.spines["bottom"].set_linewidth(0.8)
ax.tick_params(width=0.8, labelsize=10)

ax.set_xlim(YEAR_MIN, YEAR_MAX)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel(Y_LABEL, fontsize=11)
ax.set_title(FIG_TITLE, fontsize=13)


# =============================================================================
# 9. SIMPLE LEGEND
# =============================================================================

legend_handles = [
    Patch(facecolor=COLOR_BLUE, edgecolor="none", alpha=BLUE_ALPHA, label="Blue water"),
    Patch(facecolor=COLOR_GREEN, edgecolor="none", alpha=GREEN_ALPHA, label="Green water"),
]

ax.legend(
    handles=legend_handles,
    loc="upper left",
    frameon=False,
    fontsize=10
)


# =============================================================================
# 10. RIGHT-SIDE CONTINENT LABELS
# =============================================================================

"""
Labels are placed on the right based on the final-year midpoint of each
continent pair (blue + green together).

This is cleaner than labeling blue and green separately.
"""

y_mids = continent_pair_midpoints.copy()

# Simple collision avoidance
min_gap = 9.0
y_adj = y_mids.copy()

for i in range(1, len(y_adj)):
    if y_adj[i] - y_adj[i - 1] < min_gap:
        y_adj[i] = y_adj[i - 1] + min_gap

# Shift down if labels overflow above top
ymax = ax.get_ylim()[1]
overflow = y_adj[-1] - (ymax * 0.97)
if overflow > 0:
    y_adj = [y - overflow for y in y_adj]

# Positions in axis coordinates: use configurable base and stagger settings
base_x = LABEL_BASE_X

# If labels are vertically close, stagger them horizontally to avoid overlap
# without moving them up/down.
for idx, (cont, y0, y1) in enumerate(zip(continents, y_mids, y_adj)):
    # count previous labels within the vertical min_gap to determine horizontal offset
    neighbors = sum(1 for j in range(idx) if abs(y1 - y_adj[j]) < min_gap)
    x_pos = base_x + LABEL_STAGGER * neighbors

    ax.text(
        x_pos,
        y1,
        cont,
        transform=ax.get_yaxis_transform(),
        ha="left",
        va="center",
        fontsize=LABEL_SIZE,
        color="black",
        clip_on=False
    )


# =============================================================================
# 11. FINAL LAYOUT
# =============================================================================
ax.set_ylim(bottom=0)

fig.tight_layout()


# =============================================================================
# 12. EXPORT
# =============================================================================

out_base = OUT_DIR / f"Sugar_combined_WORLD_Continent_BlueGreenStack_{YEAR_MIN}_{YEAR_MAX}"

fig.savefig(out_base.with_suffix(".png"), dpi=300, bbox_inches="tight")
fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")

plt.close(fig)

print("Saved:")
print(" -", out_base.with_suffix(".png"))
print(" -", out_base.with_suffix(".pdf"))
print("\nDone.")
