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

    return PrinterConfig(
        ip=printer["ip"],
        port=printer.get("port", 9100),
        width_px=printer.get("width_px", 384),
        timeout=printer.get("timeout", 5),
        cut_after_print=defaults.get("cut_after_print", True),
        dither=defaults.get("dither", True),
        preview=PreviewConfig(
            enabled=preview.get("enabled", True),
            host=preview.get("host", "127.0.0.1"),
            port=preview.get("port", 7878),
            auto_open=preview.get("auto_open", True),
            confirm_timeout=preview.get("confirm_timeout", 120),
        ),
        fonts=FontsConfig(
            fallback_chain=fonts.get("fallback_chain", []),
        ),
    )
