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

ACCENT_HOVER_COLORS = {
    "ubuntu": "#c84316",
    "blue": "#1c71d8",
    "green": "#26a269",
    "purple": "#813d9c",
    "red": "#c01c28",
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
    color = settings.custom_colors.get("accent", ACCENT_COLORS[settings.accent])
    button_color = settings.custom_colors.get("button", color)
    text_color = settings.custom_colors.get("text", "#FFFFFF")
    background_color = settings.custom_colors.get("background", "#00000000")
    hover_color = ACCENT_HOVER_COLORS[settings.accent]
    _provider = Gtk.CssProvider()
    font_family = settings.font_family.replace("\\", "\\\\").replace('"', '\\"')
    css = f"""
        @define-color accent_color {color};
        @define-color accent_bg_color {color};
        @define-color accent_fg_color {text_color};
        @define-color theme_selected_bg_color {color};
        @define-color theme_selected_fg_color {text_color};
        @define-color theme_fg_color {text_color};
        @define-color window_bg_color {background_color};

        /* Keep Libadwaita action buttons in sync with the selected accent. */
        button.suggested-action,
        button.suggested-action:checked,
        button.suggested-action:active,
        .suggested-action > button,
        .suggested-action button {{
            background-color: {button_color};
            color: {text_color};
        }}
        button.suggested-action:hover,
        .suggested-action > button:hover,
        .suggested-action button:hover {{
            background-color: {hover_color};
        }}
        button.suggested-action:disabled {{
            background-color: {color};
            opacity: 0.45;
        }}
        window, .background {{
            color: {text_color};
        }}
        .table-cell {{
            border-right: 1px solid alpha(currentColor, 0.20);
        }}
        .table-fixed-cell {{
            border-right: 1px solid alpha(currentColor, 0.20);
        }}
        """ \
        + (f'* {{ font-family: "{font_family}"; }}' if font_family else "")
    _provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_display(
        display,
        _provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
