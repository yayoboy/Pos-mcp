from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class PrinterConfig:
    ip: str
    port: int = 9100
    width_px: int = 384
    timeout: int = 5
    cut_after_print: bool = True
    dither: bool = True


def load_config(path: Path) -> PrinterConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        raw = json.load(f)

    printer = raw.get("printer", {})
    defaults = raw.get("defaults", {})

    return PrinterConfig(
        ip=printer["ip"],
        port=printer.get("port", 9100),
        width_px=printer.get("width_px", 384),
        timeout=printer.get("timeout", 5),
        cut_after_print=defaults.get("cut_after_print", True),
        dither=defaults.get("dither", True),
    )
