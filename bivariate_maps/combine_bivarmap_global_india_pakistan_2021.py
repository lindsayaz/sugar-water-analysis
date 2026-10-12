import os

from PIL import Image, ImageChops, ImageDraw, ImageFont
import matplotlib.pyplot as plt


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GLOBAL_PNG = os.path.join(OUTPUT_DIR, "bivar_sugarBluewater_map.png")
INDIA_PNG = os.path.join(OUTPUT_DIR, "india_state_bivar_water_map_2021.png")
PAKISTAN_PNG = os.path.join(OUTPUT_DIR, "pakistan_district_bivar_water_map_2021.png")

OUT_PNG = os.path.join(OUTPUT_DIR, "bivarmap_global_india_pakistan_2021.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "bivarmap_global_india_pakistan_2021.pdf")

BG_COLOR = "white"
TEXT_COLOR = "black"
CANVAS_WIDTH = 7200
OUTER_PAD = 180
PANEL_GAP = 120
LABEL_GAP = 60
LABEL_FONT_SIZE = 150
COLORS = [
    ["#e6d8c8", "#e8b2a5", "#e07a6d"],
    ["#ebbe93", "#cf7a5b", "#b23c34"],
    ["#f0a55f", "#b45534", "#681010"],
]


def load_font(size):
    for name in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "calibri.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_image(image, max_width, max_height):
    scale = min(max_width / image.width, max_height / image.height)
    size = (round(image.width * scale), round(image.height * scale))
    return image.resize(size, Image.Resampling.LANCZOS)


def text_size(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def draw_vertical_text(draw, xy, text, font):
    """Draw bottom-to-top text for the vertical legend axis."""
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=12, align="center")
    width = int(right - left + 0.999)
    height = int(bottom - top + 0.999)
    pad = 30
    label = Image.new("RGBA", (width + 2 * pad, height + 2 * pad), (255, 255, 255, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.multiline_text(
        (pad - left, pad - top),
        text,
        fill=TEXT_COLOR,
        font=font,
        spacing=12,
        align="center",
    )
    label = label.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    draw._image.paste(label, xy, label)


def remove_embedded_legend(image, kind):
    image = image.copy()
    if kind != "global":
        return image
    draw = ImageDraw.Draw(image)
    masks = {
        "global": (500, 2900, 3100, image.height),
        "india": (0, 1900, 1700, image.height),
        "pakistan": (0, 1600, 1750, image.height),
    }
    draw.rectangle(masks[kind], fill=BG_COLOR)
    background = Image.new("RGB", image.size, BG_COLOR)
    diff = ImageChops.difference(image, background)
    bbox = diff.getbbox()
    return image.crop(bbox) if bbox else image


def draw_shared_legend(draw, left, top, font):
    cell = 340
    grid_left = left + 1350
    grid_top = top + 20
    small_font = load_font(120)
    axis_font = load_font(140)
    vertical_font = load_font(120)

    vertical_text = "Consumptive\nblue-water use"
    left_box, top_box, right_box, bottom_box = draw.multiline_textbbox(
        (0, 0), vertical_text, font=vertical_font, spacing=12, align="center"
    )
    vertical_w = round(right_box - left_box)
    vertical_h = round(bottom_box - top_box)
    rotated_w = vertical_h + 60
    rotated_h = vertical_w + 60
    draw_vertical_text(
        draw,
        (
            grid_left - 800 - rotated_w,
            grid_top + (3 * cell - rotated_h) // 2,
        ),
        vertical_text,
        vertical_font,
    )
    for row in range(3):
        for col in range(3):
            draw.rectangle(
                (
                    grid_left + col * cell,
                    grid_top + (2 - row) * cell,
                    grid_left + (col + 1) * cell,
                    grid_top + (3 - row) * cell,
                ),
                fill=COLORS[row][col],
                outline="white",
                width=3,
            )

    for col, label in enumerate(["0-1.9", "2-2.9", "3-5"]):
        width, _ = text_size(draw, label, small_font)
        x = grid_left + col * cell + (cell - width) // 2
        draw.text((x, grid_top + 3 * cell + 24), label, fill=TEXT_COLOR, font=small_font)

    water_labels = ["Low\n<= 0.1 km³", "Medium\n0.1-0.5 km³", "High\n> 0.5 km³"]
    for row, label in enumerate(water_labels):
        width, height = text_size(draw, label, small_font)
        x = grid_left - width - 42
        y = grid_top + (2 - row) * cell + (cell - height) // 2
        draw.multiline_text((x, y), label, fill=TEXT_COLOR, font=small_font, align="right")

    label = "Water Stress"
    width, _ = text_size(draw, label, axis_font)
    draw.text((grid_left + (3 * cell - width) // 2, grid_top + 3 * cell + 190), label, fill=TEXT_COLOR, font=axis_font)

    bubble_left = grid_left + 3 * cell + 400
    draw.text((bubble_left, top), "Food insecurity ≥10%", fill=TEXT_COLOR, font=axis_font)
    bubble_values = [(10, 25), (20, 39), (40, 55)]
    for index, (value, radius) in enumerate(bubble_values):
        center_y = grid_top + 215 + index * 190
        draw.ellipse(
            (bubble_left, center_y - radius, bubble_left + radius * 2, center_y + radius),
            fill="#67A0A3",
            outline=None,
        )
        draw.text((bubble_left + radius * 2 + 38, center_y - 39), f"{value}%", fill=TEXT_COLOR, font=small_font)


def main():
    sources = [
        ("(a) Global", GLOBAL_PNG),
        ("(b) India", INDIA_PNG),
        ("(c) Pakistan", PAKISTAN_PNG),
    ]
    for _, path in sources:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing input image: {path}")

    font = load_font(LABEL_FONT_SIZE)
    scratch = Image.new("RGB", (10, 10), BG_COLOR)
    scratch_draw = ImageDraw.Draw(scratch)
    label_height = max(text_size(scratch_draw, label, font)[1] for label, _ in sources)

    global_img = fit_image(remove_embedded_legend(Image.open(GLOBAL_PNG).convert("RGB"), "global"), CANVAS_WIDTH - 2 * OUTER_PAD, 3000)
    lower_width = (CANVAS_WIDTH - 2 * OUTER_PAD - PANEL_GAP) // 2
    india_img = fit_image(remove_embedded_legend(Image.open(INDIA_PNG).convert("RGB"), "india"), lower_width, 3000)
    pakistan_img = fit_image(remove_embedded_legend(Image.open(PAKISTAN_PNG).convert("RGB"), "pakistan"), lower_width, 3000)

    top_band = label_height + LABEL_GAP
    row_gap = 400
    legend_footer = 1100
    bottom_layout_pad = 320
    lower_height = max(india_img.height, pakistan_img.height)
    canvas_height = (
        OUTER_PAD * 2
        + top_band
        + global_img.height
        + row_gap
        + top_band
        + lower_height
        + legend_footer
        + bottom_layout_pad
    )
    canvas = Image.new("RGB", (CANVAS_WIDTH, canvas_height), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    global_x = (CANVAS_WIDTH - global_img.width) // 2
    global_label = "(a) Global"
    label_w, _ = text_size(draw, global_label, font)
    draw.text(((CANVAS_WIDTH - label_w) // 2, OUTER_PAD), global_label, fill=TEXT_COLOR, font=font)
    global_y = OUTER_PAD + top_band
    canvas.paste(global_img, (global_x, global_y))

    lower_y = global_y + global_img.height + row_gap
    panels = [("(b) India", india_img), ("(c) Pakistan", pakistan_img)]
    for index, (label, image) in enumerate(panels):
        slot_x = OUTER_PAD + index * (lower_width + PANEL_GAP)
        label_w, _ = text_size(draw, label, font)
        draw.text((slot_x + (lower_width - label_w) // 2, lower_y), label, fill=TEXT_COLOR, font=font)
        image_x = slot_x + (lower_width - image.width) // 2
        image_y = lower_y + top_band
        canvas.paste(image, (image_x, image_y))

    # Place the shared legend in the literal bottom-left corner of the figure.
    draw_shared_legend(draw, -180, canvas_height - legend_footer - 380, font)

    canvas.save(OUT_PNG, dpi=(300, 300))

    fig = plt.figure(figsize=(canvas.width / 300, canvas.height / 300), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(canvas)
    ax.axis("off")
    fig.savefig(OUT_PDF, dpi=300, facecolor=BG_COLOR)
    plt.close(fig)

    print(f"Saved combined PNG: {OUT_PNG}")
    print(f"Saved combined PDF: {OUT_PDF}")
    print(f"Canvas size: {canvas.width} x {canvas.height} pixels")


if __name__ == "__main__":
    main()
