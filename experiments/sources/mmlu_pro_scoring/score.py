"""Offline official MMLU-Pro exact-match scoring of frozen native TalkHier choices."""
import argparse
import ast
from collections import Counter
import csv
import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BATCH = ROOT / '.local/batches/20261006T090617775637Z_mmlu_pro_physics_n100_seed42_tb8192_mc16384_gw16x16'
SUBSET = ROOT / 'repro/subsets/mmlu_pro_physics_test_n100_seed42'
OUTPUT = ROOT / '.local/evaluations/20261006T090617775637Z_mmlu_pro_exact_match'
EXPECTED_SUBSET = '3a74f4669898b1e7521dae29e6cbc154857ed2ea447acf4d800da522ce0984c6'
EXPECTED_COMMIT = '0cddfdc3581bafb969b9d71e68dbeca1c4e6bdde'
sys.path.insert(0, str(ROOT / 'repro'))
from run_archive import RunArchive, digest, verify_archive, write, now


def official_functions():
    origin = json.loads((HERE / 'official_source.json').read_text())
    for name, info in origin['files'].items():
        assert digest(HERE / name) == info['sha256'], name
    tree = ast.parse((HERE / 'evaluate_from_api.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in origin['selected_functions']]
    assert {n.name for n in functions} == {'update_result', 'save_summary'}
    namespace = dict(os=os, json=json, random=random, time=time)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(HERE / 'evaluate_from_api.py'), 'exec'), namespace)
    return namespace


def collect(require_terminal=False):
    assert digest(SUBSET / 'manifest.json') == EXPECTED_SUBSET
    sample = json.loads((SUBSET / 'manifest.json').read_text())
    for name, expected in sample['files_sha256'].items():
        assert digest(SUBSET / name) == expected, name
    entries = [json.loads(line) for line in (SUBSET / 'questions.jsonl').read_text().splitlines()]
    assert len(entries) == 100
    ids = {str(e['split_row_index']) for e in entries}
    parent = json.loads((BATCH / 'manifest.json').read_text())
    assert parent['workspace_commit'] == EXPECTED_COMMIT
    assert parent['sample_manifest_sha256'] == EXPECTED_SUBSET
    assert set(parent['conditions']) == {'BASE', 'V2'}
    rows, predictions, summaries, proofs = [], {}, {}, []
    for arm, tasks in parent['conditions'].items():
        assert set(tasks) == ids
        predictions[arm] = []
        counts = Counter()
        for e in entries:
            pid = e['split_row_index']; record = e['record']; task = tasks[str(pid)]
            directory = Path(task['directory'])
            assert directory.resolve() == (BATCH / arm / f'q{pid}').resolve()
            state = json.loads((directory / 'manifest.json').read_text()) if (directory / 'manifest.json').exists() else task
            status = state['status']; counts[status] += 1
            if require_terminal:
                assert status not in {'running', 'starting', 'queued'}, (arm, pid, status)
                assert task['status'] == status, (arm, pid, 'parent/child mismatch')
                proof = verify_archive(directory)
                assert proof['valid'], (arm, pid, proof)
                completion = json.loads((directory / 'completion.json').read_text())
                assert not completion['live_source_changes'], (arm, pid, 'source changed')
                proofs.append({'condition': arm, 'problem_id': pid, 'directory': str(directory), **proof})
            gold = record['answer']; gi = record['answer_index']
            assert 'ABCDEFGHIJ'[gi] == gold
            answer = None; pred = None; correct = None
            native = directory / 'native_results.csv'
            if status == 'completed':
                with native.open() as stream:
                    data = list(csv.DictReader(stream))
                assert len(data) == 1
                native_row = data[0]
                assert int(native_row['Problem ID']) == pid
                assert int(native_row['Correct Answer']) == gi
                answer = int(native_row['Answer'])
                assert 0 <= answer < len(record['options']) <= 10, (arm, pid, answer)
                pred = 'ABCDEFGHIJ'[answer]; correct = pred == gold
                assert correct == (answer == gi)
                assert task['result']['answer'] == answer and task['result']['gold'] == gi
                predictions[arm].append({**record, 'pred': pred, 'split_row_index': pid,
                    'native_answer_index': answer, 'prediction_origin': 'native_results.csv structured final Answer; ordinal-to-letter mapping, no text extraction'})
            rows.append({'condition': arm, 'problem_id': pid, 'official_question_id': e['question_id'],
                'physics_index': e['physics_index'], 'status': status, 'gold': gold,
                'gold_index': gi, 'option_count': len(record['options']), 'answer_index': answer,
                'pred': pred, 'correct': None if correct is None else int(correct),
                'native_results_sha256': digest(native) if native.exists() else None,
                'child_directory': str(directory), 'mlflow_run_id': state.get('mlflow', {}).get('run_id')})
        valid = [r for r in rows if r['condition'] == arm and r['correct'] is not None]
        n = len(valid); c = sum(r['correct'] for r in valid)
        summaries[arm] = {'planned': 100, 'status_counts': dict(counts), 'scored': n,
            'correct': c, 'wrong': n-c, 'missing_or_noncompleted': 100-n,
            'accuracy_on_scored': c/n if n else None,
            'correct_answer_yield_on_fixed_100': c/100,
            'yield_definition': 'correct / all 100 planned questions; missing states retained, not relabeled as wrong answers'}
    if require_terminal:
        assert parent['status'] in {'completed', 'completed_with_errors', 'error', 'interrupted'}
        proof = verify_archive(BATCH); assert proof['valid'], proof
        completion = json.loads((BATCH / 'completion.json').read_text())
        assert not completion['live_source_changes']
        receipt = json.loads((ROOT / '.local/run_index' / (parent['launch_id'] + '.json')).read_text())
        assert receipt['index_status'] == 'finished', 'parent MLflow archival is still pending'
        proofs.append({'condition': 'parent', 'directory': str(BATCH), **proof})
    return parent, rows, predictions, summaries, proofs


def score_official(namespace, records, path):
    assert records and all(r['pred'] in 'ABCDEFGHIJ' and r['pred'] == 'ABCDEFGHIJ'[r['native_answer_index']] for r in records)
    write(path, records)
    loaded, counts = namespace['update_result'](str(path))
    assert len(loaded) == len(records)
    namespace['save_summary'](counts, str(path.with_name('physics_summary.json')))
    return counts['total']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true', help='Require completed and sealed parent/children; create independent scoring Run and archive')
    args = parser.parse_args()
    namespace = official_functions()
    if not args.final:
        parent, rows, predictions, summaries, _ = collect()
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            for n in (7, 9, 10):
                fixture = [{'category': 'physics', 'pred': 'ABCDEFGHIJ'[i], 'answer': 'A', 'answer_index': 0,
                            'native_answer_index': i, 'options': ['choice']*n} for i in (0, n-1)]
                result = score_official(namespace, fixture, Path(temp) / 'fixture.json')
                assert result == {'corr': 1.0, 'wrong': 1.0, 'acc': 0.5}
            for arm in predictions:
                result = score_official(namespace, predictions[arm], Path(temp) / f'{arm}.json')
                assert result['corr'] == summaries[arm]['correct'] and result['acc'] == summaries[arm]['accuracy_on_scored']
        validation = {'validated_at_utc': now(), 'batch_status': parent['status'], 'official_equivalence': True,
            'option_count_fixtures': [7, 9, 10], 'model_calls': 0, 'grader_calls': 0, 'final_scoring_started': False,
            'current_counts_for_validation_only': summaries}
        write(HERE / 'validation.json', validation)
        print(json.dumps(validation, ensure_ascii=False)); return
    if OUTPUT.exists():
        assert verify_archive(OUTPUT)['valid']
        completion = json.loads((OUTPUT / 'completion.json').read_text())
        assert completion['status'] == 'completed', 'Prior scoring attempt needs review; never overwrite it'
        launch = json.loads((OUTPUT / 'launch.json').read_text())
        receipt = json.loads((ROOT / '.local/run_index' / (launch['launch_id'] + '.json')).read_text())
        assert receipt['index_status'] == 'finished', 'Scoring MLflow index needs review'
        print(json.dumps({'already_archived': str(OUTPUT)})); return
    parent = json.loads((BATCH / 'manifest.json').read_text())
    if parent['status'] == 'running' or not (BATCH / 'archive_manifest.json').exists():
        print(json.dumps({'status': 'waiting_for_terminal_sealed_batch', 'model_calls': 0})); raise SystemExit(75)
    parent, rows, predictions, summaries, proofs = collect(require_terminal=True)
    parameters = {'benchmark': 'MMLU-Pro Physics fixed test n100 seed42', 'scoring': 'official valid-prediction exact match',
        'parent_batch': str(BATCH), 'parent_archive_sha256': digest(BATCH / 'archive_manifest.json'),
        'subset_manifest_sha256': EXPECTED_SUBSET, 'official_scoring_commit': json.loads((HERE / 'official_source.json').read_text())['commit'],
        'scoring_script_sha256': digest(Path(__file__)), 'model_calls': 0, 'grader_calls': 0,
        'missing_prediction_policy': 'unscored; no random fallback; fixed-sample correct-answer yield reported separately'}
    archive = RunArchive(OUTPUT, kind='offline_scoring', parameters=parameters,
        command=[sys.executable, str(Path(__file__).resolve()), '--final'], parent_run_id=parent['mlflow']['run_id'])
    try:
        shutil.copytree(HERE, OUTPUT / 'scoring_source')
        shutil.copytree(SUBSET, OUTPUT / 'sample')
        (OUTPUT / 'inputs').mkdir(exist_ok=True)
        for name in ('manifest.json', 'paired_results.csv', 'archive_manifest.json', 'checksums.sha256', 'completion.json'):
            shutil.copyfile(BATCH / name, OUTPUT / 'inputs' / name)
        for row in rows:
            native = Path(row['child_directory']) / 'native_results.csv'
            if native.exists():
                target = OUTPUT / 'inputs/native_results' / row['condition'] / f"q{row['problem_id']}.csv"
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(native, target)
        official = {}
        for arm, records in predictions.items():
            folder = OUTPUT / arm; folder.mkdir()
            official[arm] = score_official(namespace, records, folder / 'physics_result.json')
            assert official[arm]['acc'] == summaries[arm]['accuracy_on_scored']
        by_arm = {arm: {r['problem_id']: r for r in rows if r['condition'] == arm} for arm in predictions}
        paired = [pid for pid in by_arm['BASE'] if by_arm['BASE'][pid]['correct'] is not None and by_arm['V2'][pid]['correct'] is not None]
        transitions = Counter(f"{by_arm['BASE'][pid]['correct']}->{by_arm['V2'][pid]['correct']}" for pid in paired)
        paired_summary = {'both_scored': len(paired), 'transitions_BASE_to_V2': dict(transitions),
            'BASE_correct': sum(by_arm['BASE'][p]['correct'] for p in paired),
            'V2_correct': sum(by_arm['V2'][p]['correct'] for p in paired)}
        paired_summary['V2_minus_BASE_percentage_points'] = 100*(paired_summary['V2_correct']-paired_summary['BASE_correct'])/len(paired) if paired else None
        report = {'scored_at_utc': now(), 'scope': 'fixed 100 Physics questions; not full MMLU-Pro or official few-shot inference protocol',
            'parameters': parameters, 'conditions': summaries, 'official_summaries': official, 'paired': paired_summary,
            'runtime_concurrency_note': 'BASE16/V216 initially; user authorized V2 capacity32 at 2026-10-06T10:53:25Z; realized peak29',
            'no_new_inference': True, 'missing_predictions_randomly_filled': False}
        with (OUTPUT / 'per_question_scores.csv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        write(OUTPUT / 'input_archive_verification.json', proofs)
        write(OUTPUT / 'score_summary.json', report)
        write(OUTPUT / 'manifest.json', {**archive.identity, 'status': 'completed', 'parameters': parameters})
        metrics = {f'{arm}_accuracy_on_scored': s['accuracy_on_scored'] for arm, s in summaries.items()}
        metrics.update({f'{arm}_correct_answer_yield_on_fixed_100': s['correct_answer_yield_on_fixed_100'] for arm,s in summaries.items()})
        metrics['paired_count'] = len(paired)
        archive.finalize('completed', metrics=metrics)
        print(json.dumps({'archive': str(OUTPUT), 'mlflow_run_id': archive.run_id, 'summary': report}, ensure_ascii=False))
    except BaseException as error:
        if not archive.sealed:
            archive.finalize('error', error={'type': type(error).__name__, 'message': str(error)})
        raise


if __name__ == '__main__':
    main()
