import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, PathPatch
from matplotlib.path import Path
from chord_label_layout import draw_labels


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
GREENWATER_FILE = os.path.join(DATA_DIR, "green_fabio_water_all_2021.csv")
REGION_FILE = os.path.join(DATA_DIR, "country_region_map.xlsx")

OUT_PNG = os.path.join(OUTPUT_DIR, "chord_c015_c016_greenwater_2021_international_regions_matplotlib_300dpi.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "chord_c015_c016_greenwater_2021_international_regions_matplotlib_vector.pdf")

REGION_ORDER = [
    "India", "Pakistan", "Southeast Asia", "Rest of Asia",
    "Africa", "South America", "Oceania",
    "North America", "Europe", "Eurasia", "Central America"
]

PALETTE_BY_REGION = {
    "India": "#C9783A",
    "Pakistan": "#B36A33",
    "Southeast Asia": "#D69058",
    "Rest of Asia": "#E2B284",
    "Africa": "#6F8FA8",
    "South America": "#7DAA87",
    "Oceania": "#B59A5A",
    "North America": "#8C8178",
    "Europe": "#8F7DB0",
    "Eurasia": "#B97A5B",
    "Central America": "#B96767",
}
FALLBACK_HEX = "#9E9E9E"

FIGSIZE = (11.0, 11.0)
DPI = 300
OUTER_RADIUS = 1.00
RING_WIDTH = 0.28
INNER_RADIUS = OUTER_RADIUS - RING_WIDTH
CONTROL_RADIUS = 0.22
LABEL_RADIUS = 1.16
PAD_FRAC = 0.006
RIBBON_ALPHA = 0.52

LABEL_TWEAKS = {
    "India": {"x": 0.82, "y": 0.98, "ha": "left", "line_x": 0.72, "line_y": 0.94, "fontsize": 17},
    "Pakistan": {"x": 1.18, "y": 1.14, "ha": "left", "line_x": 1.06, "line_y": 1.07, "fontsize": 16},
    "Southeast Asia": {"x": 1.18, "y": 0.72, "ha": "left", "line_x": 1.06, "line_y": 0.68, "fontsize": 16},
    "Rest of Asia": {"x": 1.13, "y": -0.10, "ha": "left", "line_x": 1.02, "line_y": -0.10, "fontsize": 16},
    "Africa": {"x": 0.00, "y": -1.10, "ha": "center", "line_x": 0.00, "line_y": -1.01, "fontsize": 17},
    "South America": {"x": -1.00, "y": -0.80, "ha": "right", "line_x": -0.94, "line_y": -0.80, "fontsize": 17},
    "Oceania": {"x": -1.02, "y": 0.18, "ha": "right", "line_x": -0.96, "line_y": 0.18, "fontsize": 17},
    "North America": {"x": -1.02, "y": 0.62, "ha": "right", "line_x": -0.96, "line_y": 0.62, "fontsize": 17},
    "Europe": {"x": -0.46, "y": 1.08, "ha": "right", "line_x": -0.40, "line_y": 0.98, "fontsize": 17},
    "Eurasia": {"x": -0.02, "y": 1.27, "ha": "center", "line_x": -0.02, "line_y": 1.07, "fontsize": 17},
    "Central America": {"x": 0.24, "y": 1.18, "ha": "left", "line_x": 0.18, "line_y": 1.06, "fontsize": 17},
}


def polar_to_xy(r, theta):
    return np.array([r * np.cos(theta), r * np.sin(theta)])


def arc_points(theta0, theta1, radius, n=30):
    if theta1 < theta0:
        theta0, theta1 = theta1, theta0
    thetas = np.linspace(theta0, theta1, n)
    return np.column_stack((radius * np.cos(thetas), radius * np.sin(thetas)))


def ribbon_patch(theta_s0, theta_s1, theta_t0, theta_t1, radius, color, alpha):
    src_arc = arc_points(theta_s0, theta_s1, radius, n=24)
    tgt_arc = arc_points(theta_t0, theta_t1, radius, n=24)

    s1 = src_arc[-1]
    t0 = tgt_arc[0]
    t1 = tgt_arc[-1]
    s0 = src_arc[0]

    c1 = polar_to_xy(CONTROL_RADIUS, theta_s1)
    c2 = polar_to_xy(CONTROL_RADIUS, theta_t0)
    c3 = polar_to_xy(CONTROL_RADIUS, theta_t1)
    c4 = polar_to_xy(CONTROL_RADIUS, theta_s0)

    verts = [tuple(src_arc[0])]
    codes = [Path.MOVETO]
    for pt in src_arc[1:]:
        verts.append(tuple(pt))
        codes.append(Path.LINETO)
    verts.extend([tuple(c1), tuple(c2), tuple(t0)])
    codes.extend([Path.CURVE4, Path.CURVE4, Path.CURVE4])
    for pt in tgt_arc[1:]:
        verts.append(tuple(pt))
        codes.append(Path.LINETO)
    verts.extend([tuple(c3), tuple(c4), tuple(s0)])
    codes.extend([Path.CURVE4, Path.CURVE4, Path.CURVE4])
    verts.append((0, 0))
    codes.append(Path.CLOSEPOLY)

    return PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", alpha=alpha, antialiased=True)


def fmt_sig2(val):
    if pd.isna(val):
        return "NA"
    if val == 0:
        return "0.0"
    decimals = max(0, 1 - int(math.floor(math.log10(abs(val)))))
    return f"{val:.{decimals}f}"


def region8_map(regions_df):
    tmp = regions_df[["ISO", "Region"]].drop_duplicates().copy()
    sub_to_region8 = {
        "Western Europe": "Europe",
        "Northern Europe": "Europe",
        "Southern Europe": "Europe",
        "Southwestern Europe": "Europe",
        "Eastern Europe": "Europe",
        "Central Europe": "Europe",
        "Southeast Europe": "Europe",
        "European Union": "Europe",
        "North Africa": "Africa",
        "West Africa": "Africa",
        "Central Africa": "Africa",
        "East Africa": "Africa",
        "Southeast Africa": "Africa",
        "Southern Africa": "Africa",
        "South Asia": "Rest of Asia",
        "Southeast Asia": "Southeast Asia",
        "East Asia": "Rest of Asia",
        "East Asia (Special Administrative Region of China)": "Rest of Asia",
        "Western Asia": "Rest of Asia",
        "Middle East": "Rest of Asia",
        "Middle East - Levant": "Rest of Asia",
        "Middle East - Arabian Peninsula": "Rest of Asia",
        "Middle East - Southwestern Asia": "Rest of Asia",
        "Central Asia": "Rest of Asia",
        "South Caucasus (Southwestern Asia)": "Rest of Asia",
        "South America": "South America",
        "Central America": "Central America",
        "Caribbean": "Central America",
        "North America": "North America",
        "Oceania": "Oceania",
        "Polynesia": "Oceania",
        "Micronesia": "Oceania",
        "Melanesia": "Oceania",
        "Pacific": "Oceania",
        "Indian Ocean": "Oceania",
        "North Atlantic": "Europe",
        "South Atlantic Ocean": "South America",
        "Eurasia": "Eurasia",
        "Eastern Europe and Northern Asia": "Eurasia",
    }

    def to_region8(iso, label):
        if pd.isna(iso) or pd.isna(label):
            return np.nan
        iso = str(iso).strip().upper()
        if iso == "IND":
            return "India"
        if iso == "PAK":
            return "Pakistan"
        s = str(label).strip()
        if s in REGION_ORDER:
            return s
        if s in sub_to_region8:
            return sub_to_region8[s]
        low = s.lower()
        if "eurasia" in low or ("northern asia" in low and "europe" in low):
            return "Eurasia"
        if "europe" in low:
            return "Europe"
        if "africa" in low:
            return "Africa"
        if "southeast asia" in low:
            return "Southeast Asia"
        if any(k in low for k in ["asia", "middle east", "levant", "arabian"]):
            return "Rest of Asia"
        if any(k in low for k in ["oceania", "polynesia", "micronesia", "melanesia", "pacific"]):
            return "Oceania"
        if "south america" in low:
            return "South America"
        if "central america" in low or "caribbean" in low:
            return "Central America"
        if "north america" in low:
            return "North America"
        return np.nan

    tmp["Region8"] = tmp.apply(lambda row: to_region8(row["ISO"], row["Region"]), axis=1)
    return tmp[["ISO", "Region8"]]


def load_region_flows():
    gw_full = pd.read_csv(GREENWATER_FILE)
    regions = pd.read_excel(REGION_FILE)

    gw_full.columns = [c.strip() for c in gw_full.columns]
    regions.columns = [c.strip() for c in regions.columns]
    gw_full = gw_full[gw_full["fabio_com_order"].astype(str).str.lower().isin(["c015", "c016"])].copy()

    code_map = (
        gw_full[["fabio_country_order", "fabio_country"]]
        .drop_duplicates()
        .rename(columns={"fabio_country_order": "consumer_code", "fabio_country": "consumer_iso"})
    )

    flow_cols = [c for c in gw_full.columns if str(c).startswith("R")]
    gw = gw_full[["fabio_country"] + flow_cols].copy().rename(columns={"fabio_country": "producer_iso"})

    gw_long = gw.melt(id_vars="producer_iso", var_name="consumer_code", value_name="green_m3")
    gw_long["consumer_code"] = gw_long["consumer_code"].astype(str)
    gw_long["green_m3"] = pd.to_numeric(gw_long["green_m3"], errors="coerce")
    gw_long = gw_long.replace([np.inf, -np.inf], np.nan).dropna(subset=["green_m3"])
    gw_long = gw_long[gw_long["green_m3"] > 0]

    reg_map_df = region8_map(regions)

    gw_long = (
        gw_long
        .merge(reg_map_df.rename(columns={"Region8": "producer_region"}), left_on="producer_iso", right_on="ISO", how="left")
        .drop(columns=["ISO"])
        .merge(code_map, on="consumer_code", how="left")
        .merge(reg_map_df.rename(columns={"Region8": "consumer_region"}), left_on="consumer_iso", right_on="ISO", how="left")
        .drop(columns=["ISO"])
    )

    gw_long[["producer_region", "consumer_region"]] = gw_long[["producer_region", "consumer_region"]].replace({
        "Central Americe": "Central America",
        "South Americe": "South America",
    })

    gw_long = gw_long.dropna(subset=["producer_region", "consumer_region", "producer_iso", "consumer_iso"])
    gw_long = gw_long[gw_long["producer_iso"] != gw_long["consumer_iso"]].copy()

    region_flows = (
        gw_long.groupby(["producer_region", "consumer_region"], as_index=False)
        .agg(green_m3=("green_m3", "sum"))
    )

    present = sorted(set(region_flows["producer_region"]) | set(region_flows["consumer_region"]))
    regions_list = [r for r in REGION_ORDER if r in present] + [r for r in present if r not in REGION_ORDER]
    return region_flows, regions_list


def build_angles(region_flows, regions_list):
    out_totals = region_flows.groupby("producer_region")["green_m3"].sum().to_dict()
    in_totals = region_flows.groupby("consumer_region")["green_m3"].sum().to_dict()
    totals = {r: out_totals.get(r, 0.0) + in_totals.get(r, 0.0) for r in regions_list}

    total_sum = sum(totals.values())
    gap = 2 * np.pi * PAD_FRAC
    usable = 2 * np.pi - len(regions_list) * gap

    angles = {}
    cursor = np.pi / 2
    for region in regions_list:
        span = usable * (totals[region] / total_sum) if total_sum else usable / len(regions_list)
        start = cursor
        end = cursor - span
        angles[region] = {"start": start, "end": end, "span": span}
        cursor = end - gap
    return angles


def build_allocations(region_flows, regions_list, angles):
    out_cursor = {r: angles[r]["start"] for r in regions_list}
    in_cursor = {r: (angles[r]["start"] - angles[r]["span"] * 0.5) for r in regions_list}
    half_span = {r: angles[r]["span"] * 0.5 for r in regions_list}

    out_totals = region_flows.groupby("producer_region")["green_m3"].sum().to_dict()
    in_totals = region_flows.groupby("consumer_region")["green_m3"].sum().to_dict()

    flows = []
    for row in region_flows.sort_values("green_m3", ascending=False).itertuples(index=False):
        src = row.producer_region
        tgt = row.consumer_region
        val = float(row.green_m3)
        src_step = half_span[src] * (val / out_totals[src]) if out_totals[src] else 0
        tgt_step = half_span[tgt] * (val / in_totals[tgt]) if in_totals[tgt] else 0

        s0 = out_cursor[src]
        s1 = s0 - src_step
        out_cursor[src] = s1

        t0 = in_cursor[tgt]
        t1 = t0 - tgt_step
        in_cursor[tgt] = t1

        flows.append((src, tgt, val, s1, s0, t1, t0))
    return flows


def draw_chord(region_flows, regions_list):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    angles = build_angles(region_flows, regions_list)
    flows = build_allocations(region_flows, regions_list, angles)
    total_green_m3 = float(region_flows["green_m3"].sum())
    producer_totals = region_flows.groupby("producer_region")["green_m3"].sum().to_dict()

    for src, tgt, val, s0, s1, t0, t1 in flows:
        ax.add_patch(ribbon_patch(s0, s1, t0, t1, INNER_RADIUS, PALETTE_BY_REGION.get(src, FALLBACK_HEX), RIBBON_ALPHA))

    for region in regions_list:
        start_deg = np.degrees(angles[region]["end"])
        end_deg = np.degrees(angles[region]["start"])
        ax.add_patch(
            Wedge((0, 0), OUTER_RADIUS, start_deg, end_deg, width=RING_WIDTH,
                  facecolor=PALETTE_BY_REGION.get(region, FALLBACK_HEX), edgecolor="white", linewidth=2.0)
        )

    label_items = []
    for region in regions_list:
        theta_mid = (angles[region]["start"] + angles[region]["end"]) / 2
        x0, y0 = polar_to_xy(OUTER_RADIUS + 0.01, theta_mid)
        region_total_m3 = float(producer_totals.get(region, 0.0))
        region_total_km3 = region_total_m3 / 1e9
        region_share_pct = region_total_m3 / total_green_m3 * 100 if total_green_m3 else np.nan
        label_items.append({
            "region": region,
            "x0": float(x0),
            "y0": float(y0),
            "text": f"{region}\n{fmt_sig2(region_total_km3)} km3\n({fmt_sig2(region_share_pct)}%)",
            "fontsize": LABEL_TWEAKS.get(region, {}).get("fontsize", 17),
        })

    draw_labels(
        ax,
        label_items,
        radial_top=True,
        positions={
            "Central America": {"x_offset": 0.13, "y_offset": -0.17},
        },
    )

    ax.set_xlim(-1.52, 1.52)
    ax.set_ylim(-1.43, 1.43)
    plt.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.04)
    return fig


def main():
    region_flows, regions_list = load_region_flows()
    fig = draw_chord(region_flows, regions_list)
    fig.savefig(OUT_PNG, dpi=DPI, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved PNG:\n{OUT_PNG}")
    print(f"Saved PDF:\n{OUT_PDF}")


if __name__ == "__main__":
    main()
