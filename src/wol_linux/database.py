from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import Computer
from .wol import normalize_mac


def default_database_path() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "wake-on-lan-for-linux" / "wol-linux.db"


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS computers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    hostname TEXT NOT NULL DEFAULT '',
                    ipv4 TEXT NOT NULL DEFAULT '',
                    mac TEXT NOT NULL UNIQUE,
                    broadcast TEXT NOT NULL DEFAULT '255.255.255.255',
                    wol_port INTEGER NOT NULL DEFAULT 9 CHECK (wol_port BETWEEN 1 AND 65535),
                    vendor TEXT NOT NULL DEFAULT '',
                    manufacturer TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    serial_number TEXT NOT NULL DEFAULT '',
                    bios TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    last_seen TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def add_computer(self, computer: Computer) -> int:
        values = (
            computer.name.strip(), computer.hostname.strip(), computer.ipv4.strip(),
            normalize_mac(computer.mac), computer.broadcast.strip(), computer.wol_port,
            computer.vendor.strip(), computer.manufacturer.strip(), computer.model.strip(),
            computer.serial_number.strip(), computer.bios.strip(), computer.group_name.strip(),
            computer.notes.strip(),
        )
        if not values[0]:
            raise ValueError("Il nome del computer è obbligatorio")
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO computers (
                    name, hostname, ipv4, mac, broadcast, wol_port, vendor,
                    manufacturer, model, serial_number, bios, group_name, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_computers(self) -> list[Computer]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM computers ORDER BY name COLLATE NOCASE").fetchall()
        return [
            Computer(**{field: row[field] for field in Computer.__dataclass_fields__})
            for row in rows
        ]

