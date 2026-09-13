import unittest

from tempfile import TemporaryDirectory

from wol_linux.backup import export_backup, load_backup
from wol_linux.models import Computer
from wol_linux.settings import AppSettings


class BackupTests(unittest.TestCase):
    def test_complete_backup_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/backup.json"
            settings = AppSettings(theme="dark", accent="blue", language="en")
            computers = [
                Computer(
                    name="NAS",
                    hostname="nas.lan",
                    ipv4="192.168.1.5",
                    mac="AA:BB:CC:DD:EE:FF",
                    notes="Archivio principale",
                )
            ]
            export_backup(path, settings, computers, translations={})
            restored = load_backup(path)
            self.assertEqual(restored.settings, settings)
            self.assertEqual(restored.computers, computers)
            self.assertEqual(restored.translations, {})

    def test_invalid_backup_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/backup.json"
            with open(path, "w", encoding="utf-8") as stream:
                stream.write('{"format":"wrong","version":1}')
            with self.assertRaises(ValueError):
                load_backup(path)
