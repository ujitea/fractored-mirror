from PIL import Image
import io, random

# Pillow resampling fallback (older/newer versions)
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

def add_image_watermark(image_bytes, watermark_path='watermark.png',
                        scale_factor=0.25, opacity=0.25, # AHAHAH 6 777
                        margin_x=20, margin_y=20):
    """
    Places watermark copies in a grid pattern across the image.
    Returns a BytesIO object ready for discord.File(...)
    """
    # 1) Load base & watermark
    base = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    W, H = base.size
    watermark = Image.open(watermark_path).convert("RGBA")

    # 2) Resize watermark based on scale_factor
    w_w = int(base.width * scale_factor)
    w_h = int(watermark.height * (w_w / watermark.width))
    watermark = watermark.resize((w_w, w_h), RESAMPLE)

    # 3) Apply opacity
    r, g, b, a = watermark.split()
    a = a.point(lambda px: int(px * opacity))
    watermark.putalpha(a)

    # 4) Overlay for all marks
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    # 5) Grid placement
    for y in range(0, H, w_h + margin_y):
        for x in range(0, W, w_w + margin_x):
            overlay.alpha_composite(watermark, dest=(x, y))

    # 6) Merge and save
    out_img = Image.alpha_composite(base, overlay)

    buf = io.BytesIO()
    fmt = (Image.open(io.BytesIO(image_bytes)).format or "PNG").upper()
    if fmt == "JPEG":
        out_img.convert("RGB").save(buf, format="JPEG", quality=95, optimize=True)
    else:
        out_img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf