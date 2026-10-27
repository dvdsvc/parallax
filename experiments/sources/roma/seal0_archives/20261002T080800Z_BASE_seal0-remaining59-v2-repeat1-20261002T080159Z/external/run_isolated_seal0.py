"""Run official ROMA/SEAL-0 one-question workers with external isolation.

This controller deliberately keeps the official evaluator and RecursiveSolver
inside each worker.  Isolation is provided by the process boundary: the
ROMA-global module circuit breakers, local LiteLLM cache, DSPy cache, storage,
and trace ledger belong to one question only.  A provider safety rejection is
handled by the external LiteLLM hook, which terminates only that worker.  The
controller then records the question as SKIPPED_PROVIDER_BLOCKED and schedules
the next question.

ROMA source and the official benchmark evaluator are not modified here.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from paper_run_archive import PaperRunArchive, sha256_file


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = WORKSPACE_ROOT / "work"
DEFAULT_PROJECT_ROOT = WORKSPACE_ROOT / "forammas"
DEFAULT_PYTHON = DEFAULT_PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_BENCHMARK_DATA = WORKSPACE_ROOT / "official-roma_modified_20260914" / "data" / "sealqa" / "seal-0.parquet"
RUNNER = WORK_ROOT / "roma_v1_adapters" / "run_official_seal0.py"
PROXY_SCRIPT = WORK_ROOT / "roma_litellm_proxy" / "start_proxy.sh"
ENV_FILE = WORK_ROOT / "roma_v1_qwen_litellm.env"
CREDENTIAL_FILE = Path(
    os.environ.get("ROMA_CREDENTIAL_FILE", "external_archive/env/glm_api.env")
)
E2B_CREDENTIAL_FILE = Path(
    os.environ.get(
        "ROMA_E2B_CREDENTIAL_FILE",
        "external_archive/env/e2b_api.env",
    )
)
DEFAULT_OUTPUT_ROOT = WORK_ROOT / "isolated_seal0_runs"
MODEL_VISIBLE_PATH_POLICY = "opaque_run_id_v1"
WORKER_PYTHONHASHSEED = "0"
TOOL_ORDER_POLICY = "fixed_python_hash_seed_v1"
STUDY_ROOT = WORK_ROOT / "forammas_study"
DEFAULT_MLFLOW_PYTHON = STUDY_ROOT / ".venv" / "bin" / "python"
DEFAULT_MLFLOW_DB = STUDY_ROOT / "mlflow.db"
MLFLOW_INDEXER = STUDY_ROOT / "mlflow_archive.py"

CSV_FIELDS = [
    "index",
    "execution_id",
    "goal",
    "predicted_answer",
    "ground_truth",
    "status",
    "depth_reached",
    "duration_seconds",
    "error",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "mlflow_run_id",
    "mlflow_url",
    "provider_blocked_reason",
    "worker_exit_code",
    "worker_trace_dir",
    "condition_requested",
    "condition_observed",
    "condition_validation",
    "organization_awareness_v2_validation",
    "organization_awareness_v2_observed",
    "experiment_validation",
    "recorder_status",
    "metrics_path",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def new_worker_root() -> Path:
    """Keep experiment labels out of model-visible storage/artifact paths.

    Human-readable labels remain in the paper archive and its manifest. The
    independent worker directory uses an opaque identifier for both arms.
    """
    return DEFAULT_OUTPUT_ROOT / f"run-{uuid4().hex}.workers"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_examples(project_root: Path, benchmark_data: Path) -> list[Any]:
    """Load SEAL-0 through the official loader with its official seed."""
    sys.path.insert(0, str(project_root))
    from prompt_optimization.dataset_loaders import load_seal0_dataset

    if not benchmark_data.is_file():
        raise SystemExit(f"SEAL-0 benchmark snapshot not found: {benchmark_data}")
    return list(load_seal0_dataset(
        seed=0, no_split=True, parquet_path=str(benchmark_data.resolve())
    ))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def condition_audit(
    trace_dir: Path,
    expected: str,
    expected_organization_awareness_v2: bool = False,
) -> dict[str, Any]:
    """Audit condition and role-independent V2 context at the LiteLLM boundary."""
    rows = read_jsonl(trace_dir / "pre_call.jsonl")
    # A layer-scoped run may intentionally have different effective condition
    # codes per role. Validate the requested run condition when present, and
    # retain effective per-layer codes separately in the raw pre-call ledger.
    observed = sorted(
        {
            str(row.get("condition_requested") or row.get("condition"))
            for row in rows
            if row.get("condition_requested") or row.get("condition")
        }
    )
    guard_errors = read_jsonl(trace_dir / "condition_guard.jsonl")
    organization_rows = [
        row.get("organization_awareness_v2", {}).get("status")
        for row in rows
        if isinstance(row.get("organization_awareness_v2"), dict)
    ]
    organization_observed = sorted(
        {str(status) for status in organization_rows if status}
    )
    expected_org_status = (
        "present_pre_litellm" if expected_organization_awareness_v2 else "absent"
    )
    if not organization_rows:
        organization_validation = "not_observed"
    elif all(status == expected_org_status for status in organization_rows):
        organization_validation = "validated"
    else:
        organization_validation = "mismatch"
    if not observed and guard_errors:
        observed = sorted(
            {
                str(row.get("observed"))
                for row in guard_errors
                if row.get("observed")
            }
        )
    if guard_errors:
        validation = "mismatch"
    elif not observed:
        validation = "not_observed"
    elif observed == [expected]:
        validation = "validated"
    else:
        validation = "mismatch"
    return {
        "condition_requested": expected,
        "condition_observed": observed,
        "condition_validation": validation,
        "pre_call_count": len(rows),
        "condition_guard_error_count": len(guard_errors),
        "organization_awareness_v2_requested": expected_organization_awareness_v2,
        "organization_awareness_v2_observed": organization_observed,
        "organization_awareness_v2_validation": organization_validation,
        "organization_awareness_v2_request_count": len(organization_rows),
    }


def persist_worker_metrics(
    *,
    index: int,
    condition: str,
    run_id: str,
    worker_dir: Path,
    trace_dir: Path,
    result_path: Path,
    expected_organization_awareness_v2: bool = False,
) -> dict[str, Any]:
    """Always persist a metric artifact, including partial/error workers."""
    metrics_path = worker_dir / "result.metrics.json"
    audit = condition_audit(
        trace_dir, condition, expected_organization_awareness_v2
    )
    experiment_validation = (
        "validated"
        if audit["condition_validation"] == "validated"
        and audit["organization_awareness_v2_validation"] == "validated"
        else "mismatch"
        if "mismatch" in {
            audit["condition_validation"],
            audit["organization_awareness_v2_validation"],
        }
        else "not_observed"
    )
    try:
        if str(WORK_ROOT) not in sys.path:
            sys.path.insert(0, str(WORK_ROOT))
        from roma_litellm_proxy.summarize_metrics import summarize

        metrics = summarize(trace_dir, result_path, run_id)
        summary_error = None
    except Exception as exc:
        metrics = {
            "run_id": run_id,
            "accuracy": None,
            "correct": None,
            "examples": 0,
            "accuracy_source": "summary_error",
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "search_calls": 0,
            "agent_nodes": 0,
            "leaf_nodes": 0,
            "actual_max_depth": 0,
            "avg_branching_factor": 0.0,
            "max_branching_factor": 0,
            "max_tree_width": 0,
            "nodes_by_depth": {},
            "wall_time": None,
            "failed_calls": 0,
            "retries": 0,
            "failed_llm_calls": 0,
            "failed_tool_calls": 0,
        }
        summary_error = f"{type(exc).__name__}: {exc}"

    run_events = read_jsonl(trace_dir / "run_events.jsonl")
    recorder_started = any(
        row.get("run_id") == run_id and row.get("event") == "run_start"
        for row in run_events
    )
    recorder_finished = any(
        row.get("run_id") == run_id and row.get("event") == "run_end"
        for row in run_events
    )
    recorder_status = (
        "summary_error" if summary_error else
        "complete" if recorder_started and recorder_finished else
        "partial" if recorder_started else
        "not_started"
    )
    metrics.update(
        {
            "schema_version": 2,
            "question_index": index,
            "expected_condition": condition,
            "observed_conditions": audit["condition_observed"],
            "condition_validation": audit["condition_validation"],
            "condition_guard_error_count": audit["condition_guard_error_count"],
            "organization_awareness_v2_requested": audit["organization_awareness_v2_requested"],
            "organization_awareness_v2_observed": audit["organization_awareness_v2_observed"],
            "organization_awareness_v2_validation": audit["organization_awareness_v2_validation"],
            "organization_awareness_v2_request_count": audit["organization_awareness_v2_request_count"],
            "experiment_validation": experiment_validation,
            "recorder_status": recorder_status,
            "recorder_started": recorder_started,
            "recorder_finished": recorder_finished,
            "metrics_source": "controller_finalized",
            "metrics_path": str(metrics_path),
        }
    )
    if summary_error:
        metrics["summary_error"] = summary_error
    write_json_atomic(metrics_path, metrics)
    write_json_atomic(
        worker_dir / "recording_manifest.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "question_index": index,
            "expected_condition": condition,
            "observed_conditions": audit["condition_observed"],
            "condition_validation": audit["condition_validation"],
            "recorder_status": recorder_status,
            "trace_dir": str(trace_dir),
            "metrics_path": str(metrics_path),
            "required_ledgers": [
                "pre_call.jsonl",
                "llm_events.jsonl",
                "tree_events.jsonl",
                "tool_events.jsonl",
                "run_events.jsonl",
                "run_state.json",
                "condition_guard.jsonl",
            ],
            "pre_call_count": audit["pre_call_count"],
            "condition_guard_error_count": audit["condition_guard_error_count"],
            "organization_awareness_v2_validation": audit["organization_awareness_v2_validation"],
            "organization_awareness_v2_requested": audit["organization_awareness_v2_requested"],
            "organization_awareness_v2_observed": audit["organization_awareness_v2_observed"],
            "experiment_validation": experiment_validation,
            "updated_at": now(),
        },
    )
    return {
        "condition_requested": audit["condition_requested"],
        "condition_observed": ",".join(audit["condition_observed"]),
        "condition_validation": audit["condition_validation"],
        "organization_awareness_v2_validation": audit["organization_awareness_v2_validation"],
        "organization_awareness_v2_observed": ",".join(audit["organization_awareness_v2_observed"]),
        "experiment_validation": experiment_validation,
        "recorder_status": recorder_status,
        "metrics_path": str(metrics_path),
    }


def provider_block_events(trace_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(trace_dir / "provider_blocked.jsonl")


def first_worker_row(result_path: Path) -> dict[str, Any] | None:
    if not result_path.exists():
        return None
    try:
        with result_path.open(encoding="utf-8", newline="", errors="replace") as handle:
            for row in csv.DictReader(handle):
                if row.get("index") is not None:
                    return dict(row)
    except csv.Error:
        # A worker killed during an incremental write may leave a partial row.
        # The provider trace is authoritative for the blocked-row path.
        return None
    return None


def worker_shell(
    *,
    python: Path,
    project_root: Path,
    benchmark_data: Path,
    original_index: int,
    max_depth: int,
    condition: str,
    proxy_port: int,
    trace_dir: Path,
    result_path: Path,
    run_id: str,
) -> list[str]:
    """Build a shell command so the existing credential/env bootstrap is reused."""
    proxy_url = f"http://127.0.0.1:{proxy_port}/v1"
    statements = [
        "set -euo pipefail",
        f"export ROMA_PROXY_BASE_URL={quote(proxy_url)}",
        f"export ROMA_PROXY_CONDITION={quote(condition)}",
        # The proxy boot script already loads this file for Qwen.  The
        # official runner also needs the same process environment for the
        # provider-native Zhipu search toolkit (and optional E2B toolkit).
        f"if [[ -f {quote(CREDENTIAL_FILE)} ]]; then set -a; source {quote(CREDENTIAL_FILE)}; set +a; fi",
        f"set -a; source {quote(ENV_FILE)}; set +a",
        # Keep the E2B secret worker-only; the LiteLLM proxy is launched
        # separately and never sources this file. Load it after shared env
        # files so they cannot accidentally shadow the dedicated E2B key.
        f"if [[ -f {quote(E2B_CREDENTIAL_FILE)} ]]; then set -a; source {quote(E2B_CREDENTIAL_FILE)}; set +a; fi",
        # The one paper-run config is authoritative even when a shared env file
        # contains legacy defaults. Re-export every experiment control after it.
        "unset ROMA_PROXY_ORG_AWARENESS ROMA_PROXY_ORG_AWARENESS_CONTEXT",
        # Native toolkits register names by iterating sets. Fix the worker's
        # startup hash seed after shared env bootstrap, identically in both arms.
        f"export PYTHONHASHSEED={WORKER_PYTHONHASHSEED}",
        "export ROMA_PROXY_ORG_AWARENESS_V2=0",
        f"export ROMA_PROXY_CONDITION={quote(condition)}",
        f"export ROMA_PROXY_EXPECTED_CONDITION={quote(condition)}",
        f"export ROMA_ORG_AWARENESS_V2={quote(os.environ.get('ROMA_ORG_AWARENESS_V2', '0'))}",
        f"export ROMA_PROXY_SECOND_ORDER={quote(os.environ.get('ROMA_PROXY_SECOND_ORDER', '0'))}",
        f"export ROMA_PROXY_SECOND_ORDER_LAYERS={quote(os.environ.get('ROMA_PROXY_SECOND_ORDER_LAYERS', '{}'))}",
        *(f"export {name}={quote(os.environ[name])}" if name in os.environ else f"unset {name}"
          for name in ("ROMA_MODEL_OVERRIDE", "ROMA_TEMPERATURE_OVERRIDE")),
        f"export ROMA_PROJECT_ROOT={quote(project_root)}",
        f"export ROMA_SEAL0_PARQUET_PATH={quote(benchmark_data)}",
        f"export ROMA_PROXY_TRACE_DIR={quote(trace_dir)}",
        f"export ROMA_RUN_ID={quote(run_id)}",
        "export ROMA_PROVIDER_BLOCKED_ACTION=terminate_run",
        "export ROMA_PROVIDER_BLOCKED_TARGET_PATTERN=run_official_seal0.py",
        f"export STORAGE_BASE_PATH={quote(trace_dir / 'storage')}",
        f"export ROMA_CHECKPOINT_PATH={quote(trace_dir / 'checkpoints')}",
        f"export DSPY_CACHE_DIR={quote(trace_dir / 'dspy_cache')}",
        f"exec {quote(python)} {quote(RUNNER)}"
        f" --start {original_index} --size 1 --threads 1"
        f" --max-depth {max_depth} --output {quote(result_path)}",
    ]
    return ["/bin/zsh", "-lc", "\n".join(statements)]


def proxy_shell(*, port: int, condition: str, trace_dir: Path, run_id: str) -> list[str]:
    statements = [
        "set -euo pipefail",
        "unset ROMA_PROXY_ORG_AWARENESS ROMA_PROXY_ORG_AWARENESS_CONTEXT",
        "unset ROMA_ORG_AWARENESS_V2",
        f"export LITELLM_PROXY_PORT={port}",
        f"export ROMA_PROXY_CONDITION={quote(condition)}",
        f"export ROMA_PROXY_EXPECTED_CONDITION={quote(condition)}",
        "export ROMA_PROXY_ORG_AWARENESS_V2=0",
        f"export ROMA_PROXY_SECOND_ORDER={quote(os.environ.get('ROMA_PROXY_SECOND_ORDER', '0'))}",
        f"export ROMA_PROXY_SECOND_ORDER_LAYERS={quote(os.environ.get('ROMA_PROXY_SECOND_ORDER_LAYERS', '{}'))}",
        f"export ROMA_PROXY_TRACE_DIR={quote(trace_dir)}",
        f"export ROMA_RUN_ID={quote(run_id)}",
        "export ROMA_PROVIDER_BLOCKED_ACTION=terminate_run",
        "export ROMA_PROVIDER_BLOCKED_TARGET_PATTERN=run_official_seal0.py",
        f"exec {quote(PROXY_SCRIPT)}",
    ]
    return ["/bin/zsh", "-lc", "\n".join(statements)]


async def proxy_ready(proc: asyncio.subprocess.Process, port: int, timeout: float = 45.0) -> bool:
    """Wait for LiteLLM readiness without blocking the event loop."""
    import urllib.request

    deadline = time.monotonic() + timeout
    urls = (
        f"http://127.0.0.1:{port}/health/readiness",
        f"http://127.0.0.1:{port}/health/liveliness",
        f"http://127.0.0.1:{port}/health",
    )
    while time.monotonic() < deadline:
        if proc.returncode is not None:
            return False
        for url in urls:
            try:
                await asyncio.to_thread(urllib.request.urlopen, url, timeout=1.5)
                return True
            except Exception:
                pass
        await asyncio.sleep(0.25)
    return False


async def terminate(proc: asyncio.subprocess.Process | None, timeout: float = 5.0) -> None:
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            return
        await proc.wait()


@dataclass
class WorkerOutcome:
    index: int
    row: dict[str, Any]
    trace_dir: Path
    worker_exit_code: int | None


class IsolatedController:
    def __init__(
        self,
        args: argparse.Namespace,
        examples: list[Any],
        worker_root: Path | None = None,
    ):
        self.args = args
        self.examples = examples
        if worker_root is None:
            self.root = new_worker_root().resolve()
        else:
            self.root = worker_root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=False)
        self.active: set[tuple[asyncio.subprocess.Process, asyncio.subprocess.Process]] = set()
        self.state_path = self.root / "controller_state.json"
        self.state: dict[str, Any] = {
            "condition": args.condition,
            "max_depth": args.max_depth,
            "workers": args.workers,
            "started_at": now(),
            "total": 0,
            "completed": 0,
            "skipped_provider_blocked": 0,
            "errors": 0,
            "active_indices": [],
        }

    def save_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)

    def row_for_blocked(self, index: int, example: Any, trace_dir: Path, exit_code: int | None) -> dict[str, Any]:
        events = provider_block_events(trace_dir)
        event = events[0] if events else {}
        reason = str(event.get("provider_error_type") or "provider_blocked")
        error = str(event.get("error") or reason)
        active = event.get("active_nodes") or []
        depths = [int(node.get("depth", 0)) for node in active if isinstance(node, dict)]
        return {
            "index": index,
            "execution_id": None,
            "goal": str(getattr(example, "goal", "")),
            "predicted_answer": None,
            "ground_truth": getattr(example, "answer", None),
            "status": "SKIPPED_PROVIDER_BLOCKED",
            "depth_reached": max(depths, default=0),
            "duration_seconds": 0.0,
            "error": f"provider_blocked: {reason}: {error}",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "mlflow_run_id": "N/A",
            "mlflow_url": "N/A",
            "provider_blocked_reason": reason,
            "worker_exit_code": exit_code,
            "worker_trace_dir": str(trace_dir),
        }

    def row_for_error(self, index: int, example: Any, trace_dir: Path, exit_code: int | None, detail: str) -> dict[str, Any]:
        return {
            "index": index,
            "execution_id": None,
            "goal": str(getattr(example, "goal", "")),
            "predicted_answer": None,
            "ground_truth": getattr(example, "answer", None),
            "status": "ERROR",
            "depth_reached": 0,
            "duration_seconds": 0.0,
            "error": detail,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "mlflow_run_id": "N/A",
            "mlflow_url": "N/A",
            "provider_blocked_reason": None,
            "worker_exit_code": exit_code,
            "worker_trace_dir": str(trace_dir),
        }

    async def run_one(self, index: int) -> WorkerOutcome:
        example = self.examples[index]
        worker_dir = self.root / f"q-{index:04d}"
        worker_dir.mkdir(parents=True, exist_ok=True)
        trace_dir = worker_dir / "trace"
        result_path = worker_dir / "result.csv"
        run_id = f"roma-isolated-{self.args.condition}-{index:04d}-{int(time.time())}"
        port = free_port()

        write_json_atomic(
            worker_dir / "recording_manifest.json",
            {
                "schema_version": 1,
                "run_id": run_id,
                "question_index": index,
                "expected_condition": self.args.condition,
                "organization_awareness_v2_requested": (
                    os.environ.get("ROMA_ORG_AWARENESS_V2", "0").strip().lower()
                    in {"1", "true", "yes", "on"}
                ),
                "recorder_status": "planned",
                "trace_dir": str(trace_dir),
                "metrics_path": str(worker_dir / "result.metrics.json"),
                "required_ledgers": [
                    "pre_call.jsonl",
                    "llm_events.jsonl",
                    "tree_events.jsonl",
                    "tool_events.jsonl",
                    "run_events.jsonl",
                    "run_state.json",
                    "condition_guard.jsonl",
                ],
                "created_at": now(),
            },
        )

        proxy_log_path = worker_dir / "proxy.log"
        runner_log_path = worker_dir / "runner.log"
        proxy_proc: asyncio.subprocess.Process | None = None
        runner_proc: asyncio.subprocess.Process | None = None
        row: dict[str, Any] | None = None
        try:
            with proxy_log_path.open("w", encoding="utf-8") as proxy_log, runner_log_path.open("w", encoding="utf-8") as runner_log:
                proxy_proc = await asyncio.create_subprocess_exec(
                    *proxy_shell(
                        port=port,
                        condition=self.args.condition,
                        trace_dir=trace_dir,
                        run_id=run_id,
                    ),
                    stdout=proxy_log,
                    stderr=asyncio.subprocess.STDOUT,
                )
                if not await proxy_ready(proxy_proc, port):
                    await terminate(proxy_proc)
                    row = self.row_for_error(index, example, trace_dir, proxy_proc.returncode, "isolated proxy failed readiness")
                else:
                    runner_proc = await asyncio.create_subprocess_exec(
                        *worker_shell(
                            python=Path(self.args.python),
                            project_root=Path(self.args.project_root),
                            benchmark_data=Path(self.args.benchmark_data),
                            original_index=index,
                            max_depth=self.args.max_depth,
                            condition=self.args.condition,
                            proxy_port=port,
                            trace_dir=trace_dir,
                            result_path=result_path,
                            run_id=run_id,
                        ),
                        stdout=runner_log,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    self.active.add((runner_proc, proxy_proc))
                    self.state["active_indices"] = sorted({item[0].pid for item in self.active if item[0].pid})
                    self.save_state()
                    try:
                        await runner_proc.wait()
                    finally:
                        self.active.discard((runner_proc, proxy_proc))
                        await terminate(proxy_proc)
        except Exception as exc:
            await terminate(runner_proc)
            await terminate(proxy_proc)
            row = self.row_for_error(
                index,
                example,
                trace_dir,
                runner_proc.returncode if runner_proc else None,
                f"isolated controller error: {type(exc).__name__}: {exc}",
            )

        recording = persist_worker_metrics(
            index=index,
            condition=self.args.condition,
            run_id=run_id,
            worker_dir=worker_dir,
            trace_dir=trace_dir,
            result_path=result_path,
            expected_organization_awareness_v2=(
                os.environ.get("ROMA_ORG_AWARENESS_V2", "0").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )
        blocked = provider_block_events(trace_dir)
        parsed = first_worker_row(result_path)
        if row is not None:
            pass
        elif blocked:
            row = self.row_for_blocked(index, example, trace_dir, runner_proc.returncode if runner_proc else None)
        elif parsed is not None and (runner_proc is None or runner_proc.returncode == 0):
            row = {field: parsed.get(field) for field in CSV_FIELDS}
            row["worker_exit_code"] = runner_proc.returncode if runner_proc else None
            row["worker_trace_dir"] = str(trace_dir)
        else:
            detail = f"isolated worker exited with code {runner_proc.returncode if runner_proc else None}"
            row = self.row_for_error(index, example, trace_dir, runner_proc.returncode if runner_proc else None, detail)
        row.update(recording)
        return WorkerOutcome(index, row, trace_dir, runner_proc.returncode if runner_proc else None)

    async def run(self, indices: list[int]) -> list[dict[str, Any]]:
        self.state["total"] = len(indices)
        self.save_state()
        semaphore = asyncio.Semaphore(self.args.workers)
        rows: list[dict[str, Any]] = []

        async def limited(index: int) -> WorkerOutcome:
            async with semaphore:
                return await self.run_one(index)

        tasks = [asyncio.create_task(limited(index)) for index in indices]
        try:
            for task in asyncio.as_completed(tasks):
                outcome = await task
                rows.append(outcome.row)
                status = outcome.row.get("status")
                if status == "COMPLETED":
                    self.state["completed"] += 1
                elif status == "SKIPPED_PROVIDER_BLOCKED":
                    self.state["skipped_provider_blocked"] += 1
                else:
                    self.state["errors"] += 1
                self.state["active_indices"] = sorted({item[0].pid for item in self.active if item[0].pid})
                self.save_state()
                print(json.dumps({"index": outcome.index, "status": status, "completed": len(rows), "total": len(indices)}, ensure_ascii=False), flush=True)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for runner_proc, proxy_proc in list(self.active):
                await terminate(runner_proc)
                await terminate(proxy_proc)
            self.active.clear()
            self.state["active_indices"] = []
            self.state["finished_at"] = now()
            self.save_state()
        return sorted(rows, key=lambda row: int(row["index"]))


def write_results(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=0, help="First full-dataset index, inclusive")
    parser.add_argument("--end", type=int, default=None, help="Last full-dataset index, inclusive")
    parser.add_argument("--indices", help="Explicit comma-separated full-dataset indices; overrides start/end")
    parser.add_argument("--workers", type=int, default=5, help="Independent question workers")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--condition", default="BASE", help="BASE or a two-bit intent/plan condition such as 11")
    parser.add_argument(
        "--paper-run-config",
        help="JSON file containing the complete formal run configuration; implies --paper-run",
    )
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--benchmark-data", default=str(DEFAULT_BENCHMARK_DATA))
    parser.add_argument("--python", default=str(DEFAULT_PYTHON))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT / "seal0_isolated.csv"))
    parser.add_argument(
        "--paper-run",
        action="store_true",
        help="Create an immutable raw-trace archive and automatically index it in MLflow",
    )
    parser.add_argument(
        "--paper-runs-root",
        default=str(WORK_ROOT / "paper_runs"),
        help="Root directory for immutable paper-run archives",
    )
    parser.add_argument("--paper-run-id", default=None)
    parser.add_argument(
        "--mlflow-python",
        default=str(DEFAULT_MLFLOW_PYTHON),
        help="Isolated Python with MLflow installed (paper runs only)",
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        default=os.environ.get(
            "MLFLOW_TRACKING_URI",
            "sqlite:///" + str(DEFAULT_MLFLOW_DB.resolve()),
        ),
    )
    parser.add_argument(
        "--mlflow-experiment",
        default=os.environ.get("ROMA_MLFLOW_EXPERIMENT", "ROMA-Formal-Runs"),
    )
    args = parser.parse_args()
    # Archive metadata: this entrypoint always uses the native SEAL-0 loader.
    args.benchmark = "SEAL-0"
    if args.paper_run_config:
        config_path = Path(args.paper_run_config).resolve()
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read --paper-run-config: {exc}")
        if not isinstance(config, dict) or config.get("schema_version") != 1:
            parser.error("paper-run config must be a JSON object with schema_version=1")
        def contains_secret_key(value: Any) -> bool:
            if isinstance(value, dict):
                return any(
                    any(secret in str(key).lower() for secret in ("api_key", "secret", "password", "authorization"))
                    or contains_secret_key(child)
                    for key, child in value.items()
                )
            if isinstance(value, list):
                return any(contains_secret_key(child) for child in value)
            return False

        if contains_secret_key(config):
            parser.error("paper-run config must not contain credentials")
        try:
            args.condition = str(config["condition"])
            args.selected_indices = list(config["task_indices"])
            args.workers = int(config["workers"])
            args.max_depth = int(config["max_depth"])
            args.paper_run = True
            args.paper_run_config_path = config_path
            model = str(config["model"])
            temperature = float(config["temperature"])
            if not model.strip() or "\n" in model or "\r" in model:
                raise ValueError("model must be a non-empty single-line LiteLLM name")
            interventions = config.get("interventions", {})
            if not isinstance(interventions, dict):
                raise TypeError("interventions must be an object")
            os.environ["ROMA_MODEL_OVERRIDE"] = model
            os.environ["ROMA_TEMPERATURE_OVERRIDE"] = str(temperature)
            os.environ["ROMA_PROVIDER_LABEL"] = str(config.get("provider_label", "litellm-proxy"))
            os.environ["ROMA_ORG_AWARENESS_V2"] = "1" if interventions.get("organization_awareness_v2", False) else "0"
            # V2 is injected in the worker before LiteLLM. Keep the proxy-side
            # legacy injection switch hard-off to guarantee a single insertion.
            os.environ["ROMA_PROXY_ORG_AWARENESS_V2"] = "0"
            if "organization_awareness" in interventions:
                raise ValueError(
                    "the legacy organization-awareness switch was removed; use organization_awareness_v2 only"
                )
            second_order = interventions.get("second_order", {})
            if not isinstance(second_order, dict):
                raise TypeError("interventions.second_order must be an object")
            os.environ["ROMA_PROXY_SECOND_ORDER"] = "1" if second_order.get("enabled", False) else "0"
            layers = second_order.get("layers", {})
            if not isinstance(layers, dict):
                raise TypeError("interventions.second_order.layers must be an object")
            supported_layers = {"atomizer", "planner", "executor", "aggregator", "verifier"}
            unknown_layers = set(layers) - supported_layers
            if unknown_layers:
                raise ValueError(f"unknown second-order roles: {sorted(unknown_layers)}")
            os.environ["ROMA_PROXY_SECOND_ORDER_LAYERS"] = json.dumps(
                {str(role): int(bool(visible)) for role, visible in layers.items()},
                sort_keys=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            parser.error(f"invalid paper-run config: {exc}")
    elif args.paper_run:
        parser.error("formal --paper-run requires --paper-run-config to avoid omitted controls")
    if args.workers <= 0 or args.start < 0 or args.max_depth < 0:
        parser.error("workers must be positive; start and max-depth must be non-negative")
    if args.paper_run_config:
        indices = args.selected_indices
        if (
            not indices
            or any(not isinstance(value, int) or value < 0 for value in indices)
            or len(set(indices)) != len(indices)
        ):
            parser.error("paper-run task_indices must be non-empty, unique, non-negative integers")
    elif args.indices:
        try:
            indices = [int(value.strip()) for value in args.indices.split(",") if value.strip()]
        except ValueError as exc:
            parser.error(f"--indices must contain integers: {exc}")
        if not indices or any(value < 0 for value in indices) or len(set(indices)) != len(indices):
            parser.error("--indices must be non-empty, non-negative, and duplicate-free")
        args.selected_indices = indices
    else:
        end = args.end if args.end is not None else args.start
        if end < args.start:
            parser.error("end must be >= start")
        args.selected_indices = list(range(args.start, end + 1))
    args.condition = args.condition.strip()
    normalized_condition = args.condition.lower()
    if normalized_condition in {"base", "baseline", "b"}:
        args.condition = "BASE"
    elif re.fullmatch(r"[01]{2}", normalized_condition):
        args.condition = normalized_condition
    else:
        parser.error("condition must be BASE or a two-bit intent/plan value such as 11")
    return args


def ensure_mlflow_ready(args: argparse.Namespace) -> None:
    """Fail before any model calls if a paper run cannot be indexed."""
    if not args.paper_run:
        return
    interpreter = Path(args.mlflow_python)
    if not interpreter.is_file() or not MLFLOW_INDEXER.is_file():
        raise SystemExit(
            "Paper runs require the isolated MLflow environment and archive indexer; "
            "run uv sync in forammas_study first"
        )
    check = subprocess.run(
        [str(interpreter), "-c", "import mlflow"],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode:
        raise SystemExit("MLflow preflight failed; no benchmark workers were started")


def ensure_git_provenance(args: argparse.Namespace) -> None:
    """Formal runs require Git identities; dirty diffs are archived verbatim."""
    if not args.paper_run:
        return
    repos = [
        ("ROMA Agent", Path(args.project_root).resolve()),
        ("ROMA adapters", WORK_ROOT / "roma_v1_adapters"),
        ("LiteLLM proxy", WORK_ROOT / "roma_litellm_proxy"),
        ("paper-run/MLflow controls", STUDY_ROOT),
    ]
    problems: list[str] = []
    for label, repo in repos:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode:
            problems.append(f"{label}: no Git commit in {repo}")
            continue
    if problems:
        raise SystemExit("Paper-run Git identity check failed:\n- " + "\n- ".join(problems))


def validate_external_model_settings() -> None:
    temperature = os.environ.get("ROMA_TEMPERATURE_OVERRIDE")
    if temperature is not None:
        try:
            numeric = float(temperature)
        except ValueError as exc:
            raise SystemExit("ROMA_TEMPERATURE_OVERRIDE must be a number from 0 to 2") from exc
        if not 0.0 <= numeric <= 2.0:
            raise SystemExit("ROMA_TEMPERATURE_OVERRIDE must be between 0 and 2")
    model = os.environ.get("ROMA_MODEL_OVERRIDE", "").strip()
    if "\n" in model or "\r" in model:
        raise SystemExit("ROMA_MODEL_OVERRIDE must be a single-line LiteLLM model name")


def start_mlflow_record(archive: PaperRunArchive, args: argparse.Namespace) -> str:
    command = [
        args.mlflow_python,
        str(MLFLOW_INDEXER),
        "--start-only",
        "--experiment",
        args.mlflow_experiment,
        "--run-name",
        archive.run_id,
        "--tracking-uri",
        args.mlflow_tracking_uri,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            "MLflow could not create the pre-run record; no benchmark workers were started: "
            + (result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}")
        )
    run_id = result.stdout.strip().splitlines()[-1]
    archive.attach_mlflow(run_id, args.mlflow_tracking_uri, args.mlflow_experiment)
    return run_id


def index_paper_archive(
    archive: PaperRunArchive, args: argparse.Namespace, mlflow_run_id: str
) -> str:
    command = [
        args.mlflow_python,
        str(MLFLOW_INDEXER),
        str(archive.root),
        "--experiment",
        args.mlflow_experiment,
        "--run-name",
        archive.run_id,
        "--tracking-uri",
        args.mlflow_tracking_uri,
        "--existing-run-id",
        mlflow_run_id,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            "MLflow indexing failed after local archive finalization: "
            + (result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}")
        )
    run_id = result.stdout.strip().splitlines()[-1]
    record = {
        "timestamp": now(),
        "paper_run_id": archive.run_id,
        "archive": str(archive.root),
        "manifest_sha256": sha256_file(archive.root / "manifest.json"),
        "mlflow_run_id": run_id,
        "experiment": args.mlflow_experiment,
        "tracking_uri": args.mlflow_tracking_uri,
    }
    ledger = STUDY_ROOT / "mlflow_index.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ledger, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)
    print(f"MLflow indexed run: {run_id}")
    return run_id


def main() -> None:
    args = parse_args()
    validate_external_model_settings()
    ensure_mlflow_ready(args)
    ensure_git_provenance(args)
    project_root = Path(args.project_root).resolve()
    if not Path(args.python).exists():
        raise SystemExit(f"Python interpreter not found: {args.python}")
    if not RUNNER.exists() or not PROXY_SCRIPT.exists() or not ENV_FILE.exists():
        raise SystemExit("isolated runner dependencies are missing")
    benchmark_data = Path(args.benchmark_data).resolve()
    examples = load_examples(project_root, benchmark_data)
    invalid = [index for index in args.selected_indices if index >= len(examples)]
    if invalid:
        raise SystemExit(f"SEAL-0 index out of range: {invalid[:10]} (dataset size={len(examples)})")
    paper_archive = None
    mlflow_run_id = None
    paper_worker_root = None
    if args.paper_run:
        paper_archive = PaperRunArchive.create(
            args=args,
            examples=examples,
            selected_indices=args.selected_indices,
        )
        args.output = str(paper_archive.root / "runner_results.csv")
        paper_worker_root = new_worker_root()
        if paper_worker_root.exists():
            paper_archive.mark_preflight_failure(
                f"Refusing to reuse existing worker directory: {paper_worker_root}"
            )
            raise SystemExit(f"Paper-run worker directory already exists: {paper_worker_root}")
        paper_archive.set_worker_root(
            paper_worker_root,
            model_visible_path_policy=MODEL_VISIBLE_PATH_POLICY,
            worker_python_hash_seed=WORKER_PYTHONHASHSEED,
            tool_order_policy=TOOL_ORDER_POLICY,
        )
        # These are logging-only flags. They are inherited by the isolated
        # worker and proxy processes and do not enter ROMA's agent config.
        os.environ["ROMA_PAPER_RUN"] = "1"
        os.environ["ROMA_PAPER_RUN_ID"] = paper_archive.run_id
        os.environ["ROMA_PAPER_ARCHIVE_ROOT"] = str(paper_archive.root)
        try:
            mlflow_run_id = start_mlflow_record(paper_archive, args)
        except Exception as exc:
            paper_archive.mark_preflight_failure(f"{type(exc).__name__}: {exc}")
            raise SystemExit(str(exc)) from exc
    controller = IsolatedController(args, examples, worker_root=paper_worker_root)
    rows: list[dict[str, Any]] = []
    output_path = (
        paper_archive.root / "runner_results.csv"
        if paper_archive is not None
        else Path(args.output).resolve()
    )
    mlflow_error: Exception | None = None
    try:
        rows = asyncio.run(controller.run(args.selected_indices))
        write_results(output_path, rows)
    finally:
        if paper_archive is not None:
            paper_archive.finalize(
                rows=rows,
                worker_root=controller.root,
                output_csv=output_path,
                controller_state=controller.state,
            )
            print(f"Paper archive saved to: {paper_archive.root}")
            try:
                if mlflow_run_id:
                    index_paper_archive(paper_archive, args, mlflow_run_id)
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                mlflow_error = exc
    if mlflow_error is not None:
        raise SystemExit("Local raw archive is safe, but automatic MLflow indexing failed") from mlflow_error
    print(f"Results saved to: {Path(args.output).resolve()}")
    print(json.dumps(controller.state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
