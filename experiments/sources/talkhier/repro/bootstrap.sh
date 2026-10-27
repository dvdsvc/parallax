#!/bin/sh
set -eu
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$REPO_ROOT/.cache/uv}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$REPO_ROOT/.cache/pip}"
PYTHON_BIN=${TALKHIER_PYTHON:-python3.12}
if [ ! -x .venv/bin/python ]; then
    "$PYTHON_BIN" -m venv .venv
fi
if command -v uv >/dev/null 2>&1; then
    uv pip sync --python .venv/bin/python repro/requirements.mmlu.lock.txt
else
    .venv/bin/python -m pip install -r repro/requirements.mmlu.lock.txt
    .venv/bin/python -m pip check
fi
mkdir -p config .local results
if [ ! -f config/config.ini ]; then
    cp template/config.ini config/config.ini
fi
if [ ! -f config/config_llm.ini ]; then
    cp template/config_llm.ini config/config_llm.ini
fi
.venv/bin/python repro/prepare_mmlu.py
.venv/bin/python repro/validate_setup.py
