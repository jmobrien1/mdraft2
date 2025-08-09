#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo ".env file not found in current directory."
  exit 1
fi

export $(grep -v '^#' .env | xargs)

python app.py


