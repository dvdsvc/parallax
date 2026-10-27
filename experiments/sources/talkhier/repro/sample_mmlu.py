"""Freeze a seeded, without-replacement subset of native MMLU test rows."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil
import sys

from common import DOMAINS, MANIFEST, ROOT, digest, load_frozen
from run_archive import canonical_hash, write


def verify_subset(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['split'] != 'test' or manifest['sampling']['replacement']:
        raise ValueError('Only frozen native test rows sampled without replacement are supported')
    for name, expected in manifest['files_sha256'].items():
        if digest(directory / name) != expected:
            raise ValueError(f'Changed subset artifact: {name}')
    expected_checksums = {**manifest['files_sha256'], 'manifest.json': digest(directory / 'manifest.json')}
    actual_checksums = dict((name, sha) for sha, name in
        (line.split('  ', 1) for line in (directory / 'checksums.sha256').read_text().splitlines()))
    if actual_checksums != expected_checksums:
        raise ValueError('Subset checksum inventory differs')
    if digest(MANIFEST) != manifest['dataset_manifest_sha256']:
        raise ValueError('Frozen benchmark manifest differs from the sampled population')
    if digest(Path(__file__)) != manifest['files_sha256']['sampling_script.py']:
        raise ValueError('Current sampler differs from the saved script snapshot')
    rows = load_frozen(manifest['mode'])['test']
    if len(rows) != manifest['population_size']:
        raise ValueError('Sampled population size differs')
    draw = random.Random(manifest['seed']).sample(range(len(rows)), manifest['sample_size'])
    indices = json.loads((directory / 'indices.json').read_text())
    saved_draw = json.loads((directory / 'draw_order.json').read_text())
    questions = [json.loads(line) for line in (directory / 'questions.jsonl').read_text().splitlines()]
    if draw != saved_draw or sorted(draw) != indices or len(indices) != len(set(indices)):
        raise ValueError('Seeded draw or unique native indices differ')
    expected_questions = [{'problem_id': i, 'question': dict(rows[i]),
                           'question_sha256': canonical_hash(dict(rows[i]))} for i in indices]
    if questions != expected_questions:
        raise ValueError('Selected question text, choices, gold answer, or original index differs')
    return manifest, questions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=DOMAINS, default='college_physics')
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    if args.verify:
        manifest, questions = verify_subset(directory)
        print(json.dumps({'valid': True, 'directory': str(directory), 'seed': manifest['seed'],
                          'population_size': manifest['population_size'], 'sample_size': len(questions)}))
        return
    rows = load_frozen(args.mode)['test']
    if not 0 < args.count <= len(rows):
        parser.error('Sample count must be between 1 and the native test population size')
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Refusing to overwrite an existing frozen sample')
    directory.mkdir(parents=True, exist_ok=True)
    draw = random.Random(args.seed).sample(range(len(rows)), args.count)
    indices = sorted(draw)
    write(directory / 'indices.json', indices)
    write(directory / 'draw_order.json', draw)
    with (directory / 'questions.jsonl').open('w') as stream:
        for i in indices:
            row = dict(rows[i])
            stream.write(json.dumps({'problem_id': i, 'question': row,
                                    'question_sha256': canonical_hash(row)}, ensure_ascii=False) + '\n')
    shutil.copyfile(Path(__file__), directory / 'sampling_script.py')
    import shlex
    command = ['.venv/bin/python', 'repro/sample_mmlu.py', '--mode', args.mode,
               '--count', str(args.count), '--seed', str(args.seed), '--output-dir', str(directory.relative_to(ROOT))
               if directory.is_relative_to(ROOT) else str(directory)]
    (directory / 'command.txt').write_text(shlex.join(command) + '\n')
    source_manifest = json.loads(MANIFEST.read_text())
    manifest = {'schema_version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': args.mode, 'dataset': source_manifest['dataset'], 'dataset_revision': source_manifest['dataset_revision'],
        'dataset_manifest_sha256': digest(MANIFEST), 'split': 'test', 'population_size': len(rows),
        'sample_size': args.count, 'seed': args.seed, 'seed_scope': 'question sampling only; no model generation seed',
        'sampling': {'algorithm': 'random.Random(seed).sample(range(population_size), sample_size)',
                     'replacement': False, 'exclusions': [], 'execution_order': 'sorted original row indices',
                     'draw_order_saved': True, 'index_base': 0},
        'python_version': sys.version, 'source_script': 'repro/sample_mmlu.py', 'command': command,
        'cwd': str(ROOT), 'files_sha256': {name: digest(directory / name) for name in
             ('indices.json', 'draw_order.json', 'questions.jsonl', 'sampling_script.py', 'command.txt')}}
    write(directory / 'manifest.json', manifest)
    checksums = {**manifest['files_sha256'], 'manifest.json': digest(directory / 'manifest.json')}
    (directory / 'checksums.sha256').write_text(''.join(f'{sha}  {name}\n' for name, sha in sorted(checksums.items())))
    verify_subset(directory)
    print(json.dumps({'directory': str(directory), 'population_size': len(rows), 'sample_size': args.count,
                      'seed': args.seed, 'indices': indices, 'manifest_sha256': digest(directory / 'manifest.json')}))


if __name__ == '__main__':
    main()
