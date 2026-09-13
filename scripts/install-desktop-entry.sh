#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
application_id="io.github.Hyperboreus85.WakeOnLanForLinux"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
bin_dir="${HOME}/.local/bin"

mkdir -p \
  "$bin_dir" \
  "$data_home/applications" \
  "$data_home/icons/hicolor/scalable/apps"

ln -sfn "$project_dir/run.sh" "$bin_dir/wol-linux"
install -m 0644 \
  "$project_dir/data/$application_id.desktop" \
  "$data_home/applications/$application_id.desktop"
install -m 0644 \
  "$project_dir/data/icons/hicolor/scalable/apps/$application_id.svg" \
  "$data_home/icons/hicolor/scalable/apps/$application_id.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true
fi

echo "Launcher installato nel menu Applicazioni."
