"""Run the existing SealQA grader against one immutable paper-run archive.

The scoring prompt and parser are imported from the already-used regrade
harness; this adapter only adds raw input/output provenance and derived files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_GRADER = Path("external_archive/2026-09-16/wo/work/run_sealqa_official_regrade.py")


def load_grader(path: Path):
    spec = importlib.util.spec_from_file_location("existing_sealqa_regrade", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load grader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--grader-script", type=Path, default=Path(os.environ.get("ROMA_SEALQA_GRADER_SCRIPT", str(DEFAULT_GRADER))))
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    if not (run_dir / "manifest.json").exists():
        raise SystemExit(f"paper run manifest not found: {run_dir / 'manifest.json'}")
    if args.workers <= 0:
        raise SystemExit("--workers must be positive")
    grader = load_grader(args.grader_script.resolve())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    source_rows = read_jsonl(run_dir / "outputs.jsonl")
    rows = []
    for item in source_rows:
        if item.get("status") != "COMPLETED":
            continue
        row = dict(item.get("raw_result_row") or {})
        row.update({
            "index": item.get("question_index"),
            "condition": manifest.get("condition"),
            "goal": item.get("goal") or row.get("goal", ""),
            "ground_truth": item.get("ground_truth") or row.get("ground_truth", ""),
            "predicted_answer": item.get("predicted_answer") if item.get("predicted_answer") is not None else row.get("predicted_answer", ""),
            "paper_run_id": manifest.get("run_id"),
        })
        if row["goal"] and row["ground_truth"]:
            rows.append(row)
    grader_root = run_dir / "grader"
    grader_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    grader_dir = grader_root / f"regrade_{stamp}"
    suffix = 1
    while grader_dir.exists():
        grader_dir = grader_root / f"regrade_{stamp}_{suffix:02d}"
        suffix += 1
    grader_dir.mkdir(parents=True, exist_ok=False)
    prompt_hash = hashlib.sha256(grader.OFFICIAL_TEMPLATE.encode("utf-8")).hexdigest()
    (grader_dir / "prompt.txt").write_text(grader.OFFICIAL_TEMPLATE, encoding="utf-8")
    write_jsonl(
        grader_dir / "inputs.jsonl",
        [{"index": row.get("index"), "condition": row.get("condition"), "prompt": grader.prompt_for(row)} for row in rows],
    )
    api_key = os.environ.get("QWEN_API_KEY") or os.environ.get("JUDGE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing QWEN_API_KEY/JUDGE_API_KEY/OPENAI_API_KEY")
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    base_url = os.environ.get("QWEN_BASE_URL") or os.environ.get("JUDGE_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    scored: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(grader.score_one, client, row, args.retries) for row in rows]
        for future in as_completed(futures):
            scored.append(future.result())
    scored.sort(key=lambda row: int(row.get("index") or 0))
    raw_results = []
    for row in scored:
        raw_results.append({
            "index": row.get("index"),
            "condition": row.get("condition"),
            "prompt": grader.prompt_for(row),
            "grader_result": row,
        })
    write_jsonl(grader_dir / "raw_results.jsonl", raw_results)
    fields = sorted({key for row in scored for key in row})
    with (grader_dir / "scores.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scored)
    metrics_path = run_dir / "metrics.csv"
    if metrics_path.exists():
        with metrics_path.open(encoding="utf-8", newline="") as handle:
            metric_rows = list(csv.DictReader(handle))
        by_index = {
            str(row.get("index") if row.get("index") is not None else row.get("question_index")): row
            for row in scored
        }
        for metric in metric_rows:
            score = by_index.get(str(metric.get("question_index")))
            if score:
                metric["grader_label"] = score.get("official_sealqa_label", "")
                metric["grader_score"] = score.get("official_sealqa_score", "")
                metric["grader_model"] = score.get("official_sealqa_model", "")
        fields = sorted({key for row in metric_rows for key in row})
        with (run_dir / "metrics_with_grader.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(metric_rows)
    grader_manifest = {
        "schema_version": 1,
        "run_id": manifest.get("run_id"),
        "condition": manifest.get("condition"),
        "grader_script": str(args.grader_script.resolve()),
        "grader_script_sha256": hashlib.sha256(args.grader_script.read_bytes()).hexdigest(),
        "model": grader.MODEL,
        "temperature": grader.TEMPERATURE,
        "max_tokens": grader.MAX_TOKENS,
        "workers": args.workers,
        "retries": args.retries,
        "template_sha256": prompt_hash,
        "rows": len(scored),
        "correct": sum(row.get("official_sealqa_score") == 1 for row in scored),
        "files": ["prompt.txt", "inputs.jsonl", "raw_results.jsonl", "scores.csv"],
    }
    (grader_dir / "manifest.json").write_text(json.dumps(grader_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_manifest_path = run_dir / "manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    run_manifest["grader"] = grader_manifest
    run_manifest.setdefault("artifacts", {})["grader"] = str(grader_dir.relative_to(run_dir))
    run_manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum_path = run_dir / "checksums.sha256"
    checksum_lines = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path != checksum_path:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checksum_lines.append(f"{digest}  {path.relative_to(run_dir)}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(json.dumps(grader_manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
