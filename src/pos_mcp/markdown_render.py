"""Convert Markdown text into a list of Block objects via mistune's AST.

Supports: headings (h1-h6), paragraphs, ordered/unordered lists, GitHub task
lists, tables, fenced code blocks, blockquotes, thematic breaks (hr), inline
text. Inline emphasis is flattened to plain text — bold/italic styling on
specific runs would require splitting into multiple render passes per line,
which is not worth it on a 1-bit thermal output.
"""

from __future__ import annotations

from typing import Any

import mistune

from pos_mcp.blocks import (
    Block,
    Bullet,
    Checklist,
    Code,
    Paragraph,
    Separator,
    Spacer,
    Table,
    Title,
)


def _inline_text(children: list[dict] | None) -> str:
    if not children:
        return ""
    parts: list[str] = []
    for child in children:
        t = child.get("type")
        if t == "text":
            parts.append(child.get("raw", ""))
        elif t in ("strong", "emphasis", "codespan", "linebreak", "softbreak"):
            if t == "codespan":
                parts.append(child.get("raw", ""))
            elif t in ("linebreak", "softbreak"):
                parts.append(" ")
            else:
                parts.append(_inline_text(child.get("children")))
        elif t == "link":
            inner = _inline_text(child.get("children"))
            url = (child.get("attrs") or {}).get("url", "")
            if inner and inner != url:
                parts.append(f"{inner} ({url})")
            else:
                parts.append(url)
        elif t == "image":
            inner = _inline_text(child.get("children"))
            url = (child.get("attrs") or {}).get("url", "")
            parts.append(f"[image: {inner or url}]")
        elif "children" in child:
            parts.append(_inline_text(child.get("children")))
        elif "raw" in child:
            parts.append(child.get("raw", ""))
    return "".join(parts)


def _list_items(node: dict) -> list[dict]:
    return [
        c for c in node.get("children", [])
        if c.get("type") in ("list_item", "task_list_item")
    ]


def _list_to_block(node: dict) -> Block:
    attrs = node.get("attrs") or {}
    ordered = bool(attrs.get("ordered"))
    items = _list_items(node)

    has_task = any(
        it.get("type") == "task_list_item"
        or (it.get("attrs") or {}).get("checked") is not None
        for it in items
    )
    if has_task:
        out: list[tuple[bool, str]] = []
        for it in items:
            checked = bool((it.get("attrs") or {}).get("checked"))
            out.append((checked, _flatten_list_item(it)))
        return Checklist(items=out)

    texts = [_flatten_list_item(it) for it in items]
    if ordered:
        start = int(attrs.get("start", 1))
        labeled = [f"{start + i}." for i in range(len(texts))]
        return Bullet(items=[f"{labeled[i]} {texts[i]}".strip() for i in range(len(texts))], marker="")
    return Bullet(items=texts, marker="•")


def _flatten_list_item(item: dict) -> str:
    parts: list[str] = []
    for child in item.get("children", []):
        t = child.get("type")
        if t == "block_text":
            parts.append(_inline_text(child.get("children")))
        elif t == "paragraph":
            parts.append(_inline_text(child.get("children")))
        elif t == "text":
            parts.append(child.get("raw", ""))
        elif "children" in child:
            parts.append(_inline_text(child.get("children")))
    return " ".join(p for p in parts if p).strip()


def _table_to_block(node: dict) -> Block:
    headers: list[str] = []
    rows: list[list[str]] = []
    for child in node.get("children", []):
        t = child.get("type")
        if t == "table_head":
            headers = [
                _inline_text(cell.get("children"))
                for cell in child.get("children", [])
                if cell.get("type") == "table_cell"
            ]
        elif t == "table_body":
            for tr in child.get("children", []):
                if tr.get("type") != "table_row":
                    continue
                rows.append([
                    _inline_text(cell.get("children"))
                    for cell in tr.get("children", [])
                    if cell.get("type") == "table_cell"
                ])
    return Table(headers=headers, rows=rows)


def _heading_size(level: int) -> str:
    return "large" if level <= 2 else "normal"


def markdown_to_blocks(content: str) -> list[Block]:
    """Convert a Markdown document string into a list of Block objects."""
    md = mistune.create_markdown(
        renderer=None,
        plugins=["task_lists", "table", "strikethrough"],
    )
    tokens = md(content)
    if isinstance(tokens, tuple):
        tokens = tokens[0]

    blocks: list[Block] = []
    for tok in tokens:
        t = tok.get("type")
        if t == "heading":
            level = int((tok.get("attrs") or {}).get("level", 1))
            text = _inline_text(tok.get("children"))
            blocks.append(Title(
                text=text,
                align="center" if level == 1 else "left",
                bold=True,
                size=_heading_size(level),
                underline=(level == 1),
            ))
        elif t == "paragraph":
            text = _inline_text(tok.get("children"))
            if text.strip():
                blocks.append(Paragraph(text=text))
        elif t == "list":
            blocks.append(_list_to_block(tok))
        elif t == "table":
            blocks.append(_table_to_block(tok))
        elif t == "thematic_break":
            blocks.append(Separator())
        elif t == "block_code":
            lang = (tok.get("attrs") or {}).get("info") or None
            blocks.append(Code(text=tok.get("raw", "").rstrip("\n"), language=lang))
        elif t == "block_quote":
            inner = "\n".join(
                _inline_text(c.get("children")) if c.get("type") == "paragraph"
                else c.get("raw", "")
                for c in tok.get("children", [])
            )
            if inner.strip():
                blocks.append(Paragraph(text="❝ " + inner))
        elif t == "blank_line":
            blocks.append(Spacer(height=8))
    return blocks
