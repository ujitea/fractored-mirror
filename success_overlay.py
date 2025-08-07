from PIL import Image
import io

def add_image_watermark(image_bytes, watermark_path='watermark.png'):
    with Image.open(io.BytesIO(image_bytes)).convert("RGBA") as base:
        with Image.open(watermark_path).convert("RGBA") as watermark:
            scale_factor = 0.25
            w_width = int(base.width * scale_factor)
            w_height = int(watermark.height * (w_width / watermark.width))
            watermark = watermark.resize((w_width, w_height), Image.LANCZOS)
            # position = (base.width - w_width - 10, base.height - w_height - 10)
           
            desired_alpha = 1000  # lower = more transparent, higher = less
            if watermark.mode != 'RGBA':
                watermark = watermark.convert('RGBA')
            alpha = watermark.split()[3]
            alpha = alpha.point(lambda p: desired_alpha)
            watermark.putalpha(alpha)


            transparent = Image.new("RGBA", base.size)            
            
            for y in range(0, base.height, w_height + 20):  # 20px padding, adjust as needed
                for x in range(0, base.width, w_width + 20):
                    transparent.paste(watermark, (x,y), mask=watermark)
            
            
            out = io.BytesIO()
            transparent.convert("RGB").save(out, format="JPEG")
            out.seek(0)
            return out
