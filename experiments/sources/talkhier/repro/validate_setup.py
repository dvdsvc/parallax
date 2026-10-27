"""Validate frozen bench data and unmodified native agent paths without API calls."""
import argparse
import configparser
import contextlib
import csv
from datetime import datetime, timezone
import io
import json
import os
import platform
import signal
import socket
import subprocess
import sys
from types import SimpleNamespace
from typing import get_args

from common import DOMAINS, ROOT, UPSTREAM, MANIFEST, digest, load_frozen, native_dataset_loader, workspace_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="Write the initial validation into the tracked setup record")
    parser.add_argument("--domain", choices=DOMAINS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    workspace_environment(offline=True)
    if args.domain is None:
        # The native CLI runs one domain per process. Its global color palette is
        # finite, so validating all domains in one interpreter would add a new mode.
        output = ROOT / ".local" / "validation"
        output.mkdir(parents=True, exist_ok=True)
        combined = None
        for domain in DOMAINS:
            child = subprocess.run([sys.executable, str(ROOT / "repro" / "validate_setup.py"), "--domain", domain],
                                   cwd=ROOT, text=True, capture_output=True, timeout=90, check=True)
            print(child.stdout, end="", flush=True)
            item = json.loads((output / f"{domain}_report.json").read_text())
            if combined is None:
                combined = {**item, "domains": {}}
            combined["domains"].update(item["domains"])
        combined["validated_at_utc"] = datetime.now(timezone.utc).isoformat()
        combined["one_native_domain_per_process"] = True
        report_path = ROOT / "repro" / "setup_validation.json" if args.record else output / "report.json"
        report_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n")
        print(f"Offline validation: {report_path}", flush=True)
        return
    cli = subprocess.run([sys.executable, "experiments.py", "--help"], cwd=ROOT / "src",
                         text=True, capture_output=True, timeout=45, check=True)
    unchanged = subprocess.run(["git", "diff", "--exit-code", UPSTREAM, "--", "src", "template", "requirements.txt"],
                               cwd=ROOT, capture_output=True).returncode == 0
    if not unchanged:
        # Only the explicitly recorded provider-compatibility changes are
        # permitted; every other original source/template/requirement stays pinned.
        from org_v2.adapter import verify_artifacts
        _, compatibility = verify_artifacts(args.domain)
        allowed = set(compatibility.get('provider_compatibility_changes', {}))
        changed = subprocess.check_output(['git', 'diff', '--name-only', UPSTREAM, '--',
            'src', 'template', 'requirements.txt'], cwd=ROOT, text=True).splitlines()
        if not set(changed) <= allowed:
            raise SystemExit('Unexpected native changes outside the recorded provider compatibility files')
    os.chdir(ROOT / "src")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    import datasets
    import experiments
    from prompts.mmlu import getPrompts
    from multiagent.tools import CounterexampleVerifier, OutputTool, TruthTableGenerator
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import RunnableLambda

    class OfflineAbort(BaseException):
        pass

    def forbidden_network(*args, **kwargs):
        raise OfflineAbort("Network is forbidden during offline validation")

    def timeout(*args):
        raise OfflineAbort("Native fixture exceeded its 30-second offline time limit")

    socket.socket.connect = forbidden_network
    socket.create_connection = forbidden_network
    signal.signal(signal.SIGALRM, timeout)
    output = ROOT / ".local" / "validation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "native_help.txt").write_text(cli.stdout)
    report = {"validated_at_utc": datetime.now(timezone.utc).isoformat(),
              "upstream_agent_commit": UPSTREAM, "dataset_manifest_sha256": digest(MANIFEST),
              "python": platform.python_version(), "system": platform.system(), "machine": platform.machine(),
              "native_source_unchanged": unchanged, "native_cli_help": True,
              "agent_architecture_unchanged": True,
              "network_disabled_for_validation": True, "paid_model_calls": 0, "domains": {}}
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "template" / "config.ini")
    cfg["LLM"] = {"max_attempts": "100"}
    original_factory = experiments.LLM
    original_loader = datasets.load_dataset
    fixture_payload = {"answer": {"choice": 0, "steps": "Offline fixture; not a model answer"}}

    for domain in (args.domain,):
        dataset = load_frozen(domain)
        # All rows and gold labels must be equal between readable JSONL and native Arrow exports.
        for split, rows in dataset.items():
            exported = [json.loads(line) for line in (ROOT / "data" / "mmlu" / domain / f"{split}.jsonl").read_text().splitlines()]
            assert exported == list(rows), (domain, split)
        calls = []
        counters = {"main": 0, "evaluation": 0}

        class LocalModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "talkhier-offline-setup-fixture"

            def bind_tools(self, tools, **kwargs):
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                calls.append({"kind": "leaf", "messages": messages})
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=json.dumps(fixture_payload)))])

            def with_structured_output(self, schema, **kwargs):
                assert isinstance(schema, dict) and kwargs == {'method': 'json_schema', 'strict': True}
                def respond(value):
                    messages = value.to_messages()
                    if "next" not in schema['properties']:
                        calls.append({"kind": "leaf_format", "messages": messages})
                        return {'intermediate_output': json.dumps(fixture_payload)}
                    options = schema['properties']['next']['enum']
                    key = "main" if "FINISH" in options else "evaluation"
                    order = ["Answer Generator", "Evaluator Supervisor", "Revisor", "FINISH"] if key == "main" \
                        else [x for x in options if x != "Default Supervisor"] + ["Default Supervisor"]
                    next_role = order[counters[key]]
                    counters[key] += 1
                    calls.append({"kind": key, "messages": messages, "next": next_role})
                    return dict(thoughts="Offline fixture routing", next=next_role,
                                  messages="Perform the assigned local task or report its result.",
                                  intermediate_output=json.dumps(fixture_payload),
                                  background="Solve the provided multiple-choice task.")
                return RunnableLambda(respond)

        experiments.LLM = lambda config: SimpleNamespace(llm=LocalModel())
        datasets.load_dataset = native_dataset_loader(original_loader, domain, dataset)
        log = io.StringIO()
        csv_path = output / f"{domain}.csv"
        if csv_path.exists():
            csv_path.unlink()  # Only this script's disposable fixture output.
        try:
            signal.alarm(30)
            with contextlib.redirect_stdout(log):
                experiments.runSingleMMLU(domain, cfg, 0, results=experiments.ResultManager(str(csv_path)))
        finally:
            signal.alarm(0)
            experiments.LLM = original_factory
            datasets.load_dataset = original_loader
        (output / f"{domain}.log").write_text(log.getvalue())
        assert "Retrying..." not in log.getvalue(), "Native failure retry occurred during the fixture"
        result = list(csv.DictReader(csv_path.open()))
        assert len(result) == 1 and int(result[0]["Answer"]) == 0
        assert int(result[0]["Correct Answer"]) == dataset["test"][0]["answer"]
        assert int(result[0]["Pre-Revision"]) == 0
        members = [k for k, v in getPrompts(domain, dataset["test"][0])["team"]["Evaluator"].items() if isinstance(v, dict)]
        visited = {c["next"] for c in calls if "next" in c}
        assert {"Answer Generator", "Evaluator Supervisor", "Revisor", "FINISH", "Default Supervisor", *members} <= visited
        eval_call = next(c for c in calls if c["kind"] == "evaluation")
        prompt_text = "\n".join(str(m.content) for m in eval_call["messages"])
        assert all(m in prompt_text for m in members) and "Default Supervisor" in prompt_text
        report["domains"][domain] = {"splits": {k: len(v) for k, v in dataset.items()},
                                     "all_exported_rows_equal": True, "native_single_question_pipeline": True,
                                     "native_gold_label_preserved": True,
                                     "all_members_routed": True, "native_failure_retries": 0,
                                     "evaluation_members": members, "local_supervisor_interface_visible": True,
                                     "fixture_model_method_calls": len(calls)}
        print(f"{domain}: frozen rows + native agent/bench pipeline OK", flush=True)
    with contextlib.redirect_stdout(io.StringIO()):
        assert OutputTool().invoke({"in_str": "Offline output-tool check"}) == ""
        truth = TruthTableGenerator().invoke({"in_str": "['And(A, B)', 'Not(And(A, B))']"})
        assert "Contradictory" in truth and "Error" not in truth
        counter = CounterexampleVerifier().invoke({"in_str": "{'premises': ['A'], 'conclusion': 'B', 'truth_values': [{'A': 'True', 'B': 'False'}]}"})
        assert "Valid counterexample" in counter and "Error" not in counter
    report["native_tools"] = {"output_tool": True, "truthtable_generator": True, "counterexample_verifier": True}
    report["no_local_model_stack_imported"] = "torch" not in sys.modules and "transformers" not in sys.modules
    report["limitations"] = ["Deterministic local fixture; no model-quality or token-cost estimate",
                             "Provider credentials and real API calls have not been tested",
                             "Apple Silicon tested; Intel Mac has not been tested",
                             "Original prompt inconsistencies and retry behavior are retained unchanged"]
    report_path = output / f"{args.domain}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Offline validation: {report_path}", flush=True)


if __name__ == "__main__":
    main()
