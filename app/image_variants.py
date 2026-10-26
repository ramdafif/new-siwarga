from io import BytesIO

from PIL import Image


def render_variants(content):
    from .uploads import VARIANTS

    rendered = {}
    with Image.open(BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as source:
        source.load()
        if source.mode in {"I", "I;16", "I;16L", "I;16B"}:
            source = source.convert("I").point(lambda value: value / 257).convert("RGB")
        for name, (dimension, budget) in VARIANTS.items():
            image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            image.thumbnail((dimension, dimension), Image.Resampling.LANCZOS)
            while True:
                for quality in (76, 64, 52, 40):
                    output = BytesIO()
                    image.save(output, "WEBP", quality=quality, method=4)
                    result = output.getvalue()
                    if len(result) <= budget:
                        break
                if len(result) <= budget:
                    rendered[name] = result
                    break
                image.thumbnail((max(1, int(image.width * .8)), max(1, int(image.height * .8))), Image.Resampling.LANCZOS)
    return rendered
