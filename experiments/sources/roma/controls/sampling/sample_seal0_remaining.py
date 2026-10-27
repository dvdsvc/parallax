#!/usr/bin/env python3
"""Freeze110 native indices, exclude the old15, then sample15 of95 with seed43.

Separate index/sample phases lock the population, seed, and generator before the
draw. Neither phase uses scores, costs, completion status, or topic labels.
"""
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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HIRA = Path('external_archive/2026-09-12/hira')
CONTROL = HIRA / 'work/forammas_study'
OLD_STUDY = HIRA / 'work/paper_studies/seal0_clean_paired15_seed42_20260930'
OLD_SUBSET = HIRA / 'forammas/benchmark_subsets/seal0_clean_paired_15_seed42.json'
OLD_SAMPLER = HIRA / 'forammas/scripts/sample_seal0_clean_paired.py'
LOADER = HIRA / 'forammas/prompt_optimization/dataset_loaders.py'
HIST_MANIFEST = HIRA / 'work/paper_runs/20260929T025511Z_BASE_seal0-base-native-e2b-1-110-20260929/manifest.json'
SEED = 43
SIZE = 15
START = 1
STOP = 110


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(CONTROL), *args], text=True).strip()


def write_once(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite frozen artifact: {path}')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(content); f.flush(); os.fsync(f.fileno())
    try:
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path: Path, data: dict) -> None:
    write_once(path, (json.dumps(data, indent=2, ensure_ascii=False)+'\n').encode())


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    write_once(path, buf.getvalue().encode())


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def freeze_index(root: Path) -> None:
    import pandas as pd
    source = json.loads(HIST_MANIFEST.read_text())
    bm = source['benchmark']
    old = json.loads(OLD_SUBSET.read_text())
    old_manifest = json.loads((OLD_STUDY/'study_manifest.json').read_text())
    assert digest(OLD_SUBSET) == old_manifest['sampling']['subset_file_sha256']
    benchmark = Path(bm['file'])
    assert digest(benchmark) == bm['file_sha256'] == old['benchmark_source_file_sha256']
    assert bm['selected_indices'] == list(range(START, STOP+1))
    assert bm['seed'] == 0 and bm['no_split'] is True and bm['dataset_count'] == 111
    excluded = sorted(t['task_index'] for t in old['selected_tasks'])
    assert len(excluded) == len(set(excluded)) == 15
    assert set(excluded).issubset(range(START, STOP+1))

    native_path = root/'source_snapshot/native_loader_index_111.csv'
    native = read_csv(native_path)
    assert [int(x['task_index']) for x in native] == list(range(111))
    raw = pd.read_parquet(benchmark)
    assert len(raw) == 111
    order = list(range(len(raw))); random.Random(0).shuffle(order)
    lower = {x.lower(): x for x in raw.columns}
    question_col = lower['question']
    indexed = []
    historical_hashes = {t['index']: t['goal_sha256'] for t in bm['tasks']}
    for task_index, row_index in enumerate(order):
        question = str(raw.iloc[row_index][question_col])
        sha = hashlib.sha256(question.encode()).hexdigest()
        assert native[task_index]['question'] == question
        assert native[task_index]['goal_sha256'] == sha
        if START <= task_index <= STOP:
            assert historical_hashes[task_index] == sha
            indexed.append(dict(index=task_index, task_index=task_index,
                benchmark_row_index=row_index, question=question, goal_sha256=sha))
    by_id = {r['index']: r for r in indexed}
    assert all(by_id[t['task_index']]['question'].strip() == t['question'] for t in old['selected_tasks'])
    eligible = [r for r in indexed if r['index'] not in excluded]
    assert len(indexed) == 110 and len(eligible) == 95

    # Replay the original42 algorithm against its frozen94 indices, for parity.
    old_pop = Path(old['population_source_file'])
    assert digest(old_pop) == old['population_source_file_sha256']
    old_ids = sorted(int(x['index']) for x in read_csv(old_pop))
    assert sorted(random.Random(42).sample(old_ids, 15)) == excluded
    assert git('show', 'HEAD:sampling/sample_seal0_remaining.py').encode() == Path(__file__).read_text().strip().encode()
    files = {
        'benchmark_snapshot/seal-0.parquet': benchmark,
        'source_snapshot/previous_subset_seed42.json': OLD_SUBSET,
        'source_snapshot/previous_study_manifest.json': OLD_STUDY/'study_manifest.json',
        'source_snapshot/reference_sample_seal0_clean_paired.py': OLD_SAMPLER,
        'source_snapshot/dataset_loaders.py': LOADER,
        'sampler/sample_seal0_remaining.py': Path(__file__),
    }
    for relative, original in files.items():
        write_once(root/relative, original.read_bytes())
    write_json(root/'source_snapshot/historical_benchmark_manifest_extract.json',
               dict(source_manifest=str(HIST_MANIFEST), source_manifest_sha256=digest(HIST_MANIFEST), benchmark=bm,
                    agent_commit=old['benchmark_source_commit']))
    fields=['index','task_index','benchmark_row_index','question','goal_sha256']
    write_csv(root/'benchmark_snapshot/seal0_index_110.csv', indexed, fields)
    write_csv(root/'benchmark_snapshot/seal0_remaining_95.csv', eligible, fields)
    protocol = dict(schema_version=1, locked_at_utc=utc(), phase='population_and_seed_locked_before_draw',
        study_id=root.name, benchmark_source_file=str(benchmark), benchmark_source_sha256=digest(benchmark),
        benchmark_source_commit=old['benchmark_source_commit'], benchmark_instance_count=111,
        native_loader='prompt_optimization.dataset_loaders.load_seal0_dataset', native_loader_seed=0,
        native_loader_no_split=True, native_loader_index_semantics='zero-based position after native seed0 shuffle; not parquet row ordinal or official unique ID',
        parent_population_size=110, parent_indices=list(range(START,STOP+1)),
        excluded_task_indices=excluded, excluded_subset_sha256=digest(OLD_SUBSET),
        population_size=95, sample_size=SIZE, random_seed=SEED,
        sampling_method='uniform_without_replacement',
        selection_order='ascending_existing_task_index_after_uniform_sample',
        population_order='ascending_existing_task_index_before_random_sample',
        performance_or_label_filtering_during_sampling=False, sample_draw_count=0,
        not_restricted_to_historical_clean94=True,
        generator_git_commit=git('rev-parse','HEAD'), generator_git_repository=str(CONTROL),
        generator_script='sampler/sample_seal0_remaining.py', generator_script_sha256=digest(Path(__file__)),
        python_version=platform.python_version(),
        locked_file_sha256={str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()},
        original_source_sha256={str(p):digest(p) for p in [benchmark,OLD_SUBSET,OLD_SAMPLER,LOADER,OLD_STUDY/'study_manifest.json',HIST_MANIFEST]})
    write_json(root/'sampling_protocol.json', protocol)
    print(json.dumps(dict(phase='index_locked', parent_population=110,excluded=15,eligible=95,seed=SEED,
                         protocol_sha256=digest(root/'sampling_protocol.json')),ensure_ascii=False))


def draw(root: Path) -> None:
    protocol_path=root/'sampling_protocol.json';p=json.loads(protocol_path.read_text())
    assert p['random_seed']==SEED and p['population_size']==95 and p['sample_size']==SIZE
    assert p['sample_draw_count']==0 and p['generator_script_sha256']==digest(Path(__file__))
    for relative, sha in p['locked_file_sha256'].items():
        assert digest(root/relative)==sha,relative
    population=root/'benchmark_snapshot/seal0_remaining_95.csv'
    rows=read_csv(population);ids=[int(r['index']) for r in rows]
    assert len(ids)==len(set(ids))==95 and ids==sorted(ids)
    assert set(ids)==set(range(START,STOP+1))-set(p['excluded_task_indices'])
    # Exactly one new draw. No alternate seed or replacement selection.
    selected=sorted(random.Random(SEED).sample(ids,SIZE))
    by_id={int(r['index']):r for r in rows}
    subset_path=root/'benchmark_snapshot/seal0_remaining95_sample15_seed43.json'
    old=json.loads((root/'source_snapshot/previous_subset_seed42.json').read_text())
    subset=dict(schema_version=1,benchmark=old['benchmark'],benchmark_source=old['benchmark_source'],
        benchmark_source_commit=p['benchmark_source_commit'],benchmark_source_file=str(root/'benchmark_snapshot/seal-0.parquet'),
        benchmark_source_file_sha256=p['benchmark_source_sha256'],benchmark_source_instance_count=111,
        benchmark_has_unique_official_instance_id=old['benchmark_has_unique_official_instance_id'],
        benchmark_canary_field_unique_value_count=old['benchmark_canary_field_unique_value_count'],
        population_definition='Existing native task indices1..110 minus the15 fixed seed42 tasks; no outcome, topic, cost, status, or clean94 filter',
        population_source_file=str(population),population_source_file_sha256=digest(population),population_size=95,
        population_task_id_field='index',population_task_id_semantics=p['native_loader_index_semantics'],
        population_question_exact_match_count_in_pinned_base_snapshot=95,population_question_nonmatch_task_indices_in_pinned_base_snapshot=[],
        parent_population_size=110,excluded_task_indices=p['excluded_task_indices'],previous_subset_file=str(root/'source_snapshot/previous_subset_seed42.json'),
        previous_subset_file_sha256=p['excluded_subset_sha256'],sample_size=SIZE,random_seed=SEED,
        sampling_method=p['sampling_method'],selection_order=p['selection_order'],generated_at_utc=utc(),
        python_version=platform.python_version(),generator_git_commit=p['generator_git_commit'],generator_git_repository=p['generator_git_repository'],
        generator_script_sha256=p['generator_script_sha256'],sampling_protocol_sha256=digest(protocol_path),
        performance_or_label_filtering_during_sampling=False,sample_draw_count=1,
        selected_tasks=[dict(task_index=i,question=by_id[i]['question'],benchmark_row_index=int(by_id[i]['benchmark_row_index']),goal_sha256=by_id[i]['goal_sha256']) for i in selected],
        run_reporting=dict(actual_completed_tasks_by_condition={},common_completed_tasks_across_conditions=None,status='not_run',
                           note='Record realized completion/common counts in a separate immutable run report.'))
    write_json(subset_path,subset)
    selected_rows=[by_id[i] for i in selected]
    write_csv(root/'selected_tasks_15.csv',selected_rows,list(rows[0]))
    canonical=CONTROL/'benchmark_subsets'/subset_path.name
    write_once(canonical,subset_path.read_bytes())
    manifest=dict(schema_version=1,study_id=root.name,status='sampling_frozen_not_run',created_at_utc=utc(),
        purpose='Second disjoint fixed-seed15 sample from the full native110 task frame, excluding the original15.',
        sampling=dict(population_size=95,parent_population_size=110,sample_size=15,seed=43,method=p['sampling_method'],
            selection_order=p['selection_order'],population_task_id_field='index',official_instance_id_available=False,
            selected_task_indices=selected,excluded_task_indices=p['excluded_task_indices'],
            subset_file=str(subset_path.relative_to(root)),subset_file_sha256=digest(subset_path),
            canonical_subset_file=str(canonical),canonical_subset_file_sha256=digest(canonical),
            population_file=str(population.relative_to(root)),population_file_sha256=digest(population),
            full_index_file='benchmark_snapshot/seal0_index_110.csv',full_index_file_sha256=digest(root/'benchmark_snapshot/seal0_index_110.csv'),
            protocol_file='sampling_protocol.json',protocol_sha256=digest(protocol_path)),
        benchmark_snapshot=dict(name='SEAL-0',source_file='benchmark_snapshot/seal-0.parquet',source_file_sha256=p['benchmark_source_sha256'],
            source_instance_count=111,loader=p['native_loader'],loader_seed=0,selected_task_mapping_validated=True),
        agent=dict(repository=str(HIRA/'forammas'),commit=p['benchmark_source_commit'],agent_core_modified=False),
        generator=dict(repository=p['generator_git_repository'],commit=p['generator_git_commit'],script=p['generator_script'],script_sha256=p['generator_script_sha256']),
        execution=dict(status='not_run',paper_runs=[],mlflow_runs=[]))
    write_json(root/'study_manifest.json',manifest)
    # Independent replay and source immutability checks; no resampling decision.
    reproduced=sorted(random.Random(SEED).sample(sorted(ids),SIZE))
    assert selected==reproduced and not set(selected).intersection(p['excluded_task_indices'])
    for original,sha in p['original_source_sha256'].items():assert digest(Path(original))==sha,original
    verification=dict(verified_at_utc=utc(),original_seed42_draw_reproduced=True,native_loader_all111_mappings_match=True,
        historical110_goal_hashes_match=True,previous15_question_mapping_match=True,new15_replay_matches=True,
        selected_unique=True,overlap_with_previous15=[],all_selected_in_remaining95=True,
        protocol_precedes_sample=True,source_files_unchanged=True,subset_sha256=digest(subset_path),
        manifest_sha256=digest(root/'study_manifest.json'),canonical_subset_bytes_match=True,sample_draw_count=1)
    write_json(root/'verification.json',verification)
    notes='# 第二组固定15题抽样留底\n\n范围：原生任务索引1–110，排除旧seed42的15题后共95题。新seed在抽样前固定为43，均匀无放回抽取一次；不按分数、成本、完成状态或题类筛选，也不限制到历史clean94。\n\n原生loader对111行使用seed=0打乱，现有任务编号是打乱后的零基索引；原历史BASE范围为1–110，索引0继续不在本次110题抽样框中。CSV同时保留Parquet原始行号、原生题号、题目原文及goal SHA256，避免编号漂移。\n\n新题号：'+', '.join(map(str,selected))+'。与原15题交集为0。\n\n留底包含原始数据快照、完整110索引、候选95索引、原seed42清单及参考脚本、native loader源码与实际索引导出、新抽样脚本与Git commit、抽样前protocol、subset JSON、逐题CSV、manifest、verification与checksums。此次尚未启动Agent或MLflow实验。\n\n复验（只读，不覆盖）：\n\n```text\n/opt/homebrew/bin/python3 sampler/sample_seal0_remaining.py --phase verify --study-root .\n```\n\n|题号|题目|\n|---:|---|\n'
    for i in selected:notes+=f"|{i}|{by_id[i]['question'].replace('|','\\|')}|\n"
    write_once(root/'README.md',notes.encode())
    files=sorted(f for f in root.rglob('*') if f.is_file() and f.name!='checksums.sha256')
    write_once(root/'checksums.sha256',''.join(digest(f)+'  '+str(f.relative_to(root))+'\n' for f in files).encode())
    verify(root)


def verify(root: Path) -> None:
    for line in (root/'checksums.sha256').read_text().splitlines():
        sha,relative=line.split('  ',1);assert digest(root/relative)==sha,relative
    m=json.loads((root/'study_manifest.json').read_text());s=m['sampling']
    subset=root/s['subset_file'];p=json.loads(subset.read_text())
    rows=read_csv(root/s['population_file']);ids=[int(r['index']) for r in rows]
    selected=sorted(random.Random(p['random_seed']).sample(ids,p['sample_size']))
    assert selected==[t['task_index'] for t in p['selected_tasks']]==s['selected_task_indices']
    assert digest(subset)==s['subset_file_sha256']
    assert Path(s['canonical_subset_file']).read_bytes()==subset.read_bytes()
    print(json.dumps(dict(status='verified_frozen_not_run',study_root=str(root),population_size=95,seed=43,
        selected_task_indices=selected,subset_sha256=digest(subset),sampler_commit=m['generator']['commit'],
        files_verified=len((root/'checksums.sha256').read_text().splitlines())),ensure_ascii=False))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=['index','sample','verify'])
    parser.add_argument('--study-root',required=True,type=Path)
    args=parser.parse_args();root=args.study_root.resolve()
    {'index':freeze_index,'sample':draw,'verify':verify}[args.phase](root)


if __name__=='__main__':main()
