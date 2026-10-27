"""Offline, lossless record formatting for the pinned community MAB inputs.

No judge, API client, scoring rule, response parser, repair, or retry is provided.
Native records are not deduplicated, filtered, inferred, reordered, or truncated.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import gzip
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "work/MARBLE-community"
VERIFICATION = ROOT / "outputs/MultiAgentBench_verification/community_pinned_2efd80f/community_file_hashes.json"
INDEX = Path("archive-ref-0bc1de2547a3cf1d")
VERSION = "mab-native-format-only-2-community-2efd80f"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def native_preflight() -> dict:
    baseline = json.loads(VERIFICATION.read_text())
    relevant = [r for r in baseline["files"] if r["path"] in {
        "marble/evaluator/evaluator.py", "marble/evaluator/evaluator_prompts.json",
        "marble/llms/model_prompting.py", "marble/llms/error_handler.py"}]
    hashes = [{"path": r["path"], "expected_sha256": r["sha256"],
               "actual_sha256": sha((REPO / r["path"]).read_bytes())} for r in relevant]
    if any(r["expected_sha256"] != r["actual_sha256"] for r in hashes):
        raise RuntimeError("Pinned community source changed; refuse to prepare inputs")
    errors = []
    source = REPO / "marble/evaluator/evaluator.py"
    try:
        ast.parse(source.read_text(), filename=str(source))
    except SyntaxError as exc:
        errors.append({"stage": "official_module_syntax", "type": "SyntaxError",
                       "line": exc.lineno, "message": exc.msg})
    prompts = json.loads((REPO / "marble/evaluator/evaluator_prompts.json").read_text())
    args = {"Communication": {"task": "TASK", "communications": "COMMUNICATIONS"},
            "Planning": {"summary": "SUMMARY", "agent_profiles": "PROFILES",
                         "agent_tasks": "TASKS", "results": "RESULTS"}}
    for name, fields in args.items():
        try:
            # Exactly the formatting operation used by the official functions.
            prompts["Graph"][name]["prompt"].format(**fields)
        except (KeyError, ValueError) as exc:
            errors.append({"stage": "official_template_format", "template": name,
                           "type": type(exc).__name__, "message": str(exc)})
    return {"scorer_repository": baseline["repository"], "scorer_commit": baseline["commit"],
            "official_reference_commit": "8d60fa17b5596b44458a52d4296061b9fc13d6f2",
            "source_hashes": hashes, "verification_scope": "Syntax and template formatting only",
            "runtime_import_checked": False,
            "native_execution_ready": not errors, "errors": errors,
            "workarounds_applied": [], "api_calls": 0}


def read_jsonl(path: Path) -> tuple[bytes, list[dict]]:
    data = path.read_bytes()
    # Iterate physical file lines: U+2028 within strings is not a record separator.
    with path.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    return data, rows


def block(label: str, data: bytes) -> str:
    # Original complete JSONL bytes decoded as UTF-8; no excerpts or deduplication.
    return f"[SOURCE: {label}]\n" + data.decode("utf-8")


def prepare_one(entry: dict, output: Path, preflight: dict) -> dict:
    uid = f"q{entry['index']:04d}_{entry['cohort']}_{entry['round']}_{entry['arm']}"
    folder = output / uid
    if folder.exists():
        raise FileExistsError(f"Refuse to overwrite existing inputs: {folder}")
    trace = Path(entry["trace_directory"])
    filenames = ["raw_tree_events.jsonl", "raw_llm_events.jsonl", "raw_tool_events.jsonl", "run_events.jsonl"]
    records = {name: read_jsonl(trace / name) for name in filenames}
    # Last stored checkpoint is a native state snapshot, not a reconstructed graph.
    checkpoints = sorted((trace / "checkpoints").glob("*.json.gz"))
    checkpoint = checkpoints[-1] if checkpoints else None
    snapshot = json.loads(gzip.decompress(checkpoint.read_bytes())) if checkpoint else None
    graph = snapshot.get("root_dag") if snapshot else None
    graph_text = (json.dumps(graph, ensure_ascii=False, indent=2) if graph is not None
                  else "NOT_RECORDED")
    tree = block("raw_tree_events.jsonl", records["raw_tree_events.jsonl"][0])
    graph_block = "[SOURCE: latest stored checkpoint root_dag]\n" + graph_text
    structure = tree + "\n" + graph_block
    interactions = block("raw_llm_events.jsonl", records["raw_llm_events.jsonl"][0])
    tools = block("raw_tool_events.jsonl", records["raw_tool_events.jsonl"][0])
    run = block("run_events.jsonl", records["run_events.jsonl"][0])
    profiles = []
    for line, row in enumerate(records["raw_llm_events.jsonl"][1], 1):
        for position, message in enumerate((row.get("request") or {}).get("messages") or []):
            if message.get("role") == "system":
                profiles.append({"source_file": "raw_llm_events.jsonl", "line": line,
                                 "message_position": position, "message": message})
    # These are official function argument names, not a replacement judge prompt.
    inputs = {
        "planning": {
            "summary": entry["question"] + "\n\n" + run,
            "agent_profiles": json.dumps(profiles, ensure_ascii=False, indent=2),
            "agent_tasks": structure,
            "results": interactions + "\n" + tools,
        },
        "communication": {
            "task": entry["question"] + "\n\n" + structure,
            "communications": interactions + "\n" + tools,
        },
    }
    folder.mkdir(parents=True)
    raw = folder / "source_records"
    raw.mkdir()
    hashes = {}
    for name, (data, _) in records.items():
        (raw / name).write_bytes(data)
        hashes[str(trace / name)] = sha(data)
    if checkpoint:
        shutil.copyfile(checkpoint, raw / checkpoint.name)
        hashes[str(checkpoint)] = sha(checkpoint.read_bytes())
    data = (json.dumps(inputs, ensure_ascii=False, indent=2) + "\n").encode()
    (folder / "official_function_inputs.json.gz").write_bytes(gzip.compress(data, mtime=0))
    # Readable full field files; none contain a model-written summary.
    for kind, values in inputs.items():
        for field, text in values.items():
            (folder / f"{kind}.{field}.txt").write_text(text, encoding="utf-8")
    manifest = {
        "format_version": VERSION, "uid": uid, "question_index": entry["index"],
        "arm": entry["arm"], "repeat": entry["round"], "cohort": entry["cohort"],
        "source_trace": str(trace), "source_hashes": hashes,
        "source_record_counts": {k: len(v[1]) for k, v in records.items()},
        "system_message_count": len(profiles), "input_sha256": sha(data),
        "field_characters": {k: {f: len(t) for f, t in v.items()} for k, v in inputs.items()},
        "latest_checkpoint": str(checkpoint) if checkpoint else None,
        "mapping": {
            "summary": "Original root question plus native run records; no new summary",
            "agent_profiles": "Every original system message, including repetitions and condition-specific content",
            "agent_tasks": "Original tree event ledger and native latest root_dag; no generated edges",
            "results": "All original LLM request/response records and all original tool records",
            "task": "Original question plus the same recorded structure",
            "communications": "Complete native interaction/tool logs as context; no invented sender, recipient or ResultDelivery action",
        },
        "limitations": ["Raw LLM records without a task_id remain unbound; no identity is inferred",
                        "The interaction ledger includes intra-agent messages and tool observations; it is not relabeled as exclusively inter-agent communication",
                        "Whole-run formatting uses the existing repository templates, not the different paper-appendix templates"],
        "record_handling": {"deduplicated": 0, "filtered": 0, "truncated": 0,
                            "inferred_task_bindings": 0, "reordered": False},
        "judge_configuration": {"model_requested_by_user": "qwen3.7-flash",
                                "official_max_token_num": 512, "official_temperature": 0.0,
                                "native_parsing_and_failure_behavior": "unchanged; no substitute implemented"},
        "native_preflight": preflight, "scores": None, "api_calls": 0,
    }
    write_json(folder / "manifest.json", manifest)
    write_json(folder / "checksums.json", {str(p.relative_to(folder)): sha(p.read_bytes())
               for p in folder.rglob("*") if p.is_file() and p.name != "checksums.json"})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--question", type=int, required=True)
    parser.add_argument("--repeat", choices=["H", "N", "R1", "R2"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [r for r in json.loads(args.index.read_text())["attempts"]
            if r["index"] == args.question and r["round"] == args.repeat]
    if len(rows) != 2 or {r["arm"] for r in rows} != {"BASE", "V2"}:
        raise RuntimeError("Expected exactly one recorded BASE/V2 pair; no replacements")
    args.output.mkdir(parents=True, exist_ok=True)
    preflight = native_preflight()
    write_json(args.output / "native_preflight.json", preflight)
    manifests = [prepare_one(r, args.output, preflight) for r in rows]
    write_json(args.output / "preparation_manifest.json", {
        "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "format_version": VERSION, "formatter_sha256": sha(Path(__file__).read_bytes()),
        "source_index": str(args.index), "source_index_sha256": sha(args.index.read_bytes()),
        "scorer_repository": preflight["scorer_repository"],
        "scorer_commit": preflight["scorer_commit"],
        "official_reference_commit": preflight["official_reference_commit"],
        "selected_uids": [m["uid"] for m in manifests],
        "api_calls": 0, "scoring_started": False,
    })
    print(json.dumps({"prepared": [m["uid"] for m in manifests], "api_calls": 0,
                      "native_execution_ready": preflight["native_execution_ready"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
