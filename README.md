# Wake on LAN for Linux

A simple, modern Wake-on-LAN manager designed for Ubuntu and other Linux desktops.

The project is currently in early development. The first milestone includes a GTK 4/
Libadwaita interface, a local SQLite device list, Wake-on-LAN packet delivery, status
checks, and import/export.

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
