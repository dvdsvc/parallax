"""Aggregate ROMA result, LiteLLM, and AgentOps observer ledgers."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path, run_id: str | None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and (run_id is None or row.get("run_id") == run_id):
            rows.append(row)
    return rows


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _accuracy(result_path: Path) -> tuple[float | None, int | None, int, str]:
    if not result_path.exists():
        return None, None, 0, "missing_result"
    with result_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    comparable = [
        row for row in rows
        if row.get("predicted_answer") is not None and row.get("ground_truth") is not None
    ]
    # Do not invent grader logic. The official ROMA dataset evaluator writes
    # prediction/reference fields but does not declare correctness; an exact
    # string comparison would turn valid explanatory answers into false zeros.
    if comparable and any("is_correct" in row for row in comparable):
        flags = [str(row.get("is_correct", "")).strip().lower() in {"1", "true", "yes"} for row in comparable]
        correct = sum(flags)
        return correct / len(flags), correct, len(flags), "explicit_is_correct"
    return None, None, len(comparable), "no_official_grader_field"


def summarize(trace_dir: Path, result_path: Path, run_id: str | None = None) -> dict[str, Any]:
    if run_id is None:
        state_path = trace_dir / "run_state.json"
        if state_path.exists():
            try:
                run_id = json.loads(state_path.read_text(encoding="utf-8")).get("run_id")
            except (OSError, json.JSONDecodeError):
                pass

    llm = _read_jsonl(trace_dir / "llm_events.jsonl", run_id)
    tools = _read_jsonl(trace_dir / "tool_events.jsonl", run_id)
    starts = _read_jsonl(trace_dir / "tree_events.jsonl", run_id)
    starts = [row for row in starts if row.get("event") == "node_start"]
    runs = _read_jsonl(trace_dir / "run_events.jsonl", run_id)

    # A task can theoretically be retried. Count the logical task identity once
    # for tree metrics, while preserving every LiteLLM attempt for call metrics.
    nodes: dict[str, dict[str, Any]] = {}
    for row in starts:
        task_id = row.get("task_id")
        if task_id and task_id not in nodes:
            nodes[str(task_id)] = row
    child_counts = {task_id: 0 for task_id in nodes}
    for row in nodes.values():
        parent_id = row.get("parent_id")
        if parent_id in child_counts:
            child_counts[parent_id] += 1
    non_leaf = [count for count in child_counts.values() if count > 0]
    nodes_by_depth = Counter(int(row.get("depth") or 0) for row in nodes.values())
    max_tree_width = max(nodes_by_depth.values(), default=0)
    max_branching_factor = max(child_counts.values(), default=0)

    accuracy, correct, examples, accuracy_source = _accuracy(result_path)
    run_start = next((_timestamp(row.get("timestamp")) for row in runs if row.get("event") == "run_start"), None)
    run_end = next((_timestamp(row.get("timestamp")) for row in reversed(runs) if row.get("event") == "run_end"), None)
    wall_time = (run_end - run_start).total_seconds() if run_start and run_end else None

    failed_llm = sum(row.get("status") == "failure" for row in llm)
    failed_tools = sum(not row.get("success", False) for row in tools)
    retries = sum(int(row.get("retry_count") or 0) for row in llm)
    input_tokens = sum(int(row.get("input_tokens") or 0) for row in llm)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in llm)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in llm)
    metrics: dict[str, Any] = {
        "run_id": run_id,
        "accuracy": accuracy,
        "correct": correct,
        "examples": examples,
        "accuracy_source": accuracy_source,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
        # One entry is one upstream LiteLLM attempt, including failed attempts.
        "llm_calls": len(llm),
        "tool_calls": len(tools),
        # Search is a subtype of tool, not a second LLM call.
        "search_calls": sum(bool(row.get("is_search")) for row in tools),
        "agent_nodes": len(nodes),
        "leaf_nodes": sum(count == 0 for count in child_counts.values()),
        "actual_max_depth": max((int(row.get("depth") or 0) for row in nodes.values()), default=0),
        "avg_branching_factor": round(sum(non_leaf) / len(non_leaf), 6) if non_leaf else 0.0,
        "max_branching_factor": max_branching_factor,
        "max_tree_width": max_tree_width,
        "nodes_by_depth": {str(depth): count for depth, count in sorted(nodes_by_depth.items())},
        "wall_time": round(wall_time, 6) if wall_time is not None else None,
        "failed_calls": failed_llm + failed_tools,
        "retries": retries,
        "failed_llm_calls": failed_llm,
        "failed_tool_calls": failed_tools,
    }
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", type=Path, default=Path(__file__).resolve().parent / "traces")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = summarize(args.trace_dir, args.result, args.run_id)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
