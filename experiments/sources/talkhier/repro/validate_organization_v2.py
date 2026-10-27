"""Check native route semantics and BASE/V2 request isolation without a provider."""
import argparse
import configparser
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from types import SimpleNamespace
from typing import get_args

from common import DOMAINS, ROOT, UPSTREAM, load_frozen, native_dataset_loader, workspace_environment
from org_v2.adapter import MARKER, install, verify_artifacts

SCENARIOS = ("normal", "feedback", "direct_finish", "skip_generator", "skip_revisor", "skip_evaluation",
             "evaluation_early_return", "evaluation_subset", "tool_roundtrip")


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=DOMAINS, help=argparse.SUPPRESS)
    parser.add_argument("--record", action="store_true", help="Freeze a tracked offline validation report")
    args = parser.parse_args()
    output = ROOT / ".local" / "organization_v2"
    output.mkdir(parents=True, exist_ok=True)
    if args.domain is None:
        domains = {}
        for domain in DOMAINS:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--domain", domain],
                                    cwd=ROOT, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError(f"Offline domain validation failed: {domain}\n{result.stderr[-5000:]}")
            print(result.stdout, end="", flush=True)
            domains[domain] = json.loads((output / domain / "report.json").read_text())
        report = {"upstream_commit": UPSTREAM, "domains": domains, "paid_model_calls": 0,
                  "native_source_unchanged": False, "agent_architecture_unchanged": True,
                  "structured_output_method": "json_schema", "pydantic_response_validation": False,
                  "cross_team_routes_checked_in_provider_schema_enum": True, "main_v2_scope": "all_roles",
                  "scenario_count": len(SCENARIOS), "native_fixture_runs": len(DOMAINS) * len(SCENARIOS) * 4,
                  "meaning": "Offline route and intervention validation; not benchmark accuracy, cost, or natural LLM routing"}
        target = ROOT / "repro" / "org_v2" / "validation.json" if args.record else output / "report.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"Verified 5 domains x 9 scenarios x 4 native/condition paths: {target}")
        return

    workspace_environment(offline=True)
    domain = args.domain
    text, manifest = verify_artifacts(domain)
    os.chdir(ROOT / "src")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    import datasets
    import experiments
    from prompts.mmlu import getPrompts
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import RunnableLambda
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from multiagent.agent_team import AgentTeam, ReactAgent
    from pydantic import ValidationError

    class OfflineAbort(BaseException):
        pass

    def abort(*args, **kwargs):
        raise OfflineAbort("Network access or timeout during offline organization validation")

    socket.socket.connect = abort
    socket.create_connection = abort
    signal.signal(signal.SIGALRM, abort)
    dataset = load_frozen(domain)
    original_loader, original_factory = datasets.load_dataset, experiments.LLM
    datasets.load_dataset = native_dataset_loader(original_loader, domain, dataset)
    members = [k for k, v in getPrompts(domain, dataset["test"][0])["team"]["Evaluator"].items() if isinstance(v, dict)]
    role_names = {"Default Supervisor", "Evaluator Supervisor", "Answer Generator", "Revisor", *members}
    config = configparser.ConfigParser()
    config.read(ROOT / "template" / "config.ini")
    config["LLM"] = {"max_attempts": "100"}
    output = output / domain
    output.mkdir(exist_ok=True)
    original_supervisor, original_member = AgentTeam.loadSuperviser, ReactAgent.loadMember

    def serialize(messages):
        return [{"type": m.type, "name": m.name, "content": m.content,
                 **({"tool_calls": m.tool_calls} if getattr(m, "tool_calls", None) else {})} for m in messages]

    def run_case(scenario, condition, scope):
        inputs, native_inputs, routes, schemas, tools, blocked = [], [], [], [], [], {}
        state = {"main": 0, "evaluation": 0, "leaf": None, "choice": 0, "tool_used": False}
        main_order = {
            "direct_finish": ["FINISH"],
            "skip_generator": ["Evaluator Supervisor", "Revisor", "FINISH"],
            "skip_revisor": ["Answer Generator", "Evaluator Supervisor", "FINISH"],
            "skip_evaluation": ["Answer Generator", "Revisor", "FINISH"],
            "feedback": ["Answer Generator", "Evaluator Supervisor", "Revisor", "Evaluator Supervisor", "FINISH"],
        }.get(scenario, ["Answer Generator", "Evaluator Supervisor", "Revisor", "FINISH"])
        evaluation_order = (["Default Supervisor"] if scenario == "evaluation_early_return" else
                            [members[0], "Default Supervisor"] if scenario == "evaluation_subset" else
                            members + ["Default Supervisor"])

        def payload():
            return {"answer": {"choice": state["choice"], "steps": "Offline fixture output"}}

        def record_native(role, phase, messages):
            native_inputs.append({"role": role, "phase": phase, "messages": serialize(messages)})

        class LocalModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "offline-talkhier-route-validation"

            def bind_tools(self, supplied, **kwargs):
                tools.append([convert_to_openai_tool(t) for t in supplied])
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                role = state["leaf"]
                record_native(role, "model", messages)
                if scenario == "feedback" and role == "Revisor":
                    state["choice"] = 1
                if scenario == "tool_roundtrip" and role == "Answer Generator" and not state["tool_used"]:
                    state["tool_used"] = True
                    reply = AIMessage(content="", tool_calls=[{"name": "output_tool", "args": {"in_str": "Offline tool check"}, "id": "offline-tool-1", "type": "tool_call"}])
                else:
                    reply = AIMessage(content=json.dumps(payload()))
                return ChatResult(generations=[ChatGeneration(message=reply)])

            def with_structured_output(self, schema, **kwargs):
                assert isinstance(schema, dict) and kwargs == {'method': 'json_schema', 'strict': True}
                schemas.append(schema)
                def respond(value):
                    messages = value.to_messages() if hasattr(value, "to_messages") else list(value)
                    if "next" not in schema['properties']:
                        record_native(state["leaf"], "structured", messages)
                        return {'intermediate_output': json.dumps(payload())}
                    options = schema['properties']['next']['enum']
                    key = "main" if "FINISH" in options else "evaluation"
                    role = "Default Supervisor" if key == "main" else "Evaluator Supervisor"
                    record_native(role, "structured", messages)
                    assert set(options) == ({"FINISH", "Answer Generator", "Revisor", "Evaluator Supervisor"}
                                            if key == "main" else {"Default Supervisor", *members})
                    for forbidden in ([members[0]] if key == "main" else ["Revisor", "Answer Generator", "FINISH"]):
                        assert forbidden not in options, 'Provider schema allowed a cross-team route'
                        blocked[f"{role}->{forbidden}"] = True
                    order = main_order if key == "main" else evaluation_order
                    index = state[key] if key == "main" else state[key] % len(order)
                    next_role = order[index]
                    state[key] += 1
                    routes.append([role, next_role])
                    state["leaf"] = next_role
                    return dict(thoughts="Offline route probe", next=next_role,
                                  messages="Perform the assigned local task or report its result.",
                                  intermediate_output=json.dumps(payload()), background="Offline fixture background.")
                return RunnableLambda(respond)

        experiments.LLM = lambda cfg: SimpleNamespace(llm=LocalModel())
        csv_path = output / f"{scenario}_{condition}_{scope}.csv"
        if csv_path.exists():
            csv_path.unlink()
        context = contextlib.nullcontext() if condition == "NATIVE" else install(domain, condition, scope, inputs.append)
        log = io.StringIO()
        try:
            signal.alarm(30)
            with context, contextlib.redirect_stdout(log):
                experiments.runSingleMMLU(domain, config, 0, results=experiments.ResultManager(str(csv_path)))
        finally:
            signal.alarm(0)
            experiments.LLM = original_factory
            (output / f"{scenario}_{condition}_{scope}.log").write_text(log.getvalue())
        assert AgentTeam.loadSuperviser is original_supervisor and ReactAgent.loadMember is original_member
        assert "Retrying..." not in log.getvalue(), "Native failure retry during probe"
        results = list(csv.DictReader(csv_path.open()))
        assert len(results) == 1 and int(results[0]["Correct Answer"]) == dataset["test"][0]["answer"]
        assert int(results[0]["Answer"]) == (1 if scenario == "feedback" else 0)
        if condition == "NATIVE":
            inputs = [{**row, "injected": False} for row in native_inputs]
        assert len(inputs) == len(native_inputs)
        compact_roles = []
        for row in inputs:
            if not compact_roles or compact_roles[-1] != row["role"]:
                compact_roles.append(row["role"])
        assert compact_roles[0] == "Default Supervisor"
        for i, role in enumerate(compact_roles[:-1]):
            if role in ("Answer Generator", "Revisor"):
                assert compact_roles[i + 1] == "Default Supervisor"
            elif role in members:
                assert compact_roles[i + 1] == "Evaluator Supervisor"
        assert compact_roles[-1] == "Default Supervisor"
        stripped = []
        for row in inputs:
            messages = row["messages"]
            selected = condition == "V2" and (scope == "all_roles" or row["role"] == "Evaluator Supervisor")
            found = [m for m in messages if m["type"] == "system" and str(m["content"]).startswith(MARKER)]
            assert len(found) == int(selected)
            if selected:
                assert messages[0]["content"] == text and found[0] == messages[0]
                messages = messages[1:]
            stripped.append({"role": row["role"], "phase": row["phase"], "messages": messages})
        if scenario == "normal":
            assert {row["role"] for row in inputs} == role_names
            (output / f"normal_{condition}_{scope}_inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n")
        if scenario == "feedback":
            second_eval = [row for row in inputs if row["role"] == "Evaluator Supervisor"][len(evaluation_order):]
            assert second_eval and any('"choice": 1' in str(row["messages"]) or "'choice': 1" in str(row["messages"]) for row in second_eval)
            assert sum(1 for _, nxt in routes if nxt == "Evaluator Supervisor") == 2
        if scenario == "tool_roundtrip":
            assert any(m["type"] == "tool" for row in inputs for m in row["messages"])
        return {"stripped_inputs": stripped, "schemas": schemas, "tools": tools, "routes": routes,
                "native_result": results[0], "blocked_cross_team_routes": blocked,
                "visited_model_roles": sorted({r["role"] for r in inputs}), "input_count": len(inputs)}

    report = {"domain": domain, "evaluation_members": members, "scenarios": {}, "paid_model_calls": 0}
    try:
        for scenario in SCENARIOS:
            native = run_case(scenario, "NATIVE", "all_roles")
            entries = {}
            for condition, scope in (("BASE", "all_roles"), ("V2", "all_roles"), ("V2", "evaluation_supervisor")):
                result = run_case(scenario, condition, scope)
                for key in ("stripped_inputs", "schemas", "tools", "routes", "native_result", "blocked_cross_team_routes"):
                    assert result[key] == native[key], (domain, scenario, condition, scope, key)
                entries[f"{condition}:{scope}"] = {"only_selected_system_prefix_changed": True,
                    "native_schema_tools_routes_and_result_equal": True, "request_count": result["input_count"]}
            report["scenarios"][scenario] = {"comparisons": entries,
                "routes": native["routes"], "visited_model_roles": native["visited_model_roles"],
                "blocked_cross_team_routes": native["blocked_cross_team_routes"],
                "native_inputs_sha256": sha(native["stripped_inputs"]), "native_failure_retries": 0}
    finally:
        datasets.load_dataset, experiments.LLM = original_loader, original_factory
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"{domain}: all nodes, feedback, serial routes, bypasses, tool loop and request isolation OK", flush=True)


if __name__ == "__main__":
    main()
