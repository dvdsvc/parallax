"""Freeze an auditable, seeded 100-question Physics subset of official MMLU-Pro."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shlex
import shutil
import sys

ROOT = next((p for p in Path(__file__).resolve().parents if (p / 'repro/mmlu_pro_manifest.json').is_file()), Path(__file__).resolve().parents[1])
SOURCE = ROOT / 'repro/mmlu_pro_manifest.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def population():
    source = json.loads(SOURCE.read_text())
    for name, expected in source['files_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed official source file: ' + name)
    rows = [json.loads(line) for line in (ROOT / source['physics']['test']['path']).read_text().splitlines()]
    if len(rows) != source['physics']['test']['rows']:
        raise ValueError('Physics population size differs')
    return source, rows


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['split'] != 'test' or manifest['category'] != 'physics' or manifest['sampling']['replacement']:
        raise ValueError('Subset scope differs')
    for name, expected in manifest['files_sha256'].items():
        if digest(directory / name) != expected:
            raise ValueError('Changed subset file: ' + name)
    if digest(SOURCE) != manifest['source_manifest_sha256']:
        raise ValueError('Official source manifest differs')
    if digest(__file__) != manifest['files_sha256']['sampling_script.py']:
        raise ValueError('Working sampling script differs from frozen script')
    expected = {**manifest['files_sha256'], 'manifest.json': digest(directory / 'manifest.json')}
    actual = {name: sha for sha, name in (line.split('  ', 1) for line in (directory / 'checksums.sha256').read_text().splitlines())}
    if actual != expected:
        raise ValueError('Checksum inventory differs')
    source, rows = population()
    draw = random.Random(manifest['seed']).sample(range(len(rows)), manifest['sample_size'])
    selected = [rows[i] for i in sorted(draw)]
    if draw != json.loads((directory / 'draw_order.json').read_text()):
        raise ValueError('Seeded draw order differs')
    for file, key in [('physics_indices.json', 'physics_index'), ('indices.json', 'split_row_index'), ('question_ids.json', 'question_id')]:
        values = json.loads((directory / file).read_text())
        if values != [row[key] for row in selected] or len(set(values)) != len(selected):
            raise ValueError('Index mapping differs: ' + file)
    saved = [json.loads(line) for line in (directory / 'questions.jsonl').read_text().splitlines()]
    if saved != selected or len(selected) != manifest['sample_size']:
        raise ValueError('Selected raw question/options/gold differ')
    with (directory / 'indices.csv').open() as stream:
        table = list(csv.DictReader(stream))
    if len(table) != len(selected):
        raise ValueError('Index CSV coverage differs')
    for i, (row, record) in enumerate(zip(table, selected)):
        if any(int(row[key]) != record[key] for key in ['physics_index', 'split_row_index', 'question_id']) or int(row['sample_index']) != i:
            raise ValueError('Index CSV mapping differs')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    if args.verify:
        manifest = verify(directory)
        print(json.dumps({'valid': True, 'sample_size': manifest['sample_size'], 'population_size': manifest['population_size'], 'seed': manifest['seed']}))
        return
    source, rows = population()
    if not 0 < args.count <= len(rows):
        parser.error('Sample count must lie within Physics test population')
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Refusing to overwrite a frozen subset')
    directory.mkdir(parents=True, exist_ok=True)
    draw = random.Random(args.seed).sample(range(len(rows)), args.count)
    selected = [rows[i] for i in sorted(draw)]
    save(directory / 'draw_order.json', draw)
    for file, key in [('physics_indices.json', 'physics_index'), ('indices.json', 'split_row_index'), ('question_ids.json', 'question_id')]:
        save(directory / file, [row[key] for row in selected])
    with (directory / 'questions.jsonl').open('w') as stream:
        for row in selected:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    with (directory / 'indices.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['sample_index', 'physics_index', 'split_row_index', 'question_id', 'answer', 'answer_index', 'option_count', 'src', 'record_sha256'])
        writer.writeheader()
        for i, row in enumerate(selected):
            record = row['record']
            writer.writerow({'sample_index': i, **{k: row[k] for k in ['physics_index', 'split_row_index', 'question_id', 'record_sha256']},
                             'answer': record['answer'], 'answer_index': record['answer_index'], 'option_count': len(record['options']), 'src': record['src']})
    shutil.copyfile(__file__, directory / 'sampling_script.py')
    command = ['.venv/bin/python', 'repro/sample_mmlu_pro.py', '--count', str(args.count), '--seed', str(args.seed),
               '--output-dir', str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory)]
    (directory / 'command.txt').write_text(shlex.join(command) + '\n')
    files = sorted(x.name for x in directory.iterdir())
    manifest = {'schema_version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'dataset': source['dataset'], 'dataset_revision': source['dataset_revision'], 'source': source['source'],
                'source_manifest_sha256': digest(SOURCE), 'category': 'physics', 'split': 'test',
                'population_size': len(rows), 'sample_size': args.count, 'seed': args.seed,
                'seed_scope': 'question sampling only; no model generation seed',
                'sampling': {'algorithm': 'random.Random(seed).sample(range(number_of_Physics_test_rows), count)',
                             'replacement': False, 'exclusions': [], 'population_order': 'official test split order filtered by category == physics',
                             'execution_order': 'sorted original test split row indices', 'draw_order_saved': True},
                'index_conventions': {'indices.json': 'original full test split row index, zero based',
                                      'physics_indices.json': 'ordinal within filtered Physics test population, zero based',
                                      'question_ids.json': 'official question_id; preserve independently of row indices',
                                      'draw_order.json': 'Physics population ordinals in RNG draw order'},
                'record_policy': 'All official fields unchanged including options, gold and cot_content; no N/A removal; labels are archival, not model input',
                'raw_option_count_distribution': dict(Counter(len(row['record']['options']) for row in selected)),
                'rows_with_NA_option': sum('N/A' in row['record']['options'] for row in selected),
                'python_version': sys.version, 'command': command, 'cwd': str(ROOT),
                'agent_calls': 0, 'grader_calls': 0, 'files_sha256': {name: digest(directory / name) for name in files}}
    save(directory / 'manifest.json', manifest)
    checksums = {**manifest['files_sha256'], 'manifest.json': digest(directory / 'manifest.json')}
    (directory / 'checksums.sha256').write_text(''.join(f'{h}  {name}\n' for name, h in sorted(checksums.items())))
    verify(directory)
    print(json.dumps({'directory': str(directory), 'population_size': len(rows), 'sample_size': args.count, 'seed': args.seed,
                      'manifest_sha256': digest(directory / 'manifest.json')}))


if __name__ == '__main__':
    main()
