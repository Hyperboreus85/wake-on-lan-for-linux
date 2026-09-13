import ipaddress
import unittest

from wol_linux.network import parse_hostname, parse_neighbours, parse_routes


class NetworkParsingTests(unittest.TestCase):
    def test_parse_routes_prefers_default_interface(self) -> None:
        routes = """
        [
          {"dst":"default","gateway":"192.168.10.1","dev":"enp3s0"},
          {"dst":"172.17.0.0/16","dev":"docker0","prefsrc":"172.17.0.1"},
          {"dst":"192.168.10.0/24","dev":"enp3s0","prefsrc":"192.168.10.20"}
        ]
        """
        result = parse_routes(routes)
        self.assertEqual(str(result.network), "192.168.10.0/24")
        self.assertEqual(result.interface, "enp3s0")

    def test_parse_neighbours_filters_invalid_entries(self) -> None:
        neighbours = """
        [
          {"dst":"192.168.10.2","lladdr":"aa:bb:cc:dd:ee:ff","state":["REACHABLE"]},
          {"dst":"192.168.10.3","state":["INCOMPLETE"]},
          {"dst":"10.0.0.2","lladdr":"00:11:22:33:44:55","state":["STALE"]}
        ]
        """
        result = parse_neighbours(neighbours, ipaddress.ip_network("192.168.10.0/24"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ipv4, "192.168.10.2")
        self.assertEqual(result[0].mac, "AA:BB:CC:DD:EE:FF")

    def test_parse_hostname_from_getent_output(self) -> None:
        self.assertEqual(
            parse_hostname("192.168.10.7 pve1.lan pve1\n", "192.168.10.7"),
            "pve1.lan",
        )

    def test_parse_hostname_returns_empty_when_unknown(self) -> None:
        self.assertEqual(parse_hostname("", "192.168.10.7"), "")
