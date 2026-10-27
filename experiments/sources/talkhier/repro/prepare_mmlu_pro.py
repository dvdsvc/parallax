"""Download a pinned official MMLU-Pro snapshot and preserve Physics rows."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATASET = 'TIGER-Lab/MMLU-Pro'
REVISION = 'b189ec765aa7ed75c8acfea42df31fdae71f97be'
FILES = ('README.md', 'data/test-00000-of-00001.parquet', 'data/validation-00000-of-00001.parquet')
MANIFEST = ROOT / 'repro/mmlu_pro_manifest.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_parquet(path, python=None):
    if python:
        result = subprocess.run([python, '-c',
            'import json,sys,pyarrow.parquet as pq; print(json.dumps(pq.read_table(sys.argv[1]).to_pylist()))',
            str(path)], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def verify(parquet_python=None):
    manifest = json.loads(MANIFEST.read_text())
    for name, expected in manifest['files_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed benchmark file: ' + name)
    reader = parquet_python or manifest['parquet_reader']['python']
    for split, item in manifest['physics'].items():
        native = read_parquet(ROOT / item['official_parquet'], reader)
        physics = [dict(physics_index=i, split_row_index=j, question_id=row['question_id'],
                        record=row, record_sha256=canonical_hash(row))
                   for i, (j, row) in enumerate((j, row) for j, row in enumerate(native) if row['category'] == 'physics')]
        saved = [json.loads(line) for line in (ROOT / item['path']).read_text().splitlines()]
        if saved != physics or len(saved) != item['rows']:
            raise ValueError('Physics export differs from official parquet')
        if len({x['question_id'] for x in saved}) != len(saved):
            raise ValueError('Duplicate official Physics question IDs')
        for entry in saved:
            row = entry['record']
            if row['answer'] != 'ABCDEFGHIJ'[row['answer_index']] or not 0 <= row['answer_index'] < len(row['options']):
                raise ValueError('Official answer letter/index is inconsistent')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=REVISION)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--parquet-python', help='Optional separate interpreter for reading parquet; agent environment is unchanged')
    args = parser.parse_args()
    if args.verify or MANIFEST.exists():
        manifest = verify(args.parquet_python)
        if manifest['dataset_revision'] != args.revision:
            raise ValueError('Existing benchmark revision differs; use a new snapshot instead of overwriting')
        print(json.dumps({'valid': True, 'revision': args.revision, 'physics_counts': {k: v['rows'] for k, v in manifest['physics'].items()}}))
        return
    os.environ['HF_HOME'] = str(ROOT / '.cache/huggingface')
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from huggingface_hub import HfApi, hf_hub_download
    info = HfApi(token=False).dataset_info(DATASET, revision=args.revision, files_metadata=True)
    if info.sha != args.revision:
        raise ValueError('A full immutable dataset revision is required')
    directory = ROOT / 'data/mmlu_pro' / args.revision
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in FILES:
        downloaded = hf_hub_download(DATASET, name, repo_type='dataset', revision=args.revision, token=False)
        destination = directory / 'official' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(downloaded, destination)
        metadata = next(x for x in info.siblings if x.rfilename == name)
        if metadata.size is not None and destination.stat().st_size != metadata.size:
            raise ValueError('Downloaded size differs: ' + name)
        if metadata.lfs and digest(destination) != metadata.lfs.get('sha256'):
            raise ValueError('Downloaded LFS checksum differs: ' + name)
        paths.append(destination)
    physics, split_counts = {}, {}
    for split in ['test', 'validation']:
        source = directory / 'official/data' / f'{split}-00000-of-00001.parquet'
        rows = read_parquet(source, args.parquet_python)
        selected = [(j, row) for j, row in enumerate(rows) if row['category'] == 'physics']
        output = directory / 'physics' / f'{split}.jsonl'
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('w') as stream:
            for i, (j, row) in enumerate(selected):
                entry = dict(physics_index=i, split_row_index=j, question_id=row['question_id'],
                             record=row, record_sha256=canonical_hash(row))
                stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        paths.append(output)
        physics[split] = {'rows': len(selected), 'path': str(output.relative_to(ROOT)),
                          'official_parquet': str(source.relative_to(ROOT)),
                          'raw_option_count_distribution': dict(Counter(len(row['options']) for _, row in selected)),
                          'rows_with_NA_option': sum('N/A' in row['options'] for _, row in selected)}
        split_counts[split] = len(rows)
    receipt = directory / 'download_receipt.json'
    receipt.write_text(json.dumps({'dataset': DATASET, 'resolved_sha': info.sha, 'files': FILES,
                                  'prepared_at_utc': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')
    paths.append(receipt)
    manifest = {'dataset': DATASET, 'dataset_revision': args.revision,
                'source': f'https://huggingface.co/datasets/{DATASET}/tree/{args.revision}',
                'split_counts': split_counts, 'physics': physics,
                'selection': 'category == physics; original split order; all rows; no exclusions',
                'record_policy': 'Preserve all official fields, options, answer letter/index, cot_content and src unchanged; no N/A removal',
                'files_sha256': {str(p.relative_to(ROOT)): digest(p) for p in paths},
                'parquet_reader': {'python': args.parquet_python or sys.executable,
                    'pyarrow_version': subprocess.run([args.parquet_python or sys.executable, '-c',
                        'import pyarrow;print(pyarrow.__version__)'], capture_output=True, text=True, check=True).stdout.strip()},
                'preparation_script_sha256': digest(__file__)}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    verify(args.parquet_python)
    print(json.dumps({'manifest': str(MANIFEST), 'revision': args.revision,
                      'split_counts': split_counts, 'physics_counts': {k: v['rows'] for k, v in physics.items()}}))


if __name__ == '__main__':
    main()
