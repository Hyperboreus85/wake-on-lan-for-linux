import unittest

from wol_linux.wol import build_magic_packet, normalize_mac


class WakeOnLanTests(unittest.TestCase):
    def test_normalize_mac_accepts_common_formats(self) -> None:
        self.assertEqual(normalize_mac("aa-bb-cc-dd-ee-ff"), "AA:BB:CC:DD:EE:FF")
        self.assertEqual(normalize_mac("aabb.ccdd.eeff"), "AA:BB:CC:DD:EE:FF")

    def test_normalize_mac_rejects_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            normalize_mac("not-a-mac")

    def test_magic_packet_has_expected_shape(self) -> None:
        packet = build_magic_packet("01:23:45:67:89:AB")
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], bytes.fromhex("0123456789AB") * 16)
