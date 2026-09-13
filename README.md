# Wake on LAN for Linux

A simple, modern Wake-on-LAN manager designed for Ubuntu and other Linux desktops.

The project is currently in early development. Version 0.4 includes a GTK 4/Libadwaita
interface, a local SQLite device list, device editing and deletion, toggleable multiple
selection, local-network discovery, online indicators, and Wake-on-LAN packet delivery.

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
- Sort saved computers by the numeric value of their IPv4 address.
- Display IP, name/hostname, MAC address, and status in aligned horizontal columns.
- Show a status LED for each saved device: yellow while checking, green online, red offline.
- Validate and normalize common MAC address formats.
- Keep application data outside the source directory in a local SQLite database.

## Ubuntu development setup

From the project directory:

```bash
./scripts/bootstrap-ubuntu.sh
./run.sh
```

The bootstrap script installs the Ubuntu packages required by GTK and creates a Python
virtual environment. The application stores user data under the XDG data directory,
normally `~/.local/share/wake-on-lan-for-linux/wol-linux.db`.

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
