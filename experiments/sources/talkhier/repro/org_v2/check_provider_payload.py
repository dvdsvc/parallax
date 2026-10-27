"""Compare current provider request bodies through an in-process HTTP mock only."""
import json
import configparser
import inspect
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, workspace_environment
from org_v2.adapter import ModelView, verify_artifacts


def main():
    workspace_environment(offline=True)
    sys.path.insert(0, str(ROOT / "src"))
    from multiagent.tools import OutputTool
    from multiagent.agent_team import AgentTeam
    from multiagent.structured_output import structured_response
    from multiagent.llm import LLM
    text, _ = verify_artifacts("college_physics")
    requests = []

    def reply(request):
        payload = json.loads(request.content)
        assert payload['enable_thinking'] is True and payload['thinking_budget'] == 8192
        assert payload['max_completion_tokens'] == 16384 and 'max_tokens' not in payload
        requests.append(payload)
        if payload.get('response_format'):
            assert 'tools' not in payload and 'tool_choice' not in payload
            fmt = payload['response_format']
            assert fmt['type'] == 'json_schema' and fmt['json_schema']['strict'] is True
            properties = fmt['json_schema']['schema']['properties']
            arguments = {key: prop["enum"][0] if "enum" in prop else "offline" for key, prop in properties.items()}
            message = {'role': 'assistant', 'content': json.dumps(arguments)}
            finish = 'stop'
        else:
            message, finish = {"role": "assistant", "content": "offline"}, "stop"
        return httpx.Response(200, json={"id": "offline-completion", "object": "chat.completion", "created": 0,
            "model": "offline", "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    class Response(BaseModel):
        intermediate_output: str

    inputs = [SystemMessage(content="Native role instruction"), HumanMessage(content="Offline payload check")]
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        config = configparser.ConfigParser()
        config.read_dict({'KEYS': {'OPENAI_API_KEY': 'offline-test-only', 'OPENAI_ENDPOINT': 'https://offline.invalid/v1'},
                          'LLM': {'temperature': '0'}})
        with patch('multiagent.llm.ChatOpenAI', lambda **kwargs: ChatOpenAI(**kwargs, http_client=client)):
            model = LLM(config).llm
        schemas = {"structured": Response, "tools_then_structured": Response}
        for case, team_name, parent, members in (
            ("main_router", "Default", "FINISH", ["Answer Generator", "Revisor", "Evaluator Supervisor"]),
            ("evaluation_router", "Evaluator", "Default Supervisor", ["Physics", "Mathematics"]),
        ):
            team = AgentTeam(None, llm=model, member_names=members, member_info=["Native member"] * len(members),
                             team_name=team_name, supervisor_name=parent)
            schemas[case] = inspect.getclosurevars(team.loadSuperviser()).nonlocals["routeResponse"]
        results = []
        for case in ("plain", "tools", "structured", "tools_then_structured", "main_router", "evaluation_router"):
            native, treated = model, ModelView(model, "Answer Generator", text, True)
            if case in ("tools", "tools_then_structured"):
                native, treated = native.bind_tools([OutputTool()]), treated.bind_tools([OutputTool()])
            if case in schemas:
                native, treated = structured_response(native, schemas[case]), structured_response(treated, schemas[case])
            native_result, treated_result = native.invoke(inputs), treated.invoke(inputs)
            if case in schemas:
                assert native_result == treated_result
            before, after = requests[-2:]
            assert after["messages"][0] == {"role": "system", "content": text}
            after = {**after, "messages": after["messages"][1:]}
            assert before == after, case
            results.append({"case": case, "only_first_system_message_changed": True,
                            "provider_body_tools_schema_and_parameters_equal": True})
    report = {"transport": "httpx.MockTransport; no network/provider access", "paid_model_calls": 0,
              "real_credentials_used": False, "real_authentication_verified": False,
              "native_model_factory_used": True, "enable_thinking": True, "thinking_budget": 8192,
              "max_completion_tokens": 16384, "max_tokens_sent": False, "cases": results}
    target = ROOT / '.local' / 'validation' / 'provider_payload'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'report.json').write_text(json.dumps(report, indent=2) + "\n")
    print("Six current provider payload paths verified with an in-process HTTP mock; zero network calls.")


if __name__ == "__main__":
    main()
