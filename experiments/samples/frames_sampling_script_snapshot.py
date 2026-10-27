"""Build a source-aligned FRAMES index and one prospective SSRS candidate; no API calls."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('external_archive/2026-10-02/frames')
DEFAULT_OUT = ROOT / 'outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames80_index_20261004'
LABELS = ['Numerical reasoning', 'Tabular reasoning', 'Multiple constraints',
          'Temporal reasoning', 'Post processing']
SEED = 20261003  # Proposed before this draw in the 2026-10-03 design record.
N_SAMPLE = 80


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))


def links(value):
    parsed = value if isinstance(value, list) else ast.literal_eval(value)
    assert isinstance(parsed, list) and all(isinstance(v, str) and v for v in parsed)
    return parsed


def stratum(row):
    n = len(links(row['wiki_links']))
    labels = {v.strip() for v in row['reasoning_types'].split('|') if v.strip()}
    assert n >= 2 and labels and labels <= set(LABELS)
    return f"E{n if n < 5 else '5+'}_L{'1' if len(labels) == 1 else '2+'}"


def allocate(counts, n):
    total = sum(counts.values())
    q = {h: n * counts[h] // total for h in sorted(counts)}
    order = sorted(counts, key=lambda h: (-(n * counts[h] % total), h))
    for h in order[:n - sum(q.values())]:
        q[h] += 1
    assert sum(q.values()) == n and all(0 < q[h] <= counts[h] for h in counts)
    return q


def csv_write(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise SystemExit(f'Refusing to overwrite: {out}')
    prior_path = ROOT / 'outputs/frames_sampling_plan_20261003.json'
    prior = json.loads(prior_path.read_text())
    source = {k: Path(v['path']) for k, v in prior['source_files'].items()}
    for k, path in source.items():
        assert sha(path) == prior['source_files'][k]['sha256'], (k, 'source changed')
    tasks = [json.loads(x) for x in source['tasks'].read_text().splitlines() if x.strip()]
    with source['raw_tsv'].open(newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        fieldnames = reader.fieldnames
        raw = list(reader)
    by_id = {str(r['task_id']): r for r in tasks}
    by_prompt = {r['goal']: str(r['task_id']) for r in tasks}
    assert len(raw) == len(tasks) == len(by_id) == len(by_prompt) == 824
    normalized = Counter(' '.join(r['goal'].split()) for r in tasks)
    assert max(normalized.values()) == 1
    for r in raw:
        t = by_id[r['']]
        assert (r['Prompt'], r['Answer'], r['reasoning_types'], links(r['wiki_links'])) == (
            t['goal'], t['answer'], t['reasoning_types'], links(t['wiki_links']))
        assert t['source_row'] == r
        assert len(set(links(r['wiki_links']))) == len(links(r['wiki_links']))
    exposures = defaultdict(list)
    archives = []
    archive_root = Path(prior['historical_archive_scope']['root'])
    for p in sorted(archive_root.glob('*/manifest.json')):
        m = json.loads(p.read_text())
        b = m['benchmark']
        file = Path(b['file'])
        with file.open(newline='') as f:
            rr = list(csv.DictReader(f, delimiter='\t'))
        random.Random(b.get('seed', 0)).shuffle(rr)
        selected = [by_prompt[rr[i]['Prompt']] for i in b['selected_indices']]
        record = {'manifest': str(p), 'sha256': sha(p), 'condition': m['condition'],
                  'benchmark_file': str(file), 'benchmark_sha256': sha(file),
                  'loader_seed': b.get('seed', 0), 'planned_official_ids': selected}
        archives.append(record)
        for q in selected:
            exposures[q].append(str(p))
    assert len(archives) == 13 and len(exposures) == 41
    assert set(exposures) == set(prior['historical_archive_scope']['planned_official_ids'])
    eligible = [r for r in tasks if str(r['task_id']) not in exposures]
    assert len(eligible) == 783
    groups = {h: sorted([r for r in eligible if stratum(r) == h], key=lambda r: int(r['task_id']))
              for h in sorted({stratum(r) for r in eligible})}
    counts = {h: len(rr) for h, rr in groups.items()}
    quotas = allocate(counts, N_SAMPLE)
    assert len(groups) == 8
    prior_quotas = {f"E{r['evidence_articles']}_L{r['reasoning_label_count']}": r['quota80']
                    for r in prior['allocations']['archive_unplanned783']['strata']}
    assert quotas == prior_quotas
    shuffled_full = list(raw)
    random.Random(0).shuffle(shuffled_full)
    full_loader = {r['']: i for i, r in enumerate(shuffled_full)}
    index = []
    for source_position, r in enumerate(raw):
        q = r['']; t = by_id[q]; h = stratum(t)
        lab = [v for v in LABELS if v in {z.strip() for z in t['reasoning_types'].split('|')}]
        exposure_paths = exposures.get(q, [])
        good = not exposure_paths
        index.append({'official_task_id': q, 'source_record_index0': source_position,
                      'goal': t['goal'], 'goal_sha256': hashlib.sha256(t['goal'].encode()).hexdigest(),
                      'goal_character_count': len(t['goal']), 'reasoning_labels': lab,
                      'reasoning_label_count': len(lab), 'reasoning_combination': ' | '.join(lab),
                      'wiki_links': links(t['wiki_links']), 'evidence_article_count': len(links(t['wiki_links'])),
                      'evidence_band': h.split('_')[0][1:], 'stratum': h,
                      'prior_planned_archive_count': len(exposure_paths),
                      'prior_planned_archive_paths': exposure_paths,
                      'eligible_in_archive_unplanned783': good,
                      'eligibility_reason': 'not_planned_in_13_audited_archives' if good else 'planned_in_audited_archive',
                      'full824_loader_index_seed0': full_loader[q],
                      'inclusion_probability_if_sampled': quotas[h] / counts[h] if good else 0,
                      'inverse_probability_weight_if_sampled': counts[h] / quotas[h] if good else None,
                      'population_mean_weight_if_sampled': counts[h] / (783 * quotas[h]) if good else None,
                      'selected80': False, 'selected80_source_order_index0': None,
                      'selected80_loader_index_seed0': None})
    # Save the complete source-aligned index before doing the one random draw.
    out.mkdir(parents=True)
    jsonl(out / 'population_index_before_selection.jsonl', index)
    rng = random.Random(SEED)
    draw_order = []
    for h in sorted(groups):
        draw_order.extend(str(r['task_id']) for r in rng.sample(groups[h], quotas[h]))
    chosen = set(draw_order)
    assert len(chosen) == N_SAMPLE and not chosen.intersection(exposures)
    chosen_raw = [r for r in raw if r[''] in chosen]
    subset_source = {r['']: i for i, r in enumerate(chosen_raw)}
    shuffled_subset = list(chosen_raw)
    random.Random(0).shuffle(shuffled_subset)
    subset_loader = {r['']: i for i, r in enumerate(shuffled_subset)}
    for r in index:
        q = r['official_task_id']; r['selected80'] = q in chosen
        r['selected80_source_order_index0'] = subset_source.get(q)
        r['selected80_loader_index_seed0'] = subset_loader.get(q)
    candidate = [r for r in index if r['selected80']]
    jsonl(out / 'population_index.jsonl', index)
    jsonl(out / 'candidate80_index.jsonl', candidate)
    jsonl(out / 'candidate80_tasks_native.jsonl', [by_id[r['official_task_id']] for r in candidate])
    (out / 'candidate80_official_ids.txt').write_text(''.join(r['official_task_id'] + '\n' for r in candidate))
    with (out / 'candidate80_native_test.tsv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(chosen_raw)
    flat = []
    for r in index:
        row = {k: v for k, v in r.items() if not isinstance(v, list)}
        row['reasoning_labels'] = ' | '.join(r['reasoning_labels'])
        row['wiki_links'] = json.dumps(r['wiki_links'], ensure_ascii=False)
        row['prior_planned_archive_paths'] = ' | '.join(r['prior_planned_archive_paths'])
        flat.append(row)
    csv_write(out / 'population_index.csv', flat, list(flat[0]))
    csv_write(out / 'candidate80_index.csv', [r for r in flat if r['selected80']], list(flat[0]))
    strata = []
    for h in sorted(groups):
        n = sum(r['stratum'] == h for r in candidate); N = counts[h]
        assert n == quotas[h]
        strata.append({'stratum': h, 'population_count': N, 'sample_count': n,
                       'population_fraction': N / 783, 'sample_fraction': n / 80,
                       'difference_pp': 100 * (n / 80 - N / 783),
                       'inclusion_probability': n / N,
                       'inverse_probability_weight': N / n,
                       'population_mean_weight_per_question': N / (783 * n)})
    label_stats = []
    for label in LABELS:
        total = sum(label in r['reasoning_types'] for r in eligible)
        sample = sum(label in r['reasoning_labels'] for r in candidate)
        weighted = 0.; variance = 0.
        for h, rr in groups.items():
            N = counts[h]; n = quotas[h]; K = sum(label in r['reasoning_types'] for r in rr)
            k = sum(label in r['reasoning_labels'] and r['stratum'] == h for r in candidate)
            p = K / N; w = N / 783
            weighted += w * k / n
            variance += w * w * (1 - n / N) * (N / (N - 1)) * p * (1 - p) / n
        sd = math.sqrt(variance)
        label_stats.append({'label': label, 'population_count': total, 'sample_count': sample,
                            'population_rate': total / 783, 'sample_unweighted_rate': sample / 80,
                            'sample_weighted_rate': weighted,
                            'weighted_difference_pp': 100 * (weighted - total / 783),
                            'design_sd_pp_for_this_known_covariate': 100 * sd,
                            'standardized_deviation_diagnostic_only': (weighted - total / 783) / sd if sd else None})
    combo_counts = Counter(' | '.join(v for v in LABELS if v in r['reasoning_types']) for r in eligible)
    sample_combo = Counter(r['reasoning_combination'] for r in candidate)
    cell_counts = Counter((stratum(r).split('_')[0], ' | '.join(v for v in LABELS if v in r['reasoning_types'])) for r in eligible)
    sample_cells = Counter((r['stratum'].split('_')[0], r['reasoning_combination']) for r in candidate)
    fine = {'population_combinations': len(combo_counts), 'sample_combinations': len(sample_combo),
            'population_fine_joint_cells': len(cell_counts), 'sample_fine_joint_cells': len(sample_cells),
            'unsampled_combinations': [{'combination': h, 'population_count': combo_counts[h]}
                                        for h in sorted(combo_counts) if not sample_combo[h]]}
    checks = {'824_source_rows_aligned': True, 'official_ids_unique': True, 'normalized_prompts_unique': True,
              'parsed_evidence_lists_without_duplicates': True, '783_frame_and_41_exclusions_reproduced': True,
              '8_nonoverlapping_exhaustive_strata': True, 'all_eligible_tasks_have_positive_inclusion_probability': True,
              '80_unique_drawn_without_replacement': True, '80_quotas_match_prior_proposal': True,
              'zero_overlap_with_41_archived_planned_ids': True,
              'native80_tsv_and_index_and_jsonl_agree': True,
              'full824_and_native80_loader_mappings_separate': True,
              'no_outcome_or_cost_based_selection': True}
    # Independently reload native data and the two different loader maps.
    with (out / 'candidate80_native_test.tsv').open(newline='') as f:
        native80 = list(csv.DictReader(f, delimiter='\t'))
    assert {r[''] for r in native80} == chosen
    for r in native80:
        assert r == next(x for x in raw if x[''] == r[''])
    replay_rng = random.Random(SEED)
    replay = []
    for h in sorted(groups):
        replay.extend(str(r['task_id']) for r in replay_rng.sample(groups[h], quotas[h]))
    assert replay == draw_order
    checks['seed_replay_exactly_matches'] = True
    tv = .5 * sum(abs(r['sample_fraction'] - r['population_fraction']) for r in strata)
    audit = {'status': 'sampling_design_verified_candidate_only', 'client_date_beijing': '2026-10-04',
             'sample_size': 80, 'population_all': 824, 'target_frame': 783,
             'historical_excluded': 41, 'seed': SEED, 'seed_search': False,
             'strata': strata, 'label_descriptive_balance': label_stats, 'fine_coverage': fine,
             'coarse_total_variation': tv, 'max_absolute_coarse_difference_pp': max(abs(r['difference_pp']) for r in strata),
             'checks': checks, 'selection_scope': 'Archive-unplanned 783-task pool, not official full824 performance.',
             'history_scope_note': 'Exclusion is based on planned IDs in 13 specified archives. Extra metadata file paths were surveyed; controller totals without task-source mappings do not certify complete absence of other development exposure.',
             'statistical_scope': 'SSRS with positive inclusion probabilities and N_h/N stratum weighting permits design-unbiased finite-frame estimates when complete outcomes are available. Metadata balance does not prove effect precision, intervention control, or absence of execution noise.',
             'no_paid_agent_or_grader_calls': True, 'agent_core_modified': False,
             'main_analysis': 'For each question average available valid matched V2-BASE repeats; estimate sum_h (N_h/783)*mean_h(d_i). Report question-equal sensitivity, question-level uncertainty, and missing coverage separately.',
             'sources': ['https://www150.statcan.gc.ca/n1/pub/12-001-x/2019002/article/00006/02-eng.htm',
                         'https://arxiv.org/html/2411.00640v1']}
    dump(out / 'sampling_audit.json', audit)
    dump(out / 'historical_exposure_index.json', {'archives': archives, 'excluded_official_ids': sorted(exposures, key=int)})
    dump(out / 'workbook_input.json', {'index': index, 'candidate': candidate, 'audit': audit})
    csv_write(out / 'strata80_quotas.csv', strata, list(strata[0]))
    command = f'{sys.executable} {Path(__file__).resolve()} --output {out}\n'
    (out / 'command.txt').write_text(command)
    (out / 'sampling_script_snapshot.py').write_bytes(Path(__file__).read_bytes())
    manifest = {'schema_version': 1, 'client_date_beijing': '2026-10-04', 'status': 'candidate_list_not_experiment_run',
                'sampling_method': '8-stratum proportional simple random sampling without replacement; largest-remainder integer quotas',
                'seed': SEED, 'seed_predeclared_record': str(prior_path), 'seed_predeclared_record_sha256': sha(prior_path),
                'seed_search': False, 'draw_algorithm': 'random.Random(seed).sample; strata and eligible official numeric IDs sorted; sequential draw',
                'python_version': sys.version, 'target_frame_N': 783, 'sample_n': 80,
                'source_files': {k: {'path': str(p), 'sha256': sha(p)} for k, p in source.items()},
                'archive_manifests': archives, 'sampling_script_sha256': sha(Path(__file__)),
                'selected_official_ids_in_source_order': [r['official_task_id'] for r in candidate],
                'selected_official_ids_in_draw_order': draw_order,
                'native_loader_mapping': 'Both mappings use random.Random(0).shuffle; full824 mapping must not be used for native80 file.',
                'outputs_sha256': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    dump(out / 'selection_manifest.json', manifest)
    print(json.dumps({'output': str(out), 'index_rows': len(index), 'candidate_rows': len(candidate),
                      'coarse_tv_percent': 100 * tv, 'max_coarse_deviation_pp': audit['max_absolute_coarse_difference_pp'],
                      'labels': label_stats, 'fine_coverage': fine, 'all_checks': all(checks.values())}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
