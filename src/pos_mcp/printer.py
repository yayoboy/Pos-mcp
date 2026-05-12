import io
import base64
import logging
from PIL import Image
from escpos.printer import Network

log = logging.getLogger(__name__)

_SIZE_MAP = {
    "small": (1, 1),
    "normal": (1, 1),
    "large": (2, 2),
}


def preview_image(img: Image.Image) -> str:
    """Encode a PIL image as base64 PNG (used for preview returns)."""
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
    """Send content to a network ESC/POS printer.

    Native text path: when caller passes `text`, characters are printed via
    the printer's internal font with current ESC/POS settings. Use only for
    pure-ASCII content. Anything Unicode-rich must be rendered upstream and
    passed via `image` instead.
    """
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
            p.set(align="LEFT", bold=False, width=1, height=1)

        if image is not None:
            p.image(image)

        if barcode_data:
            if barcode_type == "qr":
                p.qr(barcode_data, size=6)
                if barcode_label:
                    p.text(barcode_label + "\n")
            else:
                if barcode_label:
                    p.text(barcode_label + "\n")
                p.barcode(barcode_data, barcode_type.upper(), 64, 2, "", "")

        if cut:
            p.cut()
    except OSError as e:
        log.error("Printer I/O error to %s:%s — %s", config.ip, config.port, e)
        raise
    finally:
        try:
            p.close()
        except Exception:
            pass

    return "OK"
