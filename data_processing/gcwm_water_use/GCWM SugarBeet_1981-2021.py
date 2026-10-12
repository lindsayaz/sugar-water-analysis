# -*- coding: utf-8 -*-
# GCWM Sugar Beet (CROP13) -> FAST Country–Year Water Use (1981–2021)
# ==================================================================
#
# Goal
# ----
# Create an Excel file with yearly country totals for sugar beet water use from GCWM:
#   iso3, country, year, blue_m3, green_irr_m3, green_rain_m3, green_total_m3
#
# Inputs - GCWM model - source: https://zenodo.org/records/14278070 - Sugar beet = crop 13
# ------
# 1) GCWM monthly rasters (ASCII grids) compressed as .ASC.gz, e.g.:
#    - MONTHLY_WU_CROP13_IRC_BLUE_MONTH01_05_M3_1981.ASC.gz
#    - MONTHLY_WU_CROP13_IRC_GREEN_MONTH01_05_M3_1981.ASC.gz
#    - MONTHLY_WU_CROP13_RFC_GREEN_MONTH01_05_M3_1981.ASC.gz
#
#    Units: m³ per grid cell per month (GCWM output).
#    Country-month totals are computed by summing all grid cells inside each country polygon.
#    Yearly totals are computed by summing months (no monthly table is saved).
#
# 2) Country boundaries:
#    Natural Earth Admin-0 Countries (free). This script downloads it once and then reads locally.
#
# Output
# ------
# Excel file saved to:
#   outputs/
#   GCWM_sugar_beet_country_1981_2021.xlsx
#
# Sheets
# ------
# 1) GCWM_country_year
# 2) missing_iso3_report
#
# Performance / timeline
# ----------------------
# The script processes many rasters. It prints:
#   - time per raster
#   - elapsed time (minutes)
#   - ETA (estimated remaining time)
#
# Raster reading note
# -------------------
# Primary method: read .ASC.gz directly using GDAL VSI (/vsigzip/).
# Fallback: if that fails, decompress each .ASC.gz once into a local cache folder
#           and read the decompressed .ASC file.
#
# Requirements (install once)
# ---------------------------
# pip install geopandas rasterio pandas openpyxl requests pyogrio
#
# (numpy is already installed in Anaconda)

import os
import re
import glob
import time
import gzip
import shutil
import zipfile
import requests

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize


# ============================================================
# STEP 0 — PATHS (YOUR SETTINGS)
# ============================================================
# GCWM sugar beet folder (CROP13)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GCWM_DIR = os.path.join(BASE_DIR, "data", "MONTHLY_WATER_USE_CROP13_ERA5")

# Output folder + file name (same folder as sugarcane)
OUT_DIR = os.path.join(BASE_DIR, "outputs")
OUT_XLSX = os.path.join(OUT_DIR, "GCWM_sugar_beet_country_1981_2021.xlsx")
os.makedirs(OUT_DIR, exist_ok=True)

YEAR_MIN, YEAR_MAX = 1981, 2021


# ============================================================
# STEP 1 — DOWNLOAD + LOAD COUNTRIES (Natural Earth Admin-0)
# ============================================================
NE_DIR = os.path.join(OUT_DIR, "_shapefiles_natural_earth")
os.makedirs(NE_DIR, exist_ok=True)

NE_ZIP = os.path.join(NE_DIR, "ne_110m_admin_0_countries.zip")
NE_UNZIP = os.path.join(NE_DIR, "ne_110m_admin_0_countries")
NE_URL = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"

def download_file(url: str, out_path: str):
    """Download a file once (skip if it already exists)."""
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return
    print("Downloading Natural Earth countries shapefile (one-time)...")
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def unzip_if_needed(zip_path: str, out_dir: str):
    """Unzip the shapefile archive if not already unzipped."""
    if os.path.exists(out_dir) and any(fn.lower().endswith(".shp") for fn in os.listdir(out_dir)):
        return
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

download_file(NE_URL, NE_ZIP)
unzip_if_needed(NE_ZIP, NE_UNZIP)

shp_files = [os.path.join(NE_UNZIP, f) for f in os.listdir(NE_UNZIP) if f.lower().endswith(".shp")]
if not shp_files:
    raise FileNotFoundError("No .shp found after unzipping Natural Earth countries.")
COUNTRIES_SHP = shp_files[0]

countries = gpd.read_file(COUNTRIES_SHP).to_crs("EPSG:4326")

# Select ISO3 + country name columns robustly
iso_candidates = ["ADM0_A3", "ISO_A3", "ADM0_A3_EH", "ISO_A3_EH"]
name_candidates = ["ADMIN", "NAME", "SOVEREIGNT"]

def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of these columns were found: {candidates}\nAvailable columns:\n{list(df.columns)}")

ISO_COL = pick_col(countries, iso_candidates)
NAME_COL = pick_col(countries, name_candidates)

countries = countries[[ISO_COL, NAME_COL, "geometry"]].copy()
countries.rename(columns={ISO_COL: "iso3", NAME_COL: "country"}, inplace=True)

# Missing/invalid ISO3 handling
missing_iso_mask = (
    countries["iso3"].isna()
    | (countries["iso3"].astype(str).str.strip() == "")
    | (countries["iso3"].astype(str).str.strip().str.upper().isin(["-99", "NA", "N/A", "NONE", "NULL"]))
)

missing_iso_report = countries.loc[missing_iso_mask, ["country", "iso3"]].copy()
countries_valid = countries.loc[~missing_iso_mask].copy()

print(f"Countries polygons loaded: {len(countries)}")
print(f"Valid ISO3 polygons:      {len(countries_valid)}")
print(f"Missing ISO3 polygons:    {len(missing_iso_report)}")


# ============================================================
# STEP 2 — DISCOVER ALL GCWM FILES (CROP13) AUTOMATICALLY
# ============================================================
pattern = os.path.join(GCWM_DIR, "MONTHLY_WU_CROP13_*_*_MONTH??_05_M3_*.ASC.gz")
all_files = sorted(glob.glob(pattern))

if not all_files:
    raise FileNotFoundError(
        f"No GCWM files found.\nCheck folder:\n{GCWM_DIR}\nExpected pattern:\n{pattern}"
    )
  
rx = re.compile(
    r"MONTHLY_WU_CROP13_(?P<mode>IRC|RFC)_(?P<water>BLUE|GREEN)_MONTH(?P<month>\d{2})_05_M3_(?P<year>\d{4})\.ASC\.gz$",
    re.IGNORECASE,
)

meta = []
for f in all_files:
    m = rx.search(os.path.basename(f))
    if not m:
        continue
    year = int(m.group("year"))
    if YEAR_MIN <= year <= YEAR_MAX:
        meta.append({
            "path": f,
            "mode": m.group("mode").upper(),
            "water": m.group("water").upper(),
            "month": int(m.group("month")),
            "year": year,
        })

meta = sorted(meta, key=lambda d: (d["year"], d["month"], d["mode"], d["water"]))
print(f"Discovered rasters for CROP13 in {YEAR_MIN}–{YEAR_MAX}: {len(meta)}")


# ============================================================
# STEP 3 — RASTER READ HELPERS (gz direct + fallback cache)
# ============================================================
CACHE_DIR = os.path.join(OUT_DIR, "_asc_cache_crop13")
os.makedirs(CACHE_DIR, exist_ok=True)

def decompress_gz_to_cache(gz_path: str) -> str:
    """Decompress .ASC.gz -> .ASC in cache (once), reuse later."""
    base = os.path.basename(gz_path)
    asc_name = base.replace(".ASC.gz", ".ASC")
    asc_path = os.path.join(CACHE_DIR, asc_name)

    if os.path.exists(asc_path) and os.path.getsize(asc_path) > 0:
        return asc_path

    with gzip.open(gz_path, "rb") as f_in, open(asc_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    return asc_path

def open_raster_fast(gz_path: str):
    """
    Try open .ASC.gz via GDAL /vsigzip/. If that fails, decompress and open .ASC.
    Returns (dataset, used_cache_fallback_bool).
    """
    vsi = f"/vsigzip/{gz_path}"
    try:
        ds = rasterio.open(vsi)
        return ds, False
    except Exception:
        asc_path = decompress_gz_to_cache(gz_path)
        ds = rasterio.open(asc_path)
        return ds, True


# ============================================================
# STEP 4 — BUILD COUNTRY-ID RASTER ONCE (FAST AGGREGATION BASE)
# ============================================================
# Read grid metadata from the first raster
template_ds, fb = open_raster_fast(meta[0]["path"])
transform = template_ds.transform
height = template_ds.height
width = template_ds.width
template_ds.close()

print(f"GCWM grid: width={width}, height={height} (cells={width*height:,})")

# Assign integer country IDs (1..N). 0 means "no country".
countries_valid = countries_valid.reset_index(drop=True).copy()
countries_valid["cid"] = np.arange(1, len(countries_valid) + 1, dtype=np.int32)

# Rasterize countries onto the GCWM grid
shapes = list(zip(countries_valid.geometry, countries_valid["cid"].astype(int)))

t0 = time.time()
country_id_grid = rasterize(
    shapes=shapes,
    out_shape=(height, width),
    transform=transform,
    fill=0,
    all_touched=False,
    dtype="int32",
)
print(f"Rasterized countries in {time.time()-t0:,.1f}s")

country_id_flat = country_id_grid.ravel()
max_cid = int(countries_valid["cid"].max())


# ============================================================
# STEP 5 — FAST AGGREGATION FUNCTION (numpy bincount)
# ============================================================
def aggregate_country_sums_m3(values_2d: np.ndarray) -> np.ndarray:
    """
    values_2d: raster values in m³ per grid cell (for one month).
    Returns sums_by_cid where sums_by_cid[cid] = country sum(m³).
    """
    v = values_2d.ravel()
    mask = (country_id_flat != 0) & np.isfinite(v) & (v != 0)

    sums = np.bincount(
        country_id_flat[mask],
        weights=v[mask],
        minlength=max_cid + 1
    )
    return sums


# ============================================================
# STEP 6 — ACCUMULATE MONTHLY -> YEARLY (YOUR SCHEMA)
# ============================================================
acc = {}  # (cid, year) -> record

def ensure_row(cid: int, year: int):
    k = (cid, year)
    if k not in acc:
        row = countries_valid.loc[countries_valid["cid"] == cid].iloc[0]
        acc[k] = {
            "iso3": row["iso3"],
            "country": row["country"],
            "year": year,
            "blue_m3": 0.0,
            "green_irr_m3": 0.0,
            "green_rain_m3": 0.0,
        }
    return k


# ============================================================
# STEP 7 — MAIN LOOP WITH ETA
# ============================================================
start = time.time()
step_times = []
used_cache_fallback_any = False

for idx, item in enumerate(meta, start=1):
    t_step = time.time()

    # Map raster type -> output column
    if item["mode"] == "IRC" and item["water"] == "BLUE":
        out_col = "blue_m3"
    elif item["mode"] == "IRC" and item["water"] == "GREEN":
        out_col = "green_irr_m3"
    elif item["mode"] == "RFC" and item["water"] == "GREEN":
        out_col = "green_rain_m3"
    else:
        continue

    ds, used_fb = open_raster_fast(item["path"])
    used_cache_fallback_any = used_cache_fallback_any or used_fb

    arr = ds.read(1).astype("float32", copy=False)
    ds.close()

    sums_by_cid = aggregate_country_sums_m3(arr)
    y = item["year"]

    for cid in range(1, max_cid + 1):
        val = float(sums_by_cid[cid])
        if val != 0.0:
            k = ensure_row(cid, y)
            acc[k][out_col] += val

    dt = time.time() - t_step
    step_times.append(dt)
    avg = sum(step_times) / len(step_times)
    remaining = (len(meta) - idx) * avg
    elapsed = time.time() - start

    print(
        f"[{idx}/{len(meta)}] {os.path.basename(item['path'])} | "
        f"step {dt:,.2f}s | elapsed {elapsed/60:,.1f} min | ETA {remaining/60:,.1f} min"
    )


# ============================================================
# STEP 8 — EXPORT EXCEL
# ============================================================
yearly = pd.DataFrame(list(acc.values()))
yearly["green_total_m3"] = yearly["green_irr_m3"] + yearly["green_rain_m3"]

yearly = yearly[[
    "iso3", "country", "year",
    "blue_m3", "green_irr_m3", "green_rain_m3", "green_total_m3"
]].sort_values(["iso3", "year"]).reset_index(drop=True)

with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    yearly.to_excel(writer, sheet_name="GCWM_country_year", index=False)
    missing_iso_report.to_excel(writer, sheet_name="missing_iso3_report", index=False)

print("\n==================== DONE ====================")
print("Saved Excel:", OUT_XLSX)
print("Rows (country-year):", len(yearly))
print("Used .ASC cache fallback at least once:", used_cache_fallback_any)
print("Missing ISO3 polygons reported:", len(missing_iso_report))
