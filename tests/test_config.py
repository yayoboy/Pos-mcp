import json
import tempfile
from pathlib import Path
from pos_mcp.config import PrinterConfig, load_config


def test_load_config_from_file():
    data = {
        "printer": {"ip": "10.0.0.5", "port": 9100, "width_px": 384, "timeout": 3},
        "defaults": {"cut_after_print": False, "dither": True},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        config = load_config(Path(f.name))

    assert config.ip == "10.0.0.5"
    assert config.port == 9100
    assert config.width_px == 384
    assert config.timeout == 3
    assert config.cut_after_print is False
    assert config.dither is True


def test_load_config_defaults():
    data = {
        "printer": {"ip": "192.168.1.1"},
        "defaults": {},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        config = load_config(Path(f.name))

    assert config.port == 9100
    assert config.width_px == 384
    assert config.timeout == 5
    assert config.cut_after_print is True
    assert config.dither is True


def test_load_config_file_not_found():
    try:
        load_config(Path("/nonexistent/config.json"))
        assert False, "Should have raised"
    except FileNotFoundError:
        pass


def test_env_overrides_take_precedence(monkeypatch):
    data = {"printer": {"ip": "1.1.1.1"}, "defaults": {}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        monkeypatch.setenv("POS_MCP_PRINTER_IP", "10.0.0.99")
        monkeypatch.setenv("POS_MCP_PRINTER_PORT", "9200")
        monkeypatch.setenv("POS_MCP_PREVIEW_HOST", "0.0.0.0")
        monkeypatch.setenv("POS_MCP_PREVIEW_PORT", "8000")
        monkeypatch.setenv("POS_MCP_PREVIEW_AUTO_OPEN", "false")
        config = load_config(Path(f.name))

    assert config.ip == "10.0.0.99"
    assert config.port == 9200
    assert config.preview.host == "0.0.0.0"
    assert config.preview.port == 8000
    assert config.preview.auto_open is False


def test_headless_env_disables_auto_open(monkeypatch):
    data = {"printer": {"ip": "1.1.1.1"}, "preview": {"auto_open": True}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        monkeypatch.setenv("POS_MCP_HEADLESS", "1")
        monkeypatch.delenv("POS_MCP_PREVIEW_AUTO_OPEN", raising=False)
        config = load_config(Path(f.name))

    assert config.preview.auto_open is False
