#!/usr/bin/env bash
set -euo pipefail

PROXY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Fresh, pinned transport environment. The previous .venv remains available
# for reproducing old runs but is no longer the default.
PROXY_VENV="${PROXY_VENV:-${PROXY_ROOT}/.venv_native}"
CREDENTIAL_FILE="${ROMA_CREDENTIAL_FILE:-external_archive/env/glm_api.env}"
ORG_AWARENESS_V2_REQUESTED="${ROMA_PROXY_ORG_AWARENESS_V2:-0}"

if [[ -f "${CREDENTIAL_FILE}" ]]; then
  set -a
  # This file is trusted local credential material; never print its contents.
  source "${CREDENTIAL_FILE}"
  set +a
fi

# Ignore stale environment files from the removed dynamic-position switch.
unset ROMA_PROXY_ORG_AWARENESS ROMA_PROXY_ORG_AWARENESS_CONTEXT

# Allow a caller to supply a one-run provider key without modifying the
# persistent credential file. The value is intentionally never printed.
if [[ -n "${ROMA_QWEN_API_KEY_OVERRIDE:-}" ]]; then
  export QWEN_API_KEY="${ROMA_QWEN_API_KEY_OVERRIDE}"
fi

# Keep this one-run experiment switch from being shadowed by a sourced env file.
export ROMA_PROXY_ORG_AWARENESS_V2="${ORG_AWARENESS_V2_REQUESTED}"
unset ORG_AWARENESS_V2_REQUESTED

: "${QWEN_API_KEY:?QWEN_API_KEY is not set}"
: "${QWEN_BASE_URL:?QWEN_BASE_URL is not set}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-roma-local}"
export LITELLM_PROXY_PORT="${LITELLM_PROXY_PORT:-4000}"
export ROMA_PROXY_TRACE_DIR="${ROMA_PROXY_TRACE_DIR:-${PROXY_ROOT}/traces}"
export ROMA_PROVIDER_BLOCKED_ACTION="${ROMA_PROVIDER_BLOCKED_ACTION:-record_only}"
export ROMA_PROVIDER_BLOCKED_TARGET_PATTERN="${ROMA_PROVIDER_BLOCKED_TARGET_PATTERN:-run_official_seal0.py}"
# External provider-cache adapter. Set to 0 for a clean no-adapter control.
export ROMA_EXTERNAL_QWEN_CACHE="${ROMA_EXTERNAL_QWEN_CACHE:-1}"
# Organization awareness has one active control: the V2 static architecture
# prompt switch. ROMA_PROXY_CONDITION contains only intent/plan bits.
export PYTHONPATH="${PROXY_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${PROXY_ROOT}"
exec "${PROXY_VENV}/bin/python" "${PROXY_ROOT}/start_proxy_stack.py"
