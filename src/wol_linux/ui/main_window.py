from __future__ import annotations

import sqlite3

from gi.repository import Adw, Gtk

from ..database import Database
from ..models import Computer
from ..wol import wake


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, database: Database) -> None:
        super().__init__(application=application, title="Wake on LAN for Linux")
        self.database = database
        self.set_default_size(920, 600)

        header = Adw.HeaderBar()
        add_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Aggiungi computer")
        add_button.connect("clicked", self._show_add_dialog)
        header.pack_start(add_button)

        self.wake_button = Gtk.Button(label="Sveglia")
        self.wake_button.add_css_class("suggested-action")
        self.wake_button.set_sensitive(False)
        self.wake_button.connect("clicked", self._wake_selected)
        header.pack_end(self.wake_button)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)

        self.empty_page = Adw.StatusPage(
            icon_name="network-wired-symbolic",
            title="Nessun computer configurato",
            description="Aggiungi un computer per inviare il primo magic packet.",
        )

        self.computer_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        self.computer_list.add_css_class("boxed-list")
        self.computer_list.connect("row-selected", self._on_row_selected)
        self.computer_list.connect("row-activated", lambda *_: self._wake_selected())

        list_scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        list_scroller.set_child(self.computer_list)

        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty_page, "empty")
        self.stack.add_named(list_scroller, "list")

        self.toasts = Adw.ToastOverlay(child=self.stack)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)
        self._refresh_computers()

    def _show_add_dialog(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title="Aggiungi computer", transient_for=self, modal=True)
        dialog.set_default_size(520, 650)
        dialog.add_button("Annulla", Gtk.ResponseType.CANCEL)
        save_button = dialog.add_button("Salva", Gtk.ResponseType.ACCEPT)
        save_button.add_css_class("suggested-action")
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)

        page = Adw.PreferencesPage()
        required_group = Adw.PreferencesGroup(
            title="Computer",
            description="Nome e indirizzo MAC sono obbligatori.",
        )
        details_group = Adw.PreferencesGroup(title="Dettagli facoltativi")
        network_group = Adw.PreferencesGroup(title="Wake-on-LAN")
        page.add(required_group)
        page.add(network_group)
        page.add(details_group)

        fields: dict[str, Adw.EntryRow] = {}

        def add_field(group: Adw.PreferencesGroup, key: str, title: str, value: str = "") -> None:
            entry = Adw.EntryRow(title=title, text=value)
            entry.set_activates_default(True)
            group.add(entry)
            fields[key] = entry

        add_field(required_group, "name", "Nome computer")
        add_field(required_group, "mac", "Indirizzo MAC")
        add_field(network_group, "ipv4", "Indirizzo IPv4")
        add_field(network_group, "broadcast", "Indirizzo broadcast", "255.255.255.255")
        add_field(network_group, "port", "Porta UDP", "9")
        add_field(details_group, "hostname", "Hostname")
        add_field(details_group, "vendor", "Produttore scheda di rete")
        add_field(details_group, "manufacturer", "Produttore computer")
        add_field(details_group, "model", "Modello")
        add_field(details_group, "serial_number", "Numero seriale")
        add_field(details_group, "bios", "BIOS")
        add_field(details_group, "group_name", "Gruppo")
        add_field(details_group, "notes", "Note")

        dialog.get_content_area().append(page)

        def handle_response(current_dialog: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current_dialog.destroy()
                return

            try:
                computer = Computer(
                    name=fields["name"].get_text(),
                    mac=fields["mac"].get_text(),
                    ipv4=fields["ipv4"].get_text(),
                    broadcast=fields["broadcast"].get_text(),
                    wol_port=int(fields["port"].get_text().strip()),
                    hostname=fields["hostname"].get_text(),
                    vendor=fields["vendor"].get_text(),
                    manufacturer=fields["manufacturer"].get_text(),
                    model=fields["model"].get_text(),
                    serial_number=fields["serial_number"].get_text(),
                    bios=fields["bios"].get_text(),
                    group_name=fields["group_name"].get_text(),
                    notes=fields["notes"].get_text(),
                )
                self.database.add_computer(computer)
            except ValueError as exc:
                self._show_error("Dati non validi", str(exc))
                return
            except sqlite3.IntegrityError:
                self._show_error(
                    "Computer già presente",
                    "Esiste già un computer con questo indirizzo MAC.",
                )
                return

            current_dialog.destroy()
            self._refresh_computers()
            self.toasts.add_toast(Adw.Toast(title=f"{computer.name.strip()} aggiunto"))

        dialog.connect("response", handle_response)
        dialog.present()

    def _refresh_computers(self) -> None:
        child = self.computer_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.computer_list.remove(child)
            child = next_child

        computers = self.database.list_computers()
        for computer in computers:
            subtitle_parts = [value for value in (computer.ipv4, computer.mac) if value]
            row = Adw.ActionRow(
                title=computer.name,
                subtitle="  ·  ".join(subtitle_parts),
                activatable=True,
            )
            row.computer = computer
            row.add_prefix(Gtk.Image.new_from_icon_name("computer-symbolic"))
            self.computer_list.append(row)

        self.stack.set_visible_child_name("list" if computers else "empty")
        self.wake_button.set_sensitive(False)

    def _on_row_selected(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        self.wake_button.set_sensitive(row is not None)

    def _wake_selected(self, *_args: object) -> None:
        row = self.computer_list.get_selected_row()
        if row is None:
            return

        computer: Computer = row.computer
        try:
            wake(computer.mac, computer.broadcast, computer.wol_port)
        except (OSError, ValueError) as exc:
            self._show_error("Invio non riuscito", str(exc))
            return

        self.toasts.add_toast(Adw.Toast(title=f"Magic packet inviato a {computer.name}"))

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("close", "Chiudi")
        dialog.set_default_response("close")
        dialog.present()
