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
