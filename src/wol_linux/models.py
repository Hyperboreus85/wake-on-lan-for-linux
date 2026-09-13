from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Computer:
    name: str
    mac: str
    id: int | None = None
    hostname: str = ""
    ipv4: str = ""
    broadcast: str = "255.255.255.255"
    wol_port: int = 9
    vendor: str = ""
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    bios: str = ""
    group_name: str = ""
    notes: str = ""

