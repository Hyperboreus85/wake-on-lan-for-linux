from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

THEMES = ("system", "light", "dark")
ACCENTS = ("ubuntu", "blue", "green", "purple", "red")
PALETTE_KEYS = ("accent", "button", "text", "background")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
COLUMN_WIDTH_DEFAULTS = {
    "select": 4,
    "ipv4": 16,
    "name": 28,
    "mac": 20,
    "status": 8,
    "vendor": 22,
    "manufacturer": 22,
    "model": 20,
    "serial_number": 20,
    "bios": 18,
    "group": 16,
    "notes": 30,
    "broadcast": 18,
    "port": 10,
}


def default_settings_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "wake-on-lan-for-linux" / "settings.json"


@dataclass(slots=True)
class AppSettings:
    theme: str = "system"
    accent: str = "ubuntu"
    language: str = "en"
    custom_colors: dict[str, str] = field(default_factory=dict)
    font_family: str = ""
    column_widths: dict[str, int] = field(default_factory=lambda: dict(COLUMN_WIDTH_DEFAULTS))

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppSettings:
        settings_path = Path(path) if path else default_settings_path()
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return cls()
        raw_colors = payload.get("custom_colors", {})
        custom_colors = {
            str(key): str(value).upper()
            for key, value in raw_colors.items()
            if key in PALETTE_KEYS and isinstance(value, str) and HEX_COLOR.fullmatch(value)
        } if isinstance(raw_colors, dict) else {}
        raw_font = payload.get("font_family", "")
        font_family = str(raw_font).strip() if isinstance(raw_font, str) else ""
        raw_widths = payload.get("column_widths", {})
        column_widths = dict(COLUMN_WIDTH_DEFAULTS)
        if isinstance(raw_widths, dict):
            for key, value in raw_widths.items():
                if key in column_widths:
                    try:
                        column_widths[key] = max(4, min(60, int(value)))
                    except (TypeError, ValueError):
                        continue
        return cls(
            theme=payload.get("theme") if payload.get("theme") in THEMES else "system",
            accent=payload.get("accent") if payload.get("accent") in ACCENTS else "ubuntu",
            language=str(payload.get("language", "en")),
            custom_colors=custom_colors,
            font_family=font_family,
            column_widths=column_widths,
        )

    def save(self, path: str | Path | None = None) -> None:
        settings_path = Path(path) if path else default_settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = settings_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(settings_path)
