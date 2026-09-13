from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from .database import Database  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402


class WakeLanApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="io.github.wol_linux.WakeOnLanForLinux")
        self.database = Database()
        self.connect("activate", self._on_activate)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def _on_activate(self, _application: Adw.Application) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self, database=self.database)
        window.present()

