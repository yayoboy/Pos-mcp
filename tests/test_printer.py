import io
import base64
from PIL import Image
from unittest.mock import patch, MagicMock
from pos_mcp.printer import send_to_printer, preview_image
from pos_mcp.config import PrinterConfig


def _test_config() -> PrinterConfig:
    return PrinterConfig(ip="192.168.1.100", port=9100)


def test_preview_image_returns_base64_png():
    img = Image.new("1", (384, 100), color=1)
    result = preview_image(img)
    assert isinstance(result, str)
    raw = base64.b64decode(result)
    restored = Image.open(io.BytesIO(raw))
    assert restored.format == "PNG"


def test_preview_image_preserves_dimensions():
    img = Image.new("1", (384, 200), color=0)
    result = preview_image(img)
    raw = base64.b64decode(result)
    restored = Image.open(io.BytesIO(raw))
    assert restored.width == 384
    assert restored.height == 200


@patch("pos_mcp.printer.Network")
def test_send_text_to_printer(mock_network_cls):
    mock_printer = MagicMock()
    mock_network_cls.return_value = mock_printer
    config = _test_config()
    result = send_to_printer(
        config,
        text="Hello\n",
        text_options={"bold": True, "size": "large", "align": "center"},
        cut=True,
    )
    assert result == "OK"
    mock_network_cls.assert_called_once_with("192.168.1.100", port=9100, timeout=5)
    mock_printer.set.assert_called_once_with(align="CENTER", bold=True, width=2, height=2)
    mock_printer.text.assert_called_once_with("Hello\n")
    mock_printer.cut.assert_called_once()
    mock_printer.close.assert_called_once()


@patch("pos_mcp.printer.Network")
def test_send_image_to_printer(mock_network_cls):
    mock_printer = MagicMock()
    mock_network_cls.return_value = mock_printer
    config = _test_config()
    img = Image.new("1", (384, 100), color=1)
    result = send_to_printer(config, image=img, cut=False)
    assert result == "OK"
    mock_printer.image.assert_called_once_with(img)
    mock_printer.cut.assert_not_called()
    mock_printer.close.assert_called_once()


@patch("pos_mcp.printer.Network")
def test_send_qr_to_printer(mock_network_cls):
    mock_printer = MagicMock()
    mock_network_cls.return_value = mock_printer
    config = _test_config()
    result = send_to_printer(
        config,
        barcode_data="https://example.com",
        barcode_type="qr",
        barcode_label="Scan me",
        cut=True,
    )
    assert result == "OK"
    mock_printer.qr.assert_called_once_with("https://example.com", size=6)
    mock_printer.cut.assert_called_once()
