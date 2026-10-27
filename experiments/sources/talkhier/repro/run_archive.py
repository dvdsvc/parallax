"""Automatic startup snapshots and sealed local run archives, indexed in MLflow."""
import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from uuid import uuid4

from common import ROOT, UPSTREAM, digest

MLFLOW_PYTHON = 'sources/roma/controls/.venv/bin/python'
TRACKING_URI = 'sqlite:///' + str(ROOT / '.local' / 'mlflow' / 'tracking.db')
ARTIFACT_ROOT = ROOT / '.local' / 'mlflow' / 'artifacts'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def git(args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode()


def source_paths():
    paths = set(git(['ls-files', '-z']).split('\0')) | set(git(['ls-files', '--others', '--exclude-standard', '-z']).split('\0'))
    roots = {'README.md', 'ENVIRONMENT.md', 'requirements.txt', 'architecture.png', 'LICENSE', '.gitignore'}
    return sorted(p for p in paths if p and (ROOT / p).is_file() and
                  (p in roots or p.startswith(('src/', 'template/', 'repro/', 'docker/'))) and
                  '__pycache__' not in Path(p).parts and not p.endswith('.pyc') and not Path(p).name.startswith('.env'))


def sanitized_ini(path):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path)
    return {section: {key: '<REDACTED>' if section.upper() == 'KEYS' or
            any(word in key.lower() for word in ('api_key', 'password', 'secret', 'authorization', 'access_token')) else value
            for key, value in config.items(section)} for section in config.sections()}


def verify_archive(directory):
    directory = Path(directory)
    proof = json.loads((directory / 'archive_manifest.json').read_text())
    errors = []
    for name, expected in proof['files_sha256'].items():
        path = directory / name
        if not path.is_file() or digest(path) != expected:
            errors.append(name)
    actual = set(archive_files(directory, proof.get('exclude_children', [])))
    if actual != set(proof['files_sha256']):
        errors.extend(sorted(actual.symmetric_difference(proof['files_sha256'])))
    lines = (directory / 'checksums.sha256').read_text().splitlines()
    checksums = {name: h for h, name in (line.split('  ', 1) for line in lines)}
    expected = {**proof['files_sha256'], 'archive_manifest.json': digest(directory / 'archive_manifest.json')}
    if checksums != expected:
        errors.append('checksums.sha256')
    return {'valid': not errors, 'mismatches': sorted(set(errors)),
            'archive_manifest_sha256': digest(directory / 'archive_manifest.json')}


def archive_files(directory, exclude):
    return sorted(str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and
                  str(p.relative_to(directory)) not in ('archive_manifest.json', 'checksums.sha256') and
                  p.relative_to(directory).parts[0] not in exclude)


def invoke_index(python, request):
    if not Path(python).is_file():
        raise RuntimeError('MLflow interpreter unavailable; no model work may start')
    result = subprocess.run([str(python), str(ROOT / 'repro' / 'mlflow_index.py')],
        input=json.dumps(request), capture_output=True, text=True, cwd=ROOT, timeout=180)
    if result.returncode:
        raise RuntimeError(f'MLflow {request["action"]} failed: {result.stderr[-1800:]}')
    lines = [line for line in result.stdout.splitlines() if line.startswith('{')]
    if not lines:
        raise RuntimeError('MLflow index returned no receipt')
    return json.loads(lines[-1])


class RunArchive:
    def __init__(self, directory, *, kind, parameters, command, mlflow_python=MLFLOW_PYTHON,
                 tracking_uri=TRACKING_URI, experiment='TalkHier-MMLU', parent_run_id=None,
                 exclude_children=(), artifact_root=ARTIFACT_ROOT):
        self.directory = Path(directory)
        if not tracking_uri.startswith('sqlite:///'):
            raise ValueError('This entry records to local SQLite MLflow; use a local tracking URI')
        if self.directory.exists() and any(self.directory.iterdir()):
            raise ValueError('Refusing to overwrite existing launch records')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.uid, self.kind = uuid4().hex, kind
        self.python, self.tracking_uri, self.experiment = mlflow_python, tracking_uri, experiment
        self.exclude = list(exclude_children)
        self.mlflow = None
        self.sealed = False
        self.receipt = ROOT / '.local' / 'run_index' / f'{self.uid}.json'
        startup = self.directory / 'startup'
        startup.mkdir()
        status = git(['status', '--porcelain=v1', '--untracked-files=all'])
        state = {'commit': git(['rev-parse', 'HEAD']).strip(), 'branch': git(['branch', '--show-current']).strip(),
                 'dirty': bool(status), 'status': status.splitlines(), 'native_upstream_commit': UPSTREAM}
        write(startup / 'git_state.json', state)
        (startup / 'git.diff').write_text(git(['diff', '--binary', 'HEAD']))
        self.source_hashes = {}
        for name in source_paths():
            source = ROOT / name
            destination = startup / 'source' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            self.source_hashes[name] = digest(destination)
        write(startup / 'source_hashes.json', self.source_hashes)
        self.agent_hash = canonical_hash({n: h for n, h in self.source_hashes.items() if n.startswith('src/')})
        self.adapter_hash = canonical_hash({n: h for n, h in self.source_hashes.items() if n.startswith('repro/') and n.endswith(('.py', '.sh'))})
        write(startup / 'command.json', {'argv': command, 'cwd': str(ROOT), 'captured_at_utc': now()})
        write(startup / 'requested_parameters.json', parameters)
        distributions = sorted({(d.metadata['Name'], d.version) for d in importlib.metadata.distributions() if d.metadata.get('Name')})
        write(startup / 'environment.json', {'python': sys.version, 'executable': sys.executable,
            'platform': platform.platform(), 'packages': dict(distributions),
            'langsmith_enabled': False, 'no_auth_environment_captured': True})
        self.identity = {'launch_id': self.uid, 'run_kind': kind, 'workspace_commit': state['commit'],
            'workspace_dirty': state['dirty'], 'native_upstream_commit': UPSTREAM,
            'agent_source_sha256': self.agent_hash, 'external_source_sha256': self.adapter_hash,
            'source_file_count': len(self.source_hashes), 'started_at_utc': now(),
            'local_archive': str(self.directory), 'parent_mlflow_run_id': parent_run_id}
        write(self.directory / 'launch.json', self.identity)
        # Always establish MLflow before importing/running a model or worker.
        try:
            Path(self.tracking_uri.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
            tags = {'launch_id': self.uid, 'run_kind': kind, 'agent_source_sha256': self.agent_hash, 'external_source_sha256': self.adapter_hash,
                    'native_upstream_commit': UPSTREAM, 'workspace_commit': state['commit'],
                    'mlflow.source.git.commit': state['commit'], 'mlflow.source.name': str(ROOT / 'repro'),
                    'validation_fixture': str(parameters.get('validation_fixture', False)).lower(),
                    'workspace_dirty': str(state['dirty']).lower(), 'condition': parameters.get('condition', 'PAIR')}
            if parent_run_id:
                tags['mlflow.parentRunId'] = parent_run_id
            self.mlflow = invoke_index(self.python, {'action': 'start', 'tracking_uri': tracking_uri,
                'experiment': experiment, 'artifact_root': str(artifact_root), 'run_name': f'{kind}-{self.uid[:12]}',
                'archive': str(self.directory), 'tags': tags,
                'params': {'mode': parameters.get('mode'), 'condition': parameters.get('condition'),
                    'scope': parameters.get('scope', 'all_roles'), 'requested_model': parameters.get('model'),
                    'agent_commit': UPSTREAM, 'workspace_commit': state['commit'], 'agent_source_sha256': self.agent_hash,
                    'external_source_sha256': self.adapter_hash}})
            self.identity['mlflow'] = self.mlflow
            write(self.directory / 'launch.json', self.identity)
            self.index_update(startup_directory=startup, tags={'archive_status': 'startup_recorded'})
        except BaseException as error:
            try:
                self.finalize('failed_preflight', error={'type': type(error).__name__, 'message': str(error)})
            except BaseException:
                # The local sealed archive and separate retry receipt survive an
                # unavailable index; preserve the original startup exception.
                pass
            raise

    @property
    def run_id(self):
        return self.mlflow['run_id'] if self.mlflow else None

    def index_update(self, *, params=None, tags=None, startup_directory=None):
        request = {'action': 'update', 'run_id': self.run_id, 'tracking_uri': self.tracking_uri,
                   'params': params or {}, 'tags': tags or {}}
        if startup_directory:
            request['startup_directory'] = str(startup_directory)
        invoke_index(self.python, request)

    def freeze_inputs(self, *, config_paths=(), questions=(), effective_configuration=None, dataset_manifest=None):
        startup = self.directory / 'startup'
        for i, path in enumerate(config_paths):
            write(startup / 'config' / f'{i}_{Path(path).name}.json', sanitized_ini(path))
        if dataset_manifest:
            shutil.copyfile(dataset_manifest, startup / 'dataset_manifest.json')
        problem_ids = []
        with (startup / 'questions.jsonl').open('w') as stream:
            for problem_id, question in questions:
                problem_ids.append(problem_id)
                stream.write(json.dumps({'problem_id': problem_id, 'question': question,
                    'question_sha256': canonical_hash(question)}, ensure_ascii=False) + '\n')
        effective = effective_configuration or {}
        write(startup / 'effective_configuration.json', effective)
        write(startup / 'input_hashes.json', {'questions_sha256': digest(startup / 'questions.jsonl'),
            'effective_configuration_sha256': canonical_hash(effective),
            'dataset_manifest_sha256': digest(startup / 'dataset_manifest.json') if dataset_manifest else None})
        self.index_update(params={**effective, 'max_tokens': 'null' if effective.get('max_tokens') is None else effective['max_tokens'],
            'seed': 'null' if effective.get('seed') is None else effective['seed'],
            'problem_ids': json.dumps(problem_ids), 'question_count': len(problem_ids),
            'questions_sha256': digest(startup / 'questions.jsonl'), 'effective_configuration_sha256': canonical_hash(effective),
            'dataset_manifest_sha256': digest(startup / 'dataset_manifest.json') if dataset_manifest else None},
            tags={'archive_status': 'inputs_recorded'}, startup_directory=startup)
        self.verify_live_sources()

    def verify_live_sources(self):
        changed = [name for name, h in self.source_hashes.items() if not (ROOT / name).is_file() or digest(ROOT / name) != h]
        if changed:
            raise RuntimeError(f'Source changed since startup snapshot: {changed}')

    def seal(self, status, *, error=None):
        if self.sealed:
            return
        changed = [name for name, h in self.source_hashes.items() if not (ROOT / name).is_file() or digest(ROOT / name) != h]
        write(self.directory / 'completion.json', {'status': status, 'finished_at_utc': now(),
            'error': error, 'live_source_changes': changed, 'mlflow_run_id': self.run_id})
        files = {name: digest(self.directory / name) for name in archive_files(self.directory, self.exclude)}
        proof = {'schema_version': 1, 'status': status, 'launch_id': self.uid, 'mlflow_run_id': self.run_id,
                 'sealed_at_utc': now(), 'exclude_children': self.exclude, 'files_sha256': files}
        write(self.directory / 'archive_manifest.json', proof)
        checksums = {**files, 'archive_manifest.json': digest(self.directory / 'archive_manifest.json')}
        (self.directory / 'checksums.sha256').write_text(''.join(f'{h}  {name}\n' for name, h in sorted(checksums.items())))
        self.sealed = True
        assert verify_archive(self.directory)['valid']

    def finalize(self, status, *, metrics=None, error=None):
        self.seal(status, error=error)
        receipt = {'local_archive': str(self.directory), 'local_archive_valid': True, 'mlflow': self.mlflow,
                   'mlflow_python': str(self.python), 'tracking_uri': self.tracking_uri,
                   'archive_manifest_sha256': digest(self.directory / 'archive_manifest.json'),
                   'metrics': metrics or {}, 'index_status': 'pending' if self.mlflow else 'not_started'}
        write(self.receipt, receipt)
        if self.mlflow:
            try:
                invoke_index(self.python, {'action': 'finish', 'run_id': self.run_id, 'tracking_uri': self.tracking_uri,
                    'archive': str(self.directory), 'exclude_children': self.exclude, 'metrics': metrics or {},
                    'tags': {'archive_status': status, 'archive_manifest_sha256': receipt['archive_manifest_sha256']},
                    'mlflow_status': 'FINISHED' if status in ('completed', 'preflight_passed') else
                                     'KILLED' if status == 'interrupted' else 'FAILED'})
                receipt['index_status'] = 'finished'
            except BaseException as failure:
                receipt.update(index_status='failed', error_type=type(failure).__name__, error=str(failure))
                write(self.receipt, receipt)
                raise
        write(self.receipt, receipt)
        return receipt


def add_arguments(parser):
    parser.add_argument('--mlflow-python', default=MLFLOW_PYTHON)
    parser.add_argument('--mlflow-tracking-uri', default=TRACKING_URI)
    parser.add_argument('--mlflow-experiment', default='TalkHier-MMLU')
    parser.add_argument('--parent-run-id')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--reindex', action='store_true', help='Retry attaching a sealed archive to its existing MLflow run; no agent execution')
    args = parser.parse_args()
    result = verify_archive(args.archive)
    print(json.dumps(result, indent=2))
    if not result['valid']:
        raise SystemExit(1)
    if args.reindex:
        proof = json.loads((args.archive / 'archive_manifest.json').read_text())
        receipt_path = ROOT / '.local' / 'run_index' / f'{proof["launch_id"]}.json'
        receipt = json.loads(receipt_path.read_text())
        if not receipt['mlflow']:
            raise RuntimeError('No MLflow run was established; this failed startup remains locally archived')
        invoke_index(receipt['mlflow_python'], {'action': 'finish', 'run_id': proof['mlflow_run_id'],
            'tracking_uri': receipt['tracking_uri'], 'archive': str(args.archive.resolve()),
            'exclude_children': proof['exclude_children'], 'metrics': receipt.get('metrics', {}),
            'tags': {'archive_status': proof['status'], 'archive_manifest_sha256': result['archive_manifest_sha256']},
            'mlflow_status': 'FINISHED' if proof['status'] in ('completed', 'preflight_passed') else
                             'KILLED' if proof['status'] == 'interrupted' else 'FAILED'})
        receipt.update(index_status='finished', reindexed_at_utc=now())
        receipt.pop('error', None)
        receipt.pop('error_type', None)
        write(receipt_path, receipt)
        print(json.dumps({'reindexed_mlflow_run_id': proof['mlflow_run_id']}))


if __name__ == '__main__':
    main()
