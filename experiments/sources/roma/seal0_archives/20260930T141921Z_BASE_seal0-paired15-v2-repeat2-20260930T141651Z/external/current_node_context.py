"""External-only current ROMA node context bridge.

The observer binds the official TaskNode facts at the node execution boundary.
The LiteLLM-facing patch copies that already-determined snapshot into request
metadata. This keeps the bridge outside the ROMA source while making the
current node explicit instead of reconstructing it from a task-id lookup.
"""

from __future__ import annotations

import os
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator


_CURRENT_NODE: ContextVar[dict[str, Any] | None] = ContextVar(
    "roma_current_node", default=None
)
_INSTALLED = False
_V2_CONTEXT_PATH = (
    Path(__file__).resolve().parents[1]
    / "forammas_study"
    / "prompts"
    / "global_organizational_architecture_v2.txt"
)
_V2_MARKER = "[ROMA GLOBAL ORGANIZATIONAL ARCHITECTURE]"


def _enabled() -> bool:
    """Enable request-local node metadata for any external layer routing.

    Organization-awareness injection and layer-scoped visibility overrides are
    independent controls.  A run may deliberately keep organization text off
    while still needing the real TaskNode role to route an intent override.
    """
    try:
        overrides = json.loads(os.environ.get("ROMA_PROXY_LAYER_OVERRIDES", "{}"))
    except json.JSONDecodeError:
        overrides = {}
    if isinstance(overrides, dict) and any(
        isinstance(values, dict) and bool(values)
        for values in overrides.values()
    ):
        return True
    if os.environ.get("ROMA_PROXY_SECOND_ORDER", "0").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        return False
    try:
        second_order = json.loads(
            os.environ.get("ROMA_PROXY_SECOND_ORDER_LAYERS", "{}")
        )
    except json.JSONDecodeError:
        return False
    return isinstance(second_order, dict) and any(
        isinstance(values, dict) and bool(values)
        for values in second_order.values()
    )


def _snapshot(node: dict[str, Any]) -> dict[str, Any]:
    """Keep only current-node facts; never include children or future-tree data."""
    return {
        "execution_id": node.get("execution_id"),
        "task_id": node.get("task_id"),
        "parent_id": node.get("parent_id"),
        "depth": node.get("depth"),
        "agent_type": node.get("agent_type"),
        "module_name": node.get("module_name"),
    }


@contextmanager
def bind_current_node(node: dict[str, Any]) -> Iterator[None]:
    """Bind one node to the current execution context until its span exits."""
    token = _CURRENT_NODE.set(_snapshot(node))
    try:
        yield
    finally:
        _CURRENT_NODE.reset(token)


def current_node() -> dict[str, Any] | None:
    """Return a copy of the node currently executing in this context."""
    node = _CURRENT_NODE.get()
    return dict(node) if node is not None else None


def _with_current_node(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Add the explicit node snapshot to a DSPy LM request when enabled."""
    node = current_node()
    if not _enabled() or node is None:
        return kwargs
    rewritten = dict(kwargs)
    # LiteLLM treats top-level ``metadata`` as an internal client argument and
    # does not serialize it through the OpenAI-compatible HTTP body. Put the
    # field in ``extra_body`` so the independent Proxy receives it as a real
    # request-local JSON field.
    extra_body = rewritten.get("extra_body")
    extra_body = dict(extra_body) if isinstance(extra_body, dict) else {}
    metadata = extra_body.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["roma_current_node"] = node
    # External role routing only: this is the same request-local TaskNode
    # snapshot, not a new agent input or a task-id lookup.
    if node.get("module_name"):
        metadata.setdefault("roma_layer", node.get("module_name"))
    elif node.get("agent_type"):
        metadata.setdefault("roma_layer", node.get("agent_type"))
    extra_body["metadata"] = metadata
    rewritten["extra_body"] = extra_body
    return rewritten


def _org_awareness_v2_enabled() -> bool:
    return os.environ.get("ROMA_ORG_AWARENESS_V2", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _inject_org_awareness_v2(prompt: Any, messages: Any) -> tuple[Any, Any]:
    """Prepend the fixed V2 system context before LiteLLM, independent of role."""
    if not _org_awareness_v2_enabled():
        return prompt, messages
    try:
        context = _V2_CONTEXT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"ROMA organization-awareness V2 prompt is unavailable: {_V2_CONTEXT_PATH}"
        ) from exc
    if not context.strip() or not context.startswith(_V2_MARKER):
        raise RuntimeError("ROMA organization-awareness V2 prompt is empty or has an unexpected header")

    if messages is None:
        message_list = [] if prompt is None else [{"role": "user", "content": prompt}]
        prompt = None
    elif isinstance(messages, list):
        message_list = list(messages)
    elif isinstance(messages, tuple):
        message_list = list(messages)
    else:
        raise TypeError("ROMA organization-awareness V2 expects chat messages")

    marker_messages = [
        message for message in message_list
        if isinstance(message, dict)
        and message.get("role") == "system"
        and str(message.get("content") or "").startswith(_V2_MARKER)
    ]
    if marker_messages:
        if len(marker_messages) != 1 or marker_messages[0].get("content") != context:
            raise ValueError("Request already contains a different ROMA architecture system context")
        return prompt, message_list
    return prompt, [{"role": "system", "content": context}, *message_list]


def install_lm_current_node_bridge() -> None:
    """Patch DSPy LM calls in-memory, without changing the ROMA checkout."""
    global _INSTALLED
    if _INSTALLED:
        return

    import dspy

    original_forward = dspy.LM.forward
    original_aforward = dspy.LM.aforward

    def bridged_forward(self: Any, prompt: Any = None, messages: Any = None, **kwargs: Any):
        prompt, messages = _inject_org_awareness_v2(prompt, messages)
        return original_forward(
            self,
            prompt=prompt,
            messages=messages,
            **_with_current_node(kwargs),
        )

    async def bridged_aforward(
        self: Any, prompt: Any = None, messages: Any = None, **kwargs: Any
    ):
        prompt, messages = _inject_org_awareness_v2(prompt, messages)
        return await original_aforward(
            self,
            prompt=prompt,
            messages=messages,
            **_with_current_node(kwargs),
        )

    dspy.LM.forward = bridged_forward
    dspy.LM.aforward = bridged_aforward
    _INSTALLED = True
