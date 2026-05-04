# src/pos_mcp/renderer.py
from PIL import Image, ImageDraw, ImageFont
import io
import base64 as b64module
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import math
import graphviz as gv

FONT_SIZES = {"small": 16, "normal": 20, "large": 32}
IMPORT_PATTERN = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)
ALLOWED_IMPORT_ROOTS = {"matplotlib", "numpy", "math"}

# Python's built-in exec for running code in restricted namespace
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
) -> Image.Image:
    font_size = FONT_SIZES.get(size, 20)
    try:
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        )
        font = ImageFont.truetype(path, font_size)
    except OSError:
        font = ImageFont.load_default(size=font_size)

    lines = text.split("\n")
    line_height = font_size + 4
    total_height = line_height * len(lines) + 20

    img = Image.new("1", (width_px, total_height), color=1)
    draw = ImageDraw.Draw(img)

    y = 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if align == "center":
            x = (width_px - text_width) // 2
        elif align == "right":
            x = width_px - text_width - 10
        else:
            x = 10

        draw.text((x, y), line, fill=0, font=font)
        y += line_height

    return img


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
