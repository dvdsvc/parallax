"""Check automatic provenance/MLflow lifecycle with native graphs and no network."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import unquote, urlparse
from uuid import uuid4

from common import ROOT, digest
from run_archive import MLFLOW_PYTHON, TRACKING_URI, invoke_index, verify_archive, write


def worker(case, target, config):
    import httpx
    import run_mmlu as runner
    import run_archive
    from local_trace import LocalTrace
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in archive validation')
    socket.socket.connect = socket.create_connection = forbidden
    traces, requests, running_checks = [], [], []
    counters = {'main': 0, 'evaluation': 0}
    class CapturedTrace(LocalTrace):
        def __init__(self, directory):
            super().__init__(directory)
            traces.append(self)
    runner.LocalTrace = CapturedTrace
    original_archive = runner.RunArchive
    def fixture_archive(*args, **kwargs):
        kwargs['parameters'] = {**kwargs['parameters'], 'validation_fixture': True}
        return original_archive(*args, **kwargs)
    runner.RunArchive = fixture_archive
    runner.connection = lambda *args: {'api_key': 'offline-only', 'base_url': 'https://offline.invalid/v1'}
    if case == 'index-failure':
        original = run_archive.invoke_index
        def fail_initial_update(python, request):
            if request['action'] == 'update':
                raise RuntimeError('Offline injected startup indexing failure')
            return original(python, request)
        run_archive.invoke_index = fail_initial_update
    def reply(request):
        body = json.loads(request.content)
        assert body['max_completion_tokens'] == 16384 and 'max_tokens' not in body
        assert body['enable_thinking'] is True and body['thinking_budget'] == 8192
        requests.append(body)
        launch = json.loads((target / 'launch.json').read_text())
        if len(requests) == 1:
            live = invoke_index(MLFLOW_PYTHON, {'action': 'inspect', 'tracking_uri': TRACKING_URI,
                'run_id': launch['mlflow']['run_id']})
            assert live['status'] == 'RUNNING'
            assert (target / 'startup' / 'questions.jsonl').is_file()
            assert (target / 'startup' / 'source_hashes.json').is_file()
            running_checks.append(True)
        active = [v['record'] for v in traces[0].active.values() if v['record']['kind'] == 'model']
        assert len(active) == 1
        assert active[0]['metadata']['mlflow_run_id'] == launch['mlflow']['run_id']
        if case == 'interrupted':
            raise KeyboardInterrupt('Offline native interruption fixture')
        payload = {'answer': {'choice': 0, 'steps': 'Offline fixture; not a model answer'}}
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
                nxt = order[counters[key]]
                counters[key] += 1
                arguments = {'thoughts': 'Offline fixture', 'next': nxt, 'messages': 'Perform local work.',
                    'intermediate_output': json.dumps(payload), 'background': 'Offline fixture'}
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
        return httpx.Response(200, json={'id': f'offline-{len(requests)}', 'object': 'chat.completion', 'created': 0,
            'model': 'offline', 'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 101, 'completion_tokens': 7, 'total_tokens': 108}})
    sys.path.insert(0, str(ROOT / 'src'))
    import multiagent.llm as native_llm
    original_model = native_llm.ChatOpenAI
    sys.argv = ['run_mmlu.py', '--mode', 'college_physics', '--condition', 'V2' if case == 'V2' else 'BASE',
        '--output-dir', str(target), '--llm-config', str(config), '--max-retries', '0',
        '--mlflow-experiment', 'TalkHier-RecordValidation']
    if case == 'invalid-question':
        sys.argv += ['--problem-id', '9999', '--preflight-only']
    if case == 'missing-mlflow':
        sys.argv += ['--preflight-only', '--mlflow-python', str(target.parent / 'nonexistent-python')]
    expected_error = {'interrupted': KeyboardInterrupt, 'invalid-question': ValueError,
                      'missing-mlflow': RuntimeError, 'index-failure': RuntimeError}.get(case)
    error_seen = None
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        def fixture_model(**kwargs):
            assert kwargs['extra_body'] == {'enable_thinking': True, 'thinking_budget': 8192}
            assert kwargs['max_completion_tokens'] == 16384
            return original_model(**kwargs, http_client=client)
        native_llm.ChatOpenAI = fixture_model
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    runner.main()
                except BaseException as error:
                    if expected_error is None or not isinstance(error, expected_error):
                        raise
                    error_seen = type(error).__name__
        finally:
            native_llm.ChatOpenAI = original_model
    assert (error_seen is not None) == (expected_error is not None)
    write(target.parent / f'{case}_fixture_receipt.json', {'http_mock_requests': len(requests),
        'mlflow_running_before_first_model': bool(running_checks), 'expected_error': error_seen,
        'network_disabled': True})


def check_run(path, expected_status):
    proof = json.loads((path / 'archive_manifest.json').read_text())
    assert verify_archive(path)['valid']
    launch = json.loads((path / 'launch.json').read_text())
    assert proof['mlflow_run_id'] == launch['mlflow']['run_id']
    info = invoke_index(MLFLOW_PYTHON, {'action': 'inspect', 'tracking_uri': TRACKING_URI, 'run_id': proof['mlflow_run_id']})
    assert info['status'] == expected_status
    artifact = Path(unquote(urlparse(launch['mlflow']['artifact_uri']).path)) / 'run_archive'
    assert verify_archive(artifact)['valid']
    assert digest(artifact / 'archive_manifest.json') == digest(path / 'archive_manifest.json')
    assert info['params']['agent_source_sha256'] == launch['agent_source_sha256']
    return info, launch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-case')
    parser.add_argument('--target', type=Path)
    parser.add_argument('--fixture-config', type=Path)
    args = parser.parse_args()
    if args.worker_case:
        worker(args.worker_case, args.target, args.fixture_config)
        return
    root = ROOT / '.local' / 'validation' / 'run_archive' / uuid4().hex
    root.mkdir(parents=True)
    config = root / 'fixture_config.ini'
    secret_key, secret_endpoint = uuid4().hex, uuid4().hex
    config.write_text('[LLM]\ntemperature=0\nmax_attempts=30\ndeployment_name=offline\nopenai_api_version=offline\n'
        f'[KEYS]\nOPENAI_API_KEY={secret_key}\nOPENAI_ENDPOINT={secret_endpoint}\n')
    cases, run_info = {}, {}
    for case in ('BASE', 'V2', 'interrupted', 'invalid-question', 'missing-mlflow', 'index-failure'):
        target = root / case
        command = [sys.executable, str(Path(__file__).resolve()), '--worker-case', case, '--target', str(target), '--fixture-config', str(config)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
        (root / f'{case}.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        assert verify_archive(target)['valid']
        fixture = json.loads((root / f'{case}_fixture_receipt.json').read_text())
        if case == 'missing-mlflow':
            proof = json.loads((target / 'archive_manifest.json').read_text())
            assert proof['status'] == 'failed_preflight' and proof['mlflow_run_id'] is None
            assert fixture['http_mock_requests'] == 0
            cases[case] = {'sealed_local_failure': True, 'model_work_started': False}
            continue
        info, launch = check_run(target, 'FINISHED' if case in ('BASE', 'V2') else 'KILLED' if case == 'interrupted' else 'FAILED')
        run_info[case] = (info, launch)
        # Config snapshots and indexed copies contain neither credential sentinel.
        assert all(secret_key.encode() not in p.read_bytes() and secret_endpoint.encode() not in p.read_bytes()
                   for p in target.rglob('*') if p.is_file())
        if case in ('BASE', 'V2'):
            assert fixture['http_mock_requests'] == 19 and fixture['mlflow_running_before_first_model']
            summary = json.loads((target / 'token_usage.json').read_text())
            assert info['metrics']['model_calls_finished'] == summary['model_calls_finished'] == 19
            assert info['metrics']['observed_total_tokens'] == summary['observed_total_tokens'] == 2052
            assert info['metrics']['native_accuracy'] == 0
            assert info['params']['model'] == 'qwen3.7-flash'
            assert info['params']['question_count'] == '1' and info['params']['problem_ids'] == '[0]'
            assert info['params']['recursion_limit'] == '30' and info['params']['sdk_max_retries'] == '0'
            assert info['params']['max_tokens'] == info['params']['seed'] == 'null'
            assert info['params']['max_completion_tokens'] == '16384'
            assert info['params']['enable_thinking'] == 'True' and info['params']['thinking_budget'] == '8192'
            assert info['params']['structured_output_method'] == 'json_schema'
            assert info['params']['pydantic_response_validation'] == 'False'
            assert launch['mlflow']['telemetry_enabled'] is False
            assert info['tags']['validation_fixture'] == 'true'
            names = {Path(name).name for name in info['artifact_names']}
            assert {'trace.jsonl', 'native_results.csv', 'native_console.log'} <= names
            assert 'Agent Answer:' in (target / 'native_console.log').read_text()
            events = [json.loads(l) for l in (target / 'trace.jsonl').read_text().splitlines()]
            assert all(e['metadata']['mlflow_run_id'] == info['run_id'] for e in events if e['event'] == 'model_start')
        elif case == 'interrupted':
            assert fixture['http_mock_requests'] == 1
            assert ',-,-,-' in (target / 'native_results.csv').read_text()
            working = Path(json.loads((target / 'manifest.json').read_text())['native_working_csv'])
            assert ',-,-,-' not in working.read_text()  # native atexit cleanup already ran
            assert 'observed_total_tokens' not in info['metrics']
            assert info['metrics']['questions_completed'] == 0 and 'native_accuracy' not in info['metrics']
        else:
            assert fixture['http_mock_requests'] == 0
        cases[case] = {'mlflow_status': info['status'], 'archive_valid_after_process_exit': True,
            'artifact_copy_matches': True, **fixture}
    assert run_info['BASE'][1]['agent_source_sha256'] == run_info['V2'][1]['agent_source_sha256']
    assert run_info['BASE'][0]['params']['questions_sha256'] == run_info['V2'][0]['params']['questions_sha256']
    base = root / 'BASE'
    file = base / 'startup' / 'questions.jsonl'
    original = file.read_bytes()
    file.write_bytes(original + b'fixture tamper\n')
    assert not verify_archive(base)['valid']
    file.write_bytes(original)
    assert verify_archive(base)['valid']
    before = digest(base / 'archive_manifest.json')
    result = subprocess.run([sys.executable, str(ROOT / 'repro' / 'run_archive.py'), str(base), '--reindex'],
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert verify_archive(base)['valid'] and digest(base / 'archive_manifest.json') == before
    report = {'paid_model_calls': 0, 'model_responses': 'deterministic local HTTP fixtures only',
        'validation_root': str(root), 'cases': cases, 'base_v2_same_agent_and_questions': True,
        'startup_snapshots_and_mlflow_run_precede_model_work': True, 'sealing_survives_native_atexit_cleanup': True,
        'tampering_detected': True, 'reindex_preserves_archive_and_run_id': True,
        'credential_redaction_checked': True, 'native_source_unchanged': False,
        'agent_architecture_unchanged': True,
        'native_model_factory_used': True, 'enable_thinking': True, 'thinking_budget': 8192,
        'max_completion_tokens': 16384, 'max_tokens': None, 'langsmith_enabled': False}
    write(root / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
