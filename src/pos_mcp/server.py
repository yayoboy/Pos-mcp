from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from pos_mcp.config import load_config, PrinterConfig
from pos_mcp.renderer import (
    render_text,
    render_native_preview,
    render_dot,
    render_matplotlib,
    prepare_image,
    should_use_bitmap,
)
from pos_mcp.printer import send_to_printer, preview_image
from pos_mcp.jobstore import get_store
from pos_mcp.blocks import RenderContext, block_from_dict, compose
from pos_mcp.markdown_render import markdown_to_blocks

log = logging.getLogger(__name__)

CONFIG_PATH: Path | None = None
_CFG_CACHE: PrinterConfig | None = None
_CFG_CACHE_KEY: Path | None = None
_PREVIEW_STARTED = False

mcp = FastMCP(
    "POS Printer",
    instructions=(
        "Thermal printer server with 4 tools (print_text, print_image, "
        "print_diagram, print_barcode). Each accepts mode='print' (default), "
        "'preview' (returns image without printing), or 'confirm' (opens a "
        "browser preview and waits for user approval — supports basic edits). "
        "Text auto-promotes to bitmap rendering for non-ASCII content so the "
        "browser preview matches the printed output exactly."
    ),
)


def _load_cfg() -> PrinterConfig:
    global _CFG_CACHE, _CFG_CACHE_KEY
    if _CFG_CACHE is None or _CFG_CACHE_KEY != CONFIG_PATH:
        _CFG_CACHE = load_config(CONFIG_PATH)
        _CFG_CACHE_KEY = CONFIG_PATH
    return _CFG_CACHE


def reset_config_cache() -> None:
    global _CFG_CACHE, _CFG_CACHE_KEY
    _CFG_CACHE = None
    _CFG_CACHE_KEY = None


def _ensure_preview_started(cfg: PrinterConfig) -> None:
    global _PREVIEW_STARTED
    if _PREVIEW_STARTED or not cfg.preview.enabled:
        return
    from pos_mcp import preview_server
    url = preview_server.start(
        host=cfg.preview.host,
        port=cfg.preview.port,
        auto_open=cfg.preview.auto_open,
    )
    log.info("Preview server: %s", url)
    _PREVIEW_STARTED = True


def _image_content(img) -> list:
    return [ImageContent(type="image", data=preview_image(img), mimeType="image/png")]


def _await_confirmation(
    kind: str,
    params: dict[str, Any],
    image,
    rerender,
    cfg: PrinterConfig,
) -> tuple[str, Any]:
    """Submit job to store, block on user decision. Returns (decision, job)."""
    _ensure_preview_started(cfg)
    store = get_store()
    job = store.create(kind=kind, params=params, image=image, rerender=rerender)
    log.info("Job %s awaiting confirmation at http://%s:%s",
             job.id, cfg.preview.host, cfg.preview.port)
    got = job.wait(timeout=cfg.preview.confirm_timeout)
    if not got:
        store.cancel(job.id)
        return ("timeout", job)
    return (job.decision or "cancel", job)


def _normalize_mode(mode: str, preview: bool) -> str:
    if preview:
        return "preview"
    if mode not in ("print", "preview", "confirm"):
        return "print"
    return mode


@mcp.tool()
def print_text(
    content: str,
    bold: bool = False,
    size: str = "normal",
    align: str = "left",
    cut: bool = True,
    render: Literal["auto", "native", "bitmap"] = "auto",
    mode: Literal["print", "preview", "confirm"] = "print",
    preview: bool = False,
) -> str | list:
    """Print formatted text. Auto-renders as bitmap when content has non-ASCII chars.

    Args:
        content: The text content to print.
        bold: Bold font.
        size: "small", "normal", or "large".
        align: "left", "center", or "right".
        cut: Cut paper after printing.
        render: "auto" picks native or bitmap based on content; "native" forces
            the printer font (ASCII only); "bitmap" forces graphical rendering
            for full Unicode + emoji support and pixel-perfect preview.
        mode: "print" sends to printer; "preview" returns image; "confirm" opens
            a browser preview and waits for the user to approve, cancel, or edit.
        preview: Deprecated. Use mode="preview" instead. Kept for compatibility.
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, preview)
    use_bitmap = should_use_bitmap(content, force=render)

    def render_preview_img(params: dict[str, Any]):
        if should_use_bitmap(params["content"], force=render):
            return render_text(
                params["content"],
                width_px=cfg.width_px,
                bold=params.get("bold", bold),
                size=params.get("size", size),
                align=params.get("align", align),
                font_chain=cfg.fonts.fallback_chain or None,
            )
        return render_native_preview(
            params["content"],
            width_px=cfg.width_px,
            bold=params.get("bold", bold),
            size=params.get("size", size),
            align=params.get("align", align),
        )

    initial_params = {"content": content, "bold": bold, "size": size, "align": align}
    img = render_preview_img(initial_params)

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation("text", initial_params, img, render_preview_img, cfg)
        if decision != "print":
            return f"Cancelled by user ({decision})"
        params = {**initial_params, **(job.edited_params or {})}
        final_use_bitmap = should_use_bitmap(params["content"], force=render)
        if final_use_bitmap:
            return send_to_printer(cfg, image=job.image, cut=cut)
        return send_to_printer(
            cfg,
            text=params["content"] + "\n",
            text_options={"bold": params["bold"], "size": params["size"], "align": params["align"]},
            cut=cut,
        )

    if use_bitmap:
        return send_to_printer(cfg, image=img, cut=cut)
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
    mode: Literal["print", "preview", "confirm"] = "print",
    preview: bool = False,
) -> str | list:
    """Print a base64-encoded image.

    Args:
        image_base64: Base64 PNG or JPG.
        dither: Floyd-Steinberg dithering for 1-bit conversion.
        cut: Cut paper after printing.
        mode: "print" / "preview" / "confirm" (see print_text for details).
        preview: Deprecated alias for mode="preview".
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, preview)

    def render_preview_img(params: dict[str, Any]):
        return prepare_image(image_base64, width_px=cfg.width_px, dither=params.get("dither", dither))

    img = render_preview_img({"dither": dither})

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation(
            "image", {"dither": dither}, img, render_preview_img, cfg
        )
        if decision != "print":
            return f"Cancelled by user ({decision})"
        return send_to_printer(cfg, image=job.image, cut=cut)

    return send_to_printer(cfg, image=img, cut=cut)


@mcp.tool()
def print_diagram(
    code: str,
    engine: Literal["graphviz", "matplotlib"] = "graphviz",
    cut: bool = True,
    mode: Literal["print", "preview", "confirm"] = "print",
    preview: bool = False,
) -> str | list:
    """Print a diagram from DOT or matplotlib code.

    Args:
        code: DOT source (graphviz) or Python source (matplotlib).
        engine: "graphviz" or "matplotlib".
        cut: Cut paper after printing.
        mode: "print" / "preview" / "confirm".
        preview: Deprecated alias for mode="preview".
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, preview)

    if engine == "graphviz":
        img = render_dot(code, width_px=cfg.width_px)
    elif engine == "matplotlib":
        img = render_matplotlib(code, width_px=cfg.width_px)
    else:
        raise ValueError(f"Unknown engine: {engine}. Use 'graphviz' or 'matplotlib'.")

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation(
            "diagram", {"engine": engine}, img, rerender=None, cfg=cfg
        )
        if decision != "print":
            return f"Cancelled by user ({decision})"
        return send_to_printer(cfg, image=job.image, cut=cut)

    return send_to_printer(cfg, image=img, cut=cut)


@mcp.tool()
def print_barcode(
    data: str,
    type: str = "qr",
    label: str = "",
    cut: bool = True,
    mode: Literal["print", "preview", "confirm"] = "print",
    preview: bool = False,
) -> str | list:
    """Print a QR code or linear barcode.

    Args:
        data: Data to encode.
        type: "qr", "ean13", "ean8", "code128", "code39".
        label: Optional text label printed alongside.
        cut: Cut paper after printing.
        mode: "print" / "preview" / "confirm".
        preview: Deprecated alias for mode="preview".
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, preview)

    img = _render_barcode_image(data, type, cfg.width_px)

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation(
            "barcode", {"data": data, "type": type, "label": label}, img, rerender=None, cfg=cfg
        )
        if decision != "print":
            return f"Cancelled by user ({decision})"
        return send_to_printer(
            cfg,
            barcode_data=data,
            barcode_type=type,
            barcode_label=label,
            cut=cut,
        )

    return send_to_printer(
        cfg,
        barcode_data=data,
        barcode_type=type,
        barcode_label=label,
        cut=cut,
    )


def _build_ctx(cfg: PrinterConfig) -> RenderContext:
    return RenderContext(
        width_px=cfg.width_px,
        custom_chain=cfg.fonts.fallback_chain or None,
    )


@mcp.tool()
def print_blocks(
    blocks: list[dict],
    cut: bool = True,
    mode: Literal["print", "preview", "confirm"] = "print",
) -> str | list:
    """Print a composed document from typed block specs, atomically (single cut).

    Each entry in `blocks` is a dict with a `type` field. Supported types:
    `title`, `paragraph`, `separator`, `spacer`, `bullet`, `checklist`,
    `keyvalue`, `table`, `code`, `box`.

    Example:
        blocks=[
            {"type": "title", "text": "Shopping list"},
            {"type": "checklist", "items": [
                {"checked": false, "text": "Milk"},
                {"checked": true, "text": "Bread"}
            ]}
        ]

    Args:
        blocks: Ordered list of block specs.
        cut: Cut paper after printing.
        mode: "print" / "preview" / "confirm" — see print_text for details.
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, False)
    ctx = _build_ctx(cfg)

    try:
        block_objs = [block_from_dict(spec) for spec in blocks]
    except ValueError as e:
        return f"Invalid block spec: {e}"

    img = compose(block_objs, ctx)

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation(
            "blocks", {"blocks": blocks}, img, rerender=None, cfg=cfg
        )
        if decision != "print":
            return f"Cancelled by user ({decision})"
        return send_to_printer(cfg, image=job.image, cut=cut)

    return send_to_printer(cfg, image=img, cut=cut)


@mcp.tool()
def print_markdown(
    content: str,
    cut: bool = True,
    mode: Literal["print", "preview", "confirm"] = "print",
) -> str | list:
    """Print Markdown content. Supports headings, paragraphs, lists, GitHub task
    lists (`- [x]`), tables, code blocks, blockquotes, horizontal rules.

    In `mode="confirm"` the browser exposes a textarea so the user can edit the
    Markdown and re-render before printing.

    Args:
        content: Markdown source.
        cut: Cut paper after printing.
        mode: "print" / "preview" / "confirm".
    """
    cfg = _load_cfg()
    effective_mode = _normalize_mode(mode, False)
    ctx = _build_ctx(cfg)

    def render_from(params: dict) -> object:
        src = params.get("content", content)
        blocks = markdown_to_blocks(src)
        return compose(blocks, ctx)

    img = render_from({"content": content})

    if effective_mode == "preview":
        return _image_content(img)

    if effective_mode == "confirm":
        decision, job = _await_confirmation(
            "markdown", {"content": content}, img, rerender=render_from, cfg=cfg
        )
        if decision != "print":
            return f"Cancelled by user ({decision})"
        return send_to_printer(cfg, image=job.image, cut=cut)

    return send_to_printer(cfg, image=img, cut=cut)


def _render_barcode_image(data: str, type: str, width_px: int):
    if type == "qr":
        import qrcode
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img = img.resize((width_px, width_px))
        return img.convert("1")

    import barcode as barcode_lib
    from barcode.writer import ImageWriter
    bc_class = barcode_lib.get_barcode_class(type)
    bc = bc_class(data, writer=ImageWriter())
    buf = bc.render()
    img = buf.convert("RGB")
    ratio = width_px / img.width
    new_h = int(img.height * ratio)
    return img.resize((width_px, new_h)).convert("1")


def main():
    global CONFIG_PATH
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if CONFIG_PATH is None:
        CONFIG_PATH = Path(__file__).parent.parent.parent / "pos-mcp.json"
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
