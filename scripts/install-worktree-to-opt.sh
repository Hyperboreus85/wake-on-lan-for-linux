#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
target_dir="/opt/wake-on-lan-for-linux"

sudo install -d -o "$USER" -g "$(id -gn)" -m 0755 "$target_dir"
cp -a "$source_dir/." "$target_dir/"

echo "Progetto copiato in $target_dir e assegnato a $USER."

