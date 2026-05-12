from pos_mcp.fonts import is_pure_ascii, build_fallback_chain, render_unicode_line


def test_is_pure_ascii_true():
    assert is_pure_ascii("Hello World")
    assert is_pure_ascii("ABC 123 !@#")
    assert is_pure_ascii("line1\nline2")
    assert is_pure_ascii("")


def test_is_pure_ascii_false():
    assert not is_pure_ascii("Caffè")
    assert not is_pure_ascii("日本語")
    assert not is_pure_ascii("Hello €")
    assert not is_pure_ascii("emoji 🙂")


def test_build_fallback_chain_returns_at_least_one_font():
    chain = build_fallback_chain()
    assert len(chain) >= 1, "Expected at least one system font; install fonts-dejavu or fonts-noto"


def test_render_unicode_line_produces_image():
    chain = build_fallback_chain()
    if not chain:
        return
    img = render_unicode_line("Hello", chain, size=20)
    assert img.width > 0
    assert img.height > 0
    assert img.mode == "RGBA"
