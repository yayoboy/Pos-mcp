import io
import base64
from PIL import Image
from escpos.printer import Network


_SIZE_MAP = {
    "small": (1, 1),
    "normal": (1, 1),
    "large": (2, 2),
}


def preview_image(img: Image.Image) -> str:
    """Save PIL Image as PNG to BytesIO and return base64-encoded string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def send_to_printer(
    config,
    image=None,
    text=None,
    text_options=None,
    barcode_data=None,
    barcode_type="qr",
    barcode_label="",
    cut=True,
) -> str:
    """Send content to a network ESC/POS printer."""
    p = Network(config.ip, port=config.port, timeout=config.timeout)
    try:
        if text:
            opts = text_options or {}
            bold = opts.get("bold", False)
            size = opts.get("size", "normal")
            align = opts.get("align", "left").upper()
            width, height = _SIZE_MAP.get(size, (1, 1))
            p.set(align=align, bold=bold, width=width, height=height)
            p.text(text)

        if image:
            p.image(image)

        if barcode_data:
            if barcode_type == "qr":
                p.qr(barcode_data, size=6)
                if barcode_label:
                    p.text(barcode_label)
            else:
                if barcode_label:
                    p.text(barcode_label)
                p.barcode(barcode_data, barcode_type.upper(), 64, 2, "", "")

        if cut:
            p.cut()
    finally:
        p.close()

    return "OK"
