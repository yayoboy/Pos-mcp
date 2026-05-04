from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent

from pos_mcp.config import load_config, PrinterConfig
from pos_mcp.renderer import render_text, render_dot, render_matplotlib, prepare_image
from pos_mcp.printer import send_to_printer, preview_image

CONFIG_PATH = Path(__file__).parent.parent.parent / "pos-mcp.json"

mcp = FastMCP(
    "POS Printer",
    instructions=(
        "POS thermal printer server with 4 tools: "
        "print_text (formatted text), "
        "print_image (base64 images), "
        "print_diagram (graphviz/matplotlib diagrams), "
        "print_barcode (QR codes and barcodes). "
        "All tools support a preview mode that returns an image instead of printing."
    ),
)


def _load_cfg() -> PrinterConfig:
    return load_config(CONFIG_PATH)


@mcp.tool()
def print_text(
    content: str,
    bold: bool = False,
    size: str = "normal",
    align: str = "left",
    cut: bool = True,
    preview: bool = False,
) -> str | list:
    """Print formatted text to the thermal printer.

    Args:
        content: The text content to print.
        bold: Whether to use bold font.
        size: Font size — "small", "normal", or "large".
        align: Text alignment — "left", "center", or "right".
        cut: Whether to cut the paper after printing.
        preview: If True, return a preview image instead of printing.
    """
    cfg = _load_cfg()

    if preview:
        img = render_text(content, width_px=cfg.width_px, bold=bold, size=size, align=align)
        b64 = preview_image(img)
        return [ImageContent(type="image", data=b64, mimeType="image/png")]

    return send_to_printer(
        cfg,
        text=content + "\n",
        text_options={"bold": bold, "size": size, "align": align},
        cut=cut,
    )


@mcp.tool()
def print_image(
    image_base64: str,
    dither: bool = True,
    cut: bool = True,
    preview: bool = False,
) -> str | list:
    """Print a base64-encoded image to the thermal printer.

    Args:
        image_base64: Base64-encoded image data.
        dither: Whether to apply Floyd-Steinberg dithering.
        cut: Whether to cut the paper after printing.
        preview: If True, return a preview image instead of printing.
    """
    cfg = _load_cfg()
    img = prepare_image(image_base64, width_px=cfg.width_px, dither=dither)

    if preview:
        b64 = preview_image(img)
        return [ImageContent(type="image", data=b64, mimeType="image/png")]

    return send_to_printer(cfg, image=img, cut=cut)


@mcp.tool()
def print_diagram(
    code: str,
    engine: str = "graphviz",
    cut: bool = True,
    preview: bool = False,
) -> str | list:
    """Print a diagram rendered from code to the thermal printer.

    Args:
        code: Source code for the diagram (DOT for graphviz, Python for matplotlib).
        engine: Rendering engine — "graphviz" or "matplotlib".
        cut: Whether to cut the paper after printing.
        preview: If True, return a preview image instead of printing.
    """
    cfg = _load_cfg()

    if engine == "graphviz":
        img = render_dot(code, width_px=cfg.width_px)
    elif engine == "matplotlib":
        img = render_matplotlib(code, width_px=cfg.width_px)
    else:
        raise ValueError(f"Unknown engine: {engine}. Use 'graphviz' or 'matplotlib'.")

    if preview:
        b64 = preview_image(img)
        return [ImageContent(type="image", data=b64, mimeType="image/png")]

    return send_to_printer(cfg, image=img, cut=cut)


@mcp.tool()
def print_barcode(
    data: str,
    type: str = "qr",
    label: str = "",
    cut: bool = True,
    preview: bool = False,
) -> str | list:
    """Print a barcode or QR code to the thermal printer.

    Args:
        data: The data to encode in the barcode.
        type: Barcode type — "qr", "ean13", "code128", etc.
        label: Optional label text to print below the barcode.
        cut: Whether to cut the paper after printing.
        preview: If True, return a preview image instead of printing.
    """
    cfg = _load_cfg()

    if preview:
        if type == "qr":
            import qrcode

            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = img.resize((cfg.width_px, cfg.width_px))
            img = img.convert("1")
        else:
            import barcode as barcode_lib
            from barcode.writer import ImageWriter

            bc_class = barcode_lib.get_barcode_class(type)
            bc = bc_class(data, writer=ImageWriter())
            buf = bc.render()
            img = buf.convert("RGB")
            ratio = cfg.width_px / img.width
            new_height = int(img.height * ratio)
            img = img.resize((cfg.width_px, new_height))
            img = img.convert("1")

        b64 = preview_image(img)
        return [ImageContent(type="image", data=b64, mimeType="image/png")]

    return send_to_printer(
        cfg,
        barcode_data=data,
        barcode_type=type,
        barcode_label=label,
        cut=cut,
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
