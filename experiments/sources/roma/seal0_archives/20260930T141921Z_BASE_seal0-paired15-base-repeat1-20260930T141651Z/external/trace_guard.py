"""Fail-closed checks for the existing external ROMA LiteLLM hook traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    if path.exists():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{number}: {exc}") from exc
            if isinstance(item, dict):
                events.append(item)
    return events


def validate_trace(trace_dir: Path, expected_code: str, org_enabled: bool) -> dict[str, Any]:
    pre_calls = _jsonl(trace_dir / "pre_call.jsonl")
    guards = _jsonl(trace_dir / "condition_guard.jsonl")
    if not pre_calls:
        raise ValueError(f"No pre-call records found in {trace_dir}")

    mismatches = []
    seen_roles: set[str] = set()
    for ordinal, event in enumerate(pre_calls, 1):
        effective = event.get("effective_condition")
        requested = event.get("condition_requested")
        if effective != expected_code or requested != expected_code:
            mismatches.append({"event": ordinal, "requested": requested, "effective": effective})
        org = event.get("organization_awareness") or {}
        expected_status = "injected" if org_enabled else "disabled"
        if org.get("status") != expected_status or bool(org.get("injected")) != org_enabled:
            mismatches.append({
                "event": ordinal,
                "organization_awareness_status": org.get("status"),
                "organization_awareness_injected": org.get("injected"),
            })
        if org.get("role"):
            seen_roles.add(str(org["role"]))
        second_order = event.get("second_order") or {}
        if second_order.get("master_enabled") or second_order.get("injected"):
            mismatches.append({"event": ordinal, "second_order": second_order})
    mismatch_guards = [g for g in guards if g.get("event") == "condition_mismatch"]
    if mismatch_guards:
        mismatches.append({"condition_guard_mismatch_count": len(mismatch_guards)})
    if mismatches:
        raise ValueError(json.dumps({"trace_dir": str(trace_dir), "mismatches": mismatches[:20]}, indent=2))
    return {
        "trace_dir": str(trace_dir),
        "pre_call_count": len(pre_calls),
        "condition": expected_code,
        "organization_awareness": "injected" if org_enabled else "disabled",
        "roles_seen": sorted(seen_roles),
        "condition_guard_mismatch_count": 0,
        "status": "validated",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("--expected-code", required=True, choices=["00", "01", "10", "11", "BASE"])
    parser.add_argument("--org-enabled", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate_trace(args.trace_dir, args.expected_code, args.org_enabled), indent=2))


if __name__ == "__main__":
    main()
