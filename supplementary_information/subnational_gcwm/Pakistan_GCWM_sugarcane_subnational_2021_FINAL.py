"""
Pakistan subnational GCWM sugarcane water-use analysis, 2021
=============================================================

PURPOSE
-------
This script reproduces, for Pakistan, the same conceptual approach used for
the India subnational sensitivity analysis:

1. Keep the original MIRCA2000 / GCWM 5-arc-minute spatial pattern.
2. Use observed Pakistan subnational sugarcane harvested area from
   MNFSR Table 7, 2021-22.
3. Use the reconciled 123-zone Pakistan geography prepared from
   WFP/OCHA ADM2 boundaries.
4. Use the final FAOSTAT-harmonized zone target area field (FAO2021_ha),
   whose national sum equals the FAOSTAT Pakistan 2021 harvested area.
5. Derive one area-scaling factor per analysis zone:
       scale_factor_zone = FAO2021_ha / MIRCA2000_area_ha
6. Apply those factors to the original 2021 GCWM CROP12 monthly water-use
   rasters, separately for:
       IRC_BLUE
       IRC_GREEN
       RFC_GREEN
7. Aggregate results by analysis zone and nationally.
8. Compare the district-constrained result with the existing country-level
   FAOSTAT-scaled Pakistan result from "Country-level blue and green ET.xlsx".
9. Export:
       - Excel diagnostics/results
       - annual blue and green GeoTIFFs
       - annual total ET GeoTIFF
       - CSV zone results

SCIENTIFIC INTERPRETATION
-------------------------
This is a district-constrained spatial scaling of GCWM sugarcane water use
to Pakistan 2021 harvested-area conditions. It is NOT a direct simulation of
the exact 2021 locations of sugarcane fields. The within-zone 5' pattern still
comes from MIRCA2000 / GCWM.

REQUIRED PACKAGES
-----------------
pip install numpy pandas geopandas rasterio openpyxl

AUTHOR WORKFLOW
---------------
Prepared for the Pakistan subnational sensitivity analysis corresponding to
the global GCWM-FAOSTAT sugarcane analysis.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin


# =============================================================================
# 1. USER PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

PAKISTAN_DIR = PROJECT_ROOT / "data"

# Reconciled 123-zone geography prepared for FAOSTAT 2021.
PAKISTAN_ZONES = PAKISTAN_DIR / "Pakistan_GCWM_analysis_zones_FAOSTAT2021.gpkg"

# MIRCA2000 harvested-area raster for sugarcane (CROP12).
MIRCA_AREA = PAKISTAN_DIR / "AH_CROP12.ASC"

# GCWM monthly water-use rasters for sugarcane.
GCWM_DIR = PAKISTAN_DIR / "MONTHLY_WATER_USE_CROP12_ERA5"

# Existing global country-level scaled results.
GLOBAL_ET_FILE = PAKISTAN_DIR / "Country-level blue and green ET.xlsx"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_XLSX = OUTPUT_DIR / "Pakistan_GCWM_sugarcane_subnational_2021.xlsx"
OUTPUT_CSV = OUTPUT_DIR / "Pakistan_GCWM_sugarcane_by_zone_2021.csv"

OUTPUT_BLUE_TIF = OUTPUT_DIR / "Pakistan_sugarcane_blue_ET_2021_m3.tif"
OUTPUT_GREEN_TIF = OUTPUT_DIR / "Pakistan_sugarcane_green_ET_2021_m3.tif"
OUTPUT_TOTAL_TIF = OUTPUT_DIR / "Pakistan_sugarcane_total_ET_2021_m3.tif"

ANALYSIS_YEAR = 2021

# Numerical tolerance for national harvested-area validation.
AREA_TOLERANCE_HA = 1e-3


# =============================================================================
# 2. BASIC VALIDATION
# =============================================================================

def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}\n"
        )


def require_directory(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(
            f"\nRequired directory not found:\n{path}\n"
        )


for _path in [PAKISTAN_ZONES, MIRCA_AREA, GLOBAL_ET_FILE]:
    require_file(_path)

require_directory(GCWM_DIR)


# =============================================================================
# 3. ESRI ASCII GRID READER
# =============================================================================

def read_ascii_grid(path: Path) -> tuple[np.ndarray, dict]:
    """
    Read an ESRI ASCII raster from .ASC or .ASC.gz.

    Returns
    -------
    array : np.ndarray
        Float64 raster array. NODATA cells are converted to np.nan.
    meta : dict
        Grid metadata with ncols, nrows, xllcorner, yllcorner,
        cellsize, nodata, transform, crs.
    """

    opener = gzip.open if path.suffix.lower() == ".gz" else open

    header = {}

    with opener(path, "rt") as f:
        # Standard ESRI ASCII uses six header rows.
        for _ in range(6):
            line = f.readline()
            if not line:
                raise ValueError(f"Unexpected end of header in {path}")
            parts = line.strip().split()
            if len(parts) < 2:
                raise ValueError(f"Malformed ASCII-grid header line in {path}: {line!r}")
            header[parts[0].lower()] = float(parts[1])

        array = np.loadtxt(f, dtype=np.float64)

    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    cellsize = float(header["cellsize"])

    if array.shape != (nrows, ncols):
        raise ValueError(
            f"Raster shape mismatch for {path.name}: "
            f"header says {(nrows, ncols)}, data are {array.shape}"
        )

    if "xllcorner" in header:
        xll = float(header["xllcorner"])
    elif "xllcenter" in header:
        xll = float(header["xllcenter"]) - cellsize / 2.0
    else:
        raise ValueError(f"No xllcorner/xllcenter found in {path}")

    if "yllcorner" in header:
        yll = float(header["yllcorner"])
    elif "yllcenter" in header:
        yll = float(header["yllcenter"]) - cellsize / 2.0
    else:
        raise ValueError(f"No yllcorner/yllcenter found in {path}")

    nodata = header.get("nodata_value", -9999.0)

    array[np.isclose(array, nodata)] = np.nan

    # ESRI ASCII rows are stored from north to south.
    north = yll + nrows * cellsize
    transform = from_origin(xll, north, cellsize, cellsize)

    meta = {
        "ncols": ncols,
        "nrows": nrows,
        "xllcorner": xll,
        "yllcorner": yll,
        "cellsize": cellsize,
        "nodata": nodata,
        "transform": transform,
        "crs": "EPSG:4326",
    }

    return array, meta


def assert_same_grid(meta_a: dict, meta_b: dict, label_a: str, label_b: str) -> None:
    """Stop if two ASCII rasters are not on the same grid."""

    checks = [
        ("ncols", meta_a["ncols"], meta_b["ncols"]),
        ("nrows", meta_a["nrows"], meta_b["nrows"]),
        ("xllcorner", meta_a["xllcorner"], meta_b["xllcorner"]),
        ("yllcorner", meta_a["yllcorner"], meta_b["yllcorner"]),
        ("cellsize", meta_a["cellsize"], meta_b["cellsize"]),
    ]

    problems = [
        f"{name}: {a} != {b}"
        for name, a, b in checks
        if not np.isclose(a, b)
    ]

    if problems:
        raise ValueError(
            f"\nGrid mismatch between {label_a} and {label_b}:\n"
            + "\n".join(problems)
        )


# =============================================================================
# 4. READ MIRCA CROP12 AREA
# =============================================================================

print("\n" + "=" * 79)
print("PAKISTAN SUBNATIONAL GCWM SUGARCANE ANALYSIS — 2021")
print("=" * 79)

print("\n[1/9] Reading MIRCA2000 CROP12 harvested-area raster...")

mirca_area, grid_meta = read_ascii_grid(MIRCA_AREA)

# Harvested-area raster should not contribute negative values.
mirca_area = np.where(
    np.isfinite(mirca_area) & (mirca_area > 0),
    mirca_area,
    0.0,
)

print(f"Grid: {grid_meta['ncols']} x {grid_meta['nrows']}")
print(f"Cell size: {grid_meta['cellsize']} degrees")
print(f"Global MIRCA CROP12 area sum: {mirca_area.sum():,.3f}")


# =============================================================================
# 5. READ AND RASTERIZE THE 123 PAKISTAN ANALYSIS ZONES
# =============================================================================

print("\n[2/9] Reading Pakistan analysis zones...")

zones = gpd.read_file(PAKISTAN_ZONES)

required_zone_columns = {
    "ZONE_ID",
    "Analysis_zone",
    "FAO2021_ha",
}

missing = required_zone_columns.difference(zones.columns)
if missing:
    raise ValueError(
        f"Pakistan zone file is missing required fields: {sorted(missing)}\n"
        f"Available fields: {list(zones.columns)}"
    )

if zones.crs is None:
    raise ValueError("Pakistan zone file has no CRS.")

zones = zones.to_crs("EPSG:4326").copy()

zones["ZONE_ID"] = pd.to_numeric(zones["ZONE_ID"], errors="raise").astype(int)
zones["FAO2021_ha"] = pd.to_numeric(zones["FAO2021_ha"], errors="raise")

if zones["ZONE_ID"].duplicated().any():
    raise ValueError("ZONE_ID is not unique.")

if zones["Analysis_zone"].duplicated().any():
    raise ValueError("Analysis_zone is not unique.")

if len(zones) != 123:
    raise ValueError(f"Expected 123 analysis zones, found {len(zones)}.")

if (~zones.geometry.is_valid).any():
    bad = zones.loc[~zones.geometry.is_valid, "Analysis_zone"].tolist()
    raise ValueError(f"Invalid geometries found: {bad}")

fao_target_sum = zones["FAO2021_ha"].sum()

print(f"Analysis zones: {len(zones)}")
print(f"FAOSTAT-harmonized zone target sum: {fao_target_sum:,.6f} ha")

# Pull the exact Pakistan 2021 FAOSTAT target from the global workbook.
global_df = pd.read_excel(GLOBAL_ET_FILE, sheet_name="Sheet1")

pak_global = global_df[
    (global_df["iso3"].astype(str).str.strip() == "PAK")
    & (pd.to_numeric(global_df["year"], errors="coerce") == ANALYSIS_YEAR)
    & (global_df["crop"].astype(str).str.strip().str.lower() == "sugarcane")
].copy()

if len(pak_global) != 1:
    raise ValueError(
        f"Expected exactly one PAK sugarcane {ANALYSIS_YEAR} row in "
        f"{GLOBAL_ET_FILE.name}; found {len(pak_global)}."
    )

pak_global_row = pak_global.iloc[0]

fao_national_area = float(pak_global_row["area_ha"])

if abs(fao_target_sum - fao_national_area) > AREA_TOLERANCE_HA:
    raise ValueError(
        "\nPakistan zone targets do not sum to the exact FAOSTAT 2021 area.\n"
        f"Zone sum: {fao_target_sum:,.6f} ha\n"
        f"FAOSTAT: {fao_national_area:,.6f} ha\n"
    )

print(f"FAOSTAT Pakistan 2021 area: {fao_national_area:,.0f} ha")
print("Area validation: PASS")

# Rasterize zone IDs onto the exact MIRCA/GCWM grid.
zone_id_raster = rasterize(
    (
        (geom, int(zone_id))
        for geom, zone_id in zip(zones.geometry, zones["ZONE_ID"])
        if geom is not None and not geom.is_empty
    ),
    out_shape=(grid_meta["nrows"], grid_meta["ncols"]),
    transform=grid_meta["transform"],
    fill=0,
    dtype="int32",
    all_touched=False,
)

pakistan_mask = zone_id_raster > 0

print(f"GCWM grid cells assigned to Pakistan analysis zones: {pakistan_mask.sum():,}")


# =============================================================================
# 6. MIRCA AREA BY ANALYSIS ZONE + SCALING FACTORS
# =============================================================================

print("\n[3/9] Calculating MIRCA2000 sugarcane area by analysis zone...")

zone_ids = zones["ZONE_ID"].to_numpy()
max_zone_id = int(zones["ZONE_ID"].max())

mirca_area_by_id = np.bincount(
    zone_id_raster[pakistan_mask].ravel(),
    weights=mirca_area[pakistan_mask].ravel(),
    minlength=max_zone_id + 1,
)

zones["MIRCA_area_ha"] = zones["ZONE_ID"].map(
    lambda z: float(mirca_area_by_id[int(z)])
)

zones["scale_factor_zone"] = np.nan

positive_target = zones["FAO2021_ha"] > 0
positive_mirca = zones["MIRCA_area_ha"] > 0

problem = zones[positive_target & ~positive_mirca]

if not problem.empty:
    print(
        "\nERROR: Some zones have positive 2021 harvested area but zero "
        "MIRCA2000 CROP12 area:"
    )
    print(
        problem[
            ["Analysis_zone", "FAO2021_ha", "MIRCA_area_ha"]
        ].to_string(index=False)
    )
    raise ValueError(
        "Cannot derive a multiplicative GCWM/MIRCA scaling factor for "
        "positive-target zones with zero MIRCA area."
    )

# Positive target and positive MIRCA -> normal scaling.
mask_normal = positive_target & positive_mirca
zones.loc[mask_normal, "scale_factor_zone"] = (
    zones.loc[mask_normal, "FAO2021_ha"]
    / zones.loc[mask_normal, "MIRCA_area_ha"]
)

# Zero observed target -> force water use to zero, even if MIRCA had crop area.
zones.loc[~positive_target, "scale_factor_zone"] = 0.0

if zones["scale_factor_zone"].isna().any():
    raise ValueError("Some zone scaling factors are still missing.")

print(
    f"MIRCA CROP12 area inside Pakistan zones: "
    f"{zones['MIRCA_area_ha'].sum():,.3f} ha"
)
print(
    f"Observed/harmonized 2021 target area: "
    f"{zones['FAO2021_ha'].sum():,.3f} ha"
)

positive_factors = zones.loc[
    zones["scale_factor_zone"] > 0,
    "scale_factor_zone"
]

print(
    "Zone scaling factor range "
    f"(positive-target zones): "
    f"{positive_factors.min():.4f} to {positive_factors.max():.4f}"
)

# Create raster of zone-specific scaling factors.
factor_lookup = np.zeros(max_zone_id + 1, dtype=np.float64)

for _, row in zones.iterrows():
    factor_lookup[int(row["ZONE_ID"])] = float(row["scale_factor_zone"])

scale_factor_raster = factor_lookup[zone_id_raster]


# =============================================================================
# 7. LOCATE AND SUM 2021 MONTHLY GCWM RASTERS
# =============================================================================

print("\n[4/9] Locating GCWM 2021 monthly water-use rasters...")

WATER_TYPES = ["IRC_BLUE", "IRC_GREEN", "RFC_GREEN"]


def find_gcwm_files(water_type: str, year: int) -> list[Path]:
    """
    Find the 12 monthly files for one GCWM water-use category and year.
    """

    candidates = sorted(
        p for p in GCWM_DIR.glob("*.ASC.gz")
        if water_type in p.name and re.search(fr"_{year}\.ASC\.gz$", p.name)
    )

    month_pattern = re.compile(r"MONTH(\d{2})_")

    parsed = []
    for p in candidates:
        m = month_pattern.search(p.name)
        if m:
            parsed.append((int(m.group(1)), p))

    parsed.sort(key=lambda x: x[0])

    months = [m for m, _ in parsed]
    paths = [p for _, p in parsed]

    if months != list(range(1, 13)):
        raise FileNotFoundError(
            f"\nExpected months 01-12 for {water_type}, {year}.\n"
            f"Found months: {months}\n"
            f"Directory: {GCWM_DIR}"
        )

    return paths


gcwm_files = {
    water_type: find_gcwm_files(water_type, ANALYSIS_YEAR)
    for water_type in WATER_TYPES
}

for water_type, paths in gcwm_files.items():
    print(f"{water_type}: {len(paths)} monthly files")
    print(f"  first: {paths[0].name}")
    print(f"  last : {paths[-1].name}")


def annual_gcwm_sum(paths: list[Path], grid_reference: dict) -> np.ndarray:
    """
    Sum 12 monthly GCWM rasters to an annual raster.
    """

    annual = np.zeros(
        (grid_reference["nrows"], grid_reference["ncols"]),
        dtype=np.float64,
    )

    for index, path in enumerate(paths, start=1):
        print(f"    reading {index:02d}/12: {path.name}")

        arr, meta = read_ascii_grid(path)
        assert_same_grid(
            grid_reference,
            meta,
            "MIRCA CROP12",
            path.name,
        )

        # Missing values contribute zero to annual water use.
        arr = np.where(np.isfinite(arr), arr, 0.0)

        annual += arr

    return annual


print("\n[5/9] Summing 2021 monthly GCWM rasters...")

annual_blue_raw = annual_gcwm_sum(
    gcwm_files["IRC_BLUE"],
    grid_meta,
)

annual_green_irr_raw = annual_gcwm_sum(
    gcwm_files["IRC_GREEN"],
    grid_meta,
)

annual_green_rain_raw = annual_gcwm_sum(
    gcwm_files["RFC_GREEN"],
    grid_meta,
)

annual_green_raw = annual_green_irr_raw + annual_green_rain_raw


# =============================================================================
# 8. APPLY SUBNATIONAL AREA-SCALING FACTORS
# =============================================================================

print("\n[6/9] Applying zone-specific harvested-area scaling factors...")

# Only Pakistan cells are retained.
annual_blue_scaled = np.where(
    pakistan_mask,
    annual_blue_raw * scale_factor_raster,
    np.nan,
)

annual_green_irr_scaled = np.where(
    pakistan_mask,
    annual_green_irr_raw * scale_factor_raster,
    np.nan,
)

annual_green_rain_scaled = np.where(
    pakistan_mask,
    annual_green_rain_raw * scale_factor_raster,
    np.nan,
)

annual_green_scaled = annual_green_irr_scaled + annual_green_rain_scaled
annual_total_scaled = annual_blue_scaled + annual_green_scaled


# =============================================================================
# 9. AGGREGATE WATER USE BY ANALYSIS ZONE
# =============================================================================

print("\n[7/9] Aggregating scaled water use by analysis zone...")


def zonal_sum(values: np.ndarray) -> np.ndarray:
    """
    Sum one raster by integer zone ID.
    """
    valid = pakistan_mask & np.isfinite(values)

    return np.bincount(
        zone_id_raster[valid].ravel(),
        weights=values[valid].ravel(),
        minlength=max_zone_id + 1,
    )


blue_by_id = zonal_sum(annual_blue_scaled)
green_irr_by_id = zonal_sum(annual_green_irr_scaled)
green_rain_by_id = zonal_sum(annual_green_rain_scaled)
green_by_id = zonal_sum(annual_green_scaled)
total_by_id = zonal_sum(annual_total_scaled)

zones["Blue_m3"] = zones["ZONE_ID"].map(lambda z: float(blue_by_id[int(z)]))
zones["Green_irrigated_m3"] = zones["ZONE_ID"].map(
    lambda z: float(green_irr_by_id[int(z)])
)
zones["Green_rainfed_m3"] = zones["ZONE_ID"].map(
    lambda z: float(green_rain_by_id[int(z)])
)
zones["Green_total_m3"] = zones["ZONE_ID"].map(
    lambda z: float(green_by_id[int(z)])
)
zones["Total_ET_m3"] = zones["ZONE_ID"].map(
    lambda z: float(total_by_id[int(z)])
)

for source_col, km3_col in [
    ("Blue_m3", "Blue_km3"),
    ("Green_irrigated_m3", "Green_irrigated_km3"),
    ("Green_rainfed_m3", "Green_rainfed_km3"),
    ("Green_total_m3", "Green_total_km3"),
    ("Total_ET_m3", "Total_ET_km3"),
]:
    zones[km3_col] = zones[source_col] / 1e9

zones["Blue_share_percent"] = np.where(
    zones["Total_ET_m3"] > 0,
    100.0 * zones["Blue_m3"] / zones["Total_ET_m3"],
    np.nan,
)

zones["Green_share_percent"] = np.where(
    zones["Total_ET_m3"] > 0,
    100.0 * zones["Green_total_m3"] / zones["Total_ET_m3"],
    np.nan,
)

national_blue = zones["Blue_m3"].sum()
national_green_irr = zones["Green_irrigated_m3"].sum()
national_green_rain = zones["Green_rainfed_m3"].sum()
national_green = zones["Green_total_m3"].sum()
national_total = zones["Total_ET_m3"].sum()

print(f"Subnational-scaled blue ET : {national_blue / 1e9:,.6f} km3")
print(f"Subnational-scaled green ET: {national_green / 1e9:,.6f} km3")
print(f"Subnational-scaled total ET: {national_total / 1e9:,.6f} km3")


# =============================================================================
# 10. NATIONAL COMPARISON AGAINST EXISTING GLOBAL RESULT
# =============================================================================

print("\n[8/9] Comparing with existing country-level FAOSTAT scaling...")

benchmark_blue = float(pak_global_row["blue_m3_scaled"])
benchmark_green = float(pak_global_row["green_total_m3_scaled"])
benchmark_total = float(pak_global_row["et_m3_scaled"])

comparison = pd.DataFrame(
    {
        "Component": ["Blue", "Green", "Total ET"],
        "National_scaling_km3": [
            benchmark_blue / 1e9,
            benchmark_green / 1e9,
            benchmark_total / 1e9,
        ],
        "Subnational_scaling_km3": [
            national_blue / 1e9,
            national_green / 1e9,
            national_total / 1e9,
        ],
    }
)

comparison["Difference_km3"] = (
    comparison["Subnational_scaling_km3"]
    - comparison["National_scaling_km3"]
)

comparison["Difference_percent"] = (
    100.0
    * comparison["Difference_km3"]
    / comparison["National_scaling_km3"]
)

print(comparison.to_string(index=False))


# =============================================================================
# 11. VALIDATION TABLES
# =============================================================================

# Check that green components add correctly.
green_component_difference_m3 = (
    national_green
    - (national_green_irr + national_green_rain)
)

# Check that zone outputs sum to raster outputs.
raster_blue_sum = np.nansum(annual_blue_scaled)
raster_green_sum = np.nansum(annual_green_scaled)
raster_total_sum = np.nansum(annual_total_scaled)

validation = pd.DataFrame(
    [
        {
            "Check": "Number of analysis zones",
            "Value": len(zones),
            "Expected": 123,
            "Difference": len(zones) - 123,
            "Status": "PASS" if len(zones) == 123 else "FAIL",
        },
        {
            "Check": "FAOSTAT-harmonized zone area sum (ha)",
            "Value": zones["FAO2021_ha"].sum(),
            "Expected": fao_national_area,
            "Difference": zones["FAO2021_ha"].sum() - fao_national_area,
            "Status": (
                "PASS"
                if abs(zones["FAO2021_ha"].sum() - fao_national_area)
                <= AREA_TOLERANCE_HA
                else "FAIL"
            ),
        },
        {
            "Check": "Green = irrigated green + rainfed green (m3)",
            "Value": national_green,
            "Expected": national_green_irr + national_green_rain,
            "Difference": green_component_difference_m3,
            "Status": (
                "PASS"
                if abs(green_component_difference_m3) < 1.0
                else "FAIL"
            ),
        },
        {
            "Check": "Zone blue sum = raster blue sum (m3)",
            "Value": national_blue,
            "Expected": raster_blue_sum,
            "Difference": national_blue - raster_blue_sum,
            "Status": (
                "PASS"
                if np.isclose(national_blue, raster_blue_sum, rtol=1e-12, atol=1.0)
                else "FAIL"
            ),
        },
        {
            "Check": "Zone green sum = raster green sum (m3)",
            "Value": national_green,
            "Expected": raster_green_sum,
            "Difference": national_green - raster_green_sum,
            "Status": (
                "PASS"
                if np.isclose(national_green, raster_green_sum, rtol=1e-12, atol=1.0)
                else "FAIL"
            ),
        },
        {
            "Check": "Zone total sum = raster total sum (m3)",
            "Value": national_total,
            "Expected": raster_total_sum,
            "Difference": national_total - raster_total_sum,
            "Status": (
                "PASS"
                if np.isclose(national_total, raster_total_sum, rtol=1e-12, atol=1.0)
                else "FAIL"
            ),
        },
    ]
)

if (validation["Status"] == "FAIL").any():
    print("\nWARNING: One or more validation checks failed:")
    print(validation.to_string(index=False))


# =============================================================================
# 12. WRITE GEOTIFFS
# =============================================================================

def write_geotiff(path: Path, array: np.ndarray, description: str) -> None:
    """
    Write an annual Pakistan water-use raster in m3/grid cell/year.
    """

    nodata = -9999.0

    output = np.where(np.isfinite(array), array, nodata).astype("float64")

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=grid_meta["nrows"],
        width=grid_meta["ncols"],
        count=1,
        dtype="float64",
        crs="EPSG:4326",
        transform=grid_meta["transform"],
        nodata=nodata,
        compress="deflate",
        predictor=3,
        tiled=True,
    ) as dst:
        dst.write(output, 1)
        dst.set_band_description(1, description)
        dst.update_tags(
            analysis_year=str(ANALYSIS_YEAR),
            crop="Sugarcane / CROP12",
            units="m3 grid-cell-1 year-1",
            method=(
                "GCWM 2021 monthly water use scaled by Pakistan "
                "FAOSTAT-harmonized MNFSR 2021-22 subnational harvested area"
            ),
        )


print("\nWriting GeoTIFFs...")

write_geotiff(
    OUTPUT_BLUE_TIF,
    annual_blue_scaled,
    "Pakistan sugarcane blue consumptive water use, 2021",
)

write_geotiff(
    OUTPUT_GREEN_TIF,
    annual_green_scaled,
    "Pakistan sugarcane green consumptive water use, 2021",
)

write_geotiff(
    OUTPUT_TOTAL_TIF,
    annual_total_scaled,
    "Pakistan sugarcane total consumptive ET, 2021",
)


# =============================================================================
# 13. WRITE EXCEL + CSV
# =============================================================================

print("\n[9/9] Writing Excel and CSV outputs...")

zone_output_columns = [
    "ZONE_ID",
    "Analysis_zone",
    "MNFSR_kha",
    "MNFSR_ha",
    "ProvAdj_ha",
    "FAO2021_ha",
    "MIRCA_area_ha",
    "scale_factor_zone",
    "Blue_m3",
    "Green_irrigated_m3",
    "Green_rainfed_m3",
    "Green_total_m3",
    "Total_ET_m3",
    "Blue_km3",
    "Green_irrigated_km3",
    "Green_rainfed_km3",
    "Green_total_km3",
    "Total_ET_km3",
    "Blue_share_percent",
    "Green_share_percent",
]

# Keep only columns actually available in the GeoPackage.
zone_output_columns = [
    c for c in zone_output_columns
    if c in zones.columns
]

zone_results = (
    zones[zone_output_columns]
    .sort_values("Analysis_zone")
    .reset_index(drop=True)
)

zone_results.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)

national_summary = pd.DataFrame(
    [
        {"Metric": "Analysis year", "Value": ANALYSIS_YEAR, "Unit": "year"},
        {
            "Metric": "FAOSTAT Pakistan sugarcane harvested area",
            "Value": fao_national_area,
            "Unit": "ha",
        },
        {
            "Metric": "MIRCA2000 CROP12 area inside analysis zones",
            "Value": zones["MIRCA_area_ha"].sum(),
            "Unit": "ha",
        },
        {
            "Metric": "Blue consumptive water use",
            "Value": national_blue / 1e9,
            "Unit": "km3",
        },
        {
            "Metric": "Green irrigated consumptive water use",
            "Value": national_green_irr / 1e9,
            "Unit": "km3",
        },
        {
            "Metric": "Green rainfed consumptive water use",
            "Value": national_green_rain / 1e9,
            "Unit": "km3",
        },
        {
            "Metric": "Total green consumptive water use",
            "Value": national_green / 1e9,
            "Unit": "km3",
        },
        {
            "Metric": "Total consumptive ET",
            "Value": national_total / 1e9,
            "Unit": "km3",
        },
    ]
)

scaling_details = zones[
    [
        "ZONE_ID",
        "Analysis_zone",
        "FAO2021_ha",
        "MIRCA_area_ha",
        "scale_factor_zone",
    ]
].copy()

global_benchmark = pd.DataFrame(
    [
        {
            "iso3": pak_global_row["iso3"],
            "country": pak_global_row["country"],
            "year": pak_global_row["year"],
            "area_ha": pak_global_row["area_ha"],
            "production_t": pak_global_row["production_t"],
            "area_ref_1999_2001": pak_global_row["area_ref_1999_2001"],
            "area_ref_1995_2005": pak_global_row["area_ref_1995_2005"],
            "area_ref_first_nonzero": pak_global_row["area_ref_first_nonzero"],
            "area_ref_final": pak_global_row["area_ref_final"],
            "baseline_used": pak_global_row["baseline_used"],
            "scale_factor_area": pak_global_row["scale_factor_area"],
            "blue_m3_scaled": pak_global_row["blue_m3_scaled"],
            "green_total_m3_scaled": pak_global_row["green_total_m3_scaled"],
            "et_m3_scaled": pak_global_row["et_m3_scaled"],
            "et_km3_scaled": pak_global_row["et_km3_scaled"],
        }
    ]
)

method = pd.DataFrame(
    {
        "Item": [
            "Purpose",
            "Spatial basis",
            "Observed subnational area",
            "National harvested-area target",
            "Zone scaling equation",
            "GCWM year",
            "Water components",
            "Interpretation",
            "National comparison",
        ],
        "Description": [
            (
                "Pakistan subnational sensitivity analysis of sugarcane "
                "blue and green consumptive water use."
            ),
            (
                "Original 5-arc-minute MIRCA2000/GCWM spatial pattern, "
                "constrained to 123 reconciled Pakistan analysis zones."
            ),
            (
                "MNFSR Table 7, sugarcane harvested area for 2021-22, "
                "reconciled to WFP/OCHA 2022 ADM2 geography and harmonized "
                "to FAOSTAT 2021."
            ),
            (
                f"FAOSTAT Pakistan sugarcane harvested area for 2021: "
                f"{fao_national_area:,.0f} ha."
            ),
            "FAO2021_ha / MIRCA2000 CROP12 harvested area in the same zone.",
            "2021 monthly ERA5-based GCWM CROP12 water-use rasters.",
            (
                "IRC_BLUE = blue; IRC_GREEN + RFC_GREEN = total green."
            ),
            (
                "The result is district-constrained spatial scaling, not a "
                "direct reconstruction of the exact 2021 field locations."
            ),
            (
                "The subnational result is compared with the existing "
                "country-level FAOSTAT-scaled Pakistan result used in the "
                "global analysis."
            ),
        ],
    }
)

with pd.ExcelWriter(
    OUTPUT_XLSX,
    engine="openpyxl",
) as writer:
    zone_results.to_excel(
        writer,
        sheet_name="Zone_results",
        index=False,
    )
    scaling_details.to_excel(
        writer,
        sheet_name="Scaling_details",
        index=False,
    )
    national_summary.to_excel(
        writer,
        sheet_name="National_summary",
        index=False,
    )
    comparison.to_excel(
        writer,
        sheet_name="National_comparison",
        index=False,
    )
    global_benchmark.to_excel(
        writer,
        sheet_name="Global_benchmark",
        index=False,
    )
    validation.to_excel(
        writer,
        sheet_name="Validation",
        index=False,
    )
    method.to_excel(
        writer,
        sheet_name="Method",
        index=False,
    )

    # Light formatting for readability.
    workbook = writer.book

    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for cell in worksheet[1]:
            cell.font = cell.font.copy(bold=True)

        # Conservative column widths.
        for column_cells in worksheet.columns:
            letter = column_cells[0].column_letter
            max_len = 0

            for cell in column_cells[:200]:
                value = "" if cell.value is None else str(cell.value)
                max_len = max(max_len, len(value))

            worksheet.column_dimensions[letter].width = min(
                max(max_len + 2, 12),
                45,
            )


# =============================================================================
# 14. FINAL REPORT
# =============================================================================

print("\n" + "=" * 79)
print("PAKISTAN 2021 SUBNATIONAL GCWM ANALYSIS COMPLETED")
print("=" * 79)

print(f"\nFAOSTAT area target : {fao_national_area:,.0f} ha")
print(f"Blue ET             : {national_blue / 1e9:,.6f} km3")
print(f"Green ET            : {national_green / 1e9:,.6f} km3")
print(f"Total ET            : {national_total / 1e9:,.6f} km3")

print("\nComparison with existing national scaling:")
print(comparison.to_string(index=False))

print("\nValidation:")
print(validation.to_string(index=False))

print("\nOutputs:")
print(f"  Excel : {OUTPUT_XLSX}")
print(f"  CSV   : {OUTPUT_CSV}")
print(f"  Blue  : {OUTPUT_BLUE_TIF}")
print(f"  Green : {OUTPUT_GREEN_TIF}")
print(f"  Total : {OUTPUT_TOTAL_TIF}")

print("\nDone.")
