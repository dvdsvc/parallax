"""Score ROMA/SEAL-0 result CSVs through the official SEAL-0 grader.

The grading semantics live in ``official-roma-v2/evals/grade_answers_simple.py``.
This file is only an adapter from ROMA's result schema to that native grader,
with bounded threaded concurrency and resumable CSV output.  It does not alter
ROMA or the benchmark evaluator.
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
NATIVE_EVALS = WORKSPACE_ROOT / "official-roma-v2" / "evals"
NATIVE_GRADER_PATH = NATIVE_EVALS / "grade_answers_simple.py"
REQUEST_INTERVAL = float(os.environ.get("ROMA_SCORER_REQUEST_INTERVAL", "2.0"))
_REQUEST_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0

sys.path.insert(0, str(NATIVE_EVALS))
import grade_answers_simple as native_grader  # noqa: E402


OUTPUT_FIELDS = [
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
    "official_grade",
    "official_score",
    "scorer_method",
    "scorer_model",
    "scorer_base_url",
    "scorer_path",
    "scorer_fast_path",
    "scorer_error",
]


def read_rows(paths: list[Path]) -> list[dict[str, Any]]:
    """Read completed, unscored rows and deduplicate by the question text."""
    goal_to_index = official_goal_indices()
    rows_by_goal: dict[str, dict[str, Any]] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="", errors="replace") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") != "COMPLETED":
                    continue
                if row.get("official_grade") or row.get("official_score"):
                    continue
                goal = str(row.get("goal") or row.get("question") or "").strip()
                if not goal:
                    continue
                normalized_goal = normalize_goal(goal)
                if goal_to_index and normalized_goal not in goal_to_index:
                    # Do not score rows that cannot be aligned to the official
                    # SEAL-0 question set.
                    continue
                # Later retry files are more authoritative when the same goal
                # occurs in more than one raw result file.
                row["goal"] = goal
                if normalized_goal in goal_to_index:
                    row["index"] = str(goal_to_index[normalized_goal])
                rows_by_goal[goal] = row
    return list(rows_by_goal.values())


def normalize_goal(value: str) -> str:
    return " ".join(str(value).split())


def official_goal_indices() -> dict[str, int]:
    """Map official seed-0 shuffled SEAL-0 goals to their full indices."""
    project_root = WORKSPACE_ROOT / "official-roma_modified_20260914"
    parquet = project_root / "data" / "sealqa" / "seal-0.parquet"
    if not parquet.exists():
        return {}
    sys.path.insert(0, str(project_root))
    from prompt_optimization.dataset_loaders import load_seal0_dataset

    examples = load_seal0_dataset(seed=0, no_split=True, parquet_path=str(parquet))
    return {normalize_goal(str(example.goal)): index for index, example in enumerate(examples)}


def numeric_fast_path(ground_truth: str, predicted: str) -> int | None:
    """Use the exact numeric shortcut from the official grader."""
    gt_num = native_grader.parse_number(str(ground_truth))
    pred_num = native_grader.parse_number(str(predicted))
    if gt_num is None or pred_num is None:
        return None
    if gt_num == 0 and pred_num == 0:
        return 1
    if gt_num != 0 and abs((pred_num - gt_num) / gt_num) <= 0.01:
        return 1
    return None


def wait_for_request_slot() -> None:
    """Smooth upstream traffic while retaining the requested worker pool."""
    global _NEXT_REQUEST_AT
    with _REQUEST_LOCK:
        now = time.monotonic()
        scheduled = max(now, _NEXT_REQUEST_AT)
        _NEXT_REQUEST_AT = scheduled + max(0.0, REQUEST_INTERVAL)
    if scheduled > now:
        time.sleep(scheduled - now)


def score_one(row: dict[str, Any], model: str) -> dict[str, Any]:
    question = str(row.get("goal") or "")
    ground_truth = str(row.get("ground_truth") or "")
    predicted = str(row.get("predicted_answer") or "")
    fast_score = numeric_fast_path(ground_truth, predicted)
    error = ""
    if fast_score is not None:
        score = fast_score
        fast_path = "numeric_tolerance"
    else:
        score = None
        fast_path = "llm_native"
        for attempt in range(6):
            try:
                wait_for_request_slot()
                # This is the official grader's own LLM function and prompt.
                score = int(native_grader.grade_answer_with_llm(
                    question,
                    ground_truth,
                    predicted,
                    model=model,
                ))
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if attempt < 5:
                    time.sleep(min(45.0, 2.0 ** attempt + random.random()))
        if score is None:
            # A judge transport failure is not an incorrect answer.
            fast_path = "llm_error"

    result = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    result.update(
        {
            "official_grade": (
                "SCORER_ERROR" if score is None else "CORRECT" if score else "INCORRECT"
            ),
            "official_score": "" if score is None else score,
            "scorer_method": "SEAL-0 native evals/grade_answers_simple.py",
            "scorer_model": model,
            "scorer_base_url": os.environ.get("OPENAI_BASE_URL", ""),
            "scorer_path": str(NATIVE_GRADER_PATH),
            "scorer_fast_path": fast_path,
            "scorer_error": error,
        }
    )
    return result


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda item: str(item.get("goal", ""))))
    os.replace(temp, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="Raw ROMA result CSV; repeatable")
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=15)
    parser.add_argument("--model", default="openai/qwen3.7-flash")
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("--workers must be positive")
    missing = [path for path in args.input if not Path(path).exists()]
    if missing:
        parser.error(f"input CSV not found: {missing}")
    return args


def main() -> None:
    args = parse_args()
    inputs = [Path(path).resolve() for path in args.input]
    rows = read_rows(inputs)
    print(f"Unscored completed rows: {len(rows)}", flush=True)
    scored: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(score_one, row, args.model) for row in rows]
        for number, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            scored.append(result)
            print(
                f"scored {number}/{len(futures)} index={result.get('index')} "
                f"grade={result.get('official_grade')} path={result.get('scorer_fast_path')}",
                flush=True,
            )
    write_rows(Path(args.output).resolve(), scored)
    correct = sum(row.get("official_score") == 1 for row in scored)
    print(f"Saved {len(scored)} rows to {Path(args.output).resolve()}", flush=True)
    print(f"Score: {correct}/{len(scored)}", flush=True)


if __name__ == "__main__":
    main()
