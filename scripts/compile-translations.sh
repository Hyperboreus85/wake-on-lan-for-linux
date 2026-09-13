#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

for source in "$project_dir"/po/*.po; do
  language="$(basename -- "$source" .po)"
  destination="$project_dir/src/wol_linux/locale/$language/LC_MESSAGES/wol-linux.mo"
  mkdir -p "$(dirname -- "$destination")"
  msgfmt --check --output-file="$destination" "$source"
done

echo "Traduzioni compilate."
