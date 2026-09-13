from __future__ import annotations

import re
import socket

_MAC_PATTERN = re.compile(r"^[0-9A-Fa-f]{12}$")


def normalize_mac(mac_address: str) -> str:
    compact = mac_address.strip().replace(":", "").replace("-", "").replace(".", "")
    if not _MAC_PATTERN.fullmatch(compact):
        raise ValueError("Indirizzo MAC non valido")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2)).upper()


def build_magic_packet(mac_address: str) -> bytes:
    mac_bytes = bytes.fromhex(normalize_mac(mac_address).replace(":", ""))
    return b"\xff" * 6 + mac_bytes * 16


def wake(mac_address: str, broadcast: str = "255.255.255.255", port: int = 9) -> int:
    if not 1 <= port <= 65535:
        raise ValueError("La porta deve essere compresa tra 1 e 65535")

    packet = build_magic_packet(mac_address)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock.sendto(packet, (broadcast, port))

