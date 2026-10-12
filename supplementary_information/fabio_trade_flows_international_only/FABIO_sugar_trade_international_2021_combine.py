import os
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BLUE_PNG = os.path.join(OUTPUT_DIR, "chord_c015_c016_bluewater_2021_international_regions_matplotlib_300dpi.png")
GREEN_PNG = os.path.join(OUTPUT_DIR, "chord_c015_c016_greenwater_2021_international_regions_matplotlib_300dpi.png")

OUT_PNG = os.path.join(OUTPUT_DIR, "Figure5_blue_green_chord_combined_2021_international_300dpi.png")
OUT_PDF = os.path.join(OUTPUT_DIR, "Figure5_blue_green_chord_combined_2021_international.pdf")

PANEL_LABELS = [("(a) Blue water", BLUE_PNG), ("(b) Green water", GREEN_PNG)]

BG_COLOR = "white"
TEXT_COLOR = "black"
OUTER_PAD = 60
INNER_GAP = 36
LABEL_TOP_PAD = 78
LABEL_TO_IMAGE_GAP = 90
LABEL_FONT_SIZE = 110


def load_font(size, bold=False):
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_bbox(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def main():
    font = load_font(LABEL_FONT_SIZE, bold=False)
    images = []
    for label, path in PANEL_LABELS:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing input image: {path}")
        images.append((label, Image.open(path).convert("RGB")))

    widths = [img.width for _, img in images]
    heights = [img.height for _, img in images]

    scratch = Image.new("RGB", (10, 10), BG_COLOR)
    draw = ImageDraw.Draw(scratch)
    label_sizes = [text_bbox(draw, label, font) for label, _ in images]
    label_band_height = max(h for _, h in label_sizes)

    canvas_width = OUTER_PAD * 2 + sum(widths) + INNER_GAP * (len(images) - 1)
    canvas_height = OUTER_PAD * 2 + LABEL_TOP_PAD + label_band_height + LABEL_TO_IMAGE_GAP + max(heights)

    canvas = Image.new("RGB", (canvas_width, canvas_height), BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    x = OUTER_PAD

    for (label, img), (label_w, label_h) in zip(images, label_sizes):
        label_x = x + (img.width - label_w) // 2
        label_y = OUTER_PAD + LABEL_TOP_PAD + (label_band_height - label_h) // 2
        draw.text((label_x, label_y), label, fill=TEXT_COLOR, font=font)
        image_top = OUTER_PAD + LABEL_TOP_PAD + label_band_height + LABEL_TO_IMAGE_GAP
        canvas.paste(img, (x, image_top))
        x += img.width + INNER_GAP

    canvas.save(OUT_PNG, dpi=(300, 300))

    fig_w = canvas_width / 300.0
    fig_h = canvas_height / 300.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=300)
    ax.imshow(canvas)
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight", pad_inches=0, facecolor=BG_COLOR)
    plt.close(fig)

    print(f"Saved PNG:\n{OUT_PNG}")
    print(f"Saved PDF:\n{OUT_PDF}")


if __name__ == "__main__":
    main()
