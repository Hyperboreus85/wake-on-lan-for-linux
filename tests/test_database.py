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

    def test_update_computer(self) -> None:
        with TemporaryDirectory() as directory:
            database = Database(f"{directory}/test.db")
            computer_id = database.add_computer(Computer(name="Vecchio", mac="00:11:22:33:44:55"))
            computer = database.list_computers()[0]
            self.assertEqual(computer.id, computer_id)

            computer.name = "Nuovo"
            computer.ipv4 = "192.168.1.25"
            database.update_computer(computer)

            updated = database.list_computers()[0]
            self.assertEqual(updated.name, "Nuovo")
            self.assertEqual(updated.ipv4, "192.168.1.25")

    def test_delete_computers(self) -> None:
        with TemporaryDirectory() as directory:
            database = Database(f"{directory}/test.db")
            first = database.add_computer(Computer(name="Uno", mac="00:11:22:33:44:55"))
            second = database.add_computer(Computer(name="Due", mac="00:11:22:33:44:66"))

            self.assertEqual(database.delete_computers([first, second]), 2)
            self.assertEqual(database.list_computers(), [])

    def test_computers_are_sorted_by_numeric_ipv4(self) -> None:
        with TemporaryDirectory() as directory:
            database = Database(f"{directory}/test.db")
            database.add_computer(
                Computer(name="Centoventi", mac="00:11:22:33:44:01", ipv4="192.168.10.120")
            )
            database.add_computer(
                Computer(name="Undici", mac="00:11:22:33:44:02", ipv4="192.168.10.11")
            )
            database.add_computer(
                Computer(name="Cinque", mac="00:11:22:33:44:03", ipv4="192.168.10.5")
            )

            self.assertEqual(
                [computer.ipv4 for computer in database.list_computers()],
                ["192.168.10.5", "192.168.10.11", "192.168.10.120"],
            )
