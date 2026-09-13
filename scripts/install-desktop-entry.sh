#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
application_id="io.github.Hyperboreus85.WakeOnLanForLinux"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
bin_dir="${HOME}/.local/bin"

mkdir -p \
  "$bin_dir" \
  "$data_home/applications" \
  "$data_home/icons/hicolor/scalable/apps" \
  "$data_home/icons/hicolor/scalable/actions"

ln -sfn "$project_dir/run.sh" "$bin_dir/wol-linux"
desktop_file="$data_home/applications/$application_id.desktop"
# Desktop launchers do not necessarily inherit the user's shell PATH.  Use
# the project path directly so the launcher works from GNOME as well as from
# a terminal, while keeping the convenience symlink for command-line use.
sed \
  -e "s|^Exec=.*|Exec=$project_dir/run.sh|" \
  -e "/^Exec=/a TryExec=$project_dir/run.sh" \
  "$project_dir/data/$application_id.desktop" > "$desktop_file"
install -m 0644 \
  "$project_dir/data/icons/hicolor/index.theme" \
  "$data_home/icons/hicolor/index.theme"
install -m 0644 \
  "$project_dir/data/icons/hicolor/scalable/apps/$application_id.svg" \
  "$data_home/icons/hicolor/scalable/apps/$application_id.svg"
install -m 0644 \
  "$project_dir/data/icons/hicolor/scalable/actions/adw-entry-edit-symbolic.svg" \
  "$data_home/icons/hicolor/scalable/actions/adw-entry-edit-symbolic.svg"
install -m 0644 \
  "$project_dir/data/icons/hicolor/scalable/actions/adw-entry-apply-symbolic.svg" \
  "$data_home/icons/hicolor/scalable/actions/adw-entry-apply-symbolic.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache --force --ignore-theme-index \
    "$data_home/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Launcher installato nel menu Applicazioni."
