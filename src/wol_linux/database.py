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
        values = self._computer_values(computer)
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

    def update_computer(self, computer: Computer) -> None:
        if computer.id is None:
            raise ValueError("Impossibile modificare un computer senza ID")
        values = self._computer_values(computer)
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE computers SET
                    name = ?, hostname = ?, ipv4 = ?, mac = ?, broadcast = ?,
                    wol_port = ?, vendor = ?, manufacturer = ?, model = ?,
                    serial_number = ?, bios = ?, group_name = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*values, computer.id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Computer non trovato")
            connection.commit()

    def delete_computers(self, computer_ids: list[int]) -> int:
        if not computer_ids:
            return 0
        placeholders = ",".join("?" for _ in computer_ids)
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                f"DELETE FROM computers WHERE id IN ({placeholders})",  # noqa: S608
                computer_ids,
            )
            connection.commit()
            return cursor.rowcount

    @staticmethod
    def _computer_values(computer: Computer) -> tuple[object, ...]:
        values = (
            computer.name.strip(), computer.hostname.strip(), computer.ipv4.strip(),
            normalize_mac(computer.mac), computer.broadcast.strip(), computer.wol_port,
            computer.vendor.strip(), computer.manufacturer.strip(), computer.model.strip(),
            computer.serial_number.strip(), computer.bios.strip(), computer.group_name.strip(),
            computer.notes.strip(),
        )
        if not values[0]:
            raise ValueError("Il nome del computer è obbligatorio")
        if not values[4]:
            raise ValueError("L'indirizzo broadcast è obbligatorio")
        if not 1 <= computer.wol_port <= 65535:
            raise ValueError("La porta deve essere compresa tra 1 e 65535")
        return values

    def list_computers(self) -> list[Computer]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM computers ORDER BY name COLLATE NOCASE").fetchall()
        return [
            Computer(**{field: row[field] for field in Computer.__dataclass_fields__})
            for row in rows
        ]
