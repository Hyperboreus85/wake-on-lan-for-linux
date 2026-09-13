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
    menu_text_color = settings.custom_colors.get("menu_text")
    list_text_color = settings.custom_colors.get("list_text")
    primary_background = settings.custom_colors.get("background_primary")
    secondary_background = settings.custom_colors.get("background_secondary")
    action_text_color = menu_text_color or "#FFFFFF"
    hover_color = ACCENT_HOVER_COLORS[settings.accent]
    _provider = Gtk.CssProvider()
    font_family = settings.font_family.replace("\\", "\\\\").replace('"', '\\"')
    font_size = f"* {{ font-size: {settings.font_size}pt; }}" if settings.font_size else ""
    menu_text_rule = f"@define-color theme_fg_color {menu_text_color};" if menu_text_color else ""
    primary_background_rule = (
        f"@define-color window_bg_color {primary_background};" if primary_background else ""
    )
    background_rule = f"background-color: {primary_background};" if primary_background else ""
    list_rule = (
        (f"color: {list_text_color};" if list_text_color else "")
        + (f"background-color: {secondary_background};" if secondary_background else "")
    )
    css = (
        f"""
        @define-color accent_color {color};
        @define-color accent_bg_color {color};
        @define-color accent_fg_color {action_text_color};
        @define-color theme_selected_bg_color {color};
        @define-color theme_selected_fg_color {action_text_color};
        {menu_text_rule}
        {primary_background_rule}

        /* Keep Libadwaita action buttons in sync with the selected accent. */
        button.suggested-action,
        button.suggested-action:checked,
        button.suggested-action:active,
        .suggested-action > button,
        .suggested-action button {{
            background-color: {button_color};
            color: {action_text_color};
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
            {f'color: {menu_text_color};' if menu_text_color else ''}
            {background_rule}
        }}
        headerbar, popover, menu, .navigation-sidebar {{
            {f'color: {menu_text_color};' if menu_text_color else ''}
        }}
        /* The header and data rows share the same 12 px grid inset.  Remove
           Libadwaita's boxed-list row inset so their first divider is exact. */
        .boxed-list > row {{
            margin: 0;
            padding: 0;
        }}
        .settings-group {{
            background-color: alpha(currentColor, 0.035);
            border: 1px solid alpha(currentColor, 0.14);
            border-radius: 12px;
            padding: 6px;
        }}
        .boxed-list, .boxed-list row, .table-cell {{
            {list_rule}
        }}
        .table-cell {{
            border-right: 1px solid alpha(currentColor, 0.20);
        }}
        .table-fixed-cell {{
            border-right: 1px solid alpha(currentColor, 0.20);
        }}
        """
        + (f'* {{ font-family: "{font_family}"; }}' if font_family else "")
        + font_size
    )
    _provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_display(
        display,
        _provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
