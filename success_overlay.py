from PIL import Image
import io, random

# Pillow resampling fallback (older/newer versions)
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

def add_image_watermark(
    image_bytes,
    watermark_path='watermark.png',
    scale_factor=0.25,
    opacity=0.2,
    margin_x=20,
    margin_y=20,
    max_dim=3000,                 # downscale massive images
    target_max_bytes=24_000_000   # stay under typical Discord cap
):
    """
    Returns a BytesIO ready for discord.File(...), ALWAYS as JPEG.
    """
    base_img = Image.open(io.BytesIO(image_bytes))
    base = base_img.convert("RGBA")
    W, H = base.size

    # Downscale huge inputs
    if max(W, H) > max_dim:
        s = max_dim / float(max(W, H))
        base = base.resize((int(W*s), int(H*s)), RESAMPLE)
        W, H = base.size

    # Watermark prep
    wm = Image.open(watermark_path).convert("RGBA")
    w_w = max(1, int(W * scale_factor))
    w_h = max(1, int(wm.height * (w_w / wm.width)))
    wm = wm.resize((w_w, w_h), RESAMPLE)
    r, g, b, a = wm.split()
    a = a.point(lambda px: int(px * opacity))
    wm.putalpha(a)

    # Tile watermark
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for y in range(0, H, w_h + margin_y):
        for x in range(0, W, w_w + margin_x):
            overlay.alpha_composite(wm, dest=(x, y))

    out = Image.alpha_composite(base, overlay).convert("RGB")

    # Compress adaptively as JPEG
    buf = io.BytesIO()
    quality = 90
    while True:
        buf.seek(0); buf.truncate(0)
        out.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= target_max_bytes or quality <= 30:
            break
        quality = max(30, quality - 8)

    buf.seek(0)
    return buf
