#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$project_dir/.venv/bin/python" ]]; then
  python_bin="$project_dir/.venv/bin/python"
else
  python_bin="python3"
fi

cd "$project_dir"
PYTHONPATH="$project_dir/src" exec "$python_bin" -m unittest discover -s tests -v
