"""Offline real-LangChain/native-factory checks for retry/trace separation."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import configparser
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from threading import Lock

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'repro'), str(ROOT / 'src')]
from repro.gateway.client import GatewayRetryTransport, GatewayRetryExhausted, model_boundary, retry_after, trace_handler
from multiagent.llm import LLM


def response(request, number, content='ok'):
    return httpx.Response(200, request=request, headers={'x-litellm-call-id': f'offline-{number}'}, json={
        'id': f'chatcmpl-offline-{number}', 'object': 'chat.completion', 'created': 0, 'model': 'qwen3.7-flash',
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 7, 'completion_tokens': 13, 'total_tokens': 20,
                  'completion_tokens_details': {'reasoning_tokens': 5}}})


def config():
    cfg = configparser.ConfigParser()
    cfg.read_dict({'KEYS': {'OPENAI_API_KEY': 'sk-offline-test', 'OPENAI_ENDPOINT': 'http://offline-gateway/v1'},
        'LLM': {'model': 'qwen3.7-flash', 'temperature': '0', 'max_completion_tokens': '16384',
                'enable_thinking': 'true', 'thinking_budget': '8192', 'request_timeout': '900', 'max_retries': '2'}})
    return cfg


def main():
    destination = ROOT / '.local/gateway/validation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_client')
    trace = trace_handler(destination)
    attempts, bodies, lock = Counter(), {}, Lock()

    def send(request):
        body = request.read()
        data = json.loads(body)
        number = int(data['messages'][0]['content'].split(':')[-1])
        with lock:
            attempts[number] += 1
            bodies.setdefault(number, []).append(body)
            count = attempts[number]
        if count == 1:
            source = 'litellm_local' if number % 2 == 0 else 'qwen_upstream'
            return httpx.Response(429, request=request, headers={'retry-after': '0', 'x-talkhier-rate-limit-origin': source},
                                  json={'error': {'message': 'offline rate limit'}})
        return response(request, number)

    transport = GatewayRetryTransport(destination, httpx.MockTransport(send), sleep=lambda seconds: None)
    with httpx.Client(transport=transport) as client, model_boundary(client):
        llm = LLM(config()).llm

        def call(number):
            condition = 'BASE' if number < 50 else 'V2'
            answer = llm.invoke(f'offline_task:{number}', config={'callbacks': [trace],
                               'metadata': {'condition': condition, 'problem_id': number}})
            assert answer.content == 'ok'

        with ThreadPoolExecutor(max_workers=100) as executor:
            list(executor.map(call, range(100)))
    usage = trace.finalize()
    calls = [json.loads(line) for line in (destination / 'model_calls.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (destination / 'gateway_events.jsonl').read_text().splitlines()]
    assert len(calls) == 100 and all(x['status'] == 'success' for x in calls)
    assert len({x['run_id'] for x in calls}) == 100
    assert usage['observed_total_tokens'] == 2000
    rate_limits = [x for x in events if x['event'] == 'rate_limit']
    assert len(rate_limits) == 100
    assert Counter(x['origin'] for x in rate_limits) == {'litellm_local': 50, 'qwen_upstream': 50}
    assert all(x['logical_call_id'] in {c['run_id'] for c in calls} for x in rate_limits)
    assert all(len(v) == 2 and v[0] == v[1] for v in bodies.values())
    for value in bodies.values():
        body = json.loads(value[0])
        assert body['max_completion_tokens'] == 16384 and 'max_tokens' not in body
        assert body['enable_thinking'] is True and body['thinking_budget'] == 8192

    # Native model -> JSON Schema dict still returns a dict; the transport changes no parser/schema.
    structured = destination / 'structured'
    captured = []
    def schema_send(request):
        captured.append(json.loads(request.read()))
        return response(request, 'schema', '{"value": 1}')
    with httpx.Client(transport=GatewayRetryTransport(structured, httpx.MockTransport(schema_send))) as client, model_boundary(client):
        schema = {'title': 'OfflineChoice', 'type': 'object', 'properties': {'value': {'type': 'integer'}},
                  'required': ['value'], 'additionalProperties': False}
        output = LLM(config()).llm.with_structured_output(schema, method='json_schema', strict=True).invoke('offline schema')
        assert output == {'value': 1}
    assert captured[0]['response_format']['type'] == 'json_schema'

    exhausted = destination / 'exhausted'
    error_trace = trace_handler(exhausted)
    def always429(request):
        return httpx.Response(429, request=request, headers={'retry-after': '120', 'x-talkhier-rate-limit-origin': 'qwen_upstream'},
                              json={'error': {'message': 'offline always429'}})
    caught_by_native_retry = False
    with httpx.Client(transport=GatewayRetryTransport(exhausted, httpx.MockTransport(always429), max_wait_seconds=1)) as client, model_boundary(client):
        try:
            try:
                LLM(config()).llm.invoke('offline exhaustion', config={'callbacks': [error_trace]})
            except Exception:
                caught_by_native_retry = True
        except GatewayRetryExhausted as error:
            assert error.failure_domain == 'infrastructure' and error.rate_limit_origin == 'qwen_upstream'
        else:
            raise AssertionError('Expected infrastructure exhaustion')
    assert not caught_by_native_retry
    error_calls = [json.loads(line) for line in (exhausted / 'model_calls.jsonl').read_text().splitlines()]
    assert len(error_calls) == 1 and error_calls[0]['failure_domain'] == 'infrastructure'
    assert retry_after('120', 1) == 120
    assert retry_after('Thu, 01 Jan 1970 00:02:00 GMT', 1, wall_clock=lambda: 0) == 120
    report = {'validated_at_utc': datetime.now(timezone.utc).isoformat(), 'output': str(destination),
              'logical_calls': 100, 'http_attempts': sum(attempts.values()), 'transient_429_in_gateway_log': len(rate_limits),
              'transient_429_in_model_errors': 0, 'logical_id_correlation': True, 'request_bytes_identical_on_retry': True,
              'native_factory_budget_preserved': True, 'native_JSON_Schema_dict_preserved': True,
              'Retry_After_seconds_and_date_supported': True, 'exhaustion_stops_native_Exception_retry': True,
              'exhaustion_failure_domain': error_calls[0]['failure_domain'], 'real_provider_calls': 0}
    (destination / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
