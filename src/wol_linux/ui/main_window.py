from __future__ import annotations

import sqlite3
import threading

from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ..appearance import apply_appearance
from ..backup import export_backup, load_backup, restore_translations
from ..database import Database
from ..fonts import install_font
from ..i18n import available_languages, install_translation, tr as _
from ..models import Computer
from ..network import DiscoveredHost, ScanResult, ping_host, scan_local_network
from ..settings import ACCENTS, COLUMN_WIDTH_DEFAULTS, THEMES, AppSettings
from ..wol import wake


class MainWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Adw.Application,
        database: Database,
        settings: AppSettings,
    ) -> None:
        super().__init__(application=application, title=_("Wake on LAN for Linux"))
        self.database = database
        self.settings = settings
        self.set_default_size(980, 620)

        header = Adw.HeaderBar()
        add_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Aggiungi computer"))
        add_button.connect("clicked", lambda *_: self._show_computer_dialog())
        header.pack_start(add_button)

        self.edit_button = Gtk.Button(icon_name="document-edit-symbolic", tooltip_text=_("Modifica"))
        self.edit_button.connect("clicked", self._edit_selected)
        header.pack_start(self.edit_button)

        self.delete_button = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Elimina"))
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", self._delete_selected)
        header.pack_start(self.delete_button)

        self.scan_button = Gtk.Button(
            icon_name="system-search-symbolic",
            tooltip_text=_("Scansiona la rete locale"),
        )
        self.scan_button.connect("clicked", self._start_network_scan)
        header.pack_start(self.scan_button)

        settings_button = Gtk.Button(
            icon_name="preferences-system-symbolic",
            tooltip_text=_("Impostazioni"),
        )
        settings_button.connect("clicked", self._show_preferences)
        header.pack_start(settings_button)

        self.wake_button = Gtk.Button(label=_("Sveglia selezionati"))
        self.wake_button.add_css_class("suggested-action")
        self.wake_button.connect("clicked", self._wake_selected)
        header.pack_end(self.wake_button)

        self.wake_all_button = Gtk.Button(label=_("Sveglia tutti"))
        self.wake_all_button.connect("clicked", self._wake_all)
        header.pack_end(self.wake_all_button)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)

        self.scan_progress = Gtk.ProgressBar(show_text=True, visible=False)
        toolbar.add_top_bar(self.scan_progress)

        self.empty_page = Adw.StatusPage(
            icon_name="network-wired-symbolic",
            title=_("Nessun computer configurato"),
            description=_("Aggiungi un computer per inviare il primo magic packet."),
        )

        self.computer_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        self.computer_list.add_css_class("boxed-list")
        self.computer_list.connect("row-activated", self._toggle_row)

        table_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        table_content.append(self._build_table_header())
        table_content.append(self.computer_list)
        table_scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        table_scroller.set_child(table_content)

        table_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        table_box.append(table_scroller)

        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty_page, "empty")
        self.stack.add_named(table_box, "list")

        self.toasts = Adw.ToastOverlay(child=self.stack)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)
        self._refresh_computers()
        GLib.timeout_add_seconds(30, self._periodic_status_check)

    def _show_preferences(self, *_args: object) -> None:
        dialog = Gtk.Dialog(title=_("Impostazioni"), transient_for=self, modal=True)
        dialog.set_default_size(520, 520)
        dialog.add_button(_("Annulla"), Gtk.ResponseType.CANCEL)
        apply_button = dialog.add_button(_("Applica"), Gtk.ResponseType.ACCEPT)
        apply_button.add_css_class("suggested-action")

        page = Adw.PreferencesPage()
        appearance_group = Adw.PreferencesGroup(title=_("Aspetto"))
        palette_group = Adw.PreferencesGroup(
            title=_("Palette personalizzata"),
            description=_("Scegli i colori RGB per accenti, pulsanti, testo e sfondo"),
        )
        font_group = Adw.PreferencesGroup(
            title=_("Font"),
            description=_("Installa un font TTF/OTF nella tua cartella utente"),
        )
        columns_group = Adw.PreferencesGroup(
            title=_("Larghezza colonne"),
            description=_("Regola le colonne con le frecce e scorri orizzontalmente se necessario"),
        )
        language_group = Adw.PreferencesGroup(title=_("Lingua"))
        backup_group = Adw.PreferencesGroup(
            title=_("Backup e trasferimento"),
            description=_("Salva macchine e personalizzazioni in un unico file"),
        )
        page.add(appearance_group)
        page.add(palette_group)
        page.add(font_group)
        page.add(columns_group)
        page.add(language_group)
        page.add(backup_group)

        theme_values = list(THEMES)
        theme_row = Adw.ComboRow(
            title=_("Tema"),
            model=Gtk.StringList.new(
                [_("Sistema"), _("Chiaro"), _("Scuro")]
            ),
            selected=theme_values.index(self.settings.theme),
        )
        appearance_group.add(theme_row)

        accent_values = list(ACCENTS)
        accent_row = Adw.ComboRow(
            title=_("Colore principale"),
            model=Gtk.StringList.new(
                [_("Arancione Ubuntu"), _("Blu"), _("Verde"), _("Viola"), _("Rosso")]
            ),
            selected=accent_values.index(self.settings.accent),
        )
        appearance_group.add(accent_row)

        palette_buttons: dict[str, Gtk.ColorDialogButton] = {}
        palette_defaults = {
            "accent": self.settings.custom_colors.get("accent", "#E95420"),
            "button": self.settings.custom_colors.get("button", "#E95420"),
            "text": self.settings.custom_colors.get("text", "#FFFFFF"),
            "background": self.settings.custom_colors.get("background", "#2D2D2D"),
        }
        palette_labels = {
            "accent": _("Colore accento"),
            "button": _("Colore pulsanti"),
            "text": _("Colore testo"),
            "background": _("Colore sfondo"),
        }
        changed_palette: set[str] = set()
        for key in ("accent", "button", "text", "background"):
            color_row = Adw.ActionRow(title=palette_labels[key])
            color_button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
            rgba = Gdk.RGBA()
            rgba.parse(palette_defaults[key])
            color_button.set_rgba(rgba)
            color_button.set_valign(Gtk.Align.CENTER)
            color_button.connect(
                "notify::rgba", lambda *_args, palette_key=key: changed_palette.add(palette_key)
            )
            color_row.add_suffix(color_button)
            palette_group.add(color_row)
            palette_buttons[key] = color_button

        pending_font = [self.settings.font_family]
        font_row = Adw.ActionRow(
            title=_("Font dell'applicazione"),
            subtitle=self.settings.font_family or _("Predefinito di sistema"),
        )
        font_button = Gtk.Button(label=_("Installa font"), valign=Gtk.Align.CENTER)
        font_button.connect(
            "clicked",
            lambda *_: self._choose_font_file(dialog, pending_font, font_row),
        )
        font_row.add_suffix(font_button)
        font_group.add(font_row)

        column_widths = dict(self.settings.column_widths)
        column_labels = (
            ("ipv4", _("Indirizzo IP")),
            ("name", _("Nome / hostname")),
            ("mac", _("Indirizzo MAC")),
            ("status", _("Stato")),
            ("vendor", _("Vendor scheda")),
            ("manufacturer", _("Produttore")),
            ("model", _("Modello")),
            ("serial_number", _("Numero seriale")),
            ("bios", _("BIOS")),
            ("group", _("Gruppo")),
            ("notes", _("Note")),
            ("broadcast", _("Broadcast")),
            ("port", _("Porta UDP")),
        )
        column_spins: dict[str, Gtk.SpinButton] = {}
        for key, label in column_labels:
            row = Adw.ActionRow(title=label, subtitle=_("Larghezza in caratteri"))
            adjustment = Gtk.Adjustment(
                value=column_widths.get(key, COLUMN_WIDTH_DEFAULTS[key]),
                lower=4,
                upper=60,
                step_increment=1,
                page_increment=5,
            )
            spin = Gtk.SpinButton(adjustment=adjustment, numeric=True, width_chars=4)
            spin.set_valign(Gtk.Align.CENTER)
            row.add_suffix(spin)
            columns_group.add(row)
            column_spins[key] = spin

        languages = available_languages()
        language_codes = [code for code, _label in languages]
        selected_language = (
            language_codes.index(self.settings.language)
            if self.settings.language in language_codes
            else 0
        )
        language_row = Adw.ComboRow(
            title=_("Lingua dell'applicazione"),
            subtitle=_("Il cambio della lingua richiede il riavvio"),
            model=Gtk.StringList.new([label for _code, label in languages]),
            selected=selected_language,
        )
        language_group.add(language_row)

        import_row = Adw.ActionRow(
            title=_("Importa traduzione"),
            subtitle=_("Catalogo GNU gettext con nome fr.mo o de_DE.mo"),
        )
        import_button = Gtk.Button(label=_("Scegli file"), valign=Gtk.Align.CENTER)
        import_button.connect("clicked", lambda *_: self._choose_translation_file(dialog))
        import_row.add_suffix(import_button)
        language_group.add(import_row)

        export_row = Adw.ActionRow(
            title=_("Esporta backup completo"),
            subtitle=_("Include macchine, indirizzi, note, colori, tema e lingua"),
        )
        export_button = Gtk.Button(label=_("Esporta"), valign=Gtk.Align.CENTER)
        export_button.connect("clicked", lambda *_: self._choose_backup_destination(dialog))
        export_row.add_suffix(export_button)
        backup_group.add(export_row)

        restore_row = Adw.ActionRow(
            title=_("Importa backup"),
            subtitle=_("Unisce le macchine usando il MAC e ripristina le impostazioni"),
        )
        restore_button = Gtk.Button(label=_("Importa"), valign=Gtk.Align.CENTER)
        restore_button.connect("clicked", lambda *_: self._choose_backup_file(dialog))
        restore_row.add_suffix(restore_button)
        backup_group.add(restore_row)

        dialog.get_content_area().append(page)

        def handle_response(current_dialog: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current_dialog.destroy()
                return
            old_language = self.settings.language
            self.settings.theme = theme_values[theme_row.get_selected()]
            self.settings.accent = accent_values[accent_row.get_selected()]
            self.settings.language = language_codes[language_row.get_selected()]
            self.settings.custom_colors.update(
                {
                    key: self._rgba_to_hex(palette_buttons[key].get_rgba())
                    for key in changed_palette
                }
            )
            self.settings.font_family = pending_font[0]
            self.settings.column_widths = {
                key: int(spin.get_value()) for key, spin in column_spins.items()
            }
            self.settings.save()
            apply_appearance(self.settings)
            current_dialog.destroy()
            if self.settings.language != old_language:
                self.toasts.add_toast(
                    Adw.Toast(title=_("Riavvia l'applicazione per applicare la nuova lingua"))
                )
            else:
                self.toasts.add_toast(Adw.Toast(title=_("Impostazioni salvate")))

        dialog.connect("response", handle_response)
        dialog.present()

    @staticmethod
    def _rgba_to_hex(rgba: Gdk.RGBA) -> str:
        return "#{:02X}{:02X}{:02X}".format(
            round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)
        )

    def _choose_font_file(
        self,
        parent: Gtk.Window,
        pending_font: list[str],
        font_row: Adw.ActionRow,
    ) -> None:
        chooser = Gtk.FileChooserNative(
            title=_("Installa font"),
            transient_for=parent,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("Installa"),
            cancel_label=_("Annulla"),
        )
        file_filter = Gtk.FileFilter(name=_("Font TTF, OTF o TTC"))
        for pattern in ("*.ttf", "*.TTF", "*.otf", "*.OTF", "*.ttc", "*.TTC"):
            file_filter.add_pattern(pattern)
        chooser.add_filter(file_filter)

        def handle_response(current_chooser: Gtk.FileChooserNative, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                return
            selected_file = current_chooser.get_file()
            path = selected_file.get_path() if selected_file else None
            if not path:
                self._show_error(_("Installazione non riuscita"), _("Seleziona un file font locale"))
                return
            try:
                family = install_font(path)
            except (OSError, ValueError) as exc:
                self._show_error(_("Installazione non riuscita"), str(exc))
                return
            pending_font[0] = family
            font_row.set_subtitle(family)
            self.toasts.add_toast(Adw.Toast(title=_("Font installato: {font}").format(font=family)))

        chooser.connect("response", handle_response)
        chooser.show()

    def _choose_translation_file(self, parent: Gtk.Window) -> None:
        chooser = Gtk.FileChooserNative(
            title=_("Importa traduzione"),
            transient_for=parent,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("Importa"),
            cancel_label=_("Annulla"),
        )
        file_filter = Gtk.FileFilter(name=_("Cataloghi gettext (.mo)"))
        file_filter.add_pattern("*.mo")
        chooser.add_filter(file_filter)

        def handle_response(current_chooser: Gtk.FileChooserNative, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                return
            selected_file = current_chooser.get_file()
            path = selected_file.get_path() if selected_file else None
            if not path:
                self._show_error(_("Importazione non riuscita"), _("Seleziona un file locale .mo"))
                return
            try:
                language = install_translation(path)
            except ValueError as exc:
                self._show_error(_("Importazione non riuscita"), str(exc))
                return
            self.toasts.add_toast(
                Adw.Toast(title=_("Traduzione {language} installata").format(language=language))
            )

        chooser.connect("response", handle_response)
        chooser.show()

    def _choose_backup_destination(self, parent: Gtk.Window) -> None:
        chooser = Gtk.FileChooserNative(
            title=_("Esporta backup completo"),
            transient_for=parent,
            action=Gtk.FileChooserAction.SAVE,
            accept_label=_("Esporta"),
            cancel_label=_("Annulla"),
        )
        chooser.set_current_name("wake-on-lan-for-linux-backup.json")

        def handle_response(current_chooser: Gtk.FileChooserNative, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                return
            selected_file = current_chooser.get_file()
            path = selected_file.get_path() if selected_file else None
            if not path:
                self._show_error(_("Esportazione non riuscita"), _("Scegli un file locale"))
                return
            try:
                export_backup(path, self.settings, self.database.list_computers())
            except OSError as exc:
                self._show_error(_("Esportazione non riuscita"), str(exc))
                return
            self.toasts.add_toast(Adw.Toast(title=_("Backup completo esportato")))

        chooser.connect("response", handle_response)
        chooser.show()

    def _choose_backup_file(self, parent: Gtk.Window) -> None:
        chooser = Gtk.FileChooserNative(
            title=_("Importa backup"),
            transient_for=parent,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("Importa"),
            cancel_label=_("Annulla"),
        )
        file_filter = Gtk.FileFilter(name=_("Backup Wake on LAN for Linux (.json)"))
        file_filter.add_pattern("*.json")
        chooser.add_filter(file_filter)

        def handle_response(current_chooser: Gtk.FileChooserNative, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                return
            selected_file = current_chooser.get_file()
            path = selected_file.get_path() if selected_file else None
            if not path:
                self._show_error(_("Importazione non riuscita"), _("Seleziona un file locale"))
                return
            try:
                backup = load_backup(path)
                imported = self.database.import_computers(backup.computers)
                restore_translations(backup.translations)
            except (OSError, ValueError, sqlite3.DatabaseError) as exc:
                self._show_error(_("Importazione non riuscita"), str(exc))
                return

            old_language = self.settings.language
            self.settings.theme = backup.settings.theme
            self.settings.accent = backup.settings.accent
            self.settings.language = backup.settings.language
            self.settings.save()
            apply_appearance(self.settings)
            self._refresh_computers()
            message = _("Backup importato: {count} macchine unite").format(count=imported)
            if self.settings.language != old_language:
                message += _(". Riavvia l'applicazione per applicare la lingua")
            self.toasts.add_toast(Adw.Toast(title=message))

        chooser.connect("response", handle_response)
        chooser.show()

    def _show_computer_dialog(self, computer: Computer | None = None) -> None:
        editing = computer is not None
        dialog = Gtk.Dialog(
            title=_("Modifica computer") if editing else _("Aggiungi computer"),
            transient_for=self,
            modal=True,
        )
        dialog.set_default_size(520, 650)
        dialog.add_button(_("Annulla"), Gtk.ResponseType.CANCEL)
        save_button = dialog.add_button(_("Salva"), Gtk.ResponseType.ACCEPT)
        save_button.add_css_class("suggested-action")
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)

        page = Adw.PreferencesPage()
        required_group = Adw.PreferencesGroup(
            title=_("Computer"),
            description=_("Nome e indirizzo MAC sono obbligatori."),
        )
        network_group = Adw.PreferencesGroup(title=_("Wake-on-LAN"))
        details_group = Adw.PreferencesGroup(title=_("Dettagli facoltativi"))
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

        add_field(required_group, "name", _("Nome computer"), value("name"))
        add_field(required_group, "mac", _("Indirizzo MAC"), value("mac"))
        add_field(network_group, "ipv4", _("Indirizzo IPv4"), value("ipv4"))
        add_field(
            network_group,
            "broadcast",
            _("Indirizzo broadcast"),
            value("broadcast", "255.255.255.255"),
        )
        add_field(network_group, "port", _("Porta UDP"), value("wol_port", "9"))
        add_field(details_group, "hostname", _("Hostname"), value("hostname"))
        add_field(details_group, "vendor", _("Produttore scheda di rete"), value("vendor"))
        add_field(details_group, "manufacturer", _("Produttore computer"), value("manufacturer"))
        add_field(details_group, "model", _("Modello"), value("model"))
        add_field(details_group, "serial_number", _("Numero seriale"), value("serial_number"))
        add_field(details_group, "bios", _("BIOS"), value("bios"))
        add_field(details_group, "group_name", _("Gruppo"), value("group_name"))
        add_field(details_group, "notes", _("Note"), value("notes"))
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
                self._show_error(_("Dati non validi"), str(exc))
                return
            except sqlite3.IntegrityError:
                self._show_error(
                    _("Indirizzo MAC già presente"),
                    _("Esiste già un altro computer con questo indirizzo MAC."),
                )
                return

            current_dialog.destroy()
            self._refresh_computers()
            action = _("modificato") if editing else _("aggiunto")
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
            row = Gtk.ListBoxRow(activatable=True)
            row.computer = computer
            row.check_button = Gtk.CheckButton(
                tooltip_text=_("Seleziona o deseleziona"),
                halign=Gtk.Align.CENTER,
            )
            row.check_button.connect("toggled", self._on_selection_changed)
            row.status_icon = Gtk.Image(
                icon_name="media-record-symbolic",
                tooltip_text=_("Stato in verifica"),
                halign=Gtk.Align.CENTER,
            )
            row.status_icon.add_css_class("warning")

            hostname = computer.hostname.strip()
            display_name = computer.name
            if hostname and hostname.casefold() != computer.name.casefold():
                display_name = f"{computer.name} · {hostname}"

            grid = self._build_table_grid()
            grid.attach(row.check_button, 0, 0, 1, 1)
            grid.attach(self._table_label(computer.ipv4 or "—", self._column_width("ipv4")), 1, 0, 1, 1)
            grid.attach(
                self._table_label(display_name, self._column_width("name"), expand=True),
                2,
                0,
                1,
                1,
            )
            grid.attach(self._table_label(computer.mac, self._column_width("mac")), 3, 0, 1, 1)
            grid.attach(row.status_icon, 4, 0, 1, 1)
            details = (
                computer.vendor,
                computer.manufacturer,
                computer.model,
                computer.serial_number,
                computer.bios,
                computer.group_name,
                computer.notes,
                computer.broadcast,
                str(computer.wol_port),
            )
            for column, value, width in zip(
                range(5, 14),
                details,
                tuple(
                    self._column_width(key)
                    for key in (
                        "vendor",
                        "manufacturer",
                        "model",
                        "serial_number",
                        "bios",
                        "group",
                        "notes",
                        "broadcast",
                        "port",
                    )
                ),
                strict=True,
            ):
                grid.attach(self._table_label(value or "—", width), column, 0, 1, 1)
            row.set_child(grid)
            self.computer_list.append(row)

        self.stack.set_visible_child_name("list" if computers else "empty")
        self.wake_all_button.set_sensitive(bool(computers))
        self._on_selection_changed()
        self._check_statuses_async(computers)

    def _selected_computers(self) -> list[Computer]:
        return [row.computer for row in self._computer_rows() if row.check_button.get_active()]

    def _computer_rows(self) -> list[Gtk.ListBoxRow]:
        rows: list[Gtk.ListBoxRow] = []
        child = self.computer_list.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        return rows

    def _toggle_row(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        row.check_button.set_active(not row.check_button.get_active())

    @staticmethod
    def _build_table_grid() -> Gtk.Grid:
        return Gtk.Grid(
            column_spacing=18,
            margin_top=10,
            margin_bottom=10,
            margin_start=12,
            margin_end=12,
        )

    @staticmethod
    def _column_width(self, key: str) -> int:
        return self.settings.column_widths.get(key, COLUMN_WIDTH_DEFAULTS[key])

    @staticmethod
    def _table_label(text: str, width: int, expand: bool = False) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=0.5, hexpand=expand, justify=Gtk.Justification.CENTER)
        label.set_width_chars(width)
        label.set_max_width_chars(width)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        return label

    def _build_table_header(self) -> Gtk.Grid:
        grid = self._build_table_grid()
        grid.set_margin_start(30)
        grid.set_margin_end(30)
        grid.attach(Gtk.Label(width_request=self._column_width("select")), 0, 0, 1, 1)
        for column, text, width, expand in (
            (1, _("Indirizzo IP"), self._column_width("ipv4"), False),
            (2, _("Nome / hostname"), self._column_width("name"), True),
            (3, _("Indirizzo MAC"), self._column_width("mac"), False),
            (4, _("Stato"), self._column_width("status"), False),
            (5, _("Vendor scheda"), self._column_width("vendor"), False),
            (6, _("Produttore"), self._column_width("manufacturer"), False),
            (7, _("Modello"), self._column_width("model"), False),
            (8, _("Numero seriale"), self._column_width("serial_number"), False),
            (9, _("BIOS"), self._column_width("bios"), False),
            (10, _("Gruppo"), self._column_width("group"), False),
            (11, _("Note"), self._column_width("notes"), False),
            (12, _("Broadcast"), self._column_width("broadcast"), False),
            (13, _("Porta UDP"), self._column_width("port"), False),
        ):
            label = self._table_label(text, width, expand)
            label.add_css_class("heading")
            grid.attach(label, column, 0, 1, 1)
        return grid

    def _on_selection_changed(self, *_args: object) -> None:
        count = len(self._selected_computers())
        self.wake_button.set_sensitive(count > 0)
        self.edit_button.set_sensitive(count == 1)
        self.delete_button.set_sensitive(count > 0)
        self.wake_button.set_label(
            _("Sveglia selezionati")
            if count < 2
            else _("Sveglia selezionati ({count})").format(count=count)
        )

    def _check_statuses_async(self, computers: list[Computer]) -> None:
        generation = getattr(self, "_status_generation", 0) + 1
        self._status_generation = generation

        def worker() -> None:
            for computer in computers:
                address = computer.ipv4 or computer.hostname
                status = ping_host(address)
                GLib.idle_add(self._apply_status, generation, computer.id, status)

        threading.Thread(target=worker, daemon=True).start()

    def _periodic_status_check(self) -> bool:
        self._check_statuses_async(self.database.list_computers())
        return GLib.SOURCE_CONTINUE

    def _apply_status(self, generation: int, computer_id: int | None, status: bool | None) -> bool:
        if generation != self._status_generation:
            return GLib.SOURCE_REMOVE
        for row in self._computer_rows():
            if row.computer.id != computer_id:
                continue
            for css_class in ("success", "error", "warning"):
                row.status_icon.remove_css_class(css_class)
            if status is True:
                row.status_icon.add_css_class("success")
                row.status_icon.set_tooltip_text(_("Online"))
            elif status is False:
                row.status_icon.add_css_class("error")
                row.status_icon.set_tooltip_text(_("Offline o non raggiungibile"))
            else:
                row.status_icon.add_css_class("warning")
                row.status_icon.set_tooltip_text(_("Stato sconosciuto: IP o hostname mancante"))
            break
        return GLib.SOURCE_REMOVE

    def _start_network_scan(self, *_args: object) -> None:
        self.scan_button.set_sensitive(False)
        self.scan_progress.set_fraction(0)
        self.scan_progress.set_text(_("Rilevamento rete…"))
        self.scan_progress.set_visible(True)

        def progress(completed: int, total: int) -> None:
            GLib.idle_add(self._update_scan_progress, completed, total)

        def worker() -> None:
            try:
                result = scan_local_network(progress)
            except (OSError, RuntimeError, ValueError) as exc:
                GLib.idle_add(self._finish_network_scan, None, str(exc))
                return
            GLib.idle_add(self._finish_network_scan, result, None)

        threading.Thread(target=worker, daemon=True).start()

    def _update_scan_progress(self, completed: int, total: int) -> bool:
        if total:
            self.scan_progress.set_fraction(completed / total)
        self.scan_progress.set_text(
            _("Scansione rete: {completed}/{total}").format(completed=completed, total=total)
        )
        return GLib.SOURCE_REMOVE

    def _finish_network_scan(self, result: ScanResult | None, error: str | None) -> bool:
        self.scan_button.set_sensitive(True)
        self.scan_progress.set_visible(False)
        if error:
            self._show_error(_("Scansione non riuscita"), error)
        elif result is not None:
            self._show_scan_results(result)
        return GLib.SOURCE_REMOVE

    def _show_scan_results(self, result: ScanResult) -> None:
        existing_macs = {computer.mac for computer in self.database.list_computers()}
        available = [host for host in result.hosts if host.mac not in existing_macs]
        if not available:
            self.toasts.add_toast(
                Adw.Toast(
                    title=_("Nessun nuovo dispositivo trovato in {network}").format(
                        network=result.local_network.network
                    )
                )
            )
            self._check_statuses_async(self.database.list_computers())
            return

        dialog = Gtk.Dialog(title=_("Dispositivi trovati"), transient_for=self, modal=True)
        dialog.set_default_size(620, 520)
        dialog.add_button(_("Annulla"), Gtk.ResponseType.CANCEL)
        import_button = dialog.add_button(_("Importa selezionati"), Gtk.ResponseType.ACCEPT)
        import_button.add_css_class("suggested-action")

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        box.append(
            Gtk.Label(
                label=_("Rete {network} · {count} nuovi dispositivi").format(
                    network=result.local_network.network,
                    count=len(available),
                ),
                xalign=0,
            )
        )
        scan_header = self._build_table_grid()
        scan_header.attach(Gtk.Label(width_request=24), 0, 0, 1, 1)
        for column, text, width, expand in (
            (1, _("Indirizzo IP"), 16, False),
            (2, _("Hostname"), 24, True),
            (3, _("Indirizzo MAC"), 20, False),
        ):
            label = self._table_label(text, width, expand)
            label.add_css_class("heading")
            scan_header.attach(label, column, 0, 1, 1)
        box.append(scan_header)

        discovered_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        discovered_list.add_css_class("boxed-list")
        choices: list[tuple[Gtk.CheckButton, DiscoveredHost]] = []
        for host in available:
            check = Gtk.CheckButton(active=True)
            row = Gtk.ListBoxRow(activatable=True)
            row.check_button = check
            grid = self._build_table_grid()
            grid.attach(check, 0, 0, 1, 1)
            grid.attach(self._table_label(host.ipv4, 16), 1, 0, 1, 1)
            grid.attach(self._table_label(host.hostname or "—", 24, expand=True), 2, 0, 1, 1)
            grid.attach(self._table_label(host.mac, 20), 3, 0, 1, 1)
            row.set_child(grid)
            discovered_list.append(row)
            choices.append((check, host))

        def toggle_discovered(_list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
            row.check_button.set_active(not row.check_button.get_active())

        discovered_list.connect("row-activated", toggle_discovered)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(discovered_list)
        box.append(scroller)
        dialog.get_content_area().append(box)

        def handle_response(current_dialog: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current_dialog.destroy()
                return
            imported = 0
            for check, host in choices:
                if not check.get_active():
                    continue
                try:
                    self.database.add_computer(
                        Computer(
                            name=host.hostname or host.ipv4,
                            hostname=host.hostname,
                            ipv4=host.ipv4,
                            mac=host.mac,
                            broadcast=str(result.local_network.network.broadcast_address),
                        )
                    )
                except sqlite3.IntegrityError:
                    continue
                imported += 1
            current_dialog.destroy()
            self._refresh_computers()
            self.toasts.add_toast(
                Adw.Toast(
                    title=_("{count} dispositivi importati").format(count=imported)
                )
            )

        dialog.connect("response", handle_response)
        dialog.present()

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
            heading=_("Eliminare i computer selezionati?")
            if count > 1
            else _("Eliminare il computer?"),
            body=_("Verranno eliminati {count} computer dal database locale.").format(
                count=count
            ),
        )
        dialog.add_response("cancel", _("Annulla"))
        dialog.add_response("delete", _("Elimina"))
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
            self.toasts.add_toast(
                Adw.Toast(title=_("{count} computer eliminati").format(count=deleted))
            )

        dialog.connect("response", handle_response)
        dialog.present()

    def _wake_selected(self, *_args: object) -> None:
        computers = self._selected_computers()
        if not computers:
            return
        if len(computers) == 1:
            self._send_wake_packets(computers)
        else:
            self._confirm_bulk_wake(computers, _("i computer selezionati"))

    def _wake_all(self, *_args: object) -> None:
        computers = self.database.list_computers()
        if computers:
            self._confirm_bulk_wake(computers, _("tutti i computer"))

    def _confirm_bulk_wake(self, computers: list[Computer], target: str, step: int = 1) -> None:
        count = len(computers)
        messages = (
            (
                _("Conferma accensione multipla — 1/3"),
                _("Stai per inviare il comando Wake-on-LAN a {count} computer ({target}).").format(
                    count=count,
                    target=target,
                ),
            ),
            (
                _("Seconda conferma — 2/3"),
                _("Controlla che nessuno dei computer sia stato selezionato per errore."),
            ),
            (
                _("Ultima conferma — 3/3"),
                _(
                    "Inviare ora {count} magic packet? Questa operazione accende i computer; "
                    "non li spegne."
                ).format(count=count),
            ),
        )
        heading, body = messages[step - 1]
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("cancel", _("Annulla"))
        dialog.add_response(
            "continue", _("OK, continua") if step < 3 else _("Sì, sveglia")
        )
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
                _("Invio parzialmente riuscito"),
                _("Pacchetti inviati: {sent}. Errori: {failures}.").format(
                    sent=sent,
                    failures=", ".join(failures),
                ),
            )
        else:
            label = (
                computers[0].name
                if len(computers) == 1
                else _("{count} computer").format(count=sent)
            )
            self.toasts.add_toast(
                Adw.Toast(title=_("Magic packet inviato a {label}").format(label=label))
            )
        GLib.timeout_add_seconds(5, self._refresh_status_after_wake)

    def _refresh_status_after_wake(self) -> bool:
        self._check_statuses_async(self.database.list_computers())
        return GLib.SOURCE_REMOVE

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("close", _("Chiudi"))
        dialog.set_default_response("close")
        dialog.present()
