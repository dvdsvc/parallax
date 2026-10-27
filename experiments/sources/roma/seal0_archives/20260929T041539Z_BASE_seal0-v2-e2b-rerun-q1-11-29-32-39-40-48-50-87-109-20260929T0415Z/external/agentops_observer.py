"""External AgentOps observer for the unmodified ROMA v1 runtime.

This module replaces only ROMA's global span-manager object from the harness.
It reads the official ``TaskNode`` and ``ExecutionContext`` objects at the
existing execution boundary, emits AgentOps task/tool spans, and writes a
small local event ledger for deterministic metric aggregation. ROMA source and
its execution primitive are not patched.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .current_node_context import bind_current_node, install_lm_current_node_bridge


ROOT = Path(__file__).resolve().parents[1] / "roma_litellm_proxy"
TRACE_DIR = Path(os.environ.get("ROMA_PROXY_TRACE_DIR", str(ROOT / "traces")))
_write_lock = threading.Lock()


def _write(name: str, record: dict[str, Any]) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with (TRACE_DIR / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _paper_enabled() -> bool:
    return str(os.environ.get("ROMA_PAPER_RUN", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }


def _paper_raw(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _paper_raw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_paper_raw(item) for item in value]
    for method in ("model_dump", "to_dict", "dict"):
        converter = getattr(value, method, None)
        if callable(converter):
            try:
                return _paper_raw(converter())
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        try:
            return _paper_raw(vars(value))
        except Exception:
            pass
    return str(value)


def _paper_redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("api_key", "authorization", "password", "secret", "credential")):
                result[str(key)] = "<REDACTED>"
            else:
                result[str(key)] = _paper_redact(item)
        return result
    if isinstance(value, list):
        return [_paper_redact(item) for item in value]
    return value


def _write_paper_raw(name: str, record: dict[str, Any]) -> None:
    if _paper_enabled():
        _write(name, _paper_redact(_paper_raw(record)))


def _update_run_state(**updates: Any) -> None:
    """Update the external controller state without changing ROMA state."""
    path = TRACE_DIR / "run_state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        state = {}
    state.update(updates)
    try:
        with _write_lock:
            temporary_path = path.with_name(path.name + ".tmp")
            temporary_path.write_text(
                json.dumps(state, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            os.replace(temporary_path, path)
    except OSError:
        pass


def _update_recording_manifest(**updates: Any) -> None:
    """Persist recorder lifecycle state even when the worker later fails."""
    path = TRACE_DIR / "recording_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(updates)
    try:
        with _write_lock:
            temporary_path = path.with_name(path.name + ".tmp")
            temporary_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, path)
    except OSError:
        pass


def _active_node_snapshot() -> list[dict[str, Any]]:
    path = TRACE_DIR / "run_state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    nodes = state.get("active_nodes", [])
    return list(nodes) if isinstance(nodes, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _goal_hash(goal: Any) -> str:
    return hashlib.sha256(str(goal or "").encode("utf-8")).hexdigest()


def _run_id() -> str | None:
    return os.environ.get("ROMA_RUN_ID")


def _tool_data(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        data = event.model_dump()
    elif isinstance(event, dict):
        data = event
    else:
        data = {name: getattr(event, name, None) for name in (
            "execution_id", "toolkit_class", "tool_name", "duration_ms", "success", "error"
        )}
    toolkit = str(data.get("toolkit_class") or "")
    name = str(data.get("tool_name") or "")
    haystack = f"{toolkit}.{name}".lower()
    return {
        "run_id": _run_id(),
        "timestamp": _now(),
        "execution_id": data.get("execution_id"),
        "toolkit_class": toolkit,
        "tool_name": name,
        "duration_ms": data.get("duration_ms"),
        "success": bool(data.get("success", False)),
        "error": str(data.get("error"))[:500] if data.get("error") else None,
        "is_search": any(token in haystack for token in ("search", "web_search", "zhipu")),
    }


class AgentOpsROMASpanManager:
    """Delegate official spans while adding AgentOps and local tree events."""

    def __init__(self, delegate: Any):
        self.delegate = delegate
        self._installed = True

    @contextmanager
    def create_span(
        self, agent_type: Any, task: Any, module_name: str | None = None
    ) -> Iterator[Any]:
        started = time.perf_counter()
        execution_id = getattr(task, "execution_id", None)
        task_id = getattr(task, "task_id", None)
        parent_id = getattr(task, "parent_id", None)
        depth = int(getattr(task, "depth", 0) or 0)
        agent_name = str(_value(agent_type))
        current_node = {
            "execution_id": execution_id,
            "task_id": task_id,
            "parent_id": parent_id,
            "depth": depth,
            "agent_type": agent_name,
            "module_name": module_name or agent_name,
        }
        ctx = None
        initial_tool_count = 0
        try:
            from roma_dspy.core.context import ExecutionContext

            ctx = ExecutionContext.get()
            initial_tool_count = len(getattr(ctx, "tool_invocations", []) or []) if ctx else 0
        except Exception:
            pass

        span = None
        token = None
        try:
            from agentops import init
            from agentops.sdk.core import SpanKind, tracer

            if not tracer.initialized:
                init(
                    auto_start_session=False,
                    auto_init=False,
                    instrument_llm_calls=False,
                    env_data_opt_out=True,
                    fail_safe=True,
                    log_level="CRITICAL",
                )
            if tracer.initialized:
                span, _, token = tracer.make_span(
                    agent_name,
                    SpanKind.TASK,
                    attributes={
                        "roma.execution_id": execution_id or "unknown",
                        "roma.task_id": task_id or "unknown",
                        "roma.parent_task_id": parent_id or "root",
                        "roma.depth": depth,
                        "roma.agent_type": agent_name,
                        "roma.goal_sha256": _goal_hash(getattr(task, "goal", "")),
                    },
                )
        except Exception as exc:
            _write("observer_events.jsonl", {
                "run_id": _run_id(), "timestamp": _now(), "event": "agentops_init_error",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })

        _write("tree_events.jsonl", {
            "run_id": _run_id(), "timestamp": _now(), "event": "node_start",
            "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
            "depth": depth, "agent_type": agent_name, "module_name": module_name,
            "goal_sha256": _goal_hash(getattr(task, "goal", "")),
        })
        _write_paper_raw("raw_tree_events.jsonl", {
            "run_id": _run_id(), "timestamp": _now(), "event": "node_start",
            "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
            "depth": depth, "agent_type": agent_name, "module_name": module_name,
            "goal": getattr(task, "goal", None),
            "goal_sha256": _goal_hash(getattr(task, "goal", "")),
        })
        active_nodes = _active_node_snapshot()
        active_nodes.append({
            "execution_id": execution_id,
            "task_id": task_id,
            "parent_id": parent_id,
            "depth": depth,
            "agent_type": agent_name,
            "module_name": module_name,
            "goal_sha256": _goal_hash(getattr(task, "goal", "")),
        })
        _update_run_state(active_nodes=active_nodes)

        try:
            with bind_current_node(current_node):
                with self.delegate.create_span(agent_type, task, module_name):
                    yield span
        except Exception as exc:
            if span is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)[:500]))
                except Exception:
                    pass
            _write("tree_events.jsonl", {
                "run_id": _run_id(), "timestamp": _now(), "event": "node_end",
                "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
                "depth": depth, "agent_type": agent_name, "status": "failed",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })
            _write_paper_raw("raw_tree_events.jsonl", {
                "run_id": _run_id(), "timestamp": _now(), "event": "node_end",
                "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
                "depth": depth, "agent_type": agent_name, "status": "failed",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": f"{type(exc).__name__}: {exc}",
                "goal": getattr(task, "goal", None),
            })
            raise
        else:
            _write("tree_events.jsonl", {
                "run_id": _run_id(), "timestamp": _now(), "event": "node_end",
                "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
                "depth": depth, "agent_type": agent_name, "status": "success",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            })
            _write_paper_raw("raw_tree_events.jsonl", {
                "run_id": _run_id(), "timestamp": _now(), "event": "node_end",
                "execution_id": execution_id, "task_id": task_id, "parent_id": parent_id,
                "depth": depth, "agent_type": agent_name, "status": "success",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "goal": getattr(task, "goal", None),
            })
        finally:
            active_nodes = [
                node for node in _active_node_snapshot()
                if node.get("task_id") != task_id
            ]
            _update_run_state(active_nodes=active_nodes)
            current_tools = []
            try:
                current_tools = list(getattr(ctx, "tool_invocations", []) or []) if ctx else []
            except Exception:
                pass
            for event in current_tools[initial_tool_count:]:
                tool = _tool_data(event)
                tool["task_id"] = task_id
                tool["parent_id"] = parent_id
                _write("tool_events.jsonl", tool)
                _write_paper_raw("raw_tool_events.jsonl", {
                    "run_id": _run_id(),
                    "timestamp": _now(),
                    "execution_id": execution_id,
                    "task_id": task_id,
                    "parent_id": parent_id,
                    "tool": tool,
                    "event": event,
                })
                if span is not None:
                    try:
                        from agentops.sdk.core import SpanKind, tracer
                        tool_span, _, tool_token = tracer.make_span(
                            tool["tool_name"] or "tool",
                            SpanKind.TOOL,
                            attributes={
                                "roma.execution_id": execution_id or "unknown",
                                "roma.task_id": task_id or "unknown",
                                "roma.toolkit": tool["toolkit_class"] or "unknown",
                                "roma.is_search": tool["is_search"],
                            },
                        )
                        if not tool["success"]:
                            from opentelemetry.trace import Status, StatusCode
                            tool_span.set_status(Status(StatusCode.ERROR, tool["error"] or "tool failed"))
                        tracer.finalize_span(tool_span, tool_token)
                    except Exception:
                        pass
            if span is not None:
                try:
                    from agentops.sdk.core import tracer
                    tracer.finalize_span(span, token)
                except Exception:
                    pass


class ObserverRun:
    def __init__(self, run_id: str, trace_context: Any):
        self.run_id = run_id
        self.trace_context = trace_context

    def finish(self, status: str = "completed") -> None:
        try:
            if self.trace_context is not None:
                import agentops
                agentops.end_trace(
                    self.trace_context,
                    end_state="Error" if status == "failed" else "Success",
                )
        finally:
            _update_recording_manifest(
                recorder_status="complete" if status == "completed" else "failed",
                recorder_finished_at=_now(),
            )
            _write("run_events.jsonl", {
                "run_id": self.run_id, "timestamp": _now(), "event": "run_end", "status": status,
            })


def install_observer() -> ObserverRun:
    """Install the external observer and start one AgentOps root trace."""
    run_id = os.environ.get("ROMA_RUN_ID") or f"roma-{uuid4()}"
    os.environ["ROMA_RUN_ID"] = run_id
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    # Install the external request bridge before any ROMA node can issue an LM call.
    install_lm_current_node_bridge()
    (TRACE_DIR / "run_state.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "started_at": _now(),
                "runner_pid": os.getpid(),
                "active_nodes": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _update_recording_manifest(
        run_id=run_id,
        recorder_status="started",
        recorder_started_at=_now(),
        recorder_pid=os.getpid(),
    )
    try:
        import agentops
        from agentops.sdk.core import tracer

        if not tracer.initialized:
            agentops.init(
                auto_start_session=False,
                auto_init=False,
                instrument_llm_calls=False,
                env_data_opt_out=True,
                fail_safe=True,
                log_level="CRITICAL",
            )
        trace_context = agentops.start_trace(
            trace_name="roma-v1-benchmark",
            tags={"roma.run_id": run_id, "benchmark": "seal0"},
        ) if tracer.initialized else None
    except Exception as exc:
        trace_context = None
        _write("observer_events.jsonl", {
            "run_id": run_id, "timestamp": _now(), "event": "agentops_trace_error",
            "error": f"{type(exc).__name__}: {exc}"[:500],
        })

    from roma_dspy.core.observability import get_span_manager, set_span_manager

    # ROMA creates a fresh official span manager for each solver. Wrap that
    # construction point externally, otherwise the solver would replace this
    # observer before the first TaskNode executes.
    from roma_dspy.core.observability.execution_manager import ObservabilityManager

    if not getattr(ObservabilityManager, "_roma_agentops_observer_installed", False):
        original_init = ObservabilityManager.__init__

        def observed_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            current = get_span_manager()
            if not isinstance(current, AgentOpsROMASpanManager):
                set_span_manager(AgentOpsROMASpanManager(current))

        ObservabilityManager.__init__ = observed_init
        ObservabilityManager._roma_agentops_observer_installed = True

    delegate = get_span_manager()
    if not isinstance(delegate, AgentOpsROMASpanManager):
        set_span_manager(AgentOpsROMASpanManager(delegate))
    _write("run_events.jsonl", {
        "run_id": run_id, "timestamp": _now(), "event": "run_start", "status": "running",
    })
    return ObserverRun(run_id, trace_context)
