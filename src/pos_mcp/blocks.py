"""Composable block primitives for multi-element thermal prints.

Each Block renders to a 1-bit-friendly PIL image (mode 'L' with 0/255 values)
of the configured paper width. compose() stacks them vertically and converts
the final canvas to 1-bit, so a whole document prints as a single ESC/POS job
with one cut at the end.

High-level tools (print_blocks, print_markdown, etc.) build Block lists rather
than calling the printer directly. New utility tools = new block classes or
new functions that emit existing blocks.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from pos_mcp.fonts import FontEntry, build_fallback_chain, render_unicode_line


@dataclass
class RenderContext:
    width_px: int = 384
    base_size: int = 20
    small_size: int = 16
    large_size: int = 32
    margin: int = 10
    custom_chain: list[str] | None = None

    def chain(self, bold: bool) -> list[FontEntry]:
        return build_fallback_chain(custom_chain=self.custom_chain, bold=bold)


def _size_px(ctx: RenderContext, size: str) -> int:
    return {"small": ctx.small_size, "normal": ctx.base_size, "large": ctx.large_size}.get(
        size, ctx.base_size
    )


def _word_wrap(text: str, chain: list[FontEntry], font_size: int, max_width: int) -> list[str]:
    """Greedy word wrap. Falls back to char-wrap for words longer than max_width."""
    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            img = render_unicode_line(candidate or " ", chain, font_size)
            if img.width <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # word alone is too wide → char-wrap
            buf = ""
            for ch in word:
                trial = buf + ch
                w = render_unicode_line(trial or " ", chain, font_size).width
                if w > max_width and buf:
                    lines.append(buf)
                    buf = ch
                else:
                    buf = trial
            current = buf
        lines.append(current)
    return lines


def _draw_line_with_chain(
    canvas: Image.Image,
    text: str,
    pos: tuple[int, int],
    chain: list[FontEntry],
    size: int,
) -> None:
    if not text:
        return
    rgba = render_unicode_line(text, chain, size)
    black = Image.new("L", rgba.size, color=0)
    canvas.paste(black, pos, mask=rgba.split()[3])


class Block(ABC):
    @abstractmethod
    def render(self, ctx: RenderContext) -> Image.Image:
        ...


@dataclass
class Spacer(Block):
    height: int = 10

    def render(self, ctx: RenderContext) -> Image.Image:
        return Image.new("L", (ctx.width_px, max(1, self.height)), color=255)


@dataclass
class Separator(Block):
    style: str = "solid"  # solid | dashed | dotted
    thickness: int = 2
    margin: int = 6

    def render(self, ctx: RenderContext) -> Image.Image:
        h = self.thickness + 2 * self.margin
        img = Image.new("L", (ctx.width_px, h), color=255)
        draw = ImageDraw.Draw(img)
        y = self.margin
        x0, x1 = ctx.margin, ctx.width_px - ctx.margin
        if self.style == "solid":
            draw.rectangle([x0, y, x1, y + self.thickness - 1], fill=0)
        elif self.style == "dashed":
            dash, gap = 8, 4
            x = x0
            while x < x1:
                end = min(x + dash, x1)
                draw.rectangle([x, y, end, y + self.thickness - 1], fill=0)
                x = end + gap
        else:  # dotted
            for x in range(x0, x1, 6):
                draw.rectangle([x, y, x + 1, y + self.thickness - 1], fill=0)
        return img


@dataclass
class Title(Block):
    text: str
    align: str = "center"
    bold: bool = True
    size: str = "large"
    underline: bool = True

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, self.size)
        chain = ctx.chain(bold=self.bold)
        lines = _word_wrap(self.text, chain, font_size, ctx.width_px - 2 * ctx.margin)
        line_h = font_size + 6
        pad = 6
        underline_h = 3 if self.underline else 0
        height = line_h * len(lines) + pad * 2 + underline_h
        img = Image.new("L", (ctx.width_px, height), color=255)
        y = pad
        for line in lines:
            rgba = render_unicode_line(line or " ", chain, font_size)
            if self.align == "center":
                x = max(ctx.margin, (ctx.width_px - rgba.width) // 2)
            elif self.align == "right":
                x = max(ctx.margin, ctx.width_px - rgba.width - ctx.margin)
            else:
                x = ctx.margin
            black = Image.new("L", rgba.size, color=0)
            img.paste(black, (x, y), mask=rgba.split()[3])
            y += line_h
        if self.underline:
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                [ctx.margin, height - underline_h - 2, ctx.width_px - ctx.margin, height - 3],
                fill=0,
            )
        return img


@dataclass
class Paragraph(Block):
    text: str
    align: str = "left"
    bold: bool = False
    size: str = "normal"

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, self.size)
        chain = ctx.chain(bold=self.bold)
        lines = _word_wrap(self.text, chain, font_size, ctx.width_px - 2 * ctx.margin)
        line_h = font_size + 4
        height = line_h * len(lines) + 6
        img = Image.new("L", (ctx.width_px, height), color=255)
        y = 3
        for line in lines:
            if line:
                rgba = render_unicode_line(line, chain, font_size)
                if self.align == "center":
                    x = max(ctx.margin, (ctx.width_px - rgba.width) // 2)
                elif self.align == "right":
                    x = max(ctx.margin, ctx.width_px - rgba.width - ctx.margin)
                else:
                    x = ctx.margin
                black = Image.new("L", rgba.size, color=0)
                img.paste(black, (x, y), mask=rgba.split()[3])
            y += line_h
        return img


@dataclass
class Bullet(Block):
    items: list[str]
    marker: str = "•"
    indent: int = 18

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, "normal")
        chain = ctx.chain(bold=False)
        line_h = font_size + 4
        text_x = ctx.margin + self.indent
        text_width = ctx.width_px - text_x - ctx.margin

        wrapped: list[tuple[bool, str]] = []  # (is_first_line, text)
        for item in self.items:
            sub = _word_wrap(item, chain, font_size, text_width)
            for i, line in enumerate(sub):
                wrapped.append((i == 0, line))

        height = line_h * len(wrapped) + 6
        img = Image.new("L", (ctx.width_px, height), color=255)
        y = 3
        for is_first, line in wrapped:
            if is_first:
                _draw_line_with_chain(img, self.marker, (ctx.margin, y), chain, font_size)
            _draw_line_with_chain(img, line, (text_x, y), chain, font_size)
            y += line_h
        return img


@dataclass
class Checklist(Block):
    items: list[tuple[bool, str]]  # (checked, text)
    indent: int = 24

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, "normal")
        chain = ctx.chain(bold=False)
        line_h = font_size + 4
        box_size = font_size - 2
        text_x = ctx.margin + self.indent
        text_width = ctx.width_px - text_x - ctx.margin

        rendered_items: list[tuple[bool, list[str], bool]] = []  # (checked, lines, drawn?)
        for checked, text in self.items:
            lines = _word_wrap(text, chain, font_size, text_width)
            rendered_items.append((checked, lines, False))

        total_lines = sum(len(lines) for _, lines, _ in rendered_items)
        height = line_h * total_lines + 6
        img = Image.new("L", (ctx.width_px, height), color=255)
        draw = ImageDraw.Draw(img)
        y = 3
        for checked, lines, _ in rendered_items:
            for i, line in enumerate(lines):
                if i == 0:
                    bx, by = ctx.margin, y + (line_h - box_size) // 2
                    draw.rectangle([bx, by, bx + box_size, by + box_size], outline=0, width=2)
                    if checked:
                        draw.line([bx + 3, by + box_size // 2, bx + box_size // 2, by + box_size - 4], fill=0, width=2)
                        draw.line([bx + box_size // 2, by + box_size - 4, bx + box_size - 2, by + 3], fill=0, width=2)
                _draw_line_with_chain(img, line, (text_x, y), chain, font_size)
                y += line_h
        return img


@dataclass
class KeyValue(Block):
    pairs: list[tuple[str, str]]
    leader: str = "."
    bold_key: bool = False

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, "normal")
        chain_key = ctx.chain(bold=self.bold_key)
        chain_val = ctx.chain(bold=False)
        line_h = font_size + 4
        line_w = ctx.width_px - 2 * ctx.margin
        height = line_h * len(self.pairs) + 6
        img = Image.new("L", (ctx.width_px, height), color=255)

        y = 3
        for key, value in self.pairs:
            key_img = render_unicode_line(key, chain_key, font_size)
            val_img = render_unicode_line(value, chain_val, font_size)
            kw, vw = key_img.width, val_img.width
            leader_space = line_w - kw - vw - 6
            leader_w = render_unicode_line(self.leader, chain_val, font_size).width
            n = max(0, leader_space // max(1, leader_w))
            leader_text = self.leader * n
            black_k = Image.new("L", key_img.size, color=0)
            img.paste(black_k, (ctx.margin, y), mask=key_img.split()[3])
            if leader_text:
                _draw_line_with_chain(img, leader_text, (ctx.margin + kw + 3, y), chain_val, font_size)
            black_v = Image.new("L", val_img.size, color=0)
            img.paste(black_v, (ctx.width_px - ctx.margin - vw, y), mask=val_img.split()[3])
            y += line_h
        return img


@dataclass
class Table(Block):
    headers: list[str]
    rows: list[list[str]]
    widths: list[float] | None = None  # relative weights; None = equal
    border: bool = True

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = _size_px(ctx, "normal")
        chain = ctx.chain(bold=False)
        chain_b = ctx.chain(bold=True)
        line_h = font_size + 4

        ncols = max(len(self.headers), max((len(r) for r in self.rows), default=0))
        if ncols == 0:
            return Image.new("L", (ctx.width_px, 1), color=255)
        weights = self.widths if self.widths and len(self.widths) == ncols else [1.0] * ncols
        total_weight = sum(weights) or 1
        avail = ctx.width_px - 2 * ctx.margin
        col_widths = [int(avail * w / total_weight) for w in weights]

        def cell_lines(text: str, w: int) -> list[str]:
            return _word_wrap(text or "", chain, font_size, w - 6)

        wrapped_rows: list[list[list[str]]] = []
        all_rows: list[tuple[bool, list[str]]] = [(True, list(self.headers))]
        for row in self.rows:
            padded = list(row) + [""] * (ncols - len(row))
            all_rows.append((False, padded))

        for _, row in all_rows:
            wrapped_rows.append([cell_lines(cell, col_widths[i]) for i, cell in enumerate(row)])

        row_heights = [max((len(cell) for cell in row), default=1) * line_h + 4 for row in wrapped_rows]
        height = sum(row_heights) + 4
        img = Image.new("L", (ctx.width_px, height), color=255)
        draw = ImageDraw.Draw(img)

        y = 2
        for r_idx, (is_header, row) in enumerate(all_rows):
            x = ctx.margin
            for c_idx, cell_text in enumerate(row):
                lines = wrapped_rows[r_idx][c_idx]
                yy = y + 2
                used_chain = chain_b if is_header else chain
                for line in lines:
                    _draw_line_with_chain(img, line, (x + 3, yy), used_chain, font_size)
                    yy += line_h
                x += col_widths[c_idx]
            if is_header:
                draw.rectangle([ctx.margin, y + row_heights[r_idx] - 2,
                                ctx.width_px - ctx.margin, y + row_heights[r_idx] - 1], fill=0)
            y += row_heights[r_idx]
        return img


@dataclass
class Box(Block):
    inner: Block
    padding: int = 6
    border: int = 2

    def render(self, ctx: RenderContext) -> Image.Image:
        inner_ctx = RenderContext(
            width_px=ctx.width_px - 2 * (self.padding + self.border),
            base_size=ctx.base_size,
            small_size=ctx.small_size,
            large_size=ctx.large_size,
            margin=2,
            custom_chain=ctx.custom_chain,
        )
        inner_img = self.inner.render(inner_ctx)
        total_w = ctx.width_px
        total_h = inner_img.height + 2 * (self.padding + self.border)
        img = Image.new("L", (total_w, total_h), color=255)
        draw = ImageDraw.Draw(img)
        for t in range(self.border):
            draw.rectangle([t, t, total_w - 1 - t, total_h - 1 - t], outline=0)
        img.paste(inner_img, (self.border + self.padding, self.border + self.padding))
        return img


@dataclass
class Code(Block):
    text: str
    language: str | None = None

    def render(self, ctx: RenderContext) -> Image.Image:
        font_size = ctx.small_size
        chain = ctx.chain(bold=False)
        line_h = font_size + 2
        header_h = (font_size + 6) if self.language else 0
        lines = []
        max_chars = max(8, (ctx.width_px - 2 * ctx.margin - 6) // (font_size // 2))
        for raw in self.text.split("\n"):
            if not raw:
                lines.append("")
                continue
            for i in range(0, len(raw), max_chars):
                lines.append(raw[i:i + max_chars])

        height = header_h + line_h * max(1, len(lines)) + 8
        img = Image.new("L", (ctx.width_px, height), color=255)
        draw = ImageDraw.Draw(img)
        draw.rectangle(
            [ctx.margin, 0, ctx.width_px - ctx.margin, height - 1],
            outline=0,
        )
        y = 4
        if self.language:
            chain_b = ctx.chain(bold=True)
            _draw_line_with_chain(img, f"[{self.language}]", (ctx.margin + 4, y), chain_b, font_size)
            y += header_h
            draw.line([ctx.margin, y - 2, ctx.width_px - ctx.margin, y - 2], fill=0)
        for line in lines:
            if line:
                _draw_line_with_chain(img, line, (ctx.margin + 4, y), chain, font_size)
            y += line_h
        return img


@dataclass
class ImageBlock(Block):
    image: Image.Image

    def render(self, ctx: RenderContext) -> Image.Image:
        img = self.image
        if img.width != ctx.width_px:
            ratio = ctx.width_px / img.width
            new_h = int(img.height * ratio)
            img = img.resize((ctx.width_px, new_h), Image.LANCZOS)
        return img.convert("L")


def compose(blocks: list[Block], ctx: RenderContext) -> Image.Image:
    """Stack rendered blocks vertically, return a 1-bit canvas of full width."""
    if not blocks:
        return Image.new("1", (ctx.width_px, 8), color=1)
    rendered = [b.render(ctx) for b in blocks]
    total_h = sum(img.height for img in rendered)
    canvas = Image.new("L", (ctx.width_px, total_h), color=255)
    y = 0
    for img in rendered:
        canvas.paste(img, (0, y))
        y += img.height
    return canvas.convert("1", dither=Image.Dither.NONE)


_DISPATCH: dict[str, Any] = {}


def register(type_name: str):
    def deco(fn):
        _DISPATCH[type_name] = fn
        return fn
    return deco


@register("title")
def _b_title(spec: dict) -> Block:
    return Title(
        text=str(spec.get("text", "")),
        align=spec.get("align", "center"),
        bold=spec.get("bold", True),
        size=spec.get("size", "large"),
        underline=spec.get("underline", True),
    )


@register("paragraph")
def _b_paragraph(spec: dict) -> Block:
    return Paragraph(
        text=str(spec.get("text", "")),
        align=spec.get("align", "left"),
        bold=spec.get("bold", False),
        size=spec.get("size", "normal"),
    )


@register("separator")
def _b_sep(spec: dict) -> Block:
    return Separator(
        style=spec.get("style", "solid"),
        thickness=int(spec.get("thickness", 2)),
        margin=int(spec.get("margin", 6)),
    )


@register("spacer")
def _b_spacer(spec: dict) -> Block:
    return Spacer(height=int(spec.get("height", 10)))


@register("bullet")
def _b_bullet(spec: dict) -> Block:
    return Bullet(
        items=list(spec.get("items", [])),
        marker=spec.get("marker", "•"),
        indent=int(spec.get("indent", 18)),
    )


@register("checklist")
def _b_checklist(spec: dict) -> Block:
    items_raw = spec.get("items", [])
    items: list[tuple[bool, str]] = []
    for it in items_raw:
        if isinstance(it, dict):
            items.append((bool(it.get("checked", False)), str(it.get("text", ""))))
        elif isinstance(it, (list, tuple)) and len(it) == 2:
            items.append((bool(it[0]), str(it[1])))
        else:
            items.append((False, str(it)))
    return Checklist(items=items, indent=int(spec.get("indent", 24)))


@register("keyvalue")
def _b_kv(spec: dict) -> Block:
    pairs_raw = spec.get("pairs", [])
    pairs: list[tuple[str, str]] = []
    for p in pairs_raw:
        if isinstance(p, dict):
            pairs.append((str(p.get("key", "")), str(p.get("value", ""))))
        elif isinstance(p, (list, tuple)) and len(p) == 2:
            pairs.append((str(p[0]), str(p[1])))
    return KeyValue(
        pairs=pairs,
        leader=spec.get("leader", "."),
        bold_key=bool(spec.get("bold_key", False)),
    )


@register("table")
def _b_table(spec: dict) -> Block:
    return Table(
        headers=[str(h) for h in spec.get("headers", [])],
        rows=[[str(c) for c in row] for row in spec.get("rows", [])],
        widths=spec.get("widths"),
        border=bool(spec.get("border", True)),
    )


@register("code")
def _b_code(spec: dict) -> Block:
    return Code(text=str(spec.get("text", "")), language=spec.get("language"))


@register("box")
def _b_box(spec: dict) -> Block:
    inner_spec = spec.get("inner") or {}
    inner = block_from_dict(inner_spec)
    return Box(
        inner=inner,
        padding=int(spec.get("padding", 6)),
        border=int(spec.get("border", 2)),
    )


def block_from_dict(spec: dict) -> Block:
    """Construct a Block from a dict spec. Raises ValueError for unknown types."""
    if not isinstance(spec, dict):
        raise ValueError(f"Block spec must be dict, got {type(spec).__name__}")
    kind = spec.get("type")
    if kind not in _DISPATCH:
        raise ValueError(f"Unknown block type: {kind!r}. Known: {sorted(_DISPATCH)}")
    return _DISPATCH[kind](spec)
