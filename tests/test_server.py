import pytest
import json
import io
import base64
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock


@pytest.fixture
def config_file(tmp_path):
    config = {
        "printer": {"ip": "192.168.1.100", "port": 9100, "width_px": 384, "timeout": 5},
        "defaults": {"cut_after_print": True, "dither": True},
    }
    path = tmp_path / "pos-mcp.json"
    path.write_text(json.dumps(config))
    return path


def test_server_has_all_tools(config_file):
    with patch("pos_mcp.server.CONFIG_PATH", config_file):
        from pos_mcp.server import mcp
        tools = mcp._tool_manager._tools
        tool_names = set(tools.keys())
        expected = {
            "print_text",
            "print_image",
            "print_diagram",
            "print_barcode",
            "print_blocks",
            "print_markdown",
        }
        assert expected <= tool_names


def test_print_text_preview(config_file):
    with patch("pos_mcp.server.CONFIG_PATH", config_file):
        from pos_mcp.server import print_text
        result = print_text("Hello World", preview=True)
        assert isinstance(result, list)
        assert result[0].type == "image"
        raw = base64.b64decode(result[0].data)
        img = Image.open(io.BytesIO(raw))
        assert img.width == 384


def test_print_diagram_preview_graphviz(config_file):
    with patch("pos_mcp.server.CONFIG_PATH", config_file):
        from pos_mcp.server import print_diagram
        result = print_diagram("digraph { A -> B }", engine="graphviz", preview=True)
        assert isinstance(result, list)
        assert result[0].type == "image"


@patch("pos_mcp.server.send_to_printer", return_value="OK")
def test_print_text_sends_to_printer(mock_send, config_file):
    with patch("pos_mcp.server.CONFIG_PATH", config_file):
        from pos_mcp.server import print_text
        result = print_text("Hello", preview=False)
        assert result == "OK"
        mock_send.assert_called_once()
