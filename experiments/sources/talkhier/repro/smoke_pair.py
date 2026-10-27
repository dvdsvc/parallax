"""Two independent native MMLU workers using direct LangChain API clients."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from common import ROOT, DOMAINS, MANIFEST, load_frozen, workspace_environment
from org_v2.adapter import verify_artifacts
from run_archive import RunArchive, add_arguments, write, verify_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=DOMAINS, default='college_physics')
    parser.add_argument('--problem-id', type=int, default=0)
    parser.add_argument('--model', default='qwen3.7-flash')
    parser.add_argument('--credential-file', default='external_archive/env/glm_api.env')
    parser.add_argument('--timeout-seconds', type=int, default=900)
    parser.add_argument('--request-timeout', type=float, default=900)
    parser.add_argument('--max-retries', type=int, default=2)
    parser.add_argument('--max-completion-tokens', type=int, default=16384)
    parser.add_argument('--thinking-budget', type=int, default=8192)
    parser.add_argument('--output-dir', help='New or empty paired-run directory')
    parser.add_argument('--preflight-only', action='store_true')
    add_arguments(parser)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.request_timeout <= 0 or args.max_retries < 0 or args.max_completion_tokens <= 0 or args.thinking_budget <= 0:
        parser.error('Timeouts/token limit must be positive and --max-retries nonnegative')
    if args.thinking_budget >= args.max_completion_tokens:
        parser.error('--thinking-budget must be smaller than --max-completion-tokens to leave room for the final response')
    workspace_environment(offline=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = Path(args.output_dir).resolve() if args.output_dir else ROOT / '.local' / 'smoke_pairs' / f'{stamp}_direct_{args.mode}_q{args.problem_id}'
    archive = RunArchive(folder, kind='paired_preflight' if args.preflight_only else 'paired_controller',
        parameters={**vars(args), 'scope': 'all_roles'}, command=[sys.executable, *sys.argv],
        mlflow_python=args.mlflow_python, tracking_uri=args.mlflow_tracking_uri,
        experiment=args.mlflow_experiment, parent_run_id=args.parent_run_id, exclude_children=('BASE', 'V2'))
    common = [sys.executable, str(ROOT / 'repro' / 'run_mmlu.py'), '--mode', args.mode,
        '--problem-id', str(args.problem_id), '--provider', 'openai', '--scope', 'all_roles',
        '--model', args.model, '--credential-file', args.credential_file,
        '--timeout-seconds', str(args.timeout_seconds), '--request-timeout', str(args.request_timeout),
        '--max-retries', str(args.max_retries), '--mlflow-python', args.mlflow_python,
        '--max-completion-tokens', str(args.max_completion_tokens),
        '--thinking-budget', str(args.thinking_budget),
        '--mlflow-tracking-uri', args.mlflow_tracking_uri, '--mlflow-experiment', args.mlflow_experiment,
        '--parent-run-id', archive.run_id]
    if args.preflight_only:
        common.append('--preflight-only')
    record = {**archive.identity, 'status': 'starting', 'split': 'test', 'mode': args.mode, 'problem_id': args.problem_id,
        'model': args.model, 'scope': 'all_roles',
        'provider': 'direct LangChain ChatOpenAI', 'proxy_used': False, 'langsmith_enabled': False,
        'native_source_modified': True, 'agent_architecture_modified': False, 'conditions': {}}
    processes, logs = {}, []
    failure = None
    def interrupt(*_):
        raise KeyboardInterrupt('Paired smoke interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    try:
        dataset = load_frozen(args.mode)
        if not 0 <= args.problem_id < len(dataset['test']):
            raise ValueError('Problem ID is outside the frozen test split')
        _, org_manifest = verify_artifacts(args.mode)
        archive.freeze_inputs(config_paths=(ROOT / 'config' / 'config.ini', ROOT / 'config' / 'config_llm.ini'),
            questions=[(args.problem_id, dict(dataset['test'][args.problem_id]))], dataset_manifest=MANIFEST,
            effective_configuration={'model': args.model, 'conditions': ['BASE', 'V2'], 'scope': 'all_roles',
                'provider': 'openai', 'request_timeout_seconds': args.request_timeout, 'sdk_max_retries': args.max_retries,
                'max_completion_tokens': args.max_completion_tokens, 'output_limit_scope': 'thinking_plus_final_response',
                'enable_thinking': True, 'thinking_budget': args.thinking_budget, 'max_tokens': None,
                'structured_output_method': 'json_schema',
                'provider_schema_strict': True, 'pydantic_response_validation': False,
                'external_timeout_seconds': args.timeout_seconds, 'preflight_only': args.preflight_only,
                'organization_prompt_sha256': org_manifest['artifact_files_sha256'][f'global_organizational_architecture_v2_{args.mode}.txt'],
                'langsmith_enabled': False})
        for condition in ['BASE', 'V2']:
            arm = folder / condition
            log = (folder / f'{condition}.log').open('w'); logs.append(log)
            command = common + ['--condition', condition, '--output-dir', str(arm)]
            processes[condition] = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                                     start_new_session=True)
            record['conditions'][condition] = {'directory': str(arm), 'command': command,
                'started_at_utc': datetime.now(timezone.utc).isoformat()}
        record['status'] = 'running'
        write(folder / 'manifest.json', record)
        print(f'Concurrent {"zero-model preflight" if args.preflight_only else "direct API smoke"} pair: {folder}', flush=True)
        deadline = time.monotonic() + args.timeout_seconds + 90
        while any(p.poll() is None for p in processes.values()):
            if time.monotonic() > deadline:
                raise TimeoutError('External worker deadline exceeded')
            time.sleep(0.5)
        record['status'] = ('preflight_passed' if args.preflight_only else 'completed') if all(p.returncode == 0 for p in processes.values()) else 'worker_error'
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'error', error=failure)
        raise
    finally:
        for process in processes.values():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
        for process in processes.values():
            if process.poll() is None:
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        for log in logs: log.close()
        references = {}
        for condition, process in processes.items():
            record['conditions'][condition]['exit_code'] = process.returncode
            child = folder / condition
            if (child / 'archive_manifest.json').exists():
                proof = json.loads((child / 'archive_manifest.json').read_text())
                references[condition] = {**verify_archive(child), 'mlflow_run_id': proof['mlflow_run_id'],
                                        'status': proof['status'], 'directory': str(child)}
                if not references[condition]['valid']:
                    record['status'] = 'worker_archive_error'
            else:
                references[condition] = {'valid': False, 'status': 'unsealed_or_not_started', 'directory': str(child)}
                record['status'] = 'worker_archive_error' if record['status'] in ('completed', 'preflight_passed') else record['status']
        write(folder / 'child_run_index.json', references)
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        write(folder / 'manifest.json', record)
        archive.finalize(record['status'], metrics={'child_runs_started': len(processes),
            'child_runs_sealed': sum(x['valid'] for x in references.values())}, error=failure)
    if record['status'] not in ('completed', 'preflight_passed'):
        raise SystemExit(1)
    print(json.dumps({'status': record['status'], 'mlflow_run_id': archive.run_id, 'archive': str(folder), 'children': references}, indent=2))


if __name__ == '__main__':
    main()
