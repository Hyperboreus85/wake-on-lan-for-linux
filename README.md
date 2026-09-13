# Wake on LAN for Linux

A simple, modern Wake-on-LAN manager designed for Ubuntu and other Linux desktops.

The project is currently in early development. Version 0.5 includes a GTK 4/Libadwaita
interface, a local SQLite device list, device editing and deletion, toggleable multiple
selection, local-network discovery, online indicators, appearance settings, translations,
complete portable backups, and Wake-on-LAN packet delivery.

Bulk wake operations are deliberately protected by three consecutive confirmation
dialogs. The final dialog shows the exact number of affected computers, helping prevent
accidental mass wake-ups.

## Current features

- Add, edit, and remove computers.
- Store IPv4, MAC, broadcast, UDP port, vendor, model, serial number, BIOS, group, and notes.
- Wake one or several selected computers.
- Wake all configured computers with three-step confirmation.
- Scan every address in the detected local IPv4 subnet and choose which devices to import.
- Resolve hostnames during discovery when local DNS, mDNS, or `/etc/hosts` provides them.
- Try reverse DNS, Avahi/mDNS, and NetBIOS fallbacks when resolving hostnames.
- Sort saved computers by the numeric value of their IPv4 address.
- Display IP, name/hostname, MAC address, and status in aligned horizontal columns.
- Show a status LED for each saved device: yellow while checking, green online, red offline.
- Choose the system, light, or dark theme and one of five accent colors.
- Use the interface in Italian or English and install additional gettext `.mo` catalogs.
- Export computers, all their fields, preferences, and custom translations to one JSON file.
- Import a backup on another installation, merging computers by MAC address without duplicates.
- Install an application-menu launcher with a dedicated icon during Ubuntu bootstrap.
- Validate and normalize common MAC address formats.
- Keep application data outside the source directory in a local SQLite database.

## Ubuntu development setup

From the project directory:

```bash
./scripts/bootstrap-ubuntu.sh
./run.sh
```

The bootstrap script installs the Ubuntu packages required by GTK, hostname discovery,
compiles translations,
creates a Python virtual environment, and installs a launcher in the current user's
application menu. The application stores user data under the XDG data directory, normally
`~/.local/share/wake-on-lan-for-linux/wol-linux.db`.

If the launcher is not visible immediately, log out and back in once. You can reinstall it
without repeating the full bootstrap:

```bash
./scripts/install-desktop-entry.sh
```

The launcher installer also refreshes the local Hicolor icon cache so updated application
icons are picked up by GNOME without reinstalling the application.

## Backup and transfer

Open **Settings → Backup and transfer → Export complete backup** to create a portable JSON
file. Importing it on another Ubuntu PC restores appearance preferences and saved devices.
Existing devices with the same normalized MAC address are updated; unrelated local devices
are kept. Any user-installed translation catalogs are embedded in the same backup.

Treat a backup as private data: it can contain IP addresses, MAC addresses, serial numbers,
BIOS information, and notes entered by the user.

## Translations

Italian is the source language and English is bundled. Additional translations use GNU
gettext `.mo` catalogs. Name a catalog after its language code, for example `fr.mo` or
`de_DE.mo`, and import it from Settings. Developers can rebuild bundled catalogs with:

```bash
./scripts/compile-translations.sh
```

## Working from `/opt`

To create a user-owned development directory and copy this checkout into it:

```bash
./scripts/install-worktree-to-opt.sh
cd /opt/wake-on-lan-for-linux
./scripts/bootstrap-ubuntu.sh
```

The `/opt` helper uses `sudo` only for creating the directory and changing its owner.
Application commands should not be run with `sudo`.

## Tests

```bash
./scripts/test.sh
```

## License

GPL-3.0-or-later.
