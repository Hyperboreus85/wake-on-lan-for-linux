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
        self.set_default_size(980, 620)

        header = Adw.HeaderBar()
        add_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Aggiungi computer")
        add_button.connect("clicked", lambda *_: self._show_computer_dialog())
        header.pack_start(add_button)

        self.edit_button = Gtk.Button(icon_name="document-edit-symbolic", tooltip_text="Modifica")
        self.edit_button.connect("clicked", self._edit_selected)
        header.pack_start(self.edit_button)

        self.delete_button = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Elimina")
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", self._delete_selected)
        header.pack_start(self.delete_button)

        self.wake_all_button = Gtk.Button(label="Sveglia tutti")
        self.wake_all_button.connect("clicked", self._wake_all)
        header.pack_end(self.wake_all_button)

        self.wake_button = Gtk.Button(label="Sveglia selezionati")
        self.wake_button.add_css_class("suggested-action")
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
            selection_mode=Gtk.SelectionMode.MULTIPLE,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        self.computer_list.add_css_class("boxed-list")
        self.computer_list.connect("selected-rows-changed", self._on_selection_changed)

        list_scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        list_scroller.set_child(self.computer_list)

        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty_page, "empty")
        self.stack.add_named(list_scroller, "list")

        self.toasts = Adw.ToastOverlay(child=self.stack)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)
        self._refresh_computers()

    def _show_computer_dialog(self, computer: Computer | None = None) -> None:
        editing = computer is not None
        dialog = Gtk.Dialog(
            title="Modifica computer" if editing else "Aggiungi computer",
            transient_for=self,
            modal=True,
        )
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
        network_group = Adw.PreferencesGroup(title="Wake-on-LAN")
        details_group = Adw.PreferencesGroup(title="Dettagli facoltativi")
        page.add(required_group)
        page.add(network_group)
        page.add(details_group)

        fields: dict[str, Adw.EntryRow] = {}

        def value(name: str, fallback: str = "") -> str:
            if computer is None:
                return fallback
            return str(getattr(computer, name))

        def add_field(group: Adw.PreferencesGroup, key: str, title: str, text: str = "") -> None:
            entry = Adw.EntryRow(title=title, text=text)
            entry.set_activates_default(True)
            group.add(entry)
            fields[key] = entry

        add_field(required_group, "name", "Nome computer", value("name"))
        add_field(required_group, "mac", "Indirizzo MAC", value("mac"))
        add_field(network_group, "ipv4", "Indirizzo IPv4", value("ipv4"))
        add_field(
            network_group,
            "broadcast",
            "Indirizzo broadcast",
            value("broadcast", "255.255.255.255"),
        )
        add_field(network_group, "port", "Porta UDP", value("wol_port", "9"))
        add_field(details_group, "hostname", "Hostname", value("hostname"))
        add_field(details_group, "vendor", "Produttore scheda di rete", value("vendor"))
        add_field(details_group, "manufacturer", "Produttore computer", value("manufacturer"))
        add_field(details_group, "model", "Modello", value("model"))
        add_field(details_group, "serial_number", "Numero seriale", value("serial_number"))
        add_field(details_group, "bios", "BIOS", value("bios"))
        add_field(details_group, "group_name", "Gruppo", value("group_name"))
        add_field(details_group, "notes", "Note", value("notes"))
        dialog.get_content_area().append(page)

        def handle_response(current_dialog: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current_dialog.destroy()
                return

            try:
                saved = Computer(
                    id=computer.id if computer else None,
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
                if editing:
                    self.database.update_computer(saved)
                else:
                    self.database.add_computer(saved)
            except ValueError as exc:
                self._show_error("Dati non validi", str(exc))
                return
            except sqlite3.IntegrityError:
                self._show_error(
                    "Indirizzo MAC già presente",
                    "Esiste già un altro computer con questo indirizzo MAC.",
                )
                return

            current_dialog.destroy()
            self._refresh_computers()
            action = "modificato" if editing else "aggiunto"
            self.toasts.add_toast(Adw.Toast(title=f"{saved.name.strip()} {action}"))

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
        self.wake_all_button.set_sensitive(bool(computers))
        self._on_selection_changed()

    def _selected_computers(self) -> list[Computer]:
        return [row.computer for row in self.computer_list.get_selected_rows()]

    def _on_selection_changed(self, *_args: object) -> None:
        count = len(self._selected_computers())
        self.wake_button.set_sensitive(count > 0)
        self.edit_button.set_sensitive(count == 1)
        self.delete_button.set_sensitive(count > 0)
        self.wake_button.set_label(
            "Sveglia selezionati" if count < 2 else f"Sveglia selezionati ({count})"
        )

    def _edit_selected(self, *_args: object) -> None:
        selected = self._selected_computers()
        if len(selected) == 1:
            self._show_computer_dialog(selected[0])

    def _delete_selected(self, *_args: object) -> None:
        selected = self._selected_computers()
        if not selected:
            return

        count = len(selected)
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Eliminare i computer selezionati?" if count > 1 else "Eliminare il computer?",
            body=f"Verranno eliminati {count} computer dal database locale.",
        )
        dialog.add_response("cancel", "Annulla")
        dialog.add_response("delete", "Elimina")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(current_dialog: Adw.MessageDialog, response: str) -> None:
            current_dialog.destroy()
            if response != "delete":
                return
            ids = [item.id for item in selected if item.id is not None]
            deleted = self.database.delete_computers(ids)
            self._refresh_computers()
            self.toasts.add_toast(Adw.Toast(title=f"{deleted} computer eliminati"))

        dialog.connect("response", handle_response)
        dialog.present()

    def _wake_selected(self, *_args: object) -> None:
        computers = self._selected_computers()
        if not computers:
            return
        if len(computers) == 1:
            self._send_wake_packets(computers)
        else:
            self._confirm_bulk_wake(computers, "i computer selezionati")

    def _wake_all(self, *_args: object) -> None:
        computers = self.database.list_computers()
        if computers:
            self._confirm_bulk_wake(computers, "tutti i computer")

    def _confirm_bulk_wake(self, computers: list[Computer], target: str, step: int = 1) -> None:
        count = len(computers)
        messages = (
            (
                "Conferma accensione multipla — 1/3",
                f"Stai per inviare il comando Wake-on-LAN a {count} computer ({target}).",
            ),
            (
                "Seconda conferma — 2/3",
                "Controlla che nessuno dei computer sia stato selezionato per errore.",
            ),
            (
                "Ultima conferma — 3/3",
                f"Inviare ora {count} magic packet? Questa operazione accende i computer; non li spegne.",
            ),
        )
        heading, body = messages[step - 1]
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("cancel", "Annulla")
        dialog.add_response("continue", "OK, continua" if step < 3 else "Sì, sveglia")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        if step == 3:
            dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)

        def handle_response(current_dialog: Adw.MessageDialog, response: str) -> None:
            current_dialog.destroy()
            if response != "continue":
                return
            if step < 3:
                self._confirm_bulk_wake(computers, target, step + 1)
            else:
                self._send_wake_packets(computers)

        dialog.connect("response", handle_response)
        dialog.present()

    def _send_wake_packets(self, computers: list[Computer]) -> None:
        failures: list[str] = []
        for computer in computers:
            try:
                wake(computer.mac, computer.broadcast, computer.wol_port)
            except (OSError, ValueError):
                failures.append(computer.name)

        sent = len(computers) - len(failures)
        if failures:
            self._show_error(
                "Invio parzialmente riuscito",
                f"Pacchetti inviati: {sent}. Errori: {', '.join(failures)}.",
            )
        else:
            label = computers[0].name if len(computers) == 1 else f"{sent} computer"
            self.toasts.add_toast(Adw.Toast(title=f"Magic packet inviato a {label}"))

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("close", "Chiudi")
        dialog.set_default_response("close")
        dialog.present()
