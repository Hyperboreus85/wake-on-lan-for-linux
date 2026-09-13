from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

THEMES = ("system", "light", "dark")
ACCENTS = ("ubuntu", "blue", "green", "purple", "red")


def default_settings_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "wake-on-lan-for-linux" / "settings.json"


@dataclass(slots=True)
class AppSettings:
    theme: str = "system"
    accent: str = "ubuntu"
    language: str = "system"

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppSettings:
        settings_path = Path(path) if path else default_settings_path()
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return cls()
        return cls(
            theme=payload.get("theme") if payload.get("theme") in THEMES else "system",
            accent=payload.get("accent") if payload.get("accent") in ACCENTS else "ubuntu",
            language=str(payload.get("language", "system")),
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
