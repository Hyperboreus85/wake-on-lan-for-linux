from __future__ import annotations

import sys


def main() -> int:
    try:
        from .application import WakeLanApplication
    except (ImportError, ValueError) as exc:
        print(
            "GTK 4/Libadwaita non disponibili. Esegui ./scripts/bootstrap-ubuntu.sh "
            f"su Ubuntu. Dettaglio: {exc}",
            file=sys.stderr,
        )
        return 2

    app = WakeLanApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

