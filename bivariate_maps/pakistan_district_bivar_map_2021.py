import os
import re
import unicodedata

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
WATER_XLSX = os.path.join(DATA_DIR, "Pakistan_sugarcane_blue_green_water_by_district_2021.xlsm")
BOUNDARY_SHAPE = os.path.join(
    DATA_DIR,
    "Pakistan_District_analysis_boundaries_123_EPSG4326",
    "Pakistan_District_analysis_boundaries_123_EPSG4326.shp",
)
AQUEDUCT_XLSX = os.path.join(DATA_DIR, "Aqueduct40_rankings_download_Y2023M07D05.xlsx")

OUT_PNG = os.path.join(OUTPUT_DIR, "pakistan_district_bivar_water_map_2021.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "pakistan_district_bivar_water_map_2021.pdf")
OUT_CSV = os.path.join(OUTPUT_DIR, "pakistan_district_bivar_map_2021.csv")

COLORS = np.array([
    ["#e6d8c8", "#e8b2a5", "#e07a6d"],
    ["#ebbe93", "#cf7a5b", "#b23c34"],
    ["#f0a55f", "#b45534", "#681010"],
], dtype=object)

PROVINCE_ALIASES = {
    "baluchistan": "balochistan",
    "balochistan": "balochistan",
    "sind": "sindh",
    "sindh": "sindh",
    "n w f p": "khyber pakhtunkhwa",
    "nwfp": "khyber pakhtunkhwa",
    "kpk": "khyber pakhtunkhwa",
    "khyber pakhtunkhwa": "khyber pakhtunkhwa",
    "f a t a": "fata",
    "fata": "fata",
    "northern areas": "gilgit baltistan",
    "gilgit baltistan": "gilgit baltistan",
    "f c t": "islamabad",
    "islamabad": "islamabad",
    "azad kashmir": "azad kashmir",
    "punjab": "punjab",
}


def normalize_name(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_province(value):
    key = normalize_name(value)
    return PROVINCE_ALIASES.get(key, key)


def compute_quantile_class(series):
    values = pd.to_numeric(series, errors="coerce")
    q33, q67 = np.nanpercentile(values.dropna(), [33, 67])
    return pd.cut(
        values,
        bins=[-np.inf, q33, q67, np.inf],
        labels=[0, 1, 2],
        include_lowest=True,
        duplicates="drop",
    ).astype(float)


def compute_blue_water_class(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[-np.inf, 0.1, 0.5, np.inf],
        labels=[0, 1, 2],
        include_lowest=True,
    ).astype(float)


def main():
    print("Loading Pakistan district shapefile...")
    gdf = gpd.read_file(BOUNDARY_SHAPE).to_crs("EPSG:4326")
    gdf = gdf[["Province", "District", "geometry"]].copy()
    gdf["province_join"] = gdf["Province"].map(canonical_province)
    gdf["district_join"] = gdf["District"].map(normalize_name)

    print("Loading Pakistan district water-use workbook...")
    water = pd.read_excel(WATER_XLSX, sheet_name="Pakistan_district_water")
    required = {"Province", "District", "Blue_water_km3"}
    missing = required.difference(water.columns)
    if missing:
        raise ValueError(f"Pakistan workbook is missing columns: {sorted(missing)}")
    water = water[["Province", "District", "Blue_water_km3"]].copy()
    water.columns = ["province_name", "district_name", "water_use_km3"]
    water["province_join"] = water["province_name"].map(canonical_province)
    water["district_join"] = water["district_name"].map(normalize_name)
    water["water_use_km3"] = pd.to_numeric(water["water_use_km3"], errors="coerce")

    print("Loading Aqueduct province_baseline BWS data...")
    aqu = pd.read_excel(AQUEDUCT_XLSX, sheet_name="province_baseline")
    aqu = aqu[
        (aqu["name_0"].astype(str).str.strip().str.lower() == "pakistan")
        & (aqu["indicator_name"].astype(str).str.strip().str.lower() == "bws")
        & (aqu["weight"].astype(str).str.strip().str.lower() == "tot")
    ][["name_1", "score"]].copy()
    aqu.columns = ["province_name", "bws_score"]
    aqu["province_join"] = aqu["province_name"].map(canonical_province)
    aqu["bws_score"] = pd.to_numeric(aqu["bws_score"], errors="coerce")
    aqu = aqu[["province_join", "bws_score"]].dropna().drop_duplicates()

    district_merged = gdf.merge(
        water[["province_join", "district_join", "water_use_km3"]],
        on=["province_join", "district_join"],
        how="left",
    )
    missing_rows = district_merged[district_merged["water_use_km3"].isna()]
    if not missing_rows.empty:
        print(f"Districts with missing water-use values: {len(missing_rows)}")
        print(missing_rows[["Province", "District"]].to_string(index=False))

    province_water = (
        district_merged.dropna(subset=["water_use_km3"])
        .groupby("province_join", as_index=False)["water_use_km3"]
        .sum()
    )
    province_shapes = district_merged[["Province", "province_join", "geometry"]].dissolve(
        by=["Province", "province_join"],
        as_index=False,
    )
    merged = province_shapes.merge(province_water, on="province_join", how="left")
    merged = merged.merge(aqu, on="province_join", how="left")

    missing_provinces = merged[merged["water_use_km3"].isna() | merged["bws_score"].isna()]
    if not missing_provinces.empty:
        print("Provinces with missing source values:")
        print(missing_provinces[["Province"]].to_string(index=False))

    merged = merged.dropna(subset=["water_use_km3", "bws_score"]).copy()
    merged["water_use_class"] = compute_blue_water_class(merged["water_use_km3"])
    merged["water_stress_class"] = pd.cut(
        merged["bws_score"],
        bins=[-np.inf, 2, 3, np.inf],
        labels=[0, 1, 2],
        include_lowest=True,
    ).astype(float)
    merged["bivar_color"] = [
        COLORS[int(row["water_use_class"]), int(row["water_stress_class"])]
        for _, row in merged.iterrows()
    ]

    fig, ax = plt.subplots(figsize=(12, 9))
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.98)
    merged.plot(ax=ax, color=merged["bivar_color"], edgecolor="white", linewidth=0.5)

    label_positions = {
        "punjab": (79.0, 31.7),
        "sindh": (77.0, 25.3),
    }
    label_text = {
        "punjab": "Punjab\n57.0 Mt\n(70.4% of\nproduction)",
        "sindh": "Sindh\n18.3 Mt\n(22.6% of\nproduction)",
    }
    for province, (label_x, label_y) in label_positions.items():
        province_rows = merged[merged["Province"].map(normalize_name).eq(province)]
        if province_rows.empty:
            continue
        point = province_rows.geometry.iloc[0].representative_point()
        ax.annotate(
            label_text[province],
            xy=(point.x, point.y),
            xytext=(label_x, label_y),
            ha="left",
            va="center",
            fontsize=28,
            color="black",
            arrowprops={
                "arrowstyle": "-",
                "color": "black",
                "linewidth": 0.8,
                "shrinkA": 0,
                "shrinkB": 0,
            },
            zorder=4,
            annotation_clip=False,
        )

    ax.set_axis_off()

    x_min, y_min, x_max, y_max = merged.total_bounds
    ax.set_xlim(x_min - (x_max - x_min) * 0.08, x_max + (x_max - x_min) * 0.08 + 7.0)
    ax.set_ylim(y_min - (y_max - y_min) * 0.08, y_max + (y_max - y_min) * 0.08)

    plt.savefig(OUT_PNG, dpi=300)
    plt.savefig(OUT_PDF)
    print(f"Saved map to: {OUT_PNG}")
    print(f"Saved map to: {OUT_PDF}")

    output = merged[["Province", "water_use_km3", "bws_score", "water_use_class", "water_stress_class"]].copy()
    output.columns = ["province", "water_use_km3", "water_stress_bws", "water_use_class", "water_stress_class"]
    output.to_csv(OUT_CSV, index=False)
    print(f"Saved district table to: {OUT_CSV}")


if __name__ == "__main__":
    main()
