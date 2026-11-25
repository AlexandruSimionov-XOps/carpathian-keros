"""Build the web and README images from the brand originals in assets/brand/.

    .venv/bin/python scripts/build_brand_assets.py

Inputs (large JPEG originals, not served):
    assets/brand/logo-mark.jpg        emblem only (mountains, cloud, wave)
    assets/brand/logo-horizontal.jpg  emblem + "Carpathian Keros" + English tagline
    assets/brand/logo-stacked.jpg     emblem above "Carpathian Keros" + English tagline

Outputs (small, committed):
    static/images/favicon.ico (16/32/48), favicon-32.png, apple-touch-icon.png (180),
    icon-192.png, icon-512.png, logo-mark-64.png (header, 2x for 32 px)
    docs/images/logo-stacked.png      README header (512x512, rounded corners)
    assets/brand/social-preview.png   1280x640 for GitHub → Settings → Social preview

Requires Pillow (requirements-dev.txt). Deterministic: re-running gives the same files.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets/brand"
WEB = ROOT / "static/images"
DOCS = ROOT / "docs/images"
BG_TOLERANCE = 28  # how far (per channel) a pixel may differ from the corner colour and still count as background


def background(im: Image.Image) -> tuple[int, int, int]:
    """Median of the four corners: the flat navy the logos are drawn on."""
    corners = [im.getpixel(p) for p in ((4, 4), (im.width - 5, 4), (4, im.height - 5), (im.width - 5, im.height - 5))]
    return tuple(sorted(c[i] for c in corners)[1] for i in range(3))


def content_box(im: Image.Image, bg: tuple[int, int, int]) -> tuple[int, int, int, int]:
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg)).convert("L")
    box = diff.point(lambda v: 255 if v > BG_TOLERANCE else 0).getbbox()
    if box is None:
        raise ValueError("image has no content distinguishable from its background")
    return box


def square_mark(im: Image.Image, bg, box, padding: float) -> Image.Image:
    content = im.crop(box)
    side = round(max(content.size) * (1 + 2 * padding))
    canvas = Image.new("RGB", (side, side), bg)
    canvas.paste(content, ((side - content.width) // 2, (side - content.height) // 2))
    return canvas


def rounded(im: Image.Image, size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Resize to size×size with transparent rounded corners (an app-icon look that works on light and dark tabs)."""
    out = im.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    scale = 4  # supersample the mask for smooth corners
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size * scale - 1, size * scale - 1), radius=round(size * scale * radius_ratio), fill=255
    )
    out.putalpha(mask.resize((size, size), Image.Resampling.LANCZOS))
    return out


def save_png(im: Image.Image, path: Path) -> None:
    im.save(path, "PNG", optimize=True)
    print(f"  {path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  {path.stat().st_size // 1024} KB")


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    mark_src = Image.open(SRC / "logo-mark.jpg").convert("RGB")
    bg = background(mark_src)
    mark = square_mark(mark_src, bg, content_box(mark_src, bg), padding=0.08)

    # Favicons: tight padding (the emblem is wide), rounded corners, transparent outside.
    for size, name in ((32, "favicon-32.png"), (64, "logo-mark-64.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        save_png(rounded(mark, size), WEB / name)
    ico = rounded(mark, 256)
    ico.save(WEB / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"  {(WEB / 'favicon.ico').relative_to(ROOT)}  16/32/48  {(WEB / 'favicon.ico').stat().st_size // 1024} KB")
    # iOS fills transparency with black and rounds corners itself: give it a full, opaque square.
    save_png(mark.resize((180, 180), Image.Resampling.LANCZOS), WEB / "apple-touch-icon.png")

    horiz_src = Image.open(SRC / "logo-horizontal.jpg").convert("RGB")
    hbg = background(horiz_src)
    hbox = content_box(horiz_src, hbg)

    # README header: the stacked logo, re-centred with even padding, rounded so it sits well on light and dark GitHub.
    stacked_src = Image.open(SRC / "logo-stacked.jpg").convert("RGB")
    sbg = background(stacked_src)
    stacked = square_mark(stacked_src, sbg, content_box(stacked_src, sbg), padding=0.12)
    save_png(rounded(stacked, 512, radius_ratio=0.08), DOCS / "logo-stacked.png")

    # GitHub social preview: 1280x640 (2:1), logo centred with breathing room.
    content = horiz_src.crop(hbox)
    target_w = 1080
    content = content.resize((target_w, round(target_w * content.height / content.width)), Image.Resampling.LANCZOS)
    social = Image.new("RGB", (1280, 640), hbg)
    social.paste(content, ((1280 - content.width) // 2, (640 - content.height) // 2))
    save_png(social, SRC / "social-preview.png")


if __name__ == "__main__":
    main()
