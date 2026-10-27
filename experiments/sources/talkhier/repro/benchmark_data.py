"""External official-data mapping; native TalkHier graph/prompts/scoring are unchanged."""
import json
from pathlib import Path

from common import ROOT, MANIFEST, load_frozen
from sample_mmlu import verify_subset as verify_native_subset
from sample_mmlu_pro import verify as verify_pro_subset

PRO_MANIFEST = ROOT / 'repro/mmlu_pro_manifest.json'


def is_pro(directory):
    return bool(directory) and json.loads((Path(directory) / 'manifest.json').read_text()).get('dataset') == 'TIGER-Lab/MMLU-Pro'


def normalize(entry):
    row = entry['record']
    return {'question': row['question'], 'choices': list(row['options']), 'answer': row['answer_index'],
            'subject': 'college_physics', 'official_question_id': row['question_id'],
            'physics_index': entry['physics_index'], 'split_row_index': entry['split_row_index']}


def verify_subset(directory):
    if not is_pro(directory):
        return verify_native_subset(directory)
    manifest = verify_pro_subset(directory)
    entries = [json.loads(line) for line in (Path(directory) / 'questions.jsonl').read_text().splitlines()]
    # The native worker indexes dataset['test'][problem_id]. Preserve the full
    # official split row index there; never substitute question_id or sample rank.
    adapted = {**manifest, 'mode': 'college_physics', 'native_domain_mapping': 'Physics -> college_physics'}
    questions = [{'problem_id': entry['split_row_index'], 'question': normalize(entry),
                  'official_question_id': entry['question_id']} for entry in entries]
    return adapted, questions


def benchmark_manifest(directory=None):
    return PRO_MANIFEST if is_pro(directory) else MANIFEST


class PhysicsRows:
    def __init__(self, entries, size):
        self.rows = {entry['split_row_index']: normalize(entry) for entry in entries}
        self.size = size

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        if index not in self.rows:
            raise IndexError('This original MMLU-Pro test row is not a Physics question')
        return dict(self.rows[index])


def load_benchmark(mode, directory=None):
    if not is_pro(directory):
        return load_frozen(mode)
    if mode != 'college_physics':
        raise ValueError('MMLU-Pro Physics must use the existing native college_physics graph')
    verify_pro_subset(directory)
    source = json.loads(PRO_MANIFEST.read_text())
    entries = [json.loads(line) for line in (ROOT / source['physics']['test']['path']).read_text().splitlines()]
    return {'test': PhysicsRows(entries, source['split_counts']['test'])}
