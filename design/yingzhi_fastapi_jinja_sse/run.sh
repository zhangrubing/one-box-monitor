#!/usr/bin/env bash
set -e
PYPI_MIRROR=${PYPI_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
if ! pip install -r requirements.txt -i "$PYPI_MIRROR" --timeout 120 --retries 3; then
  echo "[WARN] 镜像安装失败，回退官方 PyPI..."
  pip install -r requirements.txt
fi
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
