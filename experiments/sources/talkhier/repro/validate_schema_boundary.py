"""Verify the real SDK wire format and attribute mapping without network access."""
import json
from pathlib import Path
import socket
import sys

import httpx
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator

from common import ROOT, workspace_environment


def main():
    workspace_environment(offline=True)
    sys.path.insert(0, str(ROOT / 'src'))
    from multiagent.structured_output import structured_response, response_fields
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in schema-boundary validation')
    socket.socket.connect = socket.create_connection = forbidden
    bodies = []
    class SchemaOnly(BaseModel):
        messages: str = Field(description='Existing native message field')
        intermediate_output: str
        @field_validator('*')
        def never_validate(cls, value):
            raise AssertionError('A response must never enter Pydantic validation')
    payload = {'messages': 'Literal \\mu and \\sqrt are retained.',
               'intermediate_output': '{"answer": {"choice": 1}}'}
    def reply(request):
        body = json.loads(request.content); bodies.append(body)
        assert body['response_format']['type'] == 'json_schema'
        fmt = body['response_format']['json_schema']
        assert fmt['strict'] is True and fmt['schema']['additionalProperties'] is False
        assert fmt['schema']['properties'] == SchemaOnly.model_json_schema()['properties']
        assert 'tools' not in body and 'tool_choice' not in body
        assert body['max_completion_tokens'] == 32768
        return httpx.Response(200, json={'id': 'offline-json-schema', 'object': 'chat.completion',
            'created': 0, 'model': 'offline', 'choices': [{'index': 0,
            'message': {'role': 'assistant', 'content': json.dumps(payload)}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}})
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        model = ChatOpenAI(model='qwen3.7-flash', api_key='offline-only',
            base_url='https://offline.invalid/v1', max_completion_tokens=32768,
            max_retries=0, http_client=client)
        for schema in [SchemaOnly, SchemaOnly.model_json_schema()]:
            result = structured_response(model, schema).invoke('Offline check')
            assert vars(result) == payload
            result.intermediate_output = {'answer': {'choice': 1}}
            assert result.intermediate_output['answer']['choice'] == 1
    for value in [None, json.dumps(payload)]:
        try:
            response_fields(value)
        except TypeError:
            pass
        else:
            raise AssertionError('The boundary must not parse text or accept None')
    report = {'network_disabled': True, 'paid_model_calls': 0, 'sdk_mock_calls': len(bodies),
        'provider_native_json_schema': True, 'strict': True,
        'schema_properties_preserved': True, 'pydantic_response_validation': False,
        'attribute_mapping_only': True, 'text_and_none_rejected_without_repair': True,
        'max_completion_tokens': 32768}
    target = ROOT / '.local' / 'validation' / 'schema_boundary'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (target / 'provider_requests.json').write_text(json.dumps(bodies, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
