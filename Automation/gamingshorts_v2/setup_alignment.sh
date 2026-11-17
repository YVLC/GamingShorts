#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
align_python=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] <= (3,12)))'; then
    align_python="$candidate"
    break
  fi
done
if [[ -z "$align_python" ]]; then
  echo 'Install Python 3.10–3.12 with its venv package for the optional alignment environment. Your main pipeline Python remains unchanged.'
  exit 1
fi
"$align_python" -m venv .align-venv
.align-venv/bin/python -m pip install --upgrade pip
.align-venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.align-venv/bin/python -m pip install stable-ts
.align-venv/bin/python -m pip freeze > alignment-requirements-installed.txt
.align-venv/bin/python -c 'import stable_whisper; print("Alignment dependencies ready. Model downloads on first alignment.")'
