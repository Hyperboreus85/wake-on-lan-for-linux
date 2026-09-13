#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$project_dir/.venv"

if [[ ! -x "$venv_dir/bin/python" ]]; then
  echo "Ambiente non configurato. Esegui: ./scripts/bootstrap-ubuntu.sh" >&2
  exit 1
fi

exec "$venv_dir/bin/python" -m wol_linux "$@"

