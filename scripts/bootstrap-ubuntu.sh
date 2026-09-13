#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Questo script è destinato a Ubuntu/Debian (apt-get non trovato)." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  git \
  iproute2 \
  iputils-ping \
  python3 \
  python3-gi \
  python3-pip \
  python3-venv \
  gir1.2-adw-1 \
  gir1.2-gtk-4.0 \
  gettext \
  avahi-utils \
  samba-common-bin

"$project_dir/scripts/compile-translations.sh"
python3 -m venv --system-site-packages "$project_dir/.venv"
"$project_dir/.venv/bin/python" -m pip install --editable "$project_dir"
"$project_dir/scripts/install-desktop-entry.sh"

echo "Configurazione completata. Avvia dal menu Applicazioni o con: $project_dir/run.sh"
