"""Shared, collision-free label layout for the 2021 chord diagrams."""

import numpy as np


def _spread(values, lower, upper, gap):
    """Keep ordered coordinates in bounds with a guaranteed minimum gap."""
    if not values:
        return []
    values = np.clip(np.asarray(values, dtype=float), lower, upper)
    for i in range(1, len(values)):
        values[i] = max(values[i], values[i - 1] + gap)
    if values[-1] > upper:
        values -= values[-1] - upper
    for i in range(len(values) - 2, -1, -1):
        values[i] = min(values[i], values[i + 1] - gap)
    if values[0] < lower:
        values += lower - values[0]
    return values.tolist()


def draw_labels(ax, items, fontsize=16.0, positions=None, radial_top=False, radial_levels=None):
    """Lay labels around the circle with simple straight leader lines."""
    positions = positions or {}
    radial_levels = radial_levels or {}
    groups = {"top": [], "bottom": [], "left": [], "right": []}
    for item in items:
        x0, y0 = item["x0"], item["y0"]
        if y0 >= 0.72 and abs(x0) <= 0.76:
            group = "top"
        elif y0 <= -0.78 and abs(x0) <= 0.82:
            group = "bottom"
        else:
            group = "right" if x0 >= 0 else "left"
        groups[group].append(item)

    for group, y_text, y_line, va in (
        ("top", 1.12, 1.075, "bottom"),
        ("bottom", -1.12, -1.075, "top"),
    ):
        ordered = sorted(groups[group], key=lambda d: d["x0"])
        if group == "top":
            # Preserve the sector midpoint horizontally. Close neighbours are
            # separated vertically instead of being pushed sideways.
            xs = [d["x0"] * 1.08 for d in ordered]
            levels = []
            placed = []
            for item, x in zip(ordered, xs):
                half_width = 0.012 * (fontsize / 10.0) * max(len(line) for line in item["text"].splitlines())
                for level in range(3):
                    conflict = any(
                        other_level == level
                        and abs(x - other_x) < half_width + other_half_width + 0.045
                        for other_x, other_half_width, other_level in placed
                    )
                    if not conflict:
                        break
                levels.append(level)
                placed.append((x, half_width, level))
        else:
            xs = _spread([d["x0"] * 1.08 for d in ordered], -0.92, 0.92, 0.44)
            levels = [0] * len(ordered)
        for item, x_text, level in zip(ordered, xs, levels):
            if group == "top" and radial_top:
                level = radial_levels.get(item["region"], level)
                label_radius = 1.23 + 0.31 * level
                line_radius = label_radius - 0.10
                anchor_radius = float(np.hypot(item["x0"], item["y0"]))
                text_scale = label_radius / anchor_radius
                line_scale = line_radius / anchor_radius
                x_text = item["x0"] * text_scale
                item_y_text = item["y0"] * text_scale
                line_x = item["x0"] * line_scale
                item_y_line = item["y0"] * line_scale
                x_offset = positions.get(item["region"], {}).get("x_offset", 0.0)
                y_offset = positions.get(item["region"], {}).get("y_offset", 0.0)
                x_text += x_offset
                line_x += x_offset
                item_y_text += y_offset
                item_y_line += y_offset
                if positions.get(item["region"], {}).get("line_to_text", False):
                    line_x = x_text
                ax.plot(
                    [item["x0"], line_x],
                    [item["y0"], item_y_line],
                    color="#666666", linewidth=0.75, solid_capstyle="round",
                )
                ax.text(x_text, item_y_text, item["text"], fontsize=fontsize,
                        ha="center", va="center", color="black", linespacing=1.05)
                continue
            x_text = positions.get(item["region"], {}).get("x", x_text)
            if x_text == "sector":
                x_text = item["x0"] * 1.08
            default_y_text = y_text + (0.22 * level if group == "top" else 0)
            default_y_line = y_line + (0.185 * level if group == "top" else 0)
            item_y_text = positions.get(item["region"], {}).get("y", default_y_text)
            item_y_line = positions.get(item["region"], {}).get("line_y", default_y_line)
            line_x = positions.get(item["region"], {}).get("line_x", x_text)
            ax.plot(
                [item["x0"], line_x],
                [item["y0"], item_y_line],
                color="#666666", linewidth=0.75, solid_capstyle="round",
            )
            ax.text(x_text, item_y_text, item["text"], fontsize=fontsize,
                    ha="center", va=va, color="black", linespacing=1.05)

    for group, x_text, x_line, ha in (
        ("left", -1.13, -1.065, "right"),
        ("right", 1.13, 1.065, "left"),
    ):
        ordered = sorted(groups[group], key=lambda d: d["y0"])
        ys = _spread([d["y0"] * 1.10 for d in ordered], -0.91, 0.91, 0.27)
        for item, y_text in zip(ordered, ys):
            item_line_x = positions.get(item["region"], {}).get("line_x", x_line)
            item_line_y = positions.get(item["region"], {}).get("line_y", y_text)
            ax.plot(
                [item["x0"], item_line_x],
                [item["y0"], item_line_y],
                color="#666666", linewidth=0.75, solid_capstyle="round",
            )
            ax.text(x_text, y_text, item["text"], fontsize=fontsize,
                    ha=ha, va="center", color="black", linespacing=1.05)
