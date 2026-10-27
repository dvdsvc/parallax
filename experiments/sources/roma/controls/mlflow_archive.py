"""Index an already-finalized, immutable ROMA run archive in local MLflow."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from conditions import load_registry


def log_archive(
    archive: Path,
    *,
    experiment: str,
    run_name: str,
    tracking_uri: str,
    params: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    existing_run_id: str | None = None,
) -> str:
    """Log metadata and a byte-for-byte artifact copy; never edit archive files."""
    manifest_path = archive / "manifest.json"
    if not archive.is_dir() or not manifest_path.is_file():
        raise FileNotFoundError(f"Expected finalized archive with manifest.json: {archive}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") in {"running", "pending", None}:
        raise ValueError("Refusing to index an archive without a finalized status")

    try:
        import mlflow
    except ImportError as exc:
        raise RuntimeError("Install the isolated requirements from this study directory") from exc

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    auto_params, auto_tags = _manifest_metadata(manifest)
    merged_tags = {
        **auto_tags,
        **(tags or {}),
        "paper_run_status": str(manifest.get("status", "unknown")),
        "local_archive": str(archive.resolve()),
    }
    run_context = (
        mlflow.start_run(run_id=existing_run_id)
        if existing_run_id
        else mlflow.start_run(run_name=run_name, tags=merged_tags)
    )
    with run_context as run:
        for key, value in merged_tags.items():
            mlflow.set_tag(key, str(value))
        safe_params = {
            str(k): str(v)
            for k, v in {**auto_params, **(params or {})}.items()
            if v is not None
        }
        mlflow.log_params(safe_params)
        metrics = _aggregate_metrics(archive)
        if metrics:
            mlflow.log_metrics(metrics)
        mlflow.log_artifacts(str(archive), artifact_path="paper_archive")
        mlflow.set_tag("archive_manifest_sha256", _sha256(manifest_path))
        return run.info.run_id


def start_mlflow_run(*, experiment: str, run_name: str, tracking_uri: str) -> str:
    """Create the MLflow record before any benchmark/model work begins."""
    try:
        import mlflow
    except ImportError as exc:
        raise RuntimeError("Install the isolated requirements from this study directory") from exc
    mlflow.set_tracking_uri(tracking_uri)
    experiment_obj = mlflow.set_experiment(experiment)
    client = mlflow.tracking.MlflowClient()
    run = client.create_run(
        experiment_obj.experiment_id,
        tags={"mlflow.runName": run_name, "paper_run_status": "running"},
    )
    return run.info.run_id


def _manifest_metadata(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    execution = manifest.get("execution") or {}
    model = manifest.get("model") or {}
    benchmark = manifest.get("benchmark") or {}
    agent = manifest.get("agent") or {}
    git = agent.get("git") or {}
    control = agent.get("control_layer") or {}
    adapter = agent.get("adapter_repository") or {}
    proxy = agent.get("proxy_repository") or {}
    context = manifest.get("context_interventions") or {}
    condition_code = manifest.get("condition")
    condition_names = {
        (item.get("condition_code"), bool(item.get("static_global_architecture_visible"))): name
        for name, item in load_registry()["conditions"].items()
    }
    architecture_enabled = bool(context.get("organization_awareness_v2"))
    condition_name = (
        condition_names.get((condition_code, architecture_enabled), "unknown")
        if condition_code != "BASE"
        else "native_BASE"
    )
    params = {
        "run_id": manifest.get("run_id"),
        "condition": manifest.get("condition"),
        "condition_name": condition_name,
        "workers": execution.get("workers"),
        "max_depth": execution.get("max_depth"),
        "model": model.get("effective_model") or model.get("model"),
        "temperature": model.get("effective_temperature") or model.get("temperature"),
        "max_tokens": model.get("effective_max_tokens") or model.get("max_tokens"),
        "seed": model.get("effective_seed") or model.get("seed"),
        "benchmark": benchmark.get("name"),
        "benchmark_file_sha256": benchmark.get("file_sha256"),
        "agent_commit": git.get("commit"),
        "control_layer_commit": control.get("commit"),
        "adapter_commit": adapter.get("commit"),
        "proxy_commit": proxy.get("commit"),
        "organization_awareness_v2": context.get("organization_awareness_v2"),
        "organization_awareness_v2_prompt_sha256": context.get("organization_awareness_v2_prompt_sha256"),
    }
    tags = {
        "archive_status": str(manifest.get("status", "unknown")),
        "agent_commit": str(git.get("commit", "unknown")),
        "agent_dirty": str(bool(git.get("dirty"))).lower(),
        "benchmark": str(benchmark.get("name", "unknown")),
        "condition": str(manifest.get("condition", "unknown")),
        "condition_name": condition_name,
        "control_layer_commit": str(control.get("commit", "unknown")),
        "adapter_commit": str(adapter.get("commit", "unknown")),
        "proxy_commit": str(proxy.get("commit", "unknown")),
    }
    return params, tags


def _aggregate_metrics(archive: Path) -> dict[str, float]:
    """Log a small derived status summary; raw files remain immutable artifacts."""
    outputs = archive / "outputs.jsonl"
    if not outputs.is_file():
        return {}
    rows = [json.loads(line) for line in outputs.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {"questions_total": 0.0}
    statuses = [str(row.get("status", "UNKNOWN")).upper() for row in rows]
    result = {
        "questions_total": float(len(rows)),
        "questions_completed": float(sum(status == "COMPLETED" for status in statuses)),
        "questions_error": float(sum(status == "ERROR" for status in statuses)),
        "questions_provider_blocked": float(sum("PROVIDER_BLOCKED" in status for status in statuses)),
    }
    metrics_path = archive / "metrics.csv"
    if metrics_path.is_file():
        numeric: dict[str, list[float]] = {}
        with metrics_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for key, value in row.items():
                    if key in {"question_index", "status"} or value in (None, ""):
                        continue
                    try:
                        numeric.setdefault(key, []).append(float(value))
                    except (TypeError, ValueError):
                        continue
        for key, values in numeric.items():
            if key.endswith(("tokens", "tool_calls", "agent_nodes", "depth_reached")) and values:
                result[f"mean_{key}"] = sum(values) / len(values)
    return result


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, nargs="?")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--tracking-uri", required=True, help="For local use: sqlite:////absolute/path/mlflow.db")
    parser.add_argument("--params-json", type=Path)
    parser.add_argument("--tags-json", type=Path)
    parser.add_argument("--start-only", action="store_true", help="Create a RUNNING MLflow record before work begins")
    parser.add_argument("--existing-run-id", help="Finalize and attach an archive to a pre-created MLflow run")
    args = parser.parse_args()
    if args.start_only:
        if args.archive is not None or args.existing_run_id:
            parser.error("--start-only cannot be combined with an archive or --existing-run-id")
        print(start_mlflow_run(
            experiment=args.experiment,
            run_name=args.run_name,
            tracking_uri=args.tracking_uri,
        ))
        return
    if args.archive is None:
        parser.error("archive is required unless --start-only is used")
    params = json.loads(args.params_json.read_text(encoding="utf-8")) if args.params_json else None
    tags = json.loads(args.tags_json.read_text(encoding="utf-8")) if args.tags_json else None
    run_id = log_archive(
        args.archive,
        experiment=args.experiment,
        run_name=args.run_name,
        tracking_uri=args.tracking_uri,
        params=params,
        tags=tags,
        existing_run_id=args.existing_run_id,
    )
    print(run_id)


if __name__ == "__main__":
    main()
