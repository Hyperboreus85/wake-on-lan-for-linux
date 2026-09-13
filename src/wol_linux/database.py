from __future__ import annotations

import ipaddress
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .i18n import tr as _
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
            raise ValueError(_("Impossibile modificare un computer senza ID"))
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
                raise ValueError(_("Computer non trovato"))
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

    def clear_computers(self) -> int:
        """Remove every saved computer and return the number removed."""
        with closing(self.connect()) as connection:
            cursor = connection.execute("DELETE FROM computers")
            connection.commit()
            return cursor.rowcount

    def import_computers(self, computers: list[Computer]) -> int:
        prepared = [self._computer_values(computer) for computer in computers]
        if not prepared:
            return 0
        with closing(self.connect()) as connection:
            connection.executemany(
                """
                INSERT INTO computers (
                    name, hostname, ipv4, mac, broadcast, wol_port, vendor,
                    manufacturer, model, serial_number, bios, group_name, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mac) DO UPDATE SET
                    name = excluded.name,
                    hostname = excluded.hostname,
                    ipv4 = excluded.ipv4,
                    broadcast = excluded.broadcast,
                    wol_port = excluded.wol_port,
                    vendor = excluded.vendor,
                    manufacturer = excluded.manufacturer,
                    model = excluded.model,
                    serial_number = excluded.serial_number,
                    bios = excluded.bios,
                    group_name = excluded.group_name,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                prepared,
            )
            connection.commit()
        return len(prepared)

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
            raise ValueError(_("Il nome host o l'indirizzo IP è obbligatorio"))
        if not values[4]:
            raise ValueError(_("L'indirizzo broadcast è obbligatorio"))
        if not 1 <= computer.wol_port <= 65535:
            raise ValueError(_("La porta deve essere compresa tra 1 e 65535"))
        return values

    def list_computers(self) -> list[Computer]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM computers").fetchall()
        computers = [
            Computer(**{field: row[field] for field in Computer.__dataclass_fields__})
            for row in rows
        ]
        return sorted(computers, key=self._computer_sort_key)

    @staticmethod
    def _computer_sort_key(computer: Computer) -> tuple[int, int, str]:
        try:
            address = ipaddress.ip_address(computer.ipv4)
        except ValueError:
            return (1, 0, computer.name.casefold())
        if not isinstance(address, ipaddress.IPv4Address):
            return (1, 0, computer.name.casefold())
        return (0, int(address), computer.name.casefold())
