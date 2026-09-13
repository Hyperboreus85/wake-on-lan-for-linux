from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

from .settings import AppSettings

ACCENT_COLORS = {
    "ubuntu": "#E95420",
    "blue": "#3584E4",
    "green": "#2EC27E",
    "purple": "#9141AC",
    "red": "#E01B24",
}

_provider: Gtk.CssProvider | None = None


def apply_appearance(settings: AppSettings) -> None:
    schemes = {
        "system": Adw.ColorScheme.DEFAULT,
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }
    Adw.StyleManager.get_default().set_color_scheme(schemes[settings.theme])

    global _provider
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _provider is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _provider)
    color = ACCENT_COLORS[settings.accent]
    _provider = Gtk.CssProvider()
    _provider.load_from_data(
        f"""
        @define-color accent_color {color};
        @define-color accent_bg_color {color};
        @define-color accent_fg_color #ffffff;
        """.encode()
    )
    Gtk.StyleContext.add_provider_for_display(
        display,
        _provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
