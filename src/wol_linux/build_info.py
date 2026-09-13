from __future__ import annotations

import subprocess
from pathlib import Path


def build_revision() -> str:
    """Return the short source revision, or a package fallback."""
    project_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=0.5,
        )
    except (OSError, subprocess.SubprocessError):
        return "package"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "package"
