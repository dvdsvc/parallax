"""Exercise native graphs, ChatOpenAI serialization and local callbacks offline."""
import configparser
import contextlib
import csv
import io
import json
from pathlib import Path
import socket
import sys

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from common import ROOT, load_frozen, native_dataset_loader
from direct_model import install as direct
from local_trace import LocalTrace
from org_v2.adapter import install as organization, MARKER, verify_artifacts


def main():
    dataset = load_frozen('college_physics')
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT))
    import datasets
    import experiments
    from multiagent.agent_team import AgentTeam, ReactAgent
    import inspect
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in this validation')
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    original_loader = datasets.load_dataset
    original_factory = experiments.LLM
    datasets.load_dataset = native_dataset_loader(original_loader, 'college_physics', dataset)
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / 'template' / 'config.ini')
    cfg['LLM'] = {'temperature': '0', 'max_attempts': '100'}
    folder = ROOT / '.local' / 'validation' / 'direct_langchain'
    folder.mkdir(parents=True, exist_ok=True)
    prompt, _ = verify_artifacts('college_physics')
    payload = {'answer': {'choice': 0, 'steps': 'Offline fixture; not a model answer'}}
    role_set = {'Default Supervisor', 'Evaluator Supervisor', 'Answer Generator', 'Revisor', 'Physics', 'Mathematics'}
    cases = {}
    bodies = {}
    try:
        for condition in ['BASE', 'V2']:
            target = folder / condition
            if target.exists():
                for name in ['trace.jsonl', 'graph_nodes.jsonl', 'model_calls.jsonl', 'token_usage.json', 'native_results.csv']:
                    (target / name).unlink(missing_ok=True)
            trace = LocalTrace(target)
            requests = []
            counters = {'main': 0, 'evaluation': 0}
            def reply(request):
                body = json.loads(request.content)
                requests.append(body)
                active = [v['record'] for v in trace.active.values() if v['record']['kind'] == 'model']
                assert len(active) == 1 and active[0]['role'] in role_set
                functions = body.get('tools', [])
                if body.get('response_format'):
                    assert 'tools' not in body and 'tool_choice' not in body
                    fmt = body['response_format']
                    assert fmt['type'] == 'json_schema' and fmt['json_schema']['strict'] is True
                    props = fmt['json_schema']['schema']['properties']
                    if 'next' in props:
                        main = 'FINISH' in props['next']['enum']
                        key = 'main' if main else 'evaluation'
                        order = ['Answer Generator', 'Evaluator Supervisor', 'Revisor', 'FINISH'] if main else ['Physics', 'Mathematics', 'Default Supervisor']
                        nxt = order[counters[key]]; counters[key] += 1
                        arguments = {'thoughts': 'Offline fixture', 'next': nxt, 'messages': 'Perform assigned local work.',
                                     'intermediate_output': json.dumps(payload), 'background': 'Offline fixture background'}
                    else:
                        arguments = {'intermediate_output': json.dumps(payload)}
                    message = {'role': 'assistant', 'content': json.dumps(arguments)}
                    finish = 'stop'
                elif not any(m['role'] == 'tool' for m in body['messages']):
                    message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'offline-{len(requests)}',
                        'type': 'function', 'function': {'name': 'output_tool', 'arguments': json.dumps({'in_str': 'Offline tool fixture'})}}]}
                    finish = 'tool_calls'
                else:
                    message, finish = {'role': 'assistant', 'content': json.dumps(payload)}, 'stop'
                return httpx.Response(200, json={'id': f'offline-{len(requests)}', 'object': 'chat.completion',
                    'created': 0, 'model': 'offline-qwen', 'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                    'usage': {'prompt_tokens': 101, 'completion_tokens': 7, 'total_tokens': 108,
                              'prompt_tokens_details': {'cached_tokens': 12}, 'completion_tokens_details': {'reasoning_tokens': 3}}})
            with httpx.Client(transport=httpx.MockTransport(reply)) as client, direct(experiments,
                {'api_key': 'offline-only', 'base_url': 'https://offline.invalid/v1'}, 'qwen3.7-flash', 10, 0, client), organization('college_physics', condition, 'all_roles'):
                results = experiments.ResultManager(str(target / 'native_results.csv'))
                log = io.StringIO()
                with contextlib.redirect_stdout(log):
                    RunnableLambda(lambda _: experiments.runSingleMMLU('college_physics', cfg, 0, results=results)).invoke({},
                        config={'callbacks': [trace], 'metadata': {'condition': condition, 'problem_id': 0, 'domain': 'college_physics'}})
                (target / 'native.log').write_text(log.getvalue())
                assert 'Retrying' not in log.getvalue()
            assert experiments.LLM is original_factory
            summary = trace.finalize()
            events = [json.loads(l) for l in (target / 'trace.jsonl').read_text().splitlines()]
            node_events = [json.loads(l) for l in (target / 'graph_nodes.jsonl').read_text().splitlines()]
            node_names = {e['name'] for e in node_events if e['event'] == 'chain_start'}
            assert role_set <= node_names, node_names
            assert set(summary['by_role']) == role_set
            assert summary['model_calls_finished'] == len(requests) == 19
            assert summary['observed_total_tokens'] == len(requests) * 108
            assert summary['observed_cached_input_tokens'] == len(requests) * 12
            assert summary['observed_reasoning_output_tokens'] == len(requests) * 3
            assert summary['event_counts']['tool_start'] == summary['event_counts']['tool_end'] == 4
            assert summary['model_errors'] == 0 and not summary['unfinished_model_calls']
            assert all(e.get('parent_run_id') for e in events if e['event'] == 'model_start')
            starts = [e for e in events if e['event'] == 'model_start']
            for e in starts:
                msgs = e['messages'][0]
                count = sum(m['type'] == 'system' and str(m['content']).startswith(MARKER) for m in msgs)
                assert count == int(condition == 'V2')
            for b in requests:
                if condition == 'V2':
                    assert b['messages'][0] == {'role': 'system', 'content': prompt}
                else:
                    assert not any(str(m.get('content', '')).startswith(MARKER) for m in b['messages'])
            native_rows = list(csv.DictReader((target / 'native_results.csv').open()))
            assert len(native_rows) == 1 and int(native_rows[0]['Correct Answer']) == dataset['test'][0]['answer']
            cases[condition] = {'model_calls': len(requests), 'roles': sorted(summary['by_role']),
                'native_node_callbacks_cover_all_roles': True, 'native_tool_events': 4,
                'returned_usage_and_cache_reasoning_subsets_exact': True, 'native_result': native_rows[0]}
            bodies[condition] = requests
        assert bodies['BASE'] == [{**b, 'messages': b['messages'][1:]} for b in bodies['V2']]
        # Invalid provider output gets no custom repair; missing/error usage
        # remains unknown independently of the response representation.
        target = folder / 'negative'
        target.mkdir(exist_ok=True)
        for name in ['trace.jsonl', 'graph_nodes.jsonl', 'model_calls.jsonl', 'token_usage.json']:
            (target / name).unlink(missing_ok=True)
        trace = LocalTrace(target)
        def plain_json(request):
            return httpx.Response(200, json={'id': 'offline-plain', 'object': 'chat.completion', 'created': 0, 'model': 'offline',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'invalid provider response'}, 'finish_reason': 'stop'}]})
        with httpx.Client(transport=httpx.MockTransport(plain_json)) as client, direct(experiments,
                {'api_key': 'offline-only', 'base_url': 'https://offline.invalid/v1'}, 'qwen3.7-flash', 10, 0, client):
            from pydantic import BaseModel
            class NativeResponse(BaseModel):
                intermediate_output: str
            model = experiments.LLM(cfg).llm
            from multiagent.structured_output import structured_response
            from langchain_core.exceptions import OutputParserException
            try:
                structured_response(model, NativeResponse).invoke([HumanMessage(content='Offline negative case')], config={'callbacks': [trace]})
            except OutputParserException:
                pass
            else:
                raise AssertionError('Unexpected structured parser fallback')
            def failure(request):
                return httpx.Response(500, json={'error': {'message': 'Offline fixture failure', 'type': 'fixture'}})
            with httpx.Client(transport=httpx.MockTransport(failure)) as fail_client:
                from langchain_openai import ChatOpenAI
                try:
                    ChatOpenAI(model='qwen3.7-flash', api_key='offline-only', base_url='https://offline.invalid/v1',
                        http_client=fail_client, max_retries=0).invoke([HumanMessage(content='Offline error')], config={'callbacks': [trace]})
                except Exception:
                    pass
                else:
                    raise AssertionError('HTTP error was not preserved')
        negative = trace.finalize()
        assert negative['model_successes'] == negative['model_errors'] == 1
        assert negative['calls_without_usage'] == 2 and negative['observed_total_tokens'] is None
        report = {'paid_model_calls': 0, 'network_disabled': True, 'cases': cases,
            'base_v2_provider_bodies_only_global_prefix_differs': True, 'invalid_json_not_repaired': True,
            'structured_output_method': 'json_schema', 'pydantic_response_validation': False,
            'missing_and_error_usage_remains_unknown': True, 'langsmith_enabled': False}
        (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        datasets.load_dataset = original_loader


if __name__ == '__main__':
    main()
