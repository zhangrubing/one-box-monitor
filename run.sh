#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export APP_SECRET="${APP_SECRET:-dev_secret_change_me}"

exec python -m uvicorn backend.app:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000

