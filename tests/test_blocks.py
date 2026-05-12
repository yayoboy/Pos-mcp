import pytest
from PIL import Image

from pos_mcp.blocks import (
    Block,
    Bullet,
    Box,
    Checklist,
    Code,
    KeyValue,
    Paragraph,
    RenderContext,
    Separator,
    Spacer,
    Table,
    Title,
    block_from_dict,
    compose,
)


@pytest.fixture
def ctx():
    return RenderContext(width_px=384)


def test_spacer_height(ctx):
    img = Spacer(height=25).render(ctx)
    assert img.size == (384, 25)


def test_separator_renders(ctx):
    for style in ("solid", "dashed", "dotted"):
        img = Separator(style=style).render(ctx)
        assert img.width == 384
        assert img.height > 0


def test_title_renders_with_underline(ctx):
    img = Title("Hello").render(ctx)
    assert img.width == 384
    pixels = img.load()
    # Underline row near bottom should contain dark pixels.
    bottom_row = img.height - 5
    assert any(pixels[x, bottom_row] < 128 for x in range(50, 300))


def test_paragraph_word_wraps(ctx):
    long = "word " * 200
    img = Paragraph(long).render(ctx)
    assert img.width == 384
    assert img.height > 300  # many wrapped lines


def test_bullet_with_multiline_items(ctx):
    img = Bullet(items=["short", "a much longer item " * 8]).render(ctx)
    assert img.width == 384
    assert img.height > 50


def test_checklist_renders(ctx):
    items = [(True, "done item"), (False, "todo item with longer text " * 3)]
    img = Checklist(items=items).render(ctx)
    assert img.width == 384


def test_keyvalue_renders(ctx):
    img = KeyValue(pairs=[("Resistor", "4.7kΩ"), ("Tolerance", "1%")]).render(ctx)
    assert img.width == 384


def test_table_renders(ctx):
    img = Table(
        headers=["Pin", "Function"],
        rows=[["1", "VCC"], ["2", "GND"], ["3", "OUT"]],
    ).render(ctx)
    assert img.width == 384


def test_code_renders_with_language(ctx):
    img = Code(text="print('hello')\nprint('world')", language="python").render(ctx)
    assert img.width == 384


def test_box_wraps_inner_block(ctx):
    inner = Paragraph("Boxed text")
    img = Box(inner=inner).render(ctx)
    assert img.width == 384
    # Border should produce black pixels on every edge.
    pixels = img.load()
    assert pixels[0, img.height // 2] < 128 or pixels[1, img.height // 2] < 128


def test_compose_stacks_vertically(ctx):
    blocks: list[Block] = [Title("A"), Separator(), Paragraph("B")]
    img = compose(blocks, ctx)
    assert img.width == 384
    assert img.mode == "1"


def test_compose_empty(ctx):
    img = compose([], ctx)
    assert img.width == 384


def test_block_from_dict_title():
    b = block_from_dict({"type": "title", "text": "Hi"})
    assert isinstance(b, Title)
    assert b.text == "Hi"


def test_block_from_dict_checklist_dicts():
    b = block_from_dict({
        "type": "checklist",
        "items": [{"checked": True, "text": "a"}, {"checked": False, "text": "b"}],
    })
    assert isinstance(b, Checklist)
    assert b.items == [(True, "a"), (False, "b")]


def test_block_from_dict_keyvalue_pairs():
    b = block_from_dict({
        "type": "keyvalue",
        "pairs": [{"key": "k", "value": "v"}, ["k2", "v2"]],
    })
    assert isinstance(b, KeyValue)
    assert b.pairs == [("k", "v"), ("k2", "v2")]


def test_block_from_dict_box_recursive():
    b = block_from_dict({
        "type": "box",
        "inner": {"type": "paragraph", "text": "inside"},
    })
    assert isinstance(b, Box)
    assert isinstance(b.inner, Paragraph)


def test_block_from_dict_unknown():
    with pytest.raises(ValueError):
        block_from_dict({"type": "nonexistent"})
