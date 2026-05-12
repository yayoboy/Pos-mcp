# src/pos_mcp/renderer.py
from PIL import Image, ImageDraw, ImageFont
import io
import base64 as b64module
import re
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import math
import graphviz as gv

from pos_mcp.fonts import build_fallback_chain, render_unicode_line, is_pure_ascii

log = logging.getLogger(__name__)

FONT_SIZES = {"small": 16, "normal": 20, "large": 32}
IMPORT_PATTERN = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)
ALLOWED_IMPORT_ROOTS = {"matplotlib", "numpy", "math"}

_exec_code = exec
_real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__


def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"Import not allowed: {name}")
    return _real_import(name, globals, locals, fromlist, level)


def render_text(
    text: str,
    width_px: int = 384,
    bold: bool = False,
    size: str = "normal",
    align: str = "left",
    font_chain: list[str] | None = None,
) -> Image.Image:
    """Render text to a 1-bit bitmap using a fallback font chain.

    Use this when text contains non-ASCII characters or when the caller needs
    pixel-perfect preview fidelity. For pure-ASCII content the printer's
    native font is faster and uses less memory — see is_pure_ascii().
    """
    font_size = FONT_SIZES.get(size, 20)
    chain = build_fallback_chain(custom_chain=font_chain, bold=bold)

    lines = text.split("\n")
    line_imgs = [render_unicode_line(line or " ", chain, font_size) for line in lines]
    line_height = font_size + 6
    total_height = line_height * len(lines) + 20

    img = Image.new("L", (width_px, total_height), color=255)

    y = 10
    for line_img in line_imgs:
        if align == "center":
            x = max(0, (width_px - line_img.width) // 2)
        elif align == "right":
            x = max(0, width_px - line_img.width - 10)
        else:
            x = 10
        black = Image.new("L", line_img.size, color=0)
        img.paste(black, (x, y), mask=line_img.split()[3])
        y += line_height

    return img.convert("1", dither=Image.Dither.NONE)


def render_native_preview(
    text: str,
    width_px: int = 384,
    bold: bool = False,
    size: str = "normal",
    align: str = "left",
) -> Image.Image:
    """Approximate preview for text that will be printed via the native ESC/POS path.

    Uses a fixed monospace font with metrics matching a typical 80mm thermal printer
    (Font A: 12x24 dots, ~32 chars/line at normal size). Not pixel-perfect — the
    printer ROM glyphs differ slightly — but layout, char width and line count match.
    """
    char_w = 12
    line_h = 24
    if size == "large":
        char_w *= 2
        line_h *= 2

    cols = max(1, width_px // char_w)
    wrapped: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            wrapped.append("")
            continue
        for i in range(0, len(raw_line), cols):
            wrapped.append(raw_line[i:i + cols])

    total_h = max(line_h, line_h * len(wrapped) + 16)
    img = Image.new("L", (width_px, total_h), color=255)
    draw = ImageDraw.Draw(img)

    try:
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        )
        font = ImageFont.truetype(path, line_h - 4)
    except OSError:
        font = ImageFont.load_default(size=line_h - 4)

    y = 8
    for line in wrapped:
        text_w = draw.textlength(line, font=font)
        if align == "center":
            x = max(0, (width_px - int(text_w)) // 2)
        elif align == "right":
            x = max(0, width_px - int(text_w) - 8)
        else:
            x = 8
        draw.text((x, y), line, fill=0, font=font)
        y += line_h

    return img.convert("1", dither=Image.Dither.NONE)


def render_dot(dot_code: str, width_px: int = 384) -> Image.Image:
    try:
        source = gv.Source(dot_code)
        png_data = source.pipe(format="png", engine="dot")
    except Exception as e:
        raise ValueError(f"Invalid DOT code: {e}")

    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    ratio = width_px / img.width
    new_height = int(img.height * ratio)
    img = img.resize((width_px, new_height), Image.LANCZOS)
    return img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def render_matplotlib(code: str, width_px: int = 384) -> Image.Image:
    imports_found = IMPORT_PATTERN.findall(code)
    for mod in imports_found:
        root = mod.split(".")[0]
        if root not in {"matplotlib", "numpy", "math"}:
            raise ValueError(
                f"Import not allowed: {mod}. Only matplotlib, numpy, math are permitted."
            )

    namespace = {
        "plt": plt,
        "np": np,
        "math": math,
        "matplotlib": matplotlib,
        "__builtins__": {
            "range": range, "len": len, "int": int, "float": float,
            "str": str, "list": list, "tuple": tuple, "dict": dict,
            "zip": zip, "enumerate": enumerate, "min": min, "max": max,
            "sum": sum, "abs": abs, "round": round, "sorted": sorted,
            "reversed": reversed, "print": print,
            "True": True, "False": False, "None": None,
            "__import__": _restricted_import,
        },
    }

    plt.close("all")
    try:
        _exec_code(code, namespace)
    except Exception as e:
        raise ValueError(f"Matplotlib code error: {e}")

    fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=203, bbox_inches="tight", pad_inches=0.1)
    plt.close("all")
    buf.seek(0)

    img = Image.open(buf).convert("RGB")
    ratio = width_px / img.width
    new_height = int(img.height * ratio)
    img = img.resize((width_px, new_height), Image.LANCZOS)
    return img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def prepare_image(
    image_base64: str, width_px: int = 384, dither: bool = True
) -> Image.Image:
    try:
        raw = b64module.b64decode(image_base64)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid image data: {e}")

    ratio = width_px / img.width
    new_height = int(img.height * ratio)
    img = img.resize((width_px, new_height), Image.LANCZOS)

    if dither:
        return img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        return img.convert("1", dither=Image.Dither.NONE)


def should_use_bitmap(text: str, force: str = "auto") -> bool:
    """Decide whether to render text as a bitmap or send it via the native ESC/POS path.

    Returns True for bitmap, False for native. Rule: native only when text is
    pure ASCII; everything else (accents, CJK, emoji, symbols) renders as bitmap.
    """
    if force == "bitmap":
        return True
    if force == "native":
        return False
    return not is_pure_ascii(text)
