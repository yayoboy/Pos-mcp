from dataclasses import dataclass, field
from pathlib import Path
import json
import os


@dataclass
class PreviewConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 7878
    auto_open: bool = True
    confirm_timeout: int = 120


@dataclass
class FontsConfig:
    fallback_chain: list[str] = field(default_factory=list)


@dataclass
class PrinterConfig:
    ip: str
    port: int = 9100
    width_px: int = 384
    timeout: int = 5
    cut_after_print: bool = True
    dither: bool = True
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    fonts: FontsConfig = field(default_factory=FontsConfig)


def _resolve_config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    env = os.environ.get("POS_MCP_CONFIG")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent / "pos-mcp.json"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _is_headless() -> bool:
    if _env_bool("POS_MCP_HEADLESS", False):
        return True
    # Linux convention: no DISPLAY / WAYLAND_DISPLAY means no GUI session
    if os.name == "posix" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return True
    return False


def load_config(path: Path | None = None) -> PrinterConfig:
    resolved = _resolve_config_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config not found: {resolved}")

    with open(resolved) as f:
        raw = json.load(f)

    printer = raw.get("printer", {})
    defaults = raw.get("defaults", {})
    preview = raw.get("preview", {})
    fonts = raw.get("fonts", {})

    auto_open_cfg = preview.get("auto_open", True)
    auto_open = _env_bool("POS_MCP_PREVIEW_AUTO_OPEN", auto_open_cfg)
    if auto_open and _is_headless():
        auto_open = False

    return PrinterConfig(
        ip=_env_str("POS_MCP_PRINTER_IP", printer["ip"]),
        port=_env_int("POS_MCP_PRINTER_PORT", printer.get("port", 9100)),
        width_px=_env_int("POS_MCP_PRINTER_WIDTH", printer.get("width_px", 384)),
        timeout=_env_int("POS_MCP_PRINTER_TIMEOUT", printer.get("timeout", 5)),
        cut_after_print=defaults.get("cut_after_print", True),
        dither=defaults.get("dither", True),
        preview=PreviewConfig(
            enabled=_env_bool("POS_MCP_PREVIEW_ENABLED", preview.get("enabled", True)),
            host=_env_str("POS_MCP_PREVIEW_HOST", preview.get("host", "127.0.0.1")),
            port=_env_int("POS_MCP_PREVIEW_PORT", preview.get("port", 7878)),
            auto_open=auto_open,
            confirm_timeout=_env_int(
                "POS_MCP_PREVIEW_TIMEOUT", preview.get("confirm_timeout", 120)
            ),
        ),
        fonts=FontsConfig(
            fallback_chain=fonts.get("fallback_chain", []),
        ),
    )
