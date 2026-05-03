"""Generate the Open Graph share image at static/img/og-landing.png.

Run-once; the resulting PNG is committed and served as a static asset.
Re-run if the brand identity or wording changes.

Run from project root:
    .venv/Scripts/python.exe scripts/generate_og_image.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Brand tokens (DESIGN.md / tailwind.theme.json)
COL_PRIMARY = (26, 28, 30)  # #1A1C1E — near-black
COL_TERTIARY = (160, 74, 44)  # #A04A2C — warm rust
COL_SECONDARY = (108, 114, 120)  # #6C7278 — muted gray
COL_NEUTRAL = (245, 241, 234)  # #F5F1EA — cream paper
COL_GOLD = (201, 162, 39)  # #C9A227 — ceremonial gold
COL_RULE = (160, 74, 44, 60)  # tertiary @ 24% alpha for thin rules

# Open Graph spec
W, H = 1200, 630

# Windows ships Georgia regular/bold/italic — closest local match to
# Playfair Display (the brand display font). For the production-grade
# version, replace these paths with vendored Playfair Display TTFs.
FONT_REGULAR = "C:/Windows/Fonts/georgia.ttf"
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_ITALIC = "C:/Windows/Fonts/georgiai.ttf"
FONT_SANS = "C:/Windows/Fonts/segoeui.ttf"  # for the small uppercase pill


def main() -> None:
    img = Image.new("RGB", (W, H), COL_NEUTRAL)
    draw = ImageDraw.Draw(img, "RGBA")

    # Top thin rule (full-width, tertiary @ low alpha)
    draw.line([(0, 12), (W, 12)], fill=COL_TERTIARY, width=4)

    # Eyebrow pill — "PROMOTION 1980 — 1985 · CEG 1 BIRNI · ZINDER"
    pill_font = ImageFont.truetype(FONT_SANS, 22)
    pill_text = "PROMOTION 1980 — 1985  ·  CEG 1 BIRNI  ·  ZINDER"
    pill_bbox = draw.textbbox((0, 0), pill_text, font=pill_font)
    pill_w = pill_bbox[2] - pill_bbox[0]
    pill_h = pill_bbox[3] - pill_bbox[1]
    pad_x, pad_y = 28, 14
    pill_x = (W - pill_w) // 2 - pad_x
    pill_y = 100
    # Pill background (cream + thin tertiary border)
    draw.rounded_rectangle(
        [(pill_x, pill_y), (pill_x + pill_w + pad_x * 2, pill_y + pill_h + pad_y * 2)],
        radius=(pill_h + pad_y * 2) // 2,
        fill=(255, 255, 255, 200),
        outline=COL_TERTIARY,
        width=2,
    )
    draw.text(
        (pill_x + pad_x, pill_y + pad_y - 4),
        pill_text,
        font=pill_font,
        fill=COL_TERTIARY,
    )

    # Headline 1 — "Les Retrouvailles" (display serif, primary color)
    h1_font = ImageFont.truetype(FONT_BOLD, 124)
    h1_text = "Les Retrouvailles"
    h1_bbox = draw.textbbox((0, 0), h1_text, font=h1_font)
    h1_w = h1_bbox[2] - h1_bbox[0]
    draw.text(
        ((W - h1_w) // 2, 210),
        h1_text,
        font=h1_font,
        fill=COL_PRIMARY,
    )

    # Headline 2 — "des anciens du CEG 1 Birni" (italic serif, tertiary color)
    h2_font = ImageFont.truetype(FONT_ITALIC, 78)
    h2_text = "des anciens du CEG 1 Birni"
    h2_bbox = draw.textbbox((0, 0), h2_text, font=h2_font)
    h2_w = h2_bbox[2] - h2_bbox[0]
    draw.text(
        ((W - h2_w) // 2, 360),
        h2_text,
        font=h2_font,
        fill=COL_TERTIARY,
    )

    # Footer — small kicker line (secondary gray)
    foot_font = ImageFont.truetype(FONT_REGULAR, 24)
    foot_text = "Quarante ans plus tard, retrouvons-nous."
    foot_bbox = draw.textbbox((0, 0), foot_text, font=foot_font)
    foot_w = foot_bbox[2] - foot_bbox[0]
    draw.text(
        ((W - foot_w) // 2, 490),
        foot_text,
        font=foot_font,
        fill=COL_SECONDARY,
    )

    # Bottom gold rule (thin, full-width)
    draw.line([(0, H - 12), (W, H - 12)], fill=COL_GOLD, width=4)

    # Small uppercase footer label
    label_font = ImageFont.truetype(FONT_SANS, 18)
    label_text = "VILLAGERETROUVAILLES.COM"
    label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
    label_w = label_bbox[2] - label_bbox[0]
    draw.text(
        ((W - label_w) // 2, H - 60),
        label_text,
        font=label_font,
        fill=COL_GOLD,
    )

    out = Path(__file__).resolve().parents[1] / "static" / "img" / "og-landing.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
