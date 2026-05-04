import io
import base64
from PIL import Image
from pos_mcp.renderer import render_text, render_dot, render_matplotlib, prepare_image


def test_render_text_returns_1bit_image():
    img = render_text("Hello World", width_px=384)
    assert isinstance(img, Image.Image)
    assert img.mode == "1"
    assert img.width == 384


def test_render_text_multiline():
    img = render_text("Line 1\nLine 2\nLine 3", width_px=384)
    assert img.height > 50


def test_render_text_bold_larger():
    img_normal = render_text("Test", width_px=384, bold=False, size="normal")
    img_bold = render_text("Test", width_px=384, bold=True, size="large")
    assert img_bold.height >= img_normal.height


def test_render_dot_simple_graph():
    dot_code = "digraph { A -> B -> C }"
    img = render_dot(dot_code, width_px=384)
    assert isinstance(img, Image.Image)
    assert img.mode == "1"
    assert img.width == 384


def test_render_dot_invalid_code():
    try:
        render_dot("not valid dot {{{{", width_px=384)
        assert False, "Should have raised"
    except ValueError:
        pass


def test_render_matplotlib_simple_plot():
    code = """
import matplotlib.pyplot as plt
plt.figure(figsize=(4, 3))
plt.plot([1, 2, 3], [1, 4, 9])
plt.title("Test")
"""
    img = render_matplotlib(code, width_px=384)
    assert isinstance(img, Image.Image)
    assert img.mode == "1"
    assert img.width == 384


def test_render_matplotlib_invalid_code():
    try:
        render_matplotlib("raise ValueError('bad')", width_px=384)
        assert False, "Should have raised"
    except ValueError:
        pass


def test_render_matplotlib_blocked_import():
    # Test that dangerous imports are blocked by the security filter
    blocked_code = "import os; os.listdir('.')"
    try:
        render_matplotlib(blocked_code, width_px=384)
        assert False, "Should have raised"
    except ValueError as e:
        assert "not allowed" in str(e).lower()


def test_prepare_image_from_base64():
    src = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    img = prepare_image(b64, width_px=384, dither=True)
    assert isinstance(img, Image.Image)
    assert img.mode == "1"
    assert img.width == 384


def test_prepare_image_invalid_base64():
    try:
        prepare_image("not-valid-base64!!!", width_px=384, dither=True)
        assert False, "Should have raised"
    except ValueError:
        pass
