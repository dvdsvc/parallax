"""Run unmodified native MMLU functions against the verified local dataset snapshot."""
import argparse
from contextlib import nullcontext, redirect_stderr, redirect_stdout
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import shutil
import sys
import time

from common import DOMAINS, ROOT, UPSTREAM, digest, load_frozen, native_dataset_loader, MANIFEST, workspace_environment
from org_v2.adapter import SCOPES, install, verify_artifacts
from direct_model import connection
from local_trace import LocalTrace
from langchain_core.runnables import RunnableLambda
from run_archive import RunArchive, add_arguments, write
from benchmark_data import benchmark_manifest, load_benchmark, verify_subset


class ConsoleTee:
    """Keep the author's console output verbatim alongside the local trace."""
    def __init__(self, console, file):
        self.console, self.file = console, file

    def write(self, text):
        self.file.write(text)
        return self.console.write(text)

    def flush(self):
        self.file.flush()
        self.console.flush()

    def isatty(self):
        return self.console.isatty()


def result_metrics(path):
    """Index native integer-choice equality; incomplete placeholders stay missing."""
    completed, correct, incomplete = 0, 0, 0
    if path.is_file():
        with path.open() as stream:
            for row in csv.DictReader(stream):
                try:
                    answer, gold = int(row['Answer']), int(row['Correct Answer'])
                except (ValueError, KeyError):
                    incomplete += 1
                    continue
                completed += 1
                correct += answer == gold
    return {'questions_completed': completed, 'questions_incomplete_rows': incomplete,
            'questions_correct': correct, 'native_accuracy': correct / completed if completed else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=DOMAINS, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--problem-id", type=int, default=0, help="Native test-split row index; default 0")
    group.add_argument("--all", action="store_true", help="Run the complete native test split")
    parser.add_argument("--config", default=str(ROOT / "config" / "config.ini"))
    parser.add_argument("--llm-config", default=str(ROOT / "config" / "config_llm.ini"))
    parser.add_argument("--timeout-seconds", type=int, default=900, help="External wall-time limit; interrupts even the native retry loop")
    parser.add_argument("--condition", choices=("BASE", "V2"), default="BASE")
    parser.add_argument("--scope", choices=SCOPES, default="all_roles", help="V2 target roles; main condition is all_roles")
    parser.add_argument("--provider", choices=("openai",), default="openai")
    parser.add_argument("--credential-file", default="external_archive/env/glm_api.env")
    parser.add_argument("--model", default="qwen3.7-flash")
    parser.add_argument("--base-url", help="Optional direct API endpoint override")
    parser.add_argument("--gateway-url", help="Optional local LiteLLM /v1 endpoint; 429 waits stay inside one logical model call")
    parser.add_argument("--gateway-wait-seconds", type=float, default=900)
    parser.add_argument("--request-timeout", type=float, default=900)
    parser.add_argument("--max-retries", type=int, default=2, help="OpenAI SDK retries; callbacks count logical model calls")
    parser.add_argument("--max-completion-tokens", type=int, default=16384, help="Per-call combined thinking and final-response token limit")
    parser.add_argument("--thinking-budget", type=int, default=8192, help="Per-call thinking token cap; thinking stays enabled")
    parser.add_argument("--output-dir", help="Optional new or empty local result directory")
    parser.add_argument("--subset", help="Frozen sample directory; require this original problem ID to belong to it")
    parser.add_argument("--preflight-only", action="store_true", help="Verify frozen inputs and intervention without credentials or model calls")
    add_arguments(parser)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.request_timeout <= 0 or args.max_retries < 0 or args.max_completion_tokens <= 0 or args.thinking_budget <= 0:
        parser.error("Timeouts/token limit must be positive and --max-retries nonnegative")
    if args.thinking_budget >= args.max_completion_tokens:
        parser.error("--thinking-budget must be smaller than --max-completion-tokens to leave room for the final response")
    if args.gateway_url:
        from urllib.parse import urlsplit
        if urlsplit(args.gateway_url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
            parser.error('--gateway-url must be local; provider credentials must not be sent to another host')
        if args.base_url or args.model != 'qwen3.7-flash' or args.gateway_wait_seconds <= 0:
            parser.error('Gateway mode requires qwen3.7-flash, a positive wait limit, and no --base-url override')
    workspace_environment(offline=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = Path(args.output_dir).resolve() if args.output_dir else ROOT / ".local" / "runs" / f"{stamp}_{args.mode}_{args.condition}_{args.scope}"
    archive = RunArchive(run_dir, kind="preflight" if args.preflight_only else "benchmark",
        parameters=vars(args), command=[sys.executable, *sys.argv], mlflow_python=args.mlflow_python,
        tracking_uri=args.mlflow_tracking_uri, experiment=args.mlflow_experiment, parent_run_id=args.parent_run_id)
    record = {**archive.identity, "status": "starting", "mode": args.mode, "condition": args.condition,
              "scope": args.scope, "timeout_seconds": args.timeout_seconds, "upstream_agent_commit": UPSTREAM}
    record_path = run_dir / "manifest.json"
    write(record_path, record)
    trace = None
    gateway_client = None
    original_loader = original_single = None
    experiments = datasets = None
    failure = None
    stage = "preflight"
    started = time.monotonic()
    # Native atexit checkpoint cleanup may rewrite its CSV. Keep that working
    # file outside the sealed archive and preserve the final observed bytes.
    native_csv = ROOT / ".local" / "native_work" / archive.uid / "native_results.csv"
    class NativeTimeout(BaseException):
        pass
    def deadline(*_):
        raise NativeTimeout("External time limit reached; native source is unchanged")
    def interrupted(*_):
        raise KeyboardInterrupt("External run interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        dataset = load_benchmark(args.mode, args.subset)
        data_manifest = benchmark_manifest(args.subset)
        if not args.all and not 0 <= args.problem_id < len(dataset["test"]):
            raise ValueError("Problem ID is outside the frozen test split")
        _, org_manifest = verify_artifacts(args.mode)
        ids = list(range(len(dataset["test"]))) if args.all else [args.problem_id]
        subset_manifest = None
        if args.subset:
            subset_manifest, subset_questions = verify_subset(args.subset)
            if args.all or subset_manifest['mode'] != args.mode or args.problem_id not in [q['problem_id'] for q in subset_questions]:
                raise ValueError('Worker must run one original question index from the specified frozen sample')
            shutil.copytree(Path(args.subset).resolve(), run_dir / 'startup' / 'subset')
        os.chdir(ROOT / "src")
        sys.path.insert(0, str(ROOT / "src"))
        sys.path.insert(0, str(ROOT))
        import datasets
        import experiments
        cfg = experiments.loadConfig(args.config, args.llm_config)
        settings = connection(args.credential_file, args.gateway_url or args.base_url) if args.provider == "openai" and not args.preflight_only else None
        # The native LLM class owns ChatOpenAI construction. Only populate its
        # existing configuration; no in-memory replacement of experiments.LLM.
        cfg.set("LLM", "model", args.model)
        cfg.set("LLM", "request_timeout", str(args.request_timeout))
        cfg.set("LLM", "max_retries", str(0 if args.gateway_url else args.max_retries))
        cfg.set("LLM", "max_completion_tokens", str(args.max_completion_tokens))
        cfg.set("LLM", "enable_thinking", "true")
        cfg.set("LLM", "thinking_budget", str(args.thinking_budget))
        if settings:
            cfg.set("KEYS", "OPENAI_API_KEY", settings["api_key"])
            cfg.set("KEYS", "OPENAI_ENDPOINT", settings["base_url"])
        effective = {"provider": args.provider, "model": args.model if args.provider == "openai" else cfg.get("LLM", "deployment_name"),
            "base_url": settings["base_url"] if settings else (args.gateway_url or args.base_url) if args.provider == "openai" else None,
            "azure_endpoint": cfg.get("KEYS", "OPENAI_ENDPOINT", fallback=None) if args.provider == "native-azure" else None,
            "azure_api_version": cfg.get("LLM", "openai_api_version", fallback=None) if args.provider == "native-azure" else None,
            "temperature": cfg.getfloat("LLM", "temperature"), "recursion_limit": cfg.getint("LLM", "max_attempts"),
            "enable_thinking": True, "thinking_budget": args.thinking_budget, "structured_output_method": "json_schema",
            "structured_output_schema_type": "JSON Schema dictionary", "provider_schema_strict": True,
            "response_mapping": "dict_to_SimpleNamespace", "pydantic_response_validation": False,
            "max_completion_tokens": args.max_completion_tokens, "output_limit_scope": "thinking_plus_final_response",
            "request_timeout_seconds": args.request_timeout if args.provider == "openai" else None,
            "sdk_max_retries": (0 if args.gateway_url else args.max_retries) if args.provider == "openai" else "native_client_default",
            "external_timeout_seconds": args.timeout_seconds, "condition": args.condition, "scope": args.scope,
            "organization_prompt_sha256": org_manifest["artifact_files_sha256"][f"global_organizational_architecture_v2_{args.mode}.txt"],
            "organization_awareness_v2": args.condition == "V2", "preflight_only": args.preflight_only,
            "model_connection_resolved": not args.preflight_only, "max_tokens": None, "seed": None,
            "langsmith_enabled": False, "benchmark_dataset": json.loads(data_manifest.read_text())['dataset']}
        if args.gateway_url:
            quota_path = ROOT / 'repro/gateway/quota.json'
            quota = json.loads(quota_path.read_text())
            effective.update(gateway_url=args.gateway_url, gateway_wait_seconds=args.gateway_wait_seconds,
                gateway_quota=quota, gateway_quota_sha256=digest(quota_path),
                gateway_retry_layer='external HTTP transport only',
                external_wall_timeout_includes_gateway_wait=True, gateway_proxy_workers=1)
        if subset_manifest:
            effective.update(sample_seed=subset_manifest['seed'], sample_size=subset_manifest['sample_size'],
                sample_population_size=subset_manifest['population_size'],
                sample_manifest_sha256=digest(Path(args.subset) / 'manifest.json'),
                sample_questions_sha256=subset_manifest['files_sha256']['questions.jsonl'])
        archive.freeze_inputs(config_paths=(args.config, args.llm_config),
            questions=((i, dict(dataset["test"][i])) for i in ids), effective_configuration=effective, dataset_manifest=data_manifest)
        if args.gateway_url:
            shutil.copytree(ROOT / 'repro/gateway', run_dir / 'startup/gateway', ignore=shutil.ignore_patterns('__pycache__'))
        record.update(problem_ids=ids, dataset_manifest_sha256=digest(data_manifest),
            benchmark_dataset=json.loads(data_manifest.read_text())['dataset'],
            dataset_loader="verified local official snapshot", effective_configuration=effective,
            provider="native multiagent.llm.LLM creates LangChain ChatOpenAI")
        if args.preflight_only:
            record["status"] = "preflight_passed"
        else:
            original_loader = datasets.load_dataset
            datasets.load_dataset = native_dataset_loader(original_loader, args.mode, dataset)
            gateway_context = nullcontext()
            if args.gateway_url:
                import httpx
                from gateway.client import GatewayRetryTransport, model_boundary, trace_handler
                gateway_client = httpx.Client(transport=GatewayRetryTransport(run_dir / 'infrastructure',
                    max_wait_seconds=args.gateway_wait_seconds), timeout=args.request_timeout)
                trace = trace_handler(run_dir)
                gateway_context = model_boundary(gateway_client)
            else:
                trace = LocalTrace(run_dir)
            original_single = experiments.runSingleMMLU
            def single(mode, config, problem_id, results=None):
                runnable = RunnableLambda(lambda _: original_single(mode, config, problem_id, results=results))
                return runnable.invoke({}, config={"callbacks": [trace], "run_name": "TalkHier MMLU question",
                    "metadata": {"domain": mode, "problem_id": problem_id, "condition": args.condition, "scope": args.scope,
                                 "launch_id": archive.uid, "mlflow_run_id": archive.run_id,
                                 **({'official_question_id': dataset['test'][problem_id]['official_question_id']}
                                    if 'official_question_id' in dataset['test'][problem_id] else {})}})
            experiments.runSingleMMLU = single
            native_csv.parent.mkdir(parents=True, exist_ok=True)
            record["native_working_csv"] = str(native_csv)
            # BASE goes straight through the native graph and model, with only
            # inherited recording callbacks. V2 retains its external injection.
            model_record = {"client": "langchain_openai.ChatOpenAI", "factory": "src/multiagent/llm.py",
                "model": args.model, "base_url": settings["base_url"],
                "enable_thinking": True, "thinking_budget": args.thinking_budget, "structured_output_method": "json_schema",
                "provider_schema_strict": True, "pydantic_response_validation": False,
                "max_completion_tokens": args.max_completion_tokens,
                "request_timeout_seconds": args.request_timeout, "sdk_max_retries": 0 if args.gateway_url else args.max_retries,
                "model_factory_replaced_at_runtime": False, "proxy_used": bool(args.gateway_url),
                "http_client_supplied_at_external_boundary": bool(args.gateway_url)}
            org_context = install(args.mode, args.condition, args.scope) if args.condition == "V2" else nullcontext({
                "condition": "BASE", "organization_awareness_v2": False, "scope": args.scope,
                "model_view_wrapper_used": False, "agent_architecture_modified": False})
            with org_context as intervention, gateway_context:
                record["intervention"] = intervention
                record["model_connection"] = model_record
                record["status"] = "running"
                write(record_path, record)
                archive.verify_live_sources()
                archive.index_update(tags={"archive_status": "running"})
                stage = "execution"
                signal.signal(signal.SIGALRM, deadline)
                signal.alarm(args.timeout_seconds)
                with (run_dir / 'native_console.log').open('w') as console:
                    with redirect_stdout(ConsoleTee(sys.stdout, console)), redirect_stderr(ConsoleTee(sys.stderr, console)):
                        if args.all:
                            experiments.runExperimentMMLU(str(native_csv), args.mode, cfg)
                        else:
                            results = experiments.ResultManager(str(native_csv))
                            experiments.runSingleMMLU(args.mode, cfg, args.problem_id, results=results)
            record["status"] = "completed"
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error)}
        if getattr(error, 'failure_domain', None):
            failure.update(failure_domain=error.failure_domain, rate_limit_origin=getattr(error, 'rate_limit_origin', None))
        record["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "timed_out" if isinstance(error, NativeTimeout) else "failed_preflight" if stage == "preflight" else "error"
        record["error"] = failure
        raise
    finally:
        signal.alarm(0)
        if gateway_client is not None:
            gateway_client.close()
        if original_loader is not None:
            datasets.load_dataset = original_loader
        if original_single is not None:
            experiments.runSingleMMLU = original_single
        summary = trace.finalize() if trace else {"model_calls_finished": 0, "model_errors": 0}
        if native_csv.is_file():
            shutil.copyfile(native_csv, run_dir / "native_results.csv")
        record["trace_summary"] = summary
        record["result_summary"] = result_metrics(run_dir / "native_results.csv")
        record["elapsed_seconds"] = time.monotonic() - started
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        record["trace_files_sha256"] = {path.name: digest(path) for path in
            (run_dir / "trace.jsonl", run_dir / "graph_nodes.jsonl", run_dir / "model_calls.jsonl", run_dir / "token_usage.json",
             run_dir / 'infrastructure/gateway_events.jsonl') if path.exists()}
        write(record_path, record)
        metrics = {key: value for key, value in summary.items() if isinstance(value, (int, float)) and not isinstance(value, bool)}
        metrics.update({key: value for key, value in record["result_summary"].items() if value is not None})
        metrics['elapsed_seconds'] = record['elapsed_seconds']
        archive.finalize(record["status"], metrics=metrics, error=failure)
    print(json.dumps({"mode": args.mode, "condition": args.condition, "scope": args.scope, "status": record["status"],
        "model_calls_finished": summary["model_calls_finished"], "mlflow_run_id": archive.run_id, "archive": str(run_dir)}, indent=2))


if __name__ == "__main__":
    main()
