from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

SYSTEM_FONT_SIZE_FALLBACK = 11


def system_font_size() -> int:
    """Return the desktop's effective default font size in points.

    GNOME stores the chosen font (including its point size) in gsettings.  The
    fontconfig fallback keeps the setting useful on lightweight desktops where
    gsettings is not installed, while the final fallback is the GTK default.
    """
    commands = (
        ["gsettings", "get", "org.gnome.desktop.interface", "font-name"],
        ["fc-match", "-f", "%{size}", "sans"],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)\s*['\"]?\s*$", result.stdout.strip())
        if match:
            return max(6, min(32, round(float(match.group(1)))))
    return SYSTEM_FONT_SIZE_FALLBACK


def font_directory() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "wake-on-lan-for-linux" / "fonts"


def install_font(source: str | Path) -> str:
    source_path = Path(source)
    if source_path.suffix.casefold() not in {".ttf", ".otf", ".ttc"}:
        raise ValueError("Seleziona un font TTF, OTF o TTC")
    if not source_path.is_file():
        raise ValueError("Il file del font non è valido")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source_path.name).strip(".-")
    if not safe_name:
        raise ValueError("Il nome del font non è valido")
    destination_dir = font_directory()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / safe_name
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(source_path.read_bytes())
    temporary.replace(destination)
    family = destination.stem
    try:
        scan = subprocess.run(
            ["fc-scan", "--format=%{family}", str(destination)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        detected = scan.stdout.strip().split(",", maxsplit=1)[0].strip()
        if scan.returncode == 0 and detected:
            family = detected
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        subprocess.run(
            ["fc-cache", "-f", str(destination_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return family
