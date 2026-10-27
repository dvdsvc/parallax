"""Immutable, provenance-oriented archive for formal ROMA/SEAL-0 runs.

This module is deliberately outside the ROMA checkout.  It snapshots the
selected runtime state and copies the existing per-question worker ledgers;
it does not participate in agent execution or grading decisions.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _run(command: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=20)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def git_state(repo: Path) -> dict[str, Any]:
    top = _run(["git", "rev-parse", "--show-toplevel"], repo)
    if not top:
        return {"path": str(repo), "git": False, "commit": None, "dirty": None}
    status = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo)
    commit = _run(["git", "rev-parse", "HEAD"], repo)
    return {
        "path": str(repo),
        "git": True,
        "root": top,
        "commit": commit or None,
        "dirty": bool(status),
        "status": status.splitlines(),
    }


def _redact_env_line(line: str) -> str:
    if "=" not in line or line.lstrip().startswith("#"):
        return line
    key, value = line.split("=", 1)
    upper = key.upper()
    if any(token in upper for token in ("API_KEY", "SECRET", "PASSWORD", "AUTHORIZATION", "TOKEN")):
        return f"{key}=<REDACTED>"
    return line


def copy_redacted(path: Path, destination: Path) -> None:
    if not path.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix in {".env", ".yaml", ".yml", ".toml", ".json", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".env":
            text = "\n".join(_redact_env_line(line) for line in text.splitlines()) + "\n"
        destination.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(path, destination)


def package_versions(names: list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


class PaperRunArchive:
    """Create one unique archive and finalize it without replacing old runs."""

    def __init__(self, root: Path, run_id: str, args: Any, examples: list[Any]):
        self.root = root
        self.run_id = run_id
        self.args = args
        self.examples = examples
        self.started_at = utc_now()

    @classmethod
    def create(cls, *, args: Any, examples: list[Any], selected_indices: list[int]) -> "PaperRunArchive":
        root_base = Path(args.paper_runs_root).expanduser().resolve()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = args.paper_run_id or f"seal0-{args.condition.lower()}-{uuid4().hex[:12]}"
        slug = f"{timestamp}_{args.condition}_{run_id}"
        root = root_base / slug
        counter = 1
        while root.exists():
            root = root_base / f"{slug}_{counter:02d}"
            counter += 1
        root.mkdir(parents=True, exist_ok=False)
        archive = cls(root, run_id, args, examples)
        archive._write_initial_manifest(selected_indices)
        archive._snapshot_static_state()
        return archive

    def _benchmark_snapshot(self, selected_indices: list[int]) -> dict[str, Any]:
        parquet = Path(self.args.benchmark_data).resolve()
        tasks = []
        for index in selected_indices:
            example = self.examples[index]
            goal = str(getattr(example, "goal", ""))
            tasks.append({
                "index": index,
                "task_id": str(getattr(example, "id", index)),
                "goal_sha256": sha256_text(goal),
            })
        return {
            "name": "SEAL-0",
            "loader": "prompt_optimization.dataset_loaders.load_seal0_dataset",
            "seed": 0,
            "split": "test",
            "no_split": True,
            "file": str(parquet),
            "file_sha256": sha256_file(parquet),
            "dataset_count": len(self.examples),
            "selected_indices": selected_indices,
            "tasks": tasks,
        }

    def _base_manifest(self, selected_indices: list[int]) -> dict[str, Any]:
        project_root = Path(self.args.project_root).resolve()
        return {
            "schema_version": 1,
            "archive_type": "roma_seal0_paper_run",
            "run_id": self.run_id,
            "condition": self.args.condition,
            "status": "running",
            "started_at": self.started_at,
            "finished_at": None,
            "agent": {
                "checkout": str(project_root),
                "git": git_state(project_root),
                "runner": str(Path(__file__).resolve().parent / "run_isolated_seal0.py"),
                "runner_sha256": sha256_file(Path(__file__).resolve().parent / "run_isolated_seal0.py"),
                "proxy_hook": str(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "custom_hook.py"),
                "proxy_hook_sha256": sha256_file(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "custom_hook.py"),
                "control_layer": git_state(WORK_ROOT / "forammas_study"),
                "adapter_repository": git_state(WORK_ROOT / "roma_v1_adapters"),
                "proxy_repository": git_state(WORK_ROOT / "roma_litellm_proxy"),
                "proxy_stack": str(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "start_proxy_stack.py"),
                "proxy_stack_sha256": sha256_file(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "start_proxy_stack.py"),
                "cache_adapter": str(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "qwen_cache_adapter.py"),
                "cache_adapter_sha256": sha256_file(Path(__file__).resolve().parents[1] / "roma_litellm_proxy" / "qwen_cache_adapter.py"),
            },
            "benchmark": self._benchmark_snapshot(selected_indices),
            "execution": {
                "workers": self.args.workers,
                "max_depth": self.args.max_depth,
                "condition": self.args.condition,
                "paper_run": True,
            },
            "context_interventions": {
                "organization_awareness_v2": os.environ.get(
                    "ROMA_ORG_AWARENESS_V2", "0"
                ).strip().lower() in {"1", "true", "yes", "on"},
                "organization_awareness_v2_prompt_sha256": sha256_file(
                    WORK_ROOT
                    / "forammas_study"
                    / "prompts"
                    / "global_organizational_architecture_v2.txt"
                ),
                "condition_bit_order": ["intent", "plan"],
                "organization_awareness_mode": (
                    "static_global_architecture_v2"
                    if os.environ.get("ROMA_ORG_AWARENESS_V2", "0").strip().lower() in {"1", "true", "yes", "on"}
                    else "off"
                ),
                "injection_boundary": "worker_before_litellm",
                "role_dependent": False,
            },
            "paper_run_config": (
                {
                    "source": str(Path(self.args.paper_run_config_path).resolve()),
                    "sha256": sha256_file(Path(self.args.paper_run_config_path).resolve()),
                    "archive": "config/paper_run_config.json",
                }
                if getattr(self.args, "paper_run_config_path", None)
                else None
            ),
            "model": {
                "model": os.environ.get("ROMA_MODEL_OVERRIDE") or os.environ.get("ROMA_MODEL") or os.environ.get("ROMA___AGENTS__EXECUTOR__LLM__MODEL") or "openai/qwen3.7-flash",
                "provider": os.environ.get("ROMA_PROVIDER_LABEL", "dashscope-compatible-via-litellm-proxy"),
                "base_url": os.environ.get("QWEN_BASE_URL") or os.environ.get("ROMA_PROXY_BASE_URL"),
                "temperature": os.environ.get("ROMA_TEMPERATURE_OVERRIDE") or os.environ.get("ROMA_TEMPERATURE"),
                "max_tokens": os.environ.get("ROMA_MAX_TOKENS"),
                "seed": os.environ.get("ROMA_SEED"),
                "note": "Per-request effective decoding fields are also stored in traces/raw_requests.jsonl.",
            },
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
                "platform": platform.platform(),
                "packages": package_versions(["litellm", "dspy", "openai", "pyarrow", "pandas", "agentops"]),
            },
            "artifacts": {},
        }

    def _write_initial_manifest(self, selected_indices: list[int]) -> None:
        json_write(self.root / "manifest.json", self._base_manifest(selected_indices))

    def set_worker_root(
        self,
        worker_root: Path,
        *,
        model_visible_path_policy: str | None = None,
        worker_python_hash_seed: str | None = None,
        tool_order_policy: str | None = None,
    ) -> None:
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("execution", {})["worker_root"] = str(worker_root.resolve())
        manifest["execution"]["results_csv"] = "runner_results.csv"
        if model_visible_path_policy is not None:
            manifest["execution"]["model_visible_path_policy"] = model_visible_path_policy
        if worker_python_hash_seed is not None:
            manifest["execution"]["worker_python_hash_seed"] = worker_python_hash_seed
        if tool_order_policy is not None:
            manifest["execution"]["tool_order_policy"] = tool_order_policy
        json_write(manifest_path, manifest)

    def attach_mlflow(self, mlflow_run_id: str, tracking_uri: str, experiment: str) -> None:
        """Link the pre-created MLflow record to this local paper run."""
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["mlflow"] = {
            "run_id": mlflow_run_id,
            "tracking_uri": tracking_uri,
            "experiment": experiment,
            "status_at_start": "RUNNING",
        }
        json_write(manifest_path, manifest)

    def mark_preflight_failure(self, error: str) -> None:
        """Close an archive when provenance/index preflight fails before work."""
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "status": "failed_preflight",
            "finished_at": utc_now(),
            "preflight_error": error,
        })
        json_write(manifest_path, manifest)
        self._write_checksums()

    def _write_checksums(self) -> None:
        checksums = self.root / "checksums.sha256"
        lines = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and path != checksums:
                lines.append(f"{sha256_file(path)}  {path.relative_to(self.root)}")
        checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _snapshot_static_state(self) -> None:
        config = self.root / "config"
        prompts = self.root / "prompts"
        code_state = self.root / "code_state"
        config.mkdir(parents=True, exist_ok=True)
        prompts.mkdir(parents=True, exist_ok=True)
        code_state.mkdir(parents=True, exist_ok=True)

        project_root = Path(self.args.project_root).resolve()
        paper_config = getattr(self.args, "paper_run_config_path", None)
        if paper_config:
            copy_redacted(
                Path(paper_config).resolve(), config / "paper_run_config.json"
            )
        if (project_root / "config").exists():
            shutil.copytree(project_root / "config", config / "roma_config", dirs_exist_ok=True)
        # Keep a single, explicit record of the agent configuration that this
        # runner asks ROMA to load.  The complete profile is copied below as
        # a redacted file; this JSON is the stable index used by later audits.
        # This is archive-only and is deliberately not read by the agent.
        profile_name = str(getattr(self.args, "profile", "general") or "general")
        profile_path = project_root / "config" / "profiles" / f"{profile_name}.yaml"
        agent_snapshot = {
            "schema_version": 1,
            "snapshot_type": "effective_agent_configuration",
            "captured_at": utc_now(),
            "profile": profile_name,
            "profile_source": str(profile_path),
            "profile_sha256": sha256_file(profile_path),
            "profile_archive": "config/agent_snapshot/" + profile_path.name,
            "agent_checkout": str(project_root),
            "agent_git": git_state(project_root),
            "runner": str(Path(__file__).resolve()),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "condition": getattr(self.args, "condition", None),
            "benchmark": getattr(self.args, "benchmark", "FRAMES"),
            "selected_indices": list(getattr(self.args, "selected_indices", [])),
            "workers": getattr(self.args, "workers", None),
            "max_depth": getattr(self.args, "max_depth", None),
            "paper_run": bool(getattr(self.args, "paper_run", False)),
            "environment": {
                key: os.environ[key]
                for key in sorted(os.environ)
                if key in {
                    "ROMA_PROFILE", "ROMA_MODEL", "ROMA_TEMPERATURE",
                    "ROMA_MODEL_OVERRIDE", "ROMA_TEMPERATURE_OVERRIDE",
                    "ROMA_PROVIDER_LABEL",
                    "ROMA_MAX_TOKENS", "ROMA_SEED", "ROMA_PROXY_CONDITION",
                    "ROMA_PROXY_EXPECTED_CONDITION", "ROMA_PAPER_RUN",
                    "ROMA_PROXY_ORG_AWARENESS_V2",
                    "ROMA_ORG_AWARENESS_V2",
                    "ROMA_PROXY_SECOND_ORDER",
                    "ROMA_PROXY_SECOND_ORDER_LAYERS", "ROMA_PROXY_SECOND_ORDER_CONTEXT",
                    "ROMA_PROXY_LAYER_OVERRIDES",
                    "ROMA_PAPER_RUN_ID", "ROMA_CHECKPOINT_PATH",
                    "STORAGE_BASE_PATH", "LITELLM_PROXY_PORT",
                }
            },
            "note": "Archive metadata only; no agent execution behavior is changed.",
        }
        json_write(config / "agent_snapshot.json", agent_snapshot)
        if profile_path.exists():
            copy_redacted(profile_path, config / "agent_snapshot" / profile_path.name)
        manifest_path = self.root / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.setdefault("agent", {})["snapshot"] = {
                "json": "config/agent_snapshot.json",
                "profile": agent_snapshot["profile_archive"],
                "profile_sha256": agent_snapshot["profile_sha256"],
            }
            json_write(manifest_path, manifest)
        for source, target in [
            (WORK_ROOT / "roma_litellm_proxy" / "config.yaml", config / "proxy_config.yaml"),
            (WORK_ROOT / "roma_litellm_proxy" / "context_manifest.json", config / "context_manifest.json"),
            (WORK_ROOT / "forammas_study" / "prompts" / "global_organizational_architecture_v2.txt", prompts / "global_organizational_architecture_v2.txt"),
            (WORK_ROOT / "roma_litellm_proxy" / "second_order_context.txt", prompts / "second_order_context.txt"),
            (WORK_ROOT / "roma_v1_qwen_litellm.env", config / "roma_v1_qwen_litellm.env"),
            (WORK_ROOT / "roma_litellm_proxy" / "start_proxy_stack.py", config / "start_proxy_stack.py"),
            (WORK_ROOT / "roma_litellm_proxy" / "qwen_cache_adapter.py", config / "qwen_cache_adapter.py"),
        ]:
            copy_redacted(source, target)
        external_files = [
            Path(__file__),
            Path(__file__).resolve().parent / "run_isolated_seal0.py",
            WORK_ROOT / "roma_v1_adapters" / "run_official_seal0.py",
            WORK_ROOT / "roma_v1_adapters" / "paper_grade_run.py",
            WORK_ROOT / "roma_v1_adapters" / "agentops_observer.py",
            WORK_ROOT / "roma_v1_adapters" / "current_node_context.py",
            WORK_ROOT / "roma_litellm_proxy" / "custom_hook.py",
            WORK_ROOT / "forammas_study" / "prompts" / "global_organizational_architecture_v2.txt",
            WORK_ROOT / "forammas_study" / "condition_registry.json",
            WORK_ROOT / "forammas_study" / "conditions.py",
            WORK_ROOT / "forammas_study" / "trace_guard.py",
            WORK_ROOT / "roma_litellm_proxy" / "summarize_metrics.py",
            WORK_ROOT / "roma_litellm_proxy" / "start_proxy.sh",
            WORK_ROOT / "roma_litellm_proxy" / "start_proxy_stack.py",
            WORK_ROOT / "roma_litellm_proxy" / "qwen_cache_adapter.py",
        ]
        file_records = []
        for source in external_files:
            if source.exists():
                target = code_state / "external" / source.name
                copy_redacted(source, target)
                file_records.append({"source": str(source), "archive": str(target.relative_to(self.root)), "sha256": sha256_file(source)})
        official_state = git_state(project_root)
        control_layer_state = git_state(WORK_ROOT / "forammas_study")
        adapter_state = git_state(WORK_ROOT / "roma_v1_adapters")
        proxy_state = git_state(WORK_ROOT / "roma_litellm_proxy")
        json_write(code_state / "git_state.json", {
            "official_agent_repository": official_state,
            "experiment_control_layer": control_layer_state,
            "runner_adapter_repository": adapter_state,
            "litellm_proxy_repository": proxy_state,
            "external_files": file_records,
            "python_command": [str(self.args.python), "-m", "pip", "freeze"],
            "pip_freeze": _run([str(self.args.python), "-m", "pip", "freeze"]),
        })
        if official_state.get("git") and official_state.get("dirty"):
            (code_state / "official_agent.git.diff").write_text(
                _run(["git", "diff", "--binary", "HEAD"], project_root), encoding="utf-8"
            )
            (code_state / "official_agent.untracked.txt").write_text(
                "\n".join(official_state.get("status", [])) + "\n", encoding="utf-8"
            )
            for status_line in official_state.get("status", []):
                if not status_line.startswith("?? "):
                    continue
                relative = status_line[3:]
                source = project_root / relative
                if source.is_file():
                    copy_redacted(source, code_state / "untracked" / relative)
        if control_layer_state.get("git") and control_layer_state.get("dirty"):
            control_root = WORK_ROOT / "forammas_study"
            (code_state / "experiment_control.git.diff").write_text(
                _run(["git", "diff", "--binary", "HEAD"], control_root), encoding="utf-8"
            )
            (code_state / "experiment_control.untracked.txt").write_text(
                "\n".join(control_layer_state.get("status", [])) + "\n", encoding="utf-8"
            )
            for status_line in control_layer_state.get("status", []):
                if not status_line.startswith("?? "):
                    continue
                source = control_root / status_line[3:]
                if source.is_file():
                    copy_redacted(source, code_state / "experiment_control_untracked" / status_line[3:])
        for repo_name, repo_root, repo_state in [
            ("runner_adapter", WORK_ROOT / "roma_v1_adapters", adapter_state),
            ("litellm_proxy", WORK_ROOT / "roma_litellm_proxy", proxy_state),
        ]:
            if repo_state.get("git") and repo_state.get("dirty"):
                (code_state / f"{repo_name}.git.diff").write_text(
                    _run(["git", "diff", "--binary", "HEAD"], repo_root),
                    encoding="utf-8",
                )
                (code_state / f"{repo_name}.untracked.txt").write_text(
                    "\n".join(repo_state.get("status", [])) + "\n",
                    encoding="utf-8",
                )
                for status_line in repo_state.get("status", []):
                    if not status_line.startswith("?? "):
                        continue
                    source = repo_root / status_line[3:]
                    if source.is_file():
                        copy_redacted(
                            source,
                            code_state / f"{repo_name}_untracked" / status_line[3:],
                        )

    def _copy_worker(self, worker_dir: Path, trace_destination: Path) -> None:
        if worker_dir.exists():
            shutil.copytree(worker_dir, trace_destination, dirs_exist_ok=False)

    def _write_outputs(self, rows: list[dict[str, Any]], worker_root: Path) -> Path:
        output_path = self.root / "outputs.jsonl"
        with output_path.open("w", encoding="utf-8") as handle:
            for row in sorted(rows, key=lambda item: int(item.get("index", 0))):
                index = int(row.get("index", 0))
                metrics_path = worker_root / f"q-{index:04d}" / "result.metrics.json"
                metrics = {}
                if metrics_path.exists():
                    try:
                        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        metrics = {}
                payload = {
                    "paper_run_id": self.run_id,
                    "question_index": index,
                    "question_id": index,
                    "goal": row.get("goal"),
                    "ground_truth": row.get("ground_truth"),
                    "predicted_answer": row.get("predicted_answer"),
                    "status": row.get("status"),
                    "error": row.get("error"),
                    "worker_run_id": metrics.get("run_id"),
                    "raw_worker_dir": str(self.root / "traces" / f"q-{index:04d}"),
                    "metrics": metrics,
                    "raw_result_row": row,
                }
                handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return output_path

    def _write_metrics(self, rows: list[dict[str, Any]], worker_root: Path) -> Path:
        metrics_rows = []
        for row in rows:
            index = int(row.get("index", 0))
            path = worker_root / f"q-{index:04d}" / "result.metrics.json"
            if path.exists():
                try:
                    metrics = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    metrics = {}
            else:
                metrics = {}
            metrics = {"question_index": index, "status": row.get("status"), **metrics}
            metrics_rows.append(metrics)
        fields = sorted({key for row in metrics_rows for key in row})
        output = self.root / "metrics.csv"
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sorted(metrics_rows, key=lambda item: int(item.get("question_index", 0))))
        return output

    def finalize(self, *, rows: list[dict[str, Any]], worker_root: Path, output_csv: Path, controller_state: dict[str, Any]) -> None:
        traces = self.root / "traces"
        traces.mkdir(parents=True, exist_ok=True)
        copied = []
        for worker_dir in sorted(worker_root.glob("q-*")):
            destination = traces / worker_dir.name
            self._copy_worker(worker_dir, destination)
            copied.append(worker_dir.name)
        outputs = self._write_outputs(rows, worker_root)
        metrics = self._write_metrics(rows, worker_root)
        grader = self.root / "grader"
        grader.mkdir(parents=True, exist_ok=True)
        (grader / "README.txt").write_text(
            "Raw grader inputs, responses, retries, and derived scores belong here.\n"
            "This directory is append-only by run; do not replace raw judge records.\n",
            encoding="utf-8",
        )
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        request_samples = []
        for raw_path in traces.glob("q-*/trace/raw_requests.jsonl"):
            for line in raw_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(request, dict):
                    request_samples.append(request)
        def first_value(key: str) -> Any:
            for request in request_samples:
                value = request.get(key)
                if value is not None:
                    return value
            return None
        manifest["model"].update({
            "effective_model": first_value("model"),
            "effective_temperature": first_value("temperature"),
            "effective_max_tokens": first_value("max_tokens"),
            "effective_seed": first_value("seed"),
            "raw_request_count": len(request_samples),
        })
        expected_total = int(controller_state.get("total") or 0)
        is_complete = (
            expected_total > 0
            and len(rows) == expected_total
            and all(row.get("status") == "COMPLETED" for row in rows)
        )
        manifest.update({
            "status": "completed" if is_complete else "partial_or_error",
            "finished_at": utc_now(),
            "controller_state": controller_state,
            "artifacts": {
                "outputs": str(outputs.relative_to(self.root)),
                "metrics": str(metrics.relative_to(self.root)),
                "raw_traces": str(traces.relative_to(self.root)),
                "worker_count": len(copied),
                "source_result_csv": str(output_csv),
            },
        })
        json_write(self.root / "manifest.json", manifest)
        self._write_checksums()


WORK_ROOT = Path(__file__).resolve().parents[1]
