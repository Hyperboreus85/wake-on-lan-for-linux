import sqlite3
import unittest

from wol_linux.database import Database
from wol_linux.models import Computer


from tempfile import TemporaryDirectory


class DatabaseTests(unittest.TestCase):
    def test_add_and_list_computer(self) -> None:
        with TemporaryDirectory() as directory:
            database = Database(f"{directory}/test.db")
            computer_id = database.add_computer(
                Computer(name="PC Studio", mac="aa-bb-cc-dd-ee-ff", ipv4="192.168.1.20")
            )

            computers = database.list_computers()
            self.assertEqual(computer_id, 1)
            self.assertEqual(len(computers), 1)
            self.assertEqual(computers[0].name, "PC Studio")
            self.assertEqual(computers[0].mac, "AA:BB:CC:DD:EE:FF")

    def test_duplicate_mac_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            database = Database(f"{directory}/test.db")
            database.add_computer(Computer(name="Primo", mac="AA:BB:CC:DD:EE:FF"))

            with self.assertRaises(sqlite3.IntegrityError):
                database.add_computer(Computer(name="Secondo", mac="aa-bb-cc-dd-ee-ff"))
