from pos_mcp.blocks import (
    Bullet,
    Checklist,
    Code,
    Paragraph,
    Separator,
    Table,
    Title,
)
from pos_mcp.markdown_render import markdown_to_blocks


def test_heading_becomes_title():
    blocks = markdown_to_blocks("# Hello")
    assert any(isinstance(b, Title) and b.text == "Hello" for b in blocks)


def test_paragraph():
    blocks = markdown_to_blocks("Just a paragraph.")
    paragraphs = [b for b in blocks if isinstance(b, Paragraph)]
    assert paragraphs
    assert "paragraph" in paragraphs[0].text.lower()


def test_unordered_list():
    blocks = markdown_to_blocks("- a\n- b\n- c")
    bullets = [b for b in blocks if isinstance(b, Bullet)]
    assert bullets
    assert bullets[0].items == ["a", "b", "c"]


def test_ordered_list():
    blocks = markdown_to_blocks("1. first\n2. second")
    bullets = [b for b in blocks if isinstance(b, Bullet)]
    assert bullets
    assert bullets[0].items[0].startswith("1.")
    assert bullets[0].items[1].startswith("2.")


def test_task_list_becomes_checklist():
    md = "- [x] done\n- [ ] todo"
    blocks = markdown_to_blocks(md)
    checklists = [b for b in blocks if isinstance(b, Checklist)]
    assert checklists
    assert checklists[0].items == [(True, "done"), (False, "todo")]


def test_table():
    md = "| H1 | H2 |\n|---|---|\n| a | b |\n| c | d |"
    blocks = markdown_to_blocks(md)
    tables = [b for b in blocks if isinstance(b, Table)]
    assert tables
    assert tables[0].headers == ["H1", "H2"]
    assert tables[0].rows == [["a", "b"], ["c", "d"]]


def test_hr_becomes_separator():
    blocks = markdown_to_blocks("para\n\n---\n\nmore")
    assert any(isinstance(b, Separator) for b in blocks)


def test_code_block_with_language():
    md = "```python\nx = 1\n```"
    blocks = markdown_to_blocks(md)
    codes = [b for b in blocks if isinstance(b, Code)]
    assert codes
    assert codes[0].language == "python"
    assert "x = 1" in codes[0].text


def test_inline_link_flattens_with_url():
    blocks = markdown_to_blocks("See [docs](https://example.com) for more.")
    paragraphs = [b for b in blocks if isinstance(b, Paragraph)]
    assert paragraphs
    assert "https://example.com" in paragraphs[0].text
