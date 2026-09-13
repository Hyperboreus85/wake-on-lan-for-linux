from __future__ import annotations

import ipaddress
import json
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from .i18n import tr as _
from .wol import normalize_mac

MAX_SCAN_HOSTS = 1024


@dataclass(frozen=True, slots=True)
class LocalNetwork:
    network: ipaddress.IPv4Network
    interface: str


@dataclass(frozen=True, slots=True)
class DiscoveredHost:
    ipv4: str
    mac: str
    hostname: str = ""


@dataclass(frozen=True, slots=True)
class ScanResult:
    local_network: LocalNetwork
    hosts: tuple[DiscoveredHost, ...]


def parse_routes(payload: str) -> LocalNetwork:
    routes = json.loads(payload)
    default_interface = next(
        (route.get("dev") for route in routes if route.get("dst") == "default" and route.get("dev")),
        None,
    )
    candidates: list[LocalNetwork] = []
    for route in routes:
        destination = route.get("dst", "")
        interface = route.get("dev", "")
        source = route.get("prefsrc") or route.get("src")
        if not destination or destination == "default" or not interface or not source:
            continue
        try:
            network = ipaddress.ip_network(destination, strict=False)
            address = ipaddress.ip_address(source)
        except ValueError:
            continue
        if (
            isinstance(network, ipaddress.IPv4Network)
            and address in network
            and not network.is_loopback
            and not network.is_link_local
        ):
            candidates.append(LocalNetwork(network=network, interface=interface))

    if default_interface:
        preferred = [item for item in candidates if item.interface == default_interface]
        if preferred:
            candidates = preferred
    if not candidates:
        raise RuntimeError(_("Nessuna rete IPv4 locale rilevata"))
    return max(candidates, key=lambda item: item.network.prefixlen)


def parse_neighbours(payload: str, network: ipaddress.IPv4Network) -> list[DiscoveredHost]:
    neighbours = json.loads(payload)
    found: dict[str, DiscoveredHost] = {}
    for neighbour in neighbours:
        address = neighbour.get("dst", "")
        mac = neighbour.get("lladdr", "")
        state = neighbour.get("state", [])
        if isinstance(state, str):
            state = [state]
        if not address or not mac or {item.upper() for item in state} & {"FAILED", "INCOMPLETE"}:
            continue
        try:
            ipv4 = ipaddress.ip_address(address)
            normalized_mac = normalize_mac(mac)
        except ValueError:
            continue
        if isinstance(ipv4, ipaddress.IPv4Address) and ipv4 in network:
            found[str(ipv4)] = DiscoveredHost(ipv4=str(ipv4), mac=normalized_mac)
    return sorted(found.values(), key=lambda item: ipaddress.ip_address(item.ipv4))


def parse_hostname(payload: str, address: str) -> str:
    for line in payload.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == address:
            hostname = fields[1].rstrip(".")
            if hostname != address:
                return hostname
    return ""


def parse_avahi_hostname(payload: str, address: str) -> str:
    """Parse ``avahi-resolve-address`` output (address + hostname)."""
    return parse_hostname(payload, address)


def parse_nmblookup_hostname(payload: str, address: str) -> str:
    """Extract a NetBIOS computer name from ``nmblookup -A`` output."""
    del address  # NetBIOS output does not repeat the queried address.
    for line in payload.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[1] != "<00>":
            continue
        name = fields[0].strip()
        if name and name != "__MSBROWSE__" and not name.endswith("GROUP"):
            return name
    return ""


def _reverse_dns_hostname(address: str) -> str:
    try:
        hostname, _service = socket.getnameinfo(
            (address, 0), socket.NI_NAMEREQD
        )
    except (OSError, socket.gaierror):
        return ""
    return "" if hostname == address else hostname.rstrip(".")


def _command_hostname(command: list[str], address: str, parser: Callable[[str, str], str]) -> str:
    if shutil.which(command[0]) is None:
        return ""
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return parser(process.stdout, address)


def resolve_hostname(address: str) -> str:
    """Resolve a host using local NSS, DNS, mDNS, and optional NetBIOS."""
    try:
        process = subprocess.run(
            ["getent", "hosts", address],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        process = None
    if process is not None:
        hostname = parse_hostname(process.stdout, address)
        if hostname:
            return hostname

    hostname = _reverse_dns_hostname(address)
    if hostname:
        return hostname

    hostname = _command_hostname(
        ["avahi-resolve-address", "-4", address], address, parse_avahi_hostname
    )
    if hostname:
        return hostname
    return _command_hostname(["nmblookup", "-A", address], address, parse_nmblookup_hostname)


def detect_local_network() -> LocalNetwork:
    try:
        process = subprocess.run(
            ["ip", "-j", "-4", "route", "show"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(_("Impossibile rilevare la rete locale: {error}").format(error=exc)) from exc
    return parse_routes(process.stdout)


def ping_host(address: str, timeout: int = 1) -> bool | None:
    if not address.strip():
        return None
    try:
        process = subprocess.run(
            ["ping", "-n", "-c", "1", "-W", str(timeout), address],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return process.returncode == 0


def parse_neighbour_status(
    payload: str,
    address: str,
    expected_mac: str = "",
) -> bool | None:
    """Determine whether the kernel neighbour table sees ``address`` online.

    ARP/NDP entries are useful when a host firewall drops ICMP echo requests.
    A matching MAC in any usable neighbour state is treated as reachable;
    failed or incomplete entries are treated as unreachable.
    """
    active_states = {"REACHABLE", "STALE", "DELAY", "PROBE", "PERMANENT"}
    failed_states = {"FAILED", "INCOMPLETE", "NOARP", "NONE"}
    normalized_expected = ""
    if expected_mac:
        try:
            normalized_expected = normalize_mac(expected_mac)
        except ValueError:
            return None

    for line in payload.splitlines():
        fields = line.split()
        if not fields or fields[0] != address:
            continue
        mac = ""
        if "lladdr" in fields:
            mac_index = fields.index("lladdr") + 1
            if mac_index < len(fields):
                mac = fields[mac_index]
        if normalized_expected:
            try:
                if normalize_mac(mac) != normalized_expected:
                    continue
            except ValueError:
                continue
        state = next(
            (field.upper() for field in fields if field.upper() in active_states | failed_states),
            "",
        )
        if state in active_states:
            return True
        if state in failed_states:
            return False
    return None


def neighbour_host(address: str, expected_mac: str = "") -> bool | None:
    """Read one host's kernel neighbour entry as an ICMP fallback."""
    if not address.strip():
        return None
    try:
        process = subprocess.run(
            ["ip", "neigh", "show", address],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_neighbour_status(process.stdout, address, expected_mac)


def check_host_status(address: str, expected_mac: str = "") -> bool | None:
    """Check reachability using ICMP first, then the neighbour table."""
    status = ping_host(address)
    if status is True:
        return True
    neighbour_status = neighbour_host(address, expected_mac)
    if neighbour_status is not None:
        return neighbour_status
    return status


def scan_local_network(
    progress: Callable[[int, int], None] | None = None,
) -> ScanResult:
    local_network = detect_local_network()
    addresses = [str(address) for address in local_network.network.hosts()]
    if len(addresses) > MAX_SCAN_HOSTS:
        raise RuntimeError(
            _("La rete {network} contiene {count} host. ").format(
                network=local_network.network,
                count=len(addresses),
            )
            + _("Per sicurezza la scansione è limitata a {limit}.").format(
                limit=MAX_SCAN_HOSTS
            )
        )

    completed = 0
    with ThreadPoolExecutor(max_workers=min(48, max(1, len(addresses)))) as executor:
        futures = [executor.submit(ping_host, address) for address in addresses]
        for _future in as_completed(futures):
            completed += 1
            if progress:
                progress(completed, len(addresses))

    try:
        process = subprocess.run(
            ["ip", "-j", "neigh", "show", "dev", local_network.interface],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            _("Impossibile leggere i dispositivi rilevati: {error}").format(error=exc)
        ) from exc
    hosts = parse_neighbours(process.stdout, local_network.network)
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(hosts)))) as executor:
        hostnames = list(executor.map(lambda host: resolve_hostname(host.ipv4), hosts))
    resolved_hosts = tuple(
        DiscoveredHost(ipv4=host.ipv4, mac=host.mac, hostname=hostname)
        for host, hostname in zip(hosts, hostnames, strict=True)
    )
    return ScanResult(local_network=local_network, hosts=resolved_hosts)
