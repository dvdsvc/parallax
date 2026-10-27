#!/usr/bin/env python3
"""Lock paired94 minus seed42/43, then draw ten questions once with seed44."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HIRA = Path('external_archive/2026-09-12/hira')
CONTROL = HIRA / 'work/forammas_study'
AGENT = HIRA / 'forammas'
HISTORY = HIRA / 'work/analysis_outputs/roma-v2-vs-base-native-e2b-20260929T062249Z/metadata_paired_94.csv'
OLD = AGENT / 'benchmark_subsets/seal0_clean_paired_15_seed42.json'
PREVIOUS = HIRA / 'work/paper_studies/seal0_remaining95_sample15_seed43_20261001T112502Z/benchmark_snapshot/seal0_remaining95_sample15_seed43.json'
SEED, SIZE = 44, 10

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def utc():
    return datetime.now(timezone.utc).isoformat()

def git(*args):
    return subprocess.check_output(['git', '-C', str(CONTROL), *args], text=True).strip()

def once(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError('Refusing to overwrite frozen artifact: ' + str(path))
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def json_once(path, value):
    once(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())

def csv_once(path, rows, fields):
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    once(path, buf.getvalue().encode())

def csv_read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def lock(root):
    old, previous = [json.loads(p.read_text()) for p in (OLD, PREVIOUS)]
    assert digest(HISTORY) == old['population_source_file_sha256']
    benchmark = Path(old['benchmark_source_file'])
    assert digest(benchmark) == old['benchmark_source_file_sha256'] == previous['benchmark_source_file_sha256']
    # Only existing question IDs and question text are consulted from paired94.
    historical = {int(r['index']): r['question'] for r in csv_read(HISTORY)}
    assert len(historical) == 94
    seed42 = {int(t['task_index']) for t in old['selected_tasks']}
    seed43 = {int(t['task_index']) for t in previous['selected_tasks']}
    assert len(seed42) == len(seed43) == 15 and not seed42 & seed43
    assert len(seed42 & historical.keys()) == 15 and len(seed43 & historical.keys()) == 10
    excluded = sorted((seed42 | seed43) & historical.keys())
    eligible = sorted(historical.keys() - seed42 - seed43)
    assert len(excluded) == 25 and len(eligible) == 69
    sys.path.insert(0, str(AGENT))
    from prompt_optimization.dataset_loaders import load_seal0_dataset
    import pandas as pd
    examples = load_seal0_dataset(seed=0, parquet_path=str(benchmark), no_split=True)
    raw = pd.read_parquet(benchmark)
    assert len(examples) == len(raw) == 111
    order = list(range(111))
    random.Random(0).shuffle(order)
    question_column = {c.lower(): c for c in raw.columns}['question']
    native = []
    for index, example in enumerate(examples):
        question = example.goal
        assert question == str(raw.iloc[order[index]][question_column])
        native.append(dict(index=index, task_index=index, benchmark_row_index=order[index],
            question=question, goal_sha256=hashlib.sha256(question.encode()).hexdigest()))
    assert all(native[i]['question'] == q for i, q in historical.items())
    assert sorted(random.Random(42).sample(sorted(historical), 15)) == sorted(seed42)
    assert Path(__file__).read_text().strip() == git('show', 'HEAD:sampling/sample_seal0_supplement.py')
    loader = AGENT / 'prompt_optimization/dataset_loaders.py'
    files = {'benchmark_snapshot/seal-0.parquet': benchmark,
        'source_snapshot/historical_paired94.csv': HISTORY,
        'source_snapshot/previous_subset_seed42.json': OLD,
        'source_snapshot/previous_subset_seed43.json': PREVIOUS,
        'source_snapshot/reference_sample_seed42.py': AGENT / 'scripts/sample_seal0_clean_paired.py',
        'source_snapshot/reference_sample_seed43.py': CONTROL / 'sampling/sample_seal0_remaining.py',
        'source_snapshot/dataset_loaders.py': loader,
        'sampler/sample_seal0_supplement.py': Path(__file__)}
    for relative, source in files.items():
        once(root / relative, source.read_bytes())
    fields = list(native[0])
    csv_once(root / 'source_snapshot/native_loader_index_111.csv', native, fields)
    csv_once(root / 'benchmark_snapshot/historical_paired94_index.csv', [native[i] for i in sorted(historical)], fields)
    csv_once(root / 'benchmark_snapshot/remaining69_index.csv', [native[i] for i in eligible], fields)
    json_once(root / 'source_snapshot/native_loader_execution.json', dict(executed_at_utc=utc(),
        loader='prompt_optimization.dataset_loaders.load_seal0_dataset', seed=0, no_split=True,
        parquet=str(benchmark), parquet_sha256=digest(benchmark), loader_sha256=digest(loader),
        native_count=111, paired94_question_mappings_verified=94, original_seed42_draw_reproduced=True,
        model_calls=0, executable=sys.executable))
    protocol = dict(schema_version=1, phase='population_and_seed_locked_before_draw', locked_at_utc=utc(),
        study_id=root.name, parent_population_size=94, population_size=69, sample_size=SIZE, random_seed=SEED,
        population_definition='Previously frozen historical paired94, excluding seed42 selected15 and the10 seed43 questions in paired94.',
        seed42_excluded=sorted(seed42), seed43_excluded_from94=sorted(seed43 & historical.keys()),
        seed43_outside94=sorted(seed43 - historical.keys()), excluded_task_indices=excluded,
        eligible_task_indices=eligible, population_order='ascending_existing_native_task_index',
        selection_order='ascending_existing_task_index_after_uniform_sample', sampling_method='uniform_without_replacement',
        performance_or_label_filtering_during_sampling=False, historical_clean_pair_membership_filter=True,
        sample_draw_count=0, benchmark_source_sha256=digest(benchmark), benchmark_source_commit=old['benchmark_source_commit'],
        native_loader_seed=0, native_loader_no_split=True, native_index_semantics='zero-based position after native seed0 shuffle; not Parquet row number or official instance ID',
        generator_git_repository=str(CONTROL), generator_git_commit=git('rev-parse', 'HEAD'),
        generator_script_sha256=digest(Path(__file__)), python_version=platform.python_version(),
        original_source_sha256={str(f): digest(f) for f in files.values()},
        locked_file_sha256={str(f.relative_to(root)): digest(f) for f in sorted(root.rglob('*')) if f.is_file()})
    json_once(root / 'sampling_protocol.json', protocol)
    print(json.dumps(dict(phase='index_locked', eligible=69, excluded=25, seed=44, sample_size=10,
        protocol_sha256=digest(root / 'sampling_protocol.json'))))

def draw(root):
    p = json.loads((root / 'sampling_protocol.json').read_text())
    assert p['random_seed'] == SEED and p['sample_size'] == SIZE and p['population_size'] == 69
    assert p['sample_draw_count'] == 0 and p['generator_script_sha256'] == digest(Path(__file__))
    for relative, sha in p['locked_file_sha256'].items():
        assert digest(root / relative) == sha
    rows = csv_read(root / 'benchmark_snapshot/remaining69_index.csv')
    ids = [int(r['index']) for r in rows]
    assert ids == sorted(set(ids)) == p['eligible_task_indices']
    # One committed draw. Subsequent replay is verification, never reselection.
    selected = sorted(random.Random(SEED).sample(ids, SIZE))
    by_id = {int(r['index']): r for r in rows}
    selected_tasks = [dict(task_index=i, question=by_id[i]['question'], benchmark_row_index=int(by_id[i]['benchmark_row_index']),
        goal_sha256=by_id[i]['goal_sha256']) for i in selected]
    subset_file = root / 'benchmark_snapshot/seal0_paired94_remaining69_sample10_seed44.json'
    subset = dict(schema_version=1, benchmark='SEAL-0 as exposed by ROMA', benchmark_source='Same pinned historical BASE Parquet',
        benchmark_source_file=str(root / 'benchmark_snapshot/seal-0.parquet'), benchmark_source_file_sha256=p['benchmark_source_sha256'],
        benchmark_source_commit=p['benchmark_source_commit'], benchmark_source_instance_count=111,
        benchmark_has_unique_official_instance_id=False, population_definition=p['population_definition'],
        parent_population_size=94, population_size=69, population_source_file=str(root / 'benchmark_snapshot/remaining69_index.csv'),
        population_source_file_sha256=digest(root / 'benchmark_snapshot/remaining69_index.csv'),
        population_task_id_field='index', population_task_id_semantics=p['native_index_semantics'],
        sample_size=SIZE, random_seed=SEED, sampling_method=p['sampling_method'], selection_order=p['selection_order'],
        excluded_task_indices=p['excluded_task_indices'], generated_at_utc=utc(),
        generator_git_commit=p['generator_git_commit'], generator_git_repository=p['generator_git_repository'],
        generator_script_sha256=p['generator_script_sha256'], sampling_protocol_sha256=digest(root / 'sampling_protocol.json'),
        performance_or_label_filtering_during_sampling=False, historical_clean_pair_membership_filter=True,
        sample_draw_count=1, selected_tasks=selected_tasks,
        run_reporting=dict(status='not_run', note='Record actual completion and common coverage in a separate run artifact.'))
    json_once(subset_file, subset)
    csv_once(root / 'selected_tasks_10.csv', [by_id[i] for i in selected], list(rows[0]))
    canonical = CONTROL / 'benchmark_subsets' / subset_file.name
    once(canonical, subset_file.read_bytes())
    manifest = dict(schema_version=1, study_id=root.name, status='sampling_frozen_not_run', created_at_utc=utc(),
        sampling=dict(population_size=69, parent_population_size=94, sample_size=10, seed=44,
            selected_task_indices=selected, excluded_task_indices=p['excluded_task_indices'],
            subset_file=str(subset_file.relative_to(root)), subset_file_sha256=digest(subset_file),
            canonical_subset_file=str(canonical), canonical_subset_file_sha256=digest(canonical),
            population_file='benchmark_snapshot/remaining69_index.csv', population_file_sha256=digest(root / 'benchmark_snapshot/remaining69_index.csv'),
            protocol_sha256=digest(root / 'sampling_protocol.json'), method=p['sampling_method']),
        benchmark_snapshot=dict(source_file='benchmark_snapshot/seal-0.parquet', source_file_sha256=p['benchmark_source_sha256'], loader_seed=0, count=111),
        agent=dict(commit=p['benchmark_source_commit'], agent_core_modified=False),
        generator=dict(commit=p['generator_git_commit'], script='sampler/sample_seal0_supplement.py', script_sha256=p['generator_script_sha256']),
        execution=dict(status='not_run', paper_runs=[], mlflow_runs=[]))
    json_once(root / 'study_manifest.json', manifest)
    for source, sha in p['original_source_sha256'].items():
        assert digest(Path(source)) == sha
    json_once(root / 'verification.json', dict(verified_at_utc=utc(), selected_replay_matches=True,
        native_loader_111_mappings_verified=True, historical94_mappings_verified=True,
        seed42_replay_verified=True, overlap_with_seed42=[], overlap_with_seed43=[],
        original_sources_unchanged=True, subset_sha256=digest(subset_file), sample_draw_count=1))
    notes = '# seed44 固定10题补充抽样\n\n历史paired94扣除seed42的15题与seed43重合的10题，剩余69题。固定seed44，按升序题号均匀无放回抽取一次。沿用原生seed0 loader编号及原始数据；抽样不读取正确率、Token、题类或运行成本，不因结果更换seed或题目。历史paired94成员资格是预先限定的抽样范围。\n\n题号：' + ', '.join(map(str, selected)) + '。\n\n| 题号 | 题目 |\n|---:|---|\n'
    for i in selected:
        notes += '| ' + str(i) + ' | ' + by_id[i]['question'].replace('|', '\\|').replace('\n', ' ') + ' |\n'
    once(root / 'README.md', notes.encode())
    files = [f for f in sorted(root.rglob('*')) if f.is_file() and f.name != 'checksums.sha256']
    once(root / 'checksums.sha256', ''.join(digest(f) + '  ' + str(f.relative_to(root)) + '\n' for f in files).encode())
    verify(root)

def verify(root):
    for line in (root / 'checksums.sha256').read_text().splitlines():
        sha, relative = line.split('  ', 1)
        assert digest(root / relative) == sha
    m = json.loads((root / 'study_manifest.json').read_text())
    s = m['sampling']
    subset = json.loads((root / s['subset_file']).read_text())
    ids = [int(r['index']) for r in csv_read(root / s['population_file'])]
    assert sorted(random.Random(SEED).sample(ids, SIZE)) == s['selected_task_indices'] == [t['task_index'] for t in subset['selected_tasks']]
    assert not set(s['selected_task_indices']) & set(s['excluded_task_indices'])
    assert (root / s['subset_file']).read_bytes() == Path(s['canonical_subset_file']).read_bytes()
    print(json.dumps(dict(status='verified_frozen_not_run', population_size=69, sample_size=10, seed=44,
        selected_task_indices=s['selected_task_indices'], subset_sha256=s['subset_file_sha256'],
        sampler_commit=m['generator']['commit'], study_root=str(root),
        files_verified=len((root / 'checksums.sha256').read_text().splitlines()))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['index', 'sample', 'verify'])
    parser.add_argument('--study-root', type=Path, required=True)
    args = parser.parse_args()
    {'index': lock, 'sample': draw, 'verify': verify}[args.phase](args.study_root.resolve())
