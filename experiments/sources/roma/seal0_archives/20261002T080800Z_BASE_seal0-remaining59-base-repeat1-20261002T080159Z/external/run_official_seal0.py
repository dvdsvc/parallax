"""Run the official ROMA v1 dataset evaluator with an external search toolkit."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make the external runner self-contained when invoked by absolute path.
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = WORKSPACE_ROOT / "work"
PROJECT_ROOT = Path(
    os.environ.get(
        "ROMA_PROJECT_ROOT", str(WORKSPACE_ROOT / "official-roma")
    )
).resolve()
# Keep the selected checkout's package and official ``scripts`` namespace
# ahead of any inherited PYTHONPATH entry from another ROMA checkout.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(WORK_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from roma_dspy.config.manager import ConfigManager
from roma_dspy.config.schemas.toolkit import ToolkitConfig
from roma_dspy.tools.base.manager import ToolkitManager

from roma_litellm_proxy.summarize_metrics import summarize
from roma_v1_adapters import ZhipuSearchToolkit
from roma_v1_adapters.agentops_observer import install_observer


PROVIDER_BLOCKED_ERROR_MARKERS = (
    "DataInspectionFailed",
    "inappropriate content",
    "Circuit breaker is open",
    "CircuitOpenError",
)


def install_external_toolkit() -> None:
    ToolkitManager.get_instance().register_external_toolkit(
        "ZhipuSearchToolkit", ZhipuSearchToolkit
    )


def patch_official_config() -> None:
    """Patch only in-memory runtime configuration; never write agent config."""
    original_load = ConfigManager.load_config

    def load_config(self, *args, **kwargs):
        overrides = list(kwargs.pop("overrides", None) or [])
        if "runtime.timeout=900" not in overrides:
            overrides.append("runtime.timeout=900")
        model_override = os.environ.get("ROMA_MODEL_OVERRIDE", "").strip()
        if model_override:
            for role in ("atomizer", "planner", "executor", "aggregator", "verifier"):
                overrides.append(f"agents.{role}.llm.model={model_override}")
        temperature_raw = os.environ.get("ROMA_TEMPERATURE_OVERRIDE")
        if temperature_raw is not None:
            try:
                temperature = float(temperature_raw)
            except ValueError as exc:
                raise ValueError("ROMA_TEMPERATURE_OVERRIDE must be a number from 0 to 2") from exc
            if not 0.0 <= temperature <= 2.0:
                raise ValueError("ROMA_TEMPERATURE_OVERRIDE must be between 0 and 2")
            for role in ("atomizer", "planner", "executor", "aggregator", "verifier"):
                overrides.append(f"agents.{role}.llm.temperature={temperature}")
        config = original_load(self, *args, overrides=overrides, **kwargs)
        search_config = ToolkitConfig(
            class_name="ZhipuSearchToolkit",
            enabled=True,
            toolkit_config={
                "search_engine": "search_std",
                "count": 10,
                "content_size": "medium",
                "timeout": 30.0,
            },
        )
        for name in ("planner", "executor"):
            agent = getattr(config.agents, name)
            agent.toolkits = [
                search_config if toolkit.class_name == "WebSearchToolkit" else toolkit
                for toolkit in agent.toolkits
            ]
        return config

    ConfigManager.load_config = load_config


def patch_dataset_slice(
    evaluator_module: object,
    start: int,
    size: int,
    positions: list[int] | None = None,
) -> None:
    """Select an external slice/index list while retaining the official loop."""
    loaders = evaluator_module.DATASET_LOADERS
    original_loader = loaders["seal0"]
    local_parquet = os.environ.get("ROMA_SEAL0_PARQUET_PATH")

    def load_slice(*args, **kwargs):
        if local_parquet:
            kwargs["parquet_path"] = local_parquet
        dataset = original_loader(*args, **kwargs)
        if kwargs.get("no_split"):
            if positions is not None:
                return [dataset[start + position] for position in positions]
            return dataset[start : start + size]
        return dataset

    loaders["seal0"] = load_slice


def patch_provider_blocked_status(evaluator_module: object) -> None:
    """Label provider blocks and their circuit-open result as skipped examples.

    The official evaluator already catches exceptions per example and keeps
    consuming ``asyncio.as_completed`` results. This wrapper only changes the
    returned row label after that official catch; it does not change the
    evaluator loop or ROMA execution semantics. The circuit-open marker is
    included because it is the provider-block cascade returned by ROMA after
    the upstream request has already been rejected.
    """
    original_solve_example = evaluator_module.solve_example

    def provider_blocked_reason(error: str) -> str | None:
        lowered = error.lower()
        for marker in PROVIDER_BLOCKED_ERROR_MARKERS:
            if marker.lower() in lowered:
                return marker
        return None

    async def solve_example(*args, **kwargs):
        result = await original_solve_example(*args, **kwargs)
        error = str(result.get("error") or "")
        reason = provider_blocked_reason(error)
        if result.get("status") == "ERROR" and reason:
            result["status"] = "SKIPPED_PROVIDER_BLOCKED"
            result["provider_blocked_reason"] = reason
            result["error"] = f"provider_blocked: {reason}: {error}"
        return result

    evaluator_module.solve_example = solve_example


def align_result_indices(
    result_path: Path, start: int, positions: list[int] | None = None
) -> None:
    """Keep result indices aligned with the original full dataset."""
    import pandas as pd

    frame = pd.read_csv(result_path)
    if "index" in frame.columns:
        indices = frame["index"].astype(int)
        if positions is None:
            frame["index"] = indices + start
        else:
            frame["index"] = indices.map(lambda value: start + positions[value])
        frame.to_csv(result_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=2)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument(
        "--indices",
        default=None,
        help="Comma-separated positions within the selected full-dataset range",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "results" / "roma_v1_qwen_glm_seal0.csv"),
    )
    args = parser.parse_args()
    if args.size <= 0 or args.start < 0 or args.threads <= 0:
        parser.error("--size, --start, and --threads must be positive/non-negative")
    selected_positions = None
    if args.indices is not None:
        try:
            selected_positions = [
                int(value.strip()) for value in args.indices.split(",") if value.strip()
            ]
        except ValueError as exc:
            parser.error(f"--indices must be comma-separated integers: {exc}")
        if not selected_positions or any(value < 0 for value in selected_positions):
            parser.error("--indices must contain at least one non-negative integer")
        if len(set(selected_positions)) != len(selected_positions):
            parser.error("--indices must not contain duplicates")
    result_path = Path(args.output)
    if not result_path.is_absolute():
        result_path = PROJECT_ROOT / result_path

    install_external_toolkit()
    patch_official_config()
    os.chdir(PROJECT_ROOT)

    import scripts.evaluate_dataset as evaluator_module

    patch_dataset_slice(
        evaluator_module, args.start, args.size, positions=selected_positions
    )
    patch_provider_blocked_status(evaluator_module)

    observer_run = None
    run_id = os.environ.get("ROMA_RUN_ID") or "roma-unstarted"
    run_status = "failed"
    try:
        observer_run = install_observer()
        run_id = observer_run.run_id
        asyncio.run(
            evaluator_module.evaluate_dataset(
                dataset_name="seal0",
                split="test",
                size=args.size,
                num_threads=args.threads,
                profile="general",
                max_depth=args.max_depth,
                output_path=str(result_path),
                seed=0,
                no_split=True,
                skip_mlflow_info=True,
            )
        )
        run_status = "completed"
    finally:
        if observer_run is not None:
            observer_run.finish(run_status)

        trace_dir = Path(
            os.environ.get(
                "ROMA_PROXY_TRACE_DIR", str(WORK_ROOT / "roma_litellm_proxy" / "traces")
            )
        )
        try:
            metrics = summarize(trace_dir, result_path, run_id)
            metrics_error = None
        except Exception as exc:
            metrics = {
                "run_id": run_id,
                "accuracy": None,
                "accuracy_source": "summary_error",
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
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
            metrics_error = f"{type(exc).__name__}: {exc}"
        metrics.update(
            {
                "schema_version": 2,
                "recorder_required": True,
                "recorder_started": observer_run is not None,
                "recorder_status": (
                    "complete"
                    if observer_run is not None and run_status == "completed"
                    else "failed"
                    if observer_run is not None
                    else "not_started"
                ),
                "condition_requested": os.environ.get("ROMA_PROXY_CONDITION", "BASE"),
                "metrics_source": "runner_finalized",
            }
        )
        if metrics_error:
            metrics["summary_error"] = metrics_error
        metrics_path = result_path.with_suffix(".metrics.json")
        temporary_metrics_path = metrics_path.with_suffix(metrics_path.suffix + ".tmp")
        temporary_metrics_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary_metrics_path, metrics_path)
        print(f"Metrics saved to: {metrics_path}")

    align_result_indices(result_path, args.start, positions=selected_positions)


if __name__ == "__main__":
    main()
