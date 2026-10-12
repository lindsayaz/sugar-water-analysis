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
WATER_XLSX = os.path.join(DATA_DIR, "India_sugarcane_blue_green_water_by_state_2021.xlsx")
WATER_XLSX_FALLBACK = os.path.join(DATA_DIR, "_india_water_copy.xlsx")
BOUNDARY_SHAPE = os.path.join(
    DATA_DIR,
    "India_State_UT_boundaries_36_EPSG4326",
    "India_State_UT_boundaries_36.shp",
)
AQUEDUCT_XLSX = os.path.join(DATA_DIR, "Aqueduct40_rankings_download_Y2023M07D05.xlsx")

OUT_PNG = os.path.join(OUTPUT_DIR, "india_state_bivar_water_map_2021.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "india_state_bivar_water_map_2021.pdf")
OUT_CSV = os.path.join(OUTPUT_DIR, "india_state_bivar_map_2021.csv")

COLORS = np.array([
    ["#e6d8c8", "#e8b2a5", "#e07a6d"],
    ["#ebbe93", "#cf7a5b", "#b23c34"],
    ["#f0a55f", "#b45534", "#681010"],
], dtype=object)

STATE_NAME_ALIASES = {
    "andaman nicobar": "andaman and nicobar",
    "andaman and nicobar": "andaman and nicobar",
    "andaman and nicobar islands": "andaman and nicobar",
    "andaman nicobar islands": "andaman and nicobar",
    "lakshadweep islands": "lakshadweep",
    "lakshadweep": "lakshadweep",
    "jammu kashmir": "jammu and kashmir",
    "jammu and kashmir": "jammu and kashmir",
    "dadra and nagar haveli and daman and diu": "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
    "daman and diu": "dadra and nagar haveli and daman and diu",
    "daman diu": "dadra and nagar haveli and daman and diu",
    "delhi": "delhi",
    "nct of delhi": "delhi",
    "national capital territory of delhi": "delhi",
    "chandigarh": "chandigarh",
    "ladakh": "ladakh",
    "puducherry": "puducherry",
}


def normalize_name(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_state_name(value):
    key = normalize_name(value)
    return STATE_NAME_ALIASES.get(key, key)


def find_column(columns, aliases):
    norm_map = {normalize_name(col): col for col in columns}
    for alias in aliases:
        alias_norm = normalize_name(alias)
        if alias_norm in norm_map:
            return norm_map[alias_norm]

    for col in columns:
        norm = normalize_name(col)
        for alias in aliases:
            if normalize_name(alias) in norm:
                return col
    return None


def compute_class(series):
    values = pd.to_numeric(series, errors="coerce")
    if values.dropna().empty:
        return pd.Series(np.nan, index=series.index)

    q33 = np.nanpercentile(values.dropna(), 33)
    q67 = np.nanpercentile(values.dropna(), 67)

    bins = [-np.inf, q33, q67, np.inf]
    labels = pd.cut(values, bins=bins, labels=[0, 1, 2], include_lowest=True, duplicates="drop")
    return labels.astype(float)


def compute_blue_water_class(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[-np.inf, 0.1, 0.5, np.inf],
        labels=[0, 1, 2],
        include_lowest=True,
    ).astype(float)


def compute_bws_class(series):
    values = pd.to_numeric(series, errors="coerce")
    return pd.cut(
        values,
        bins=[-np.inf, 2, 3, np.inf],
        labels=[0, 1, 2],
        include_lowest=True,
    ).astype(float)


def main():
    print("Loading India state shapefile...")
    gdf = gpd.read_file(BOUNDARY_SHAPE)
    gdf = gdf.to_crs("EPSG:4326")

    shape_state_col = find_column(gdf.columns, [
        "State_UT",
        "state_ut",
        "state",
        "state_name",
        "name",
        "STATE",
    ])
    if shape_state_col is None:
        raise ValueError(f"Could not find a state column in the shapefile. Available columns: {list(gdf.columns)}")

    gdf = gdf[[shape_state_col, "geometry"]].copy()
    gdf["state_join"] = gdf[shape_state_col].map(canonical_state_name)

    print("Loading India water-use workbook...")
    try:
        water_df = pd.read_excel(WATER_XLSX, sheet_name="India_state_water")
    except PermissionError:
        water_df = pd.read_excel(WATER_XLSX_FALLBACK, sheet_name="India_state_water")
    water_state_col = find_column(water_df.columns, [
        "State_UT",
        "state_ut",
        "state",
        "state_name",
        "State",
    ])
    if water_state_col is None:
        raise ValueError(f"Could not find a state column in the India workbook. Available columns: {list(water_df.columns)}")

    water_use_col = "Blue_water_km3"
    if water_use_col not in water_df.columns:
        raise ValueError(f"Expected '{water_use_col}' in the India workbook. Available columns: {list(water_df.columns)}")

    water_df = water_df[[water_state_col, water_use_col]].copy()
    water_df.columns = ["state_name", "water_use_km3"]
    water_df["state_join"] = water_df["state_name"].map(canonical_state_name)

    print("Loading Aqueduct province_baseline BWS data...")
    aqu = pd.read_excel(AQUEDUCT_XLSX, sheet_name="province_baseline")
    aqu = aqu[
        (aqu["name_0"].astype(str).str.strip().str.lower() == "india")
        & (aqu["indicator_name"].astype(str).str.strip().str.lower() == "bws")
        & (aqu["weight"].astype(str).str.strip().str.lower() == "tot")
    ].copy()

    if "name_1" not in aqu.columns or "score" not in aqu.columns:
        raise ValueError(f"Aqueduct province_baseline does not contain the expected province-name and score columns. Columns: {list(aqu.columns)}")

    aqu = aqu[["name_1", "score"]].copy()
    aqu.columns = ["state_name", "bws_score"]
    aqu["bws_score"] = pd.to_numeric(aqu["bws_score"], errors="coerce")
    aqu["state_join"] = aqu["state_name"].map(canonical_state_name)
    aqu = aqu[["state_join", "bws_score"]].dropna().drop_duplicates()

    merged = gdf.merge(water_df[["state_join", "water_use_km3"]], on="state_join", how="left")
    merged = merged.merge(aqu, on="state_join", how="left")

    missing = merged[merged["water_use_km3"].isna() | merged["bws_score"].isna()]
    if not missing.empty:
        print("States with missing source values:")
        for _, row in missing.iterrows():
            print(
                f"  {row[shape_state_col]}: "
                f"water_use={'missing' if pd.isna(row['water_use_km3']) else 'ok'}, "
                f"bws={'missing' if pd.isna(row['bws_score']) else 'ok'}"
            )

    merged["water_use_km3"] = pd.to_numeric(merged["water_use_km3"], errors="coerce")
    merged["bws_score"] = pd.to_numeric(merged["bws_score"], errors="coerce")
    merged = merged.dropna(subset=["water_use_km3", "bws_score"]).copy()

    merged["water_use_class"] = compute_blue_water_class(merged["water_use_km3"])
    merged["water_stress_class"] = compute_bws_class(merged["bws_score"])

    merged["bivar_color"] = [
        COLORS[int(row["water_use_class"]), int(row["water_stress_class"])]
        for _, row in merged.iterrows()
    ]

    fig, ax = plt.subplots(figsize=(12, 12))
    merged.plot(
        ax=ax,
        color=merged["bivar_color"],
        edgecolor="white",
        linewidth=0.8,
    )

    label_positions = {
        "uttar pradesh": (93.0, 31.5),
        "maharashtra": (63.0, 19.0),
    }
    label_text = {
        "uttar pradesh": "Uttar Pradesh\n178.3 Mt\n(44.0% of\nproduction)",
        "maharashtra": "Maharashtra\n105.1 Mt\n(25.9% of\nproduction)",
    }
    label_rows = merged[merged[shape_state_col].map(normalize_name).isin(label_positions)]
    for _, row in label_rows.iterrows():
        point = row.geometry.representative_point()
        label_x, label_y = label_positions[normalize_name(row[shape_state_col])]
        ax.annotate(
            label_text[normalize_name(row[shape_state_col])],
            xy=(point.x, point.y),
            xytext=(label_x, label_y),
            ha="center",
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
    pad_x = (x_max - x_min) * 0.08
    pad_y = (y_max - y_min) * 0.08
    ax.set_xlim(x_min - pad_x, x_max + pad_x)
    ax.set_ylim(y_min - pad_y, y_max + pad_y)

    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"Saved map to: {OUT_PNG}")
    plt.savefig(OUT_PDF, bbox_inches="tight")
    print(f"Saved map to: {OUT_PDF}")

    output_df = merged[[shape_state_col, "water_use_km3", "bws_score", "water_use_class", "water_stress_class"]].copy()
    output_df.columns = ["state_name", "water_use_km3", "water_stress_bws", "water_use_class", "water_stress_class"]
    output_df.to_csv(OUT_CSV, index=False)
    print(f"Saved merged state table to: {OUT_CSV}")


if __name__ == "__main__":
    main()
