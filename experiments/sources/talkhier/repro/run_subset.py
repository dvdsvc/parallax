"""Run identical frozen MMLU questions in two bounded process queues."""
import argparse
from collections import Counter, deque
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from common import DOMAINS, MANIFEST, ROOT, digest, workspace_environment
from org_v2.adapter import verify_artifacts
from run_archive import RunArchive, add_arguments, verify_archive, write
from benchmark_data import benchmark_manifest, verify_subset


def utc():
    return datetime.now(timezone.utc).isoformat()


def summaries(tasks):
    result = {}
    for condition, entries in tasks.items():
        counts = Counter(item['status'] for item in entries.values())
        done = [item for item in entries.values() if item['status'] == 'completed']
        correct = sum(item['result']['answer'] == item['result']['gold'] for item in done)
        result[condition] = {'questions_planned': len(entries), 'status_counts': dict(counts),
            'questions_completed': len(done), 'questions_correct': correct,
            'accuracy_on_completed': correct / len(done) if done else None,
            'observed_total_tokens': sum(item.get('trace_summary', {}).get('observed_total_tokens', 0) for item in entries.values()),
            'model_calls_finished': sum(item.get('trace_summary', {}).get('model_calls_finished', 0) for item in entries.values()),
            'calls_without_usage': sum(item.get('trace_summary', {}).get('calls_without_usage', 0) for item in entries.values())}
    return result


def harvest(task, process):
    task.update(exit_code=process.returncode, finished_at_utc=utc())
    directory = Path(task['directory'])
    record_file = directory / 'manifest.json'
    proof_file = directory / 'archive_manifest.json'
    if not record_file.exists() or not proof_file.exists():
        task.update(status='unsealed_worker_error', archive_valid=False)
        return
    record = json.loads(record_file.read_text())
    proof = json.loads(proof_file.read_text())
    completion = json.loads((directory / 'completion.json').read_text())
    verification = verify_archive(directory)
    task.update(status=record['status'], archive_valid=verification['valid'],
        archive_manifest_sha256=verification['archive_manifest_sha256'], mlflow_run_id=proof['mlflow_run_id'],
        trace_summary=record.get('trace_summary', {}), result_summary=record.get('result_summary', {}),
        elapsed_seconds=record.get('elapsed_seconds'), error=record.get('error'),
        live_source_changes=completion['live_source_changes'])
    if not verification['valid'] or completion['live_source_changes']:
        task['status'] = 'worker_archive_error'
    if (directory / 'native_results.csv').exists():
        rows = list(csv.DictReader((directory / 'native_results.csv').open()))
        if len(rows) == 1:
            row = rows[0]
            task['native_result_row'] = row
            try:
                if int(row['Problem ID']) != task['problem_id']:
                    raise ValueError('Native output problem ID differs')
                task['result'] = {'answer': int(row['Answer']), 'gold': int(row['Correct Answer']),
                                  'pre_revision': row['Pre-Revision']}
            except (ValueError, KeyError):
                if task['status'] == 'completed':
                    task['status'] = 'incomplete_native_result'
    if task['status'] == 'completed' and (process.returncode != 0 or 'result' not in task):
        task['status'] = 'incomplete_native_result'


def export_results(folder, tasks, questions):
    columns = ['problem_id', 'gold']
    for condition in tasks:
        columns += [f'{condition}_status', f'{condition}_answer', f'{condition}_correct', f'{condition}_run_id']
    with (folder / 'paired_results.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for question in questions:
            i = question['problem_id']; gold = question['question']['answer']
            row = {'problem_id': i, 'gold': gold}
            for condition in tasks:
                task = tasks[condition][str(i)]
                answer = task.get('result', {}).get('answer') if task['status'] == 'completed' else None
                row.update({f'{condition}_status': task['status'], f'{condition}_answer': answer,
                            f'{condition}_correct': int(answer == gold) if answer is not None else None,
                            f'{condition}_run_id': task.get('mlflow_run_id')})
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subset', required=True)
    concurrency = parser.add_mutually_exclusive_group()
    concurrency.add_argument('--workers-per-condition', type=int)
    concurrency.add_argument('--task-concurrency', type=int, help='Total BASE+V2 task slots; must be even (100 gives 50+50)')
    parser.add_argument('--model', default='qwen3.7-flash')
    parser.add_argument('--credential-file', default='external_archive/env/glm_api.env')
    parser.add_argument('--gateway-url', help='Local LiteLLM endpoint shared by BASE/V2')
    parser.add_argument('--gateway-wait-seconds', type=float, default=900)
    parser.add_argument('--timeout-seconds', type=int, default=3600, help='Per-question external wall-time limit')
    parser.add_argument('--request-timeout', type=float, default=900)
    parser.add_argument('--max-retries', type=int, default=2)
    parser.add_argument('--max-completion-tokens', type=int, default=16384)
    parser.add_argument('--thinking-budget', type=int, default=8192)
    parser.add_argument('--output-dir')
    parser.add_argument('--preflight-only', action='store_true', help='Same queues and archives, zero model calls')
    add_arguments(parser)
    args = parser.parse_args()
    if args.task_concurrency is not None:
        if args.task_concurrency < 2 or args.task_concurrency % 2:
            parser.error('--task-concurrency must be a positive even number of at least 2')
        args.workers_per_condition = args.task_concurrency // 2
    elif args.workers_per_condition is None:
        args.workers_per_condition = 8
    if min(args.workers_per_condition, args.timeout_seconds, args.request_timeout, args.max_completion_tokens, args.thinking_budget) <= 0 or args.max_retries < 0:
        parser.error('Worker count, timeouts and token cap must be positive; retries must be nonnegative')
    if args.thinking_budget >= args.max_completion_tokens:
        parser.error('--thinking-budget must be smaller than --max-completion-tokens to leave room for the final response')
    if args.gateway_url:
        from urllib.parse import urlsplit
        if urlsplit(args.gateway_url).hostname not in {'127.0.0.1', 'localhost', '::1'} or args.model != 'qwen3.7-flash' or args.gateway_wait_seconds <= 0:
            parser.error('Gateway mode requires a local endpoint, qwen3.7-flash and positive wait limit')
    workspace_environment(offline=True)
    sample, questions = verify_subset(args.subset)
    data_manifest = benchmark_manifest(args.subset)
    mode = sample['mode']
    _, org_manifest = verify_artifacts(mode)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = Path(args.output_dir).resolve() if args.output_dir else ROOT / '.local' / 'batches' / f'{stamp}_{mode}_n{len(questions)}_seed{sample["seed"]}'
    parameters = {**vars(args), 'mode': mode, 'scope': 'all_roles', 'sample_seed': sample['seed'], 'sample_size': len(questions)}
    archive = RunArchive(folder, kind='subset_preflight' if args.preflight_only else 'subset_batch', parameters=parameters,
        command=[sys.executable, *sys.argv], mlflow_python=args.mlflow_python, tracking_uri=args.mlflow_tracking_uri,
        experiment=args.mlflow_experiment, parent_run_id=args.parent_run_id, exclude_children=('BASE', 'V2'))
    tasks = {condition: {str(q['problem_id']): {'problem_id': q['problem_id'], 'status': 'queued',
             'directory': str(folder / condition / f'q{q["problem_id"]:03d}')} for q in questions} for condition in ('BASE', 'V2')}
    pending = {condition: deque(q['problem_id'] for q in questions) for condition in tasks}
    active = {condition: {} for condition in tasks}
    record = {**archive.identity, 'status': 'starting', 'mode': mode, 'split': 'test',
        'sample_size': len(questions), 'sample_seed': sample['seed'], 'sample_population_size': sample['population_size'],
        'sample_manifest_sha256': digest(Path(args.subset) / 'manifest.json'), 'scope': 'all_roles',
        'workers_per_condition': args.workers_per_condition, 'peak_workers_per_condition': dict.fromkeys(tasks, 0),
        'conditions': tasks, 'model': args.model, 'max_completion_tokens': args.max_completion_tokens,
        'enable_thinking': True, 'thinking_budget': args.thinking_budget, 'preflight_only': args.preflight_only,
        'benchmark_dataset': sample['dataset']}
    log_handles = {}
    failure = None
    def interrupt(*_):
        raise KeyboardInterrupt('Frozen subset batch interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    try:
        shutil.copytree(Path(args.subset).resolve(), folder / 'startup' / 'subset')
        archive.freeze_inputs(config_paths=(ROOT / 'config/config.ini', ROOT / 'config/config_llm.ini'),
            questions=((q['problem_id'], q['question']) for q in questions), dataset_manifest=data_manifest,
            effective_configuration={'model': args.model, 'conditions': ['BASE', 'V2'], 'scope': 'all_roles',
                'sample_seed': sample['seed'], 'sample_size': len(questions), 'sample_population_size': sample['population_size'],
                'sample_manifest_sha256': record['sample_manifest_sha256'], 'workers_per_condition': args.workers_per_condition,
                'max_completion_tokens': args.max_completion_tokens, 'output_limit_scope': 'thinking_plus_final_response',
                'enable_thinking': True, 'thinking_budget': args.thinking_budget, 'max_tokens': None,
                'structured_output_method': 'json_schema', 'provider_schema_strict': True,
                'pydantic_response_validation': False, 'request_timeout_seconds': args.request_timeout,
                'sdk_max_retries': 0 if args.gateway_url else args.max_retries, 'external_timeout_seconds_per_question': args.timeout_seconds,
                'organization_prompt_sha256': org_manifest['artifact_files_sha256'][f'global_organizational_architecture_v2_{mode}.txt'],
                'model_generation_seed': None, 'preflight_only': args.preflight_only, 'langsmith_enabled': False,
                'benchmark_dataset': sample['dataset'],
                **({'gateway_url': args.gateway_url, 'gateway_wait_seconds': args.gateway_wait_seconds,
                    'gateway_quota': json.loads((ROOT / 'repro/gateway/quota.json').read_text()),
                    'gateway_quota_sha256': digest(ROOT / 'repro/gateway/quota.json'),
                    'gateway_proxy_workers': 1, 'task_concurrency_total': args.workers_per_condition * 2,
                    'external_wall_timeout_includes_gateway_wait': True} if args.gateway_url else {})})
        if args.gateway_url:
            shutil.copytree(ROOT / 'repro/gateway', folder / 'startup/gateway', ignore=shutil.ignore_patterns('__pycache__'))
        common = [sys.executable, str(ROOT / 'repro/run_mmlu.py'), '--mode', mode, '--provider', 'openai',
            '--scope', 'all_roles', '--subset', str(Path(args.subset).resolve()), '--model', args.model,
            '--credential-file', args.credential_file, '--timeout-seconds', str(args.timeout_seconds),
            '--request-timeout', str(args.request_timeout), '--max-retries', str(args.max_retries),
            '--max-completion-tokens', str(args.max_completion_tokens), '--thinking-budget', str(args.thinking_budget),
            '--parent-run-id', archive.run_id,
            '--mlflow-python', args.mlflow_python, '--mlflow-tracking-uri', args.mlflow_tracking_uri,
            '--mlflow-experiment', args.mlflow_experiment]
        if args.preflight_only:
            common.append('--preflight-only')
        if args.gateway_url:
            common += ['--gateway-url', args.gateway_url, '--gateway-wait-seconds', str(args.gateway_wait_seconds)]
        (folder / 'worker_logs').mkdir()
        record['status'] = 'running'
        print(json.dumps({'status': 'running', 'archive': str(folder), 'mlflow_run_id': archive.run_id,
                          'questions_per_condition': len(questions), 'workers_per_condition': args.workers_per_condition}), flush=True)
        last_write = 0
        while any(pending[c] or active[c] for c in tasks):
            changed = False
            for condition in tasks:
                for i, process in list(active[condition].items()):
                    if process.poll() is not None:
                        log_handles.pop((condition, i)).close()
                        harvest(tasks[condition][str(i)], process)
                        del active[condition][i]
                        changed = True
                while pending[condition] and len(active[condition]) < args.workers_per_condition:
                    archive.verify_live_sources()
                    i = pending[condition].popleft(); task = tasks[condition][str(i)]
                    command = common + ['--condition', condition, '--problem-id', str(i), '--output-dir', task['directory']]
                    log = (folder / 'worker_logs' / f'{condition}_q{i:03d}.log').open('w')
                    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                    log_handles[condition, i] = log
                    active[condition][i] = process
                    task.update(status='running', pid=process.pid, command=command, started_at_utc=utc())
                    record['peak_workers_per_condition'][condition] = max(record['peak_workers_per_condition'][condition], len(active[condition]))
                    changed = True
            if changed or time.monotonic() - last_write >= 5:
                record['summary'] = summaries(tasks)
                record['last_updated_at_utc'] = utc()
                write(folder / 'manifest.json', record)
                export_results(folder, tasks, questions)
                last_write = time.monotonic()
            time.sleep(0.25)
        expected = 'preflight_passed' if args.preflight_only else 'completed'
        record['status'] = 'preflight_passed' if args.preflight_only else 'completed'
        if any(t['status'] != expected for condition in tasks.values() for t in condition.values()):
            record['status'] = 'completed_with_errors'
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'error', error=failure)
        raise
    finally:
        for condition in active:
            for process in active[condition].values():
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
        for condition in active:
            for i, process in active[condition].items():
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                harvest(tasks[condition][str(i)], process)
        for log in log_handles.values():
            log.close()
        record.update(summary=summaries(tasks), finished_at_utc=utc())
        write(folder / 'manifest.json', record)
        export_results(folder, tasks, questions)
        write(folder / 'child_run_index.json', tasks)
        metrics = {f'{condition}_{key}': value for condition, summary in record['summary'].items()
                   for key, value in summary.items() if isinstance(value, (int, float))}
        metrics['matched_questions_completed'] = sum(all(tasks[c][str(q['problem_id'])]['status'] == 'completed' for c in tasks) for q in questions)
        archive.finalize(record['status'], metrics=metrics, error=failure)
    print(json.dumps({'status': record['status'], 'archive': str(folder), 'summary': record['summary']}), flush=True)
    if record['status'] not in ('completed', 'preflight_passed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
