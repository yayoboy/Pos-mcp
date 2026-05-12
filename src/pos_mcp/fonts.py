"""Font discovery and per-character fallback rendering.

Scans the system for installed fonts (Noto family preferred) and renders text
using a fallback chain: for each character, the first font in the chain that
has a glyph for it is used. Enables CJK, Indic, Arabic/Hebrew, math symbols
and monochrome emoji on a 1-bit thermal printer.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

_PREFERRED_FAMILIES = [
    "NotoSansMono",
    "DejaVuSansMono",
    "NotoSans",
    "NotoSansCJK",
    "NotoSansArabic",
    "NotoSansHebrew",
    "NotoSansDevanagari",
    "NotoSansThai",
    "NotoSansSymbols",
    "NotoSansSymbols2",
    "NotoSansMath",
    "NotoEmoji",
]

_SEARCH_DIRS = [
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    str(Path.home() / ".fonts"),
    str(Path.home() / ".local/share/fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "C:/Windows/Fonts",
]


@dataclass
class FontEntry:
    path: str
    family: str
    bold: bool = False
    cached: dict = field(default_factory=dict)

    def at_size(self, size: int) -> ImageFont.FreeTypeFont:
        if size not in self.cached:
            self.cached[size] = ImageFont.truetype(self.path, size)
        return self.cached[size]

    def has_glyph(self, char: str, size: int = 20) -> bool:
        font = self.at_size(size)
        try:
            return font.getmask(char).getbbox() is not None
        except Exception:
            return False


def _scan_dir(d: str) -> list[str]:
    if not os.path.isdir(d):
        return []
    found: list[str] = []
    for root, _, files in os.walk(d):
        for f in files:
            if f.lower().endswith((".ttf", ".otf")):
                found.append(os.path.join(root, f))
    return found


def _fc_list_files() -> list[str]:
    try:
        out = subprocess.run(
            ["fc-list", ":", "file"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        return [line.rstrip(":").strip() for line in out.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.SubprocessError):
        return []


@lru_cache(maxsize=1)
def discover_fonts() -> list[str]:
    paths: set[str] = set()
    for p in _fc_list_files():
        paths.add(p)
    for d in _SEARCH_DIRS:
        for p in _scan_dir(d):
            paths.add(p)
    log.info("Discovered %d font files", len(paths))
    return sorted(paths)


def _family_key(path: str) -> str:
    name = os.path.basename(path).rsplit(".", 1)[0]
    return name.replace("-", "").replace("_", "").replace(" ", "")


def build_fallback_chain(custom_chain: list[str] | None = None, bold: bool = False) -> list[FontEntry]:
    """Build an ordered list of FontEntry for fallback rendering.

    Custom chain (font family substrings) takes priority. After that, the
    preferred Noto/DejaVu families are appended in a fixed order so coverage
    extends to CJK, RTL, Indic, symbols and emoji when those packages exist.
    """
    all_paths = discover_fonts()
    families: dict[str, list[str]] = {}
    for p in all_paths:
        families.setdefault(_family_key(p), []).append(p)

    chain_keys: list[str] = []
    if custom_chain:
        chain_keys.extend(custom_chain)
    chain_keys.extend(_PREFERRED_FAMILIES)

    selected: list[FontEntry] = []
    seen: set[str] = set()
    for wanted in chain_keys:
        wanted_norm = wanted.replace("-", "").replace("_", "").replace(" ", "")
        for fam_key, paths in families.items():
            if wanted_norm.lower() not in fam_key.lower():
                continue
            preferred = _pick_variant(paths, bold=bold)
            if preferred and preferred not in seen:
                selected.append(FontEntry(path=preferred, family=fam_key, bold=bold))
                seen.add(preferred)
    return selected


def _pick_variant(paths: list[str], bold: bool) -> str | None:
    if not paths:
        return None
    def score(p: str) -> int:
        name = os.path.basename(p).lower()
        s = 0
        if "italic" in name or "oblique" in name:
            s -= 5
        is_bold = "bold" in name or "black" in name
        if bold and is_bold:
            s += 10
        if not bold and not is_bold:
            s += 10
        if "regular" in name:
            s += 2
        if "mono" in name:
            s += 1
        return s
    return sorted(paths, key=score, reverse=True)[0]


def _pick_font_for_char(chain: list[FontEntry], char: str, size: int) -> FontEntry:
    if char in (" ", "\t", "\n"):
        return chain[0]
    for entry in chain:
        if entry.has_glyph(char, size=size):
            return entry
    return chain[0]


def render_unicode_line(
    text: str,
    chain: list[FontEntry],
    size: int,
) -> Image.Image:
    """Render a single line by selecting a font per character. Returns RGBA strip."""
    if not chain:
        raise RuntimeError("No fonts discovered. Install fonts-noto* or fonts-dejavu.")

    runs: list[tuple[FontEntry, str]] = []
    for ch in text:
        font = _pick_font_for_char(chain, ch, size)
        if runs and runs[-1][0] is font:
            runs[-1] = (font, runs[-1][1] + ch)
        else:
            runs.append((font, ch))

    widths = []
    heights = []
    ascent_max = 0
    for entry, run in runs:
        f = entry.at_size(size)
        bbox = f.getbbox(run)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3])
        try:
            asc, _ = f.getmetrics()
        except Exception:
            asc = bbox[3]
        ascent_max = max(ascent_max, asc)

    total_w = sum(widths) or 1
    total_h = max(heights + [size]) + 4

    img = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    x = 0
    for (entry, run), w in zip(runs, widths):
        f = entry.at_size(size)
        try:
            asc, _ = f.getmetrics()
        except Exception:
            asc = total_h
        y = ascent_max - asc
        draw.text((x, y), run, fill=(0, 0, 0, 255), font=f)
        x += w
    return img


def is_pure_ascii(text: str) -> bool:
    """True when every character is ASCII printable or whitespace (< 0x80)."""
    return all(ord(c) < 0x80 for c in text)
