"""External LiteLLM observer and opt-in ROMA context experiment hook.

The default condition is ``BASE``: the request is passed through without
context intervention.  The intent block is identified dynamically from
ROMA's ``<overall_objective>`` XML element and removed only when its exact
canonical SHA-256 matches the request's captured source block.  Other
experimental blocks may still use the optional manifest.  This keeps all
intervention outside ROMA and avoids position-based mapping.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from litellm.integrations.custom_logger import CustomLogger


ROOT = Path(__file__).resolve().parent
TRACE_DIR = Path(os.environ.get("ROMA_PROXY_TRACE_DIR", str(ROOT / "traces")))
MANIFEST_PATH = Path(
    os.environ.get("ROMA_PROXY_MANIFEST", str(ROOT / "context_manifest.json"))
)
ORG_AWARENESS_V2_CONTEXT_PATH = Path(
    os.environ.get(
        "ROMA_PROXY_ORG_AWARENESS_V2_CONTEXT",
        str(
            ROOT.parent
            / "forammas_study"
            / "prompts"
            / "global_organizational_architecture_v2.txt"
        ),
    )
)
SECOND_ORDER_CONTEXT_PATH = Path(
    os.environ.get(
        "ROMA_PROXY_SECOND_ORDER_CONTEXT",
        str(ROOT / "second_order_context.txt"),
    )
)
LAYERS = {"atomizer", "planner", "executor", "aggregator", "verifier", "unknown"}
ORG_AWARENESS_ROLES = {"atomizer", "planner", "executor", "aggregator"}
# Condition bits are ordered as: intent, plan. Organization awareness is a
# separate, single V2 switch and has no legacy/dynamic-position counterpart.
BLOCK_TYPES = ("intent", "plan")
LAYER_ALIASES = {
    "roma-atomizer": "atomizer",
    "roma-planner": "planner",
    "roma-executor": "executor",
    "roma-aggregator": "aggregator",
    "roma-verifier": "verifier",
}


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write_trace(name: str, record: dict[str, Any]) -> None:
    """Write only metadata; never persist prompts, completions, or secrets."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    with (TRACE_DIR / name).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _paper_run_enabled() -> bool:
    return str(os.environ.get("ROMA_PAPER_RUN", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }


def _paper_jsonable(value: Any) -> Any:
    """Convert provider objects to JSON without changing the request path."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _paper_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_paper_jsonable(item) for item in value]
    for method in ("model_dump", "to_dict", "dict"):
        converter = getattr(value, method, None)
        if callable(converter):
            try:
                return _paper_jsonable(converter())
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        try:
            return _paper_jsonable(vars(value))
        except Exception:
            pass
    return str(value)


def _paper_redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("api_key", "authorization", "password", "secret", "credential")):
                redacted[str(key)] = "<REDACTED>"
            else:
                redacted[str(key)] = _paper_redact(item)
        return redacted
    if isinstance(value, list):
        return [_paper_redact(item) for item in value]
    return value


def _write_paper_raw(name: str, record: dict[str, Any]) -> None:
    if not _paper_run_enabled():
        return
    _write_trace(name, _paper_redact(_paper_jsonable(record)))


def _run_id() -> str | None:
    value = os.environ.get("ROMA_RUN_ID")
    if value:
        return value
    state_path = TRACE_DIR / "run_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return str(state.get("run_id")) if state.get("run_id") else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _latency_ms(start_time: Any, end_time: Any) -> float | None:
    if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
        return round(max(0.0, end_time - start_time) * 1000, 3)
    if hasattr(start_time, "timestamp") and hasattr(end_time, "timestamp"):
        return round(max(0.0, end_time.timestamp() - start_time.timestamp()) * 1000, 3)
    return None


def _usage(response_obj: Any) -> dict[str, Any]:
    usage = _get(response_obj, "usage") or {}
    prompt = _get(usage, "prompt_tokens")
    if prompt is None:
        prompt = _get(usage, "input_tokens", 0)
    completion = _get(usage, "completion_tokens")
    if completion is None:
        completion = _get(usage, "output_tokens", 0)
    total = _get(usage, "total_tokens")
    prompt = int(prompt or 0)
    completion = int(completion or 0)
    total = int(total if total is not None else prompt + completion)

    prompt_details = _get(usage, "prompt_tokens_details") or {}
    input_details = _get(usage, "input_tokens_details") or {}

    def _detail_max(*names: str) -> int:
        values: list[int] = []
        for details in (prompt_details, input_details, usage):
            for name in names:
                value = _get(details, name)
                if value is not None:
                    try:
                        values.append(int(value or 0))
                    except (TypeError, ValueError):
                        continue
        return max(values, default=0)

    cached = _detail_max("cached_tokens", "cache_read_input_tokens")
    created = _detail_max("cache_creation_input_tokens", "cache_write_input_tokens")
    hidden_params = _get(response_obj, "_hidden_params") or {}
    exact_cache_hit = _get(hidden_params, "cache_hit")
    if isinstance(exact_cache_hit, str):
        exact_cache_hit = exact_cache_hit.strip().lower() in {"1", "true", "yes", "on"}
    elif exact_cache_hit is not None:
        exact_cache_hit = bool(exact_cache_hit)
    else:
        exact_cache_hit = False

    return {
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": total,
        "cached_input_tokens": cached,
        "cache_creation_input_tokens": created,
        "uncached_input_tokens": max(0, prompt - cached - created),
        "provider_prompt_cache_hit": cached > 0,
        "litellm_response_cache_hit": exact_cache_hit,
    }


def _request_id(kwargs: Any, response_obj: Any) -> str | None:
    for key in ("request_id", "litellm_call_id", "litellm_trace_id", "call_id"):
        value = _get(kwargs, key)
        if value:
            return str(value)
    value = _get(response_obj, "id")
    return str(value) if value else None


def _request_context(kwargs: Any, response_obj: Any) -> dict[str, Any]:
    metadata = _get(kwargs, "metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    model = _get(kwargs, "model") or _get(response_obj, "model")
    try:
        condition = _condition()[0]
    except (ValueError, RuntimeError):
        condition = os.environ.get("ROMA_PROXY_CONDITION", "baseline")
    return {
        "request_id": _request_id(kwargs, response_obj),
        "model": model,
        "condition": condition,
        "layer": metadata.get("roma_layer") or _get(kwargs, "roma_layer", "unknown"),
        "node_code": metadata.get("roma_node_code") or _get(kwargs, "roma_node_code"),
        "call_type": _get(kwargs, "call_type"),
    }


def _error_text(kwargs: Any, response_obj: Any) -> str:
    """Extract provider error text without serializing the request payload."""
    values: list[str] = []
    if response_obj is not None:
        values.append(str(response_obj))
    for key in (
        "exception",
        "error",
        "error_message",
        "exception_string",
        "exception_message",
        "original_exception",
    ):
        value = _get(kwargs, key)
        if value is not None:
            values.append(str(value))
    return " | ".join(value for value in values if value)


def _provider_block_reason(error_text: str) -> str | None:
    if re.search(r"DataInspectionFailed", error_text, re.IGNORECASE):
        return "DataInspectionFailed"
    if re.search(r"inappropriate\s+content", error_text, re.IGNORECASE):
        return "DataInspectionFailed"
    if re.search(r"circuit\s*breaker\s+is\s+open|CircuitOpenError", error_text, re.IGNORECASE):
        return "CircuitBreakerOpen"
    return None


def _active_node_snapshot() -> list[dict[str, Any]]:
    state_path = TRACE_DIR / "run_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    nodes = state.get("active_nodes", [])
    return nodes if isinstance(nodes, list) else []


def _runner_pid() -> int | None:
    state_path = TRACE_DIR / "run_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        value = state.get("runner_pid")
        return int(value) if value is not None else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _abort_runner_on_provider_block(
    *, error_text: str, context: dict[str, Any], reason: str, source: str
) -> None:
    """Record a provider block and optionally signal the owning runner.

    This is intentionally outside ROMA. A provider safety rejection is not
    retryable, but it is a single-example failure: the official evaluator's
    per-example exception path can return that row and continue the batch.
    The safe default is therefore ``record_only``; whole-run termination is
    available only as an explicit opt-in.
    """
    action = os.environ.get("ROMA_PROVIDER_BLOCKED_ACTION", "record_only").strip().lower()
    run_id = _run_id()
    active_nodes = _active_node_snapshot()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "event": "provider_blocked",
        "failure_class": "provider_blocked",
        "provider_error_type": reason,
        "request_phase": "llm_request",
        "source": source,
        "question_execution_id": active_nodes[-1].get("execution_id") if active_nodes else None,
        "active_nodes": active_nodes,
        **context,
        "error": error_text[:1000],
        "action": action,
    }

    marker_path = TRACE_DIR / "provider_blocked.marker"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        marker = {}
    if marker.get("run_id") == run_id:
        record["abort_sent"] = bool(marker.get("abort_sent"))
        _write_trace("provider_blocked.jsonl", record)
        return

    pid = _runner_pid()
    record["runner_pid"] = pid
    abort_sent = False
    if action in {"terminate_run", "abort", "kill_runner"} and pid:
        try:
            command = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
            target_pattern = os.environ.get(
                "ROMA_PROVIDER_BLOCKED_TARGET_PATTERN", "run_official_seal0.py"
            )
            if target_pattern in command and pid != os.getpid():
                os.kill(pid, signal.SIGTERM)
                abort_sent = True
        except (OSError, subprocess.SubprocessError):
            abort_sent = False
    record["abort_sent"] = abort_sent
    _write_trace("provider_blocked.jsonl", record)
    try:
        marker_path.write_text(
            json.dumps(
                {"run_id": run_id, "runner_pid": pid, "abort_sent": abort_sent},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _record_llm_event(
    status: str,
    kwargs: Any,
    response_obj: Any,
    start_time: Any,
    end_time: Any,
) -> bool:
    error_text = _error_text(kwargs, response_obj) if status == "failure" else ""
    provider_block_reason = _provider_block_reason(error_text)
    event_status = "provider_blocked" if provider_block_reason else status
    usage = _usage(response_obj) if status == "success" else {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "uncached_input_tokens": 0,
        "provider_prompt_cache_hit": False,
        "litellm_response_cache_hit": False,
    }
    retry_count = _get(kwargs, "num_retries")
    if retry_count is None:
        retry_count = _get(kwargs, "retry_count", 0)
    try:
        retry_count = int(retry_count or 0)
    except (TypeError, ValueError):
        retry_count = 0
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": _run_id(),
        "status": event_status,
        **_request_context(kwargs, response_obj),
        **usage,
        "latency_ms": _latency_ms(start_time, end_time),
        "retry_count": retry_count,
        "exception_type": provider_block_reason or (type(response_obj).__name__ if status == "failure" else None),
        "error": error_text[:500] if status == "failure" else None,
    }
    _write_trace("llm_events.jsonl", record)
    _write_paper_raw(
        "raw_llm_events.jsonl",
        {
            "timestamp": record["timestamp"],
            "run_id": record.get("run_id"),
            "request_id": record.get("request_id"),
            "status": event_status,
            "request": {
                "model": _get(kwargs, "model"),
                "messages": _get(kwargs, "messages"),
                "tools": _get(kwargs, "tools"),
                "tool_choice": _get(kwargs, "tool_choice"),
                "temperature": _get(kwargs, "temperature"),
                "max_tokens": _get(kwargs, "max_tokens"),
                "seed": _get(kwargs, "seed"),
            },
            "response": response_obj,
            "usage": usage,
            "latency_ms": record.get("latency_ms"),
            "retry_count": record.get("retry_count"),
            "error": record.get("error"),
        },
    )
    if provider_block_reason:
        _abort_runner_on_provider_block(
            error_text=error_text,
            context={key: record.get(key) for key in (
                "request_id", "model", "condition", "layer", "node_code", "call_type"
            )},
            reason=provider_block_reason,
            source="llm_failure_event",
        )
    return bool(provider_block_reason)


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _message_summary(messages: Any) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    summary: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            summary.append({"type": type(message).__name__})
            continue
        content = message.get("content")
        if isinstance(content, list):
            content_size = sum(
                len(str(part.get("text", ""))) if isinstance(part, dict) else len(str(part))
                for part in content
            )
        else:
            content_size = len(str(content or ""))
        summary.append(
            {
                "role": message.get("role"),
                "content_chars": content_size,
                "has_tool_calls": bool(message.get("tool_calls")),
                "has_tool_call_id": bool(message.get("tool_call_id")),
            }
        )
    return summary


def _parse_bit(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _validate_expected_condition(observed: str) -> None:
    """Fail closed when an isolated runner and proxy disagree."""
    expected_raw = os.environ.get("ROMA_PROXY_EXPECTED_CONDITION")
    if not expected_raw:
        return
    expected_raw = expected_raw.strip().lower()
    if expected_raw in {"baseline", "base", "b"}:
        expected = "BASE"
    elif re.fullmatch(r"[01]{2}", expected_raw):
        expected = expected_raw
    else:
        raise ValueError(
            "ROMA_PROXY_EXPECTED_CONDITION must be BASE or a two-bit intent/plan value"
        )
    if observed != expected:
        _write_trace(
            "condition_guard.jsonl",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": _run_id(),
                "event": "condition_mismatch",
                "observed": observed,
                "expected": expected,
            },
        )
        raise RuntimeError(
            f"ROMA condition mismatch: proxy observed {observed}, expected {expected}"
        )


def _condition() -> tuple[str, dict[str, bool], bool]:
    """Return (label, visibility, is_baseline).

    ``BASE`` is intentionally distinct from ``111``. BASE means no rewrite at
    all and therefore remains valid even if the official prompt does not
    contain one of the three experimental block types. For bit conditions the
    order is ``intent, plan``. Organization awareness is injected by the
    worker before LiteLLM; this hook only observes whether the exact block arrived.
    """
    raw = os.environ.get("ROMA_PROXY_CONDITION", "baseline").strip().lower()
    if raw in {"baseline", "base", "b"}:
        label = "BASE"
        _validate_expected_condition(label)
        return label, dict.fromkeys(BLOCK_TYPES, True), True
    if not re.fullmatch(r"[01]{2}", raw):
        raise ValueError(
            "ROMA_PROXY_CONDITION must be BASE or a two-bit intent/plan value such as 11"
        )
    visible = dict(zip(BLOCK_TYPES, (_parse_bit(bit, False) for bit in raw)))
    _validate_expected_condition(raw)
    return raw, visible, False


def _layer(data: dict[str, Any]) -> str:
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("roma_layer"):
        candidate = str(metadata["roma_layer"]).lower()
        role = _normalize_role(candidate)
        if role:
            return role
        if candidate in LAYERS:
            return candidate
    # The external worker bridge carries the real TaskNode snapshot in the
    # request-local metadata. Use it as a fallback for role routing so a
    # layer-scoped experiment does not depend on model-name aliases.
    if isinstance(metadata, dict):
        current = metadata.get("roma_current_node")
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except json.JSONDecodeError:
                current = None
        if isinstance(current, dict):
            for value in (
                current.get("module_name"),
                current.get("agent_type"),
                current.get("role"),
            ):
                role = _normalize_role(value)
                if role:
                    return role
    public_model = str(data.get("model", "")).rsplit("/", 1)[-1].lower()
    return LAYER_ALIASES.get(public_model, "unknown")


def _node_code(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("roma_node_code"):
        return str(metadata["roma_node_code"])
    return data.get("roma_node_code") or os.environ.get("ROMA_PROXY_NODE_CODE")


def _normalize_role(value: Any) -> str:
    """Normalize ROMA enum/class names to one of the four exposed roles."""
    raw = str(value or "").strip().lower()
    for role in ORG_AWARENESS_ROLES:
        if raw == role or raw.endswith(f".{role}") or role in raw:
            return role
    return ""


def _current_org_position(
    data: dict[str, Any], layer: str
) -> dict[str, Any] | None:
    """Read the explicit current-node snapshot carried by this request.

    The worker-side external bridge binds the official TaskNode at node entry
    and serializes it as ``metadata.roma_current_node``. The proxy deliberately
    does not match task IDs or consult the shared active-node stack here.
    """
    metadata = data.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    current = metadata.get("roma_current_node") or data.get("roma_current_node")
    if isinstance(current, str):
        try:
            current = json.loads(current)
        except json.JSONDecodeError:
            return None
    if not isinstance(current, dict):
        return None

    role = _normalize_role(
        (current or {}).get("agent_type")
        or (current or {}).get("role")
    )
    if role not in ORG_AWARENESS_ROLES:
        return None

    depth_value = current.get("depth")
    try:
        depth = int(depth_value)
    except (TypeError, ValueError):
        return None
    if depth < 0:
        return None

    parent_id = current.get("parent_id")
    module = current.get("module_name") or current.get("module") or role
    return {
        "role": role,
        "depth": depth,
        "origin": "delegated by a parent node" if parent_id else "root node; no parent node",
        "module": str(module),
        "return_path": "return to the parent node" if parent_id else "return to the root caller",
        "source": "request_current_node",
    }


def _observe_org_awareness_v2(messages: Any) -> dict[str, Any]:
    """Audit the pre-LiteLLM V2 system block without changing messages or role."""
    marker = "[ROMA GLOBAL ORGANIZATIONAL ARCHITECTURE]"
    try:
        template = ORG_AWARENESS_V2_CONTEXT_PATH.read_text(encoding="utf-8")
    except OSError:
        return {"status": "template_unavailable", "template_sha256": None, "matches": 0}
    digest = _digest(template)
    if not isinstance(messages, list):
        return {"status": "messages_not_list", "template_sha256": digest, "matches": 0}
    system_contents = [
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, dict) and message.get("role") == "system"
    ]
    matches = sum(content == template for content in system_contents)
    marker_count = sum(content.startswith(marker) for content in system_contents)
    if matches == 1 and marker_count == 1:
        status = "present_pre_litellm"
    elif matches > 1 or marker_count > 1:
        status = "duplicate_or_conflicting"
    elif marker_count:
        status = "content_mismatch"
    else:
        status = "absent"
    return {"status": status, "template_sha256": digest, "matches": matches}


def _layer_overrides() -> dict[str, dict[str, bool]]:
    raw = os.environ.get("ROMA_PROXY_LAYER_OVERRIDES", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("ROMA_PROXY_LAYER_OVERRIDES must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("ROMA_PROXY_LAYER_OVERRIDES must be a JSON object")
    result: dict[str, dict[str, bool]] = {}
    for raw_layer, raw_values in parsed.items():
        layer = str(raw_layer).lower()
        if layer not in LAYERS or not isinstance(raw_values, dict):
            continue
        result[layer] = {
            block_type: _parse_bit(raw_values[block_type])
            for block_type in BLOCK_TYPES
            if block_type in raw_values
        }
    return result


def _second_order_layers() -> dict[str, Any]:
    """Read role-scoped second-order settings.

    Boolean values preserve the original optional second-order text-block
    switch.  Mapping values are the newer visibility-only form, for example
    ``{"executor": {"intent": 0}}``; they never inject extra prompt text.
    """
    raw = os.environ.get("ROMA_PROXY_SECOND_ORDER_LAYERS", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "ROMA_PROXY_SECOND_ORDER_LAYERS must be valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("ROMA_PROXY_SECOND_ORDER_LAYERS must be a JSON object")
    result: dict[str, Any] = {}
    for role in ORG_AWARENESS_ROLES:
        if role not in parsed:
            continue
        value = parsed[role]
        if isinstance(value, dict):
            result[role] = {
                block_type: _parse_bit(value[block_type])
                for block_type in BLOCK_TYPES
                if block_type in value
            }
        else:
            result[role] = _parse_bit(value, False)
    return result


def _second_order_enabled(layer: str) -> tuple[bool, bool, dict[str, bool]]:
    """Return legacy text-block settings for one layer."""
    master = _parse_bit(os.environ.get("ROMA_PROXY_SECOND_ORDER", "0"), False)
    configured = _second_order_layers()
    configured_value = configured.get(layer, False)
    return master, bool(master and configured_value is True), configured


def _second_order_visibility(layer: str) -> dict[str, bool]:
    """Return independent per-layer visibility overrides, if configured."""
    if not _parse_bit(os.environ.get("ROMA_PROXY_SECOND_ORDER", "0"), False):
        return {}
    configured = _second_order_layers().get(layer)
    return dict(configured) if isinstance(configured, dict) else {}


def _apply_second_order(
    messages: Any,
    position: dict[str, Any] | None,
    layer: str,
    master_enabled: bool,
    layer_enabled: bool,
) -> tuple[Any, dict[str, Any]]:
    """Inject one independent, role-scoped second-order context block."""
    audit: dict[str, Any] = {
        "master_enabled": master_enabled,
        "layer_enabled": layer_enabled,
        "layer": layer,
        "injected": False,
        "status": "disabled" if not master_enabled or not layer_enabled else "pending",
        "template_sha256": None,
        "position_source": None,
    }
    if not master_enabled or not layer_enabled:
        return messages, audit
    if position is None:
        audit["status"] = "position_unavailable"
        return messages, audit
    if not isinstance(messages, list):
        audit["status"] = "messages_not_list"
        return messages, audit
    try:
        template = SECOND_ORDER_CONTEXT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            "ROMA second-order context is unavailable: "
            f"{SECOND_ORDER_CONTEXT_PATH}"
        ) from exc
    if not template.strip():
        raise RuntimeError("ROMA second-order context must not be empty")
    marker = "[ROMA SECOND-ORDER CONTEXT]"
    audit.update(
        {
            "template_sha256": _digest(template),
            "position_source": position.get("source"),
        }
    )
    for message in messages:
        if isinstance(message, dict) and str(message.get("content") or "").startswith(marker):
            audit["status"] = "already_present"
            return messages, audit
    content = template.format(**position)
    rewritten = copy.deepcopy(messages)
    rewritten.insert(0, {"role": "system", "content": content})
    audit.update({"injected": True, "status": "injected"})
    return rewritten, audit


def _effective_visibility(
    layer: str, node_code: str | None = None
) -> tuple[str, dict[str, bool], bool]:
    condition_code, visible, is_baseline = _condition()
    if is_baseline:
        return condition_code, visible, is_baseline
    visible.update(_layer_overrides().get(layer, {}))
    visible.update(_second_order_visibility(layer))
    raw = os.environ.get("ROMA_PROXY_NODE_OVERRIDES", "{}")
    node_overrides = json.loads(raw)
    if isinstance(node_overrides, dict) and node_code:
        values = node_overrides.get(node_code)
        if isinstance(values, dict):
            visible.update(
                {
                    block_type: _parse_bit(values[block_type])
                    for block_type in BLOCK_TYPES
                    if block_type in values
                }
            )
    condition_code = "".join("1" if visible[name] else "0" for name in BLOCK_TYPES)
    return condition_code, visible, is_baseline


def _load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("blocks", payload) if isinstance(payload, (dict, list)) else []
    if not isinstance(entries, list):
        raise ValueError("ROMA_PROXY_MANIFEST must contain a 'blocks' list")
    return [entry for entry in entries if isinstance(entry, dict)]


def _string_content(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    return content if isinstance(content, str) else None


def _canonical_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


_OVERALL_OBJECTIVE_RE = re.compile(
    r"<overall_objective>.*?</overall_objective>", re.IGNORECASE | re.DOTALL
)


def _intent_candidates(messages: Any) -> list[dict[str, Any]]:
    """Find ROMA's complete global-intent XML blocks without storing content."""
    candidates: list[dict[str, Any]] = []
    if not isinstance(messages, list):
        return candidates
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = _string_content(message)
        if content is None:
            continue
        for match in _OVERALL_OBJECTIVE_RE.finditer(content):
            block = _canonical_text(match.group(0))
            candidates.append(
                {
                    "message_index": message_index,
                    "start": match.start(),
                    "end": match.end(),
                    "sha256": _digest(block),
                    "chars": len(block),
                }
            )
    return candidates


def _apply_dynamic_intent_hash(
    messages: Any, visible: bool
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Remove exact copies of ROMA's captured global-intent block.

    The first observed ``overall_objective`` block is the source of truth for
    this request.  We then match every candidate by its canonical hash, so a
    repeated root objective is removed consistently while a different XML
    block is left untouched.
    """
    rewritten = copy.deepcopy(messages)
    candidates = _intent_candidates(rewritten)
    if not candidates:
        return rewritten, [], [{"block_type": "intent", "status": "not_found"}], None

    source_hash = candidates[0]["sha256"]
    applied: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    by_message: dict[int, list[dict[str, Any]]] = {}
    for candidate in candidates:
        if candidate["sha256"] == source_hash:
            by_message.setdefault(candidate["message_index"], []).append(candidate)

    for message_index, spans in by_message.items():
        message = rewritten[message_index]
        content = _string_content(message)
        if content is None:
            continue
        for span in sorted(spans, key=lambda item: item["start"], reverse=True):
            start, end = span["start"], span["end"]
            audit = {
                "block_type": "intent",
                "message_index": message_index,
                "start": start,
                "end": end,
                "sha256": span["sha256"],
                "visible": visible,
            }
            if visible:
                audit["status"] = "retained"
            else:
                content = content[:start] + content[end:]
                message["content"] = content
                audit["status"] = "removed"
            applied.append(audit)

    if not by_message:
        unknown.append(
            {"block_type": "intent", "sha256": source_hash, "status": "not_found"}
        )
    return rewritten, applied, unknown, source_hash


def _apply_manifest(
    messages: Any,
    layer: str,
    node_code: str | None,
    visible: dict[str, bool],
    manifest: list[dict[str, Any]],
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    rewritten = copy.deepcopy(messages)
    applied: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    if not isinstance(rewritten, list):
        return rewritten, applied, unknown

    for index, message in enumerate(rewritten):
        if not isinstance(message, dict):
            continue
        content = _string_content(message)
        if content is None:
            continue
        entries = []
        for entry in manifest:
            if entry.get("message_index") != index or entry.get("block_type") not in BLOCK_TYPES:
                continue
            if entry.get("node_code"):
                if not node_code or str(entry["node_code"]).lower() not in {
                    str(node_code).lower(),
                    "all",
                }:
                    continue
            elif str(entry.get("layer", layer)).lower() not in {layer, "all"}:
                continue
            entries.append(entry)
        for entry in sorted(entries, key=lambda item: int(item.get("start", 0)), reverse=True):
            block_type = str(entry["block_type"])
            start = int(entry.get("start", -1))
            end = int(entry.get("end", -1))
            candidate = _canonical_text(content[start:end]) if 0 <= start <= end <= len(content) else ""
            observed_hash = _digest(candidate)
            expected_hash = str(entry.get("sha256", ""))
            audit = {
                "block_id": entry.get("block_id"),
                "message_index": index,
                "block_type": block_type,
                "layer": layer,
                "node_code": node_code,
                "expected_sha256": expected_hash,
                "observed_sha256": observed_hash,
                "start": start,
                "end": end,
                "visible": visible[block_type],
            }
            if not candidate or observed_hash != expected_hash:
                audit["status"] = "hash_mismatch"
                unknown.append(audit)
                continue
            if not visible[block_type]:
                content = content[:start] + content[end:]
                message["content"] = content
                audit["status"] = "removed"
            else:
                audit["status"] = "retained"
            applied.append(audit)
    return rewritten, applied, unknown


class RomaPreCallHook(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,
        data: dict,
        call_type: str,
    ) -> dict:
        before = copy.deepcopy(data.get("messages"))
        layer = _layer(data)
        node_code = _node_code(data)
        condition_code, visible, is_baseline = _effective_visibility(layer, node_code)
        manifest = _load_manifest()
        after, intent_applied, intent_unknown, intent_hash = _apply_dynamic_intent_hash(
            before, visible["intent"]
        )
        after, manifest_applied, manifest_unknown = _apply_manifest(
            after, layer, node_code, visible, manifest
        )
        applied = intent_applied + manifest_applied
        unknown = intent_unknown + manifest_unknown
        # V2 insertion happens in the worker before LiteLLM. This hook only
        # records whether the exact static system block arrived; it never
        # branches on role or mutates the V2 context.
        org_awareness_v2 = _observe_org_awareness_v2(before)
        second_order_master, second_order_layer, second_order_layers = _second_order_enabled(layer)
        second_order_visibility = _second_order_visibility(layer)
        after, second_order = _apply_second_order(
            after,
            _current_org_position(data, layer),
            layer,
            second_order_master,
            second_order_layer,
        )
        if second_order_visibility:
            second_order.update(
                {
                    "mode": "visibility_override",
                    "status": "visibility_only",
                    "layer_enabled": True,
                    "visibility_overrides": second_order_visibility,
                }
            )
        # Prompt caching is deliberately outside LiteLLM. The external Qwen
        # adapter adds only provider transport metadata after this hook; this
        # hook never rewrites messages for caching.
        provider_prompt_cache = {
            "enabled": False,
            "status": "delegated_external_adapter",
            "transport_mutation": False,
        }
        if not is_baseline and any(not value for value in visible.values()) and unknown and _parse_bit(
            os.environ.get("ROMA_PROXY_REQUIRE_MAPPED"), False
        ):
            raise ValueError(
                f"Unmapped ROMA context blocks for restricted condition: {unknown[:3]}"
            )
        data["messages"] = after

        metadata = data.get("metadata")
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        data["metadata"] = metadata

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": _run_id(),
            "request_id": data.get("request_id"),
            "call_type": call_type,
            "model": data.get("model"),
            "layer": layer,
            "node_code": node_code,
            "condition_requested": _condition()[0],
            "condition": condition_code,
            "effective_condition": condition_code,
            "cache_namespace": None,
            "baseline": is_baseline,
            "visibility": visible,
            "manifest_entries": len(manifest),
            "dynamic_intent_sha256": intent_hash,
            "applied_blocks": applied,
            "unmapped_blocks": unknown,
            "organization_awareness": org_awareness_v2,
            "organization_awareness_v2": org_awareness_v2,
            "second_order": {
                **second_order,
                "configured_layers": second_order_layers,
            },
            "provider_prompt_cache": provider_prompt_cache,
            "message_count_before": len(before) if isinstance(before, list) else None,
            "message_count_after": len(after) if isinstance(after, list) else None,
            "messages_before_sha256": _digest(before),
            "messages_after_sha256": _digest(after),
            "changed": before != after,
            "messages_before": _message_summary(before),
            "messages_after": _message_summary(after),
        }
        _write_trace("pre_call.jsonl", record)
        _write_paper_raw(
            "raw_requests.jsonl",
            {
                "timestamp": record["timestamp"],
                "run_id": record.get("run_id"),
                "request_id": record.get("request_id"),
                "call_type": call_type,
                "condition": condition_code,
                "layer": layer,
                "node_code": node_code,
                "messages_before": before,
                "messages_after": after,
                "tools": data.get("tools"),
                "tool_choice": data.get("tool_choice"),
                "model": data.get("model"),
                "temperature": data.get("temperature"),
                "max_tokens": data.get("max_tokens"),
                "seed": data.get("seed"),
                "metadata": data.get("metadata"),
                "organization_awareness": org_awareness_v2,
                "organization_awareness_v2": org_awareness_v2,
                "second_order": {
                    **second_order,
                    "configured_layers": second_order_layers,
                },
                "provider_prompt_cache": provider_prompt_cache,
            },
        )
        return data

    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict: Any,
        traceback_str: str | None = None,
    ) -> None:
        """Stop the external benchmark immediately on a provider safety block."""
        error_text = str(original_exception)
        reason = _provider_block_reason(error_text)
        if reason:
            _abort_runner_on_provider_block(
                error_text=error_text,
                context=_request_context(request_data, None),
                reason=reason,
                source="async_post_call_failure_hook",
            )

    async def async_log_success_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        _record_llm_event("success", kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        _record_llm_event("failure", kwargs, response_obj, start_time, end_time)

    def log_success_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        _record_llm_event("success", kwargs, response_obj, start_time, end_time)

    def log_failure_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        _record_llm_event("failure", kwargs, response_obj, start_time, end_time)


proxy_handler_instance = RomaPreCallHook()
