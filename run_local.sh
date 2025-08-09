#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo ".env file not found in current directory."
  exit 1
fi

export $(grep -v '^#' .env | xargs)

# Activate local virtualenv if present
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec python3 -u app.py


