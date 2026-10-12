# -*- coding: utf-8 -*-
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgb
from shapely.geometry import Polygon, MultiPolygon

# =========================================================
# PATHS
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AQUEDUCT_XLSX = os.path.join(DATA_DIR, "Aqueduct40_rankings_download_Y2023M07D05.xlsx")

GCWM_XLSX = os.path.join(DATA_DIR, "GCWM_FAOscaled_sugar_WATER_km3_1981_2021.xlsx")
GCWM_SHEET = "Cane+Beet"
GCWM_YEAR = 2021
GCWM_ISO_COL = "iso3"
GCWM_WF_COL = "blue_km3_total"

FI_XLSX = os.path.join(DATA_DIR, "AllCountryData.xlsx")
FI_SHEET = 0
FI_ISO_COL = "CountryCode"
FI_COL = "Food_Insecurity_2021"

# KEEP THIS NAME EXACTLY
OUT_PNG = os.path.join(OUTPUT_DIR, "bivar_sugarBluewater_map.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "bivar_sugarBluewater_map.pdf")
OUT_TABLE_CSV = os.path.join(OUTPUT_DIR, "bivarmap_2021_bluewater_country_table.csv")
OUT_TABLE_FALLBACK_CSV = os.path.join(OUTPUT_DIR, "bivarmap_2021_bluewater_country_table_new.csv")
OUT_SUMMARY_CSV = os.path.join(OUTPUT_DIR, "bivarmap_2021_bluewater_summary.csv")

# =========================================================
# SETTINGS
# =========================================================
FI_THRESHOLD = 10.0

BORDER_ALL_COLOR = "white"
BORDER_ALL_WIDTH = 0.4

FI_BUBBLE_FILL = "#67A0A3"
FI_BUBBLE_EDGE = "none"
FI_BUBBLE_ALPHA = 0.55

# =========================================================
# HELPERS
# =========================================================
def norm_iso(s):
    return s.astype(str).str.strip().str.upper()


def remove_polygon_holes(geom):
    if geom is None or geom.is_empty:
        return geom
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([Polygon(part.exterior) for part in geom.geoms])
    return geom


def bivar_colors(ny, nx, c_bl, c_br, c_tl, c_tr):
    c_bl = np.array(to_rgb(c_bl))
    c_br = np.array(to_rgb(c_br))
    c_tl = np.array(to_rgb(c_tl))
    c_tr = np.array(to_rgb(c_tr))
    out = np.empty((ny, nx), dtype=object)
    for i in range(ny):
        y = i / (ny - 1)
        for j in range(nx):
            x = j / (nx - 1)
            c = (
                (1 - x) * (1 - y) * c_bl +
                x * (1 - y) * c_br +
                (1 - x) * y * c_tl +
                x * y * c_tr
            )
            out[i, j] = "#{:02x}{:02x}{:02x}".format(
                *np.clip(np.round(c * 255), 0, 255).astype(int)
            )
    return out


def bubble_size(fi_pct):
    return fi_pct * 14


def fmt_km3(val):
    if val < 0.1:
        return f"{val:.2f}"
    if val < 1:
        return f"{val:.1f}"
    return f"{val:.2f}".rstrip("0").rstrip(".")


def stress_category(bws):
    if pd.isna(bws):
        return np.nan
    if bws < 2:
        return "Low"
    if bws < 3:
        return "Moderate"
    if bws < 4:
        return "High"
    return "Extremely high"


def log(msg):
    print(msg, flush=True)


# =========================================================
# COLOR PALETTE (3x3)
# Written explicitly so individual cells can be adjusted directly
# without changing neighboring classes.
# =========================================================
COLORS = np.array([
    ["#e6d8c8", "#e8b2a5", "#e07a6d"],  # Low blue water
    ["#ebbe93", "#cf7a5b", "#b23c34"],  # Medium blue water
    ["#f0a55f", "#b45534", "#681010"],  # High blue water
], dtype=object)

NO_DATA = "#d9d9d9"

# =========================================================
# LOAD WORLD
# =========================================================
WORLD_GEOJSON = os.path.join(DATA_DIR, "world_countries.geojson")
log("Loading world boundaries...")
world = gpd.read_file(WORLD_GEOJSON)
world["iso3"] = norm_iso(world["ISO3166-1-Alpha-3"])
world = world[world["name"] != "Baykonur Cosmodrome"].copy()
world.loc[world["iso3"] == "KAZ", "geometry"] = (
    world.loc[world["iso3"] == "KAZ", "geometry"].apply(remove_polygon_holes)
)

# =========================================================
# LOAD AQUEDUCT
# =========================================================
log("Loading Aqueduct water stress data...")
aqu = pd.read_excel(AQUEDUCT_XLSX, sheet_name="country_baseline")

aqu = aqu[
    (aqu["indicator_name"] == "bws") &
    (aqu["weight"] == "Tot")
][["gid_0", "score"]].copy()

aqu.columns = ["iso3", "bws"]
aqu["iso3"] = norm_iso(aqu["iso3"])
aqu["bws"] = pd.to_numeric(aqu["bws"], errors="coerce")
aqu = aqu[(aqu["bws"] >= 0) & (aqu["bws"] <= 5)]
aqu["bws_class"] = pd.cut(
    aqu["bws"],
    bins=[-np.inf, 2, 3, np.inf],
    labels=[0, 1, 2],
    include_lowest=True
).astype(int)

# =========================================================
# LOAD GCWM WATER FOOTPRINT (2021)
# =========================================================
log("Loading 2021 blue-water footprint data...")
gcwm = pd.read_excel(GCWM_XLSX, sheet_name=GCWM_SHEET)

gcwm["iso3"] = norm_iso(gcwm[GCWM_ISO_COL])
gcwm["year"] = pd.to_numeric(gcwm["year"], errors="coerce")
gcwm["wf_km3"] = pd.to_numeric(gcwm[GCWM_WF_COL], errors="coerce")

gcwm = gcwm[gcwm["year"] == GCWM_YEAR]
gcwm = gcwm.groupby("iso3", as_index=False)["wf_km3"].sum()

# =========================================================
# LOAD FOOD INSECURITY
# =========================================================
log("Loading food insecurity data...")
fi = pd.read_excel(FI_XLSX, sheet_name=FI_SHEET)
fi = fi[[FI_ISO_COL, FI_COL]].copy()
fi.columns = ["iso3", "fi_pct"]
fi["iso3"] = norm_iso(fi["iso3"])
fi["fi_pct"] = pd.to_numeric(fi["fi_pct"], errors="coerce")
fi = fi[(fi["fi_pct"] >= 0) & (fi["fi_pct"] <= 100)]
fi = fi.groupby("iso3", as_index=False)["fi_pct"].mean()

# =========================================================
# MERGE
# =========================================================
log("Merging datasets and classifying countries...")
df = gcwm.merge(aqu[["iso3", "bws_class"]], on="iso3", how="inner")
df = df.merge(fi, on="iso3", how="left")

# Fixed blue-water bins based on the 2021 country distribution:
# countries below 0.1 km3 form a long tail of minimal contributors,
# while countries above 0.5 km3 account for most global sugar-related
# blue water use.
wf_q33 = 0.1
wf_q67 = 0.5

df["wf_class"] = pd.cut(
    df["wf_km3"],
    bins=[-np.inf, wf_q33, wf_q67, np.inf],
    labels=[0, 1, 2],
    include_lowest=True
).astype(int)

df["color"] = COLORS[df["wf_class"].to_numpy(),
                     df["bws_class"].to_numpy()]

# =========================================================
# MAP
# =========================================================
log("Rendering bivariate map...")
gdf = world.merge(df[["iso3", "color", "fi_pct"]],
                  on="iso3", how="left")
gdf["color"] = gdf["color"].fillna(NO_DATA)

fig, ax = plt.subplots(figsize=(20, 10.5))

# Filled countries
gdf.plot(ax=ax,
         color=gdf["color"],
         edgecolor="none",
         zorder=2)

# Thin borders for all countries
gdf.boundary.plot(ax=ax,
                  color=BORDER_ALL_COLOR,
                  linewidth=BORDER_ALL_WIDTH,
                  zorder=3)

# Food insecurity bubbles are drawn independently of GCWM/Aqueduct coverage
fi_gdf = world.merge(fi[["iso3", "fi_pct"]], on="iso3", how="left")
hi = fi_gdf[fi_gdf["fi_pct"] >= FI_THRESHOLD].copy()
if not hi.empty:
    pts = hi.geometry.representative_point()
    hi["x"] = pts.x
    hi["y"] = pts.y
    ax.scatter(
        hi["x"],
        hi["y"],
        s=bubble_size(hi["fi_pct"]),
        facecolor=FI_BUBBLE_FILL,
        edgecolor=FI_BUBBLE_EDGE,
        linewidth=0,
        alpha=FI_BUBBLE_ALPHA,
        zorder=4
    )

ax.set_axis_off()

# Tighten the visible world extent so land occupies more of the figure.
ax.set_xlim(-180, 180)
ax.set_ylim(-58, 88)

# =========================================================
# LEGENDS
# =========================================================
leg_left = 0.12
leg_width = 0.12
leg_height = 0.14
leg_bottom = 0.08
bubble_leg_left = leg_left - 0.065
bubble_leg_bottom = leg_bottom + leg_height + 0.045
bubble_leg_width = leg_width + 0.065
bubble_leg_height = 0.13

leg = fig.add_axes([leg_left, leg_bottom,
                    leg_width, leg_height])
leg.set_axis_off()

for i in range(3):
    for j in range(3):
        leg.add_patch(Rectangle((j, i), 1, 1,
                                facecolor=COLORS[i, j],
                                edgecolor="white",
                                linewidth=0.6))

leg.set_xlim(0, 3)
leg.set_ylim(0, 3)

aqu_labels = ["0-1.9", "2-2.9", "3-5"]

for j, lab in enumerate(aqu_labels):
    leg.text(j + 0.5, -0.12, lab,
             ha="center", va="top", fontsize=13)

wf_labels = [
    f"Low\n<= {fmt_km3(wf_q33)} km3",
    f"Medium\n{fmt_km3(wf_q33)}-{fmt_km3(wf_q67)} km3",
    f"High\n> {fmt_km3(wf_q67)} km3",
]

for i, lab in enumerate(wf_labels):
    leg.text(-0.18, i + 0.5, lab,
             ha="right", va="center", fontsize=13)

fig.text(
    leg_left + leg_width / 2,
    leg_bottom - 0.038,
    "Water Stress",
    ha="center", fontsize=15
)

fig.text(
    leg_left - 0.065,
    leg_bottom + leg_height / 2,
    "Consumptive Blue Water",
    ha="center", va="center", rotation=90, fontsize=15
)

bubble_values = [10, 20, 40]
bub = fig.add_axes([bubble_leg_left, bubble_leg_bottom,
                    bubble_leg_width, bubble_leg_height])
bub.set_axis_off()
bub.set_xlim(0, 1)
bub.set_ylim(0, 1)

bub.text(0.0, 0.98, "Food insecurity\n(>=10%)",
         ha="left", va="top", fontsize=14)

bubble_ys = [0.55, 0.30, 0.06]
for y, v in zip(bubble_ys, bubble_values):
    bub.scatter(
        [0.10], [y],
        s=bubble_size(v),
        facecolor=FI_BUBBLE_FILL,
        edgecolor=FI_BUBBLE_EDGE,
        linewidth=0,
        alpha=FI_BUBBLE_ALPHA,
        clip_on=False
    )
    bub.text(0.26, y, f"{v}%", ha="left", va="center", fontsize=13)


# caption = (
#     r"$\bf{Spatial\ alignment\ of\ sugar-related\ water\ use,\ water\ stress,\ and\ food\ insecurity.}$ "
#     "National evapotranspiration associated with sugar production (GCWM, 2021) is shown together with "
#     "baseline water stress from Aqueduct and food insecurity prevalence. Evapotranspiration was aggregated "
#     "to the country level and grouped into terciles so that each class contains approximately the same number "
#     f"of countries: low (<= {fmt_km3(wf_q33)} km3 yr-1), medium ({fmt_km3(wf_q33)}-{fmt_km3(wf_q67)} km3 yr-1), "
#     f"and high (> {fmt_km3(wf_q67)} km3 yr-1), corresponding to <=33rd, 33rd-67th, and >67th percentiles "
#     "within countries retained in the GCWM-Aqueduct merge. Water stress was aggregated into low (0-1.99), "
#     "medium-high (2.0-2.99), and high (3.0-5.0) categories. Countries with >=10% prevalence of moderate or "
#     "severe food insecurity (FIES) are indicated by semi-transparent circles, with size proportional to prevalence, "
#     "and are displayed independently of whether a country has data for the bivariate map fill."
# )



# fig.text(
#     0.5, 0.015, caption,
#     ha="center", va="bottom", fontsize=8.5, wrap=True
# )

plt.subplots_adjust(left=0.01, right=0.99,
                    top=0.98, bottom=0.06)

log("Saving figure files...")
plt.savefig(OUT_PNG, dpi=600, bbox_inches="tight")
plt.savefig(OUT_PDF, bbox_inches="tight")
plt.close()

log(f"Saved: {OUT_PNG}")
log(
    "Blue-water bins (km3): "
    f"Low <= {fmt_km3(wf_q33)}, "
    f"Medium {fmt_km3(wf_q33)}-{fmt_km3(wf_q67)}, "
    f"High > {fmt_km3(wf_q67)}"
)


# =========================================================
# ==================== QUANTIFICATION =====================
# =========================================================

log("\n================ BLUE-WATER SUMMARY =================")

df_full = gcwm.merge(aqu[["iso3", "bws"]], on="iso3", how="inner")
df_full = df_full.merge(fi, on="iso3", how="left")
df_full = df_full.merge(world[["iso3", "name"]].drop_duplicates(), on="iso3", how="left")
df_full["country"] = df_full["name"].fillna(df_full["iso3"])
df_full["global_share_pct"] = df_full["wf_km3"] / df_full["wf_km3"].sum() * 100
df_full["water_stress_category"] = df_full["bws"].apply(stress_category)
df_full["food_insecure"] = np.where(df_full["fi_pct"] >= FI_THRESHOLD, "Y", "N")
df_full["overlap_group"] = np.where(
    (df_full["bws"] >= 3.0) & (df_full["fi_pct"] >= FI_THRESHOLD),
    "Y",
    "N",
)

total_wf = float(df_full["wf_km3"].sum())

bws_ge3_mask = df_full["bws"] >= 3.0
fies_ge10_mask = df_full["fi_pct"] >= FI_THRESHOLD
overlap_mask = bws_ge3_mask & fies_ge10_mask

bws_ge3_share = float(df_full.loc[bws_ge3_mask, "wf_km3"].sum()) / total_wf * 100 if total_wf else np.nan
fies_ge10_share = float(df_full.loc[fies_ge10_mask, "wf_km3"].sum()) / total_wf * 100 if total_wf else np.nan
overlap_share = float(df_full.loc[overlap_mask, "wf_km3"].sum()) / total_wf * 100 if total_wf else np.nan
overlap_total_wf = float(df_full.loc[overlap_mask, "wf_km3"].sum())

log(f"Total global sugar-related blue-water use (km3): {total_wf:.3f}")
log(f"Share in countries with BWS >= 3: {bws_ge3_share:.1f}%")
log(f"Share in countries with FIES >= 10%: {fies_ge10_share:.1f}%")
log(f"Share in countries with BOTH BWS >= 3 and FIES >= 10%: {overlap_share:.1f}%")

overlap_cols = ["country", "iso3", "wf_km3", "global_share_pct", "bws", "fi_pct"]
overlap_df = (
    df_full.loc[overlap_mask, overlap_cols]
    .sort_values("wf_km3", ascending=False)
    .copy()
)
overlap_df["wf_km3"] = overlap_df["wf_km3"].round(3)
overlap_df["global_share_pct"] = overlap_df["global_share_pct"].round(2)
overlap_df["bws"] = overlap_df["bws"].round(2)
overlap_df["fi_pct"] = overlap_df["fi_pct"].round(1)

log("\nCountries with BOTH BWS >= 3 and FIES >= 10%:")
if overlap_df.empty:
    log("None")
else:
    log(overlap_df.to_string(index=False))

for iso, label in [("IND", "India"), ("PAK", "Pakistan")]:
    subset = df_full.loc[df_full["iso3"] == iso]
    if subset.empty:
        log(f"\n{label}: not found in merged dataset")
        continue
    row = subset.iloc[0]
    log(f"\n{label}:")
    log(f" Blue-water use (km3): {row['wf_km3']:.3f}")
    log(f" Global share (%): {row['global_share_pct']:.2f}")

ind_pak = df_full.loc[df_full["iso3"].isin(["IND", "PAK"])].copy()
ind_pak_total = float(ind_pak["wf_km3"].sum())
ind_pak_global_share = ind_pak_total / total_wf * 100 if total_wf else np.nan
ind_pak_overlap_share = ind_pak_total / overlap_total_wf * 100 if overlap_total_wf else np.nan

log("\nIndia + Pakistan combined:")
log(f" Global share (%): {ind_pak_global_share:.2f}")
log(f" Share of overlap-group blue-water use (%): {ind_pak_overlap_share:.2f}")

summary_rows = [
    {"Metric": "Total global sugar-related blue-water use (km3)", "Value": round(total_wf, 3)},
    {"Metric": "Share of global blue-water use in countries with BWS >= 3 (%)", "Value": round(bws_ge3_share, 2)},
    {"Metric": "Share of global blue-water use in countries with FIES >= 10% (%)", "Value": round(fies_ge10_share, 2)},
    {"Metric": "Share of global blue-water use in countries with BOTH BWS >= 3 and FIES >= 10% (%)", "Value": round(overlap_share, 2)},
]

for iso, label in [("IND", "India"), ("PAK", "Pakistan")]:
    subset = df_full.loc[df_full["iso3"] == iso]
    if subset.empty:
        continue
    row = subset.iloc[0]
    summary_rows.extend([
        {"Metric": f"{label} blue-water use (km3)", "Value": round(float(row['wf_km3']), 3)},
        {"Metric": f"{label} global share (%)", "Value": round(float(row['global_share_pct']), 2)},
    ])

summary_rows.extend([
    {"Metric": "India + Pakistan combined global share (%)", "Value": round(ind_pak_global_share, 2)},
    {"Metric": "India + Pakistan share of overlap-group blue-water use (%)", "Value": round(ind_pak_overlap_share, 2)},
])

pd.DataFrame(summary_rows).to_csv(OUT_SUMMARY_CSV, index=False)
log(f"\nSummary calculations saved: {OUT_SUMMARY_CSV}")

table_df = df_full[[
    "country", "wf_km3", "global_share_pct", "bws", "fi_pct",
    "water_stress_category", "food_insecure", "overlap_group"
]].copy()
table_df.columns = [
    "Country",
    "Blue-water use (km3)",
    "Global share (%)",
    "BWS",
    "FIES",
    "Water-stress category",
    "Food-insecure (Y/N)",
    "Overlap group (Y/N)",
]
table_df = table_df.sort_values("Blue-water use (km3)", ascending=False)
table_df["Blue-water use (km3)"] = table_df["Blue-water use (km3)"].round(3)
table_df["Global share (%)"] = table_df["Global share (%)"].round(2)
table_df["BWS"] = table_df["BWS"].round(2)
table_df["FIES"] = table_df["FIES"].round(1)
saved_table = OUT_TABLE_CSV
try:
    table_df.to_csv(OUT_TABLE_CSV, index=False)
except PermissionError:
    saved_table = OUT_TABLE_FALLBACK_CSV
    table_df.to_csv(saved_table, index=False)
    log(f"\nPrimary CSV was locked, so the table was saved to: {saved_table}")
else:
    log(f"\nFull country table saved: {saved_table}")
