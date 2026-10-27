"""SCORER INPUT COPIES ONLY. Offline; originals and prior artifacts are read-only.

Flatten the earlier research encoding into ordered lists of direct original-text
blocks. No dictionary entry references another entry; no model calls or scores.
"""
import sys
sys.dont_write_bytecode = True
import concurrent.futures as cf
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PREVIOUS = ROOT / 'outputs/mab_compression_feasibility_20261004_sample1'
BASE = ROOT / 'outputs/mab_native_coverage_all94_20261003'
OLD_MARKER = '\n\n[COMPLETE EXACT BODY DICTIONARY]\n'
OLD_REF = re.compile(r'\[\[BODY_SHA256:([0-9a-f]{64})\]\]')
FLAT_REF = re.compile(r'\[\[SCORER_BLOCKS:(B[0-9]{4,}(?:,B[0-9]{4,})*)\]\]')
FLAT_MARKER = '\n\n[SCORER INPUT ONLY: COMPLETE FLAT ORIGINAL-TEXT BLOCK DICTIONARY]\n'

def sha(data): return hashlib.sha256(data).hexdigest()
def js(x): return json.dumps(x, ensure_ascii=False, indent=2)
def write(path, x): path.write_text(js(x) + '\n')
def gz(path, data): path.write_bytes(gzip.compress(data, mtime=0))

def setup():
    global audit, previous
    def imp(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module
    audit = imp('readonly_original_audit', ROOT / 'outputs/mab_native_coverage_20261003/audit_coverage.py')
    audit.setup()
    previous = imp('readonly_previous_size_experiment', PREVIOUS / 'estimate.py')

class FlatBlocks:
    def __init__(self, nested):
        self.nested = nested; self.blocks = {}; self.sequences = {}; self.depths = {}
        for h in sorted(nested): self.flatten(h)
        self.ids = {h:f'B{i:04d}' for i,h in enumerate(sorted(self.blocks),1)}
        self.by_id = {self.ids[h]:body for h,body in self.blocks.items()}
        self.references = 0; self.max_blocks_per_reference = 0

    def literal(self, body):
        h = sha(body.encode())
        if h in self.blocks and self.blocks[h] != body: raise ValueError('Hash collision')
        self.blocks[h] = body
        return h

    def flatten(self, h, stack=()):
        if h in self.sequences: return self.sequences[h]
        if h in stack: raise ValueError('Cyclic old dictionary')
        body = self.nested[h]['body']; matches = list(OLD_REF.finditer(body))
        sequence = []; depths = []; start = 0
        for m in matches:
            if m.start() > start: sequence.append(self.literal(body[start:m.start()]))
            sequence.extend(self.flatten(m.group(1),stack+(h,)))
            depths.append(self.depths[m.group(1)]); start = m.end()
        if start < len(body): sequence.append(self.literal(body[start:]))
        if not matches and not body: sequence.append(self.literal(''))
        original = ''.join(self.blocks[x] for x in sequence)
        if sha(original.encode()) != h: raise ValueError('Old dictionary does not reconstruct')
        self.sequences[h] = sequence; self.depths[h] = 1 + max(depths,default=0)
        return sequence

    def convert(self, text):
        if not isinstance(text,str): return text
        if '[[SCORER_BLOCKS:' in text: raise ValueError('New reference marker collision')
        def sub(m):
            seq = self.sequences[m.group(1)]
            self.references += 1; self.max_blocks_per_reference = max(self.max_blocks_per_reference,len(seq))
            return '[[SCORER_BLOCKS:' + ','.join(self.ids[h] for h in seq) + ']]'
        return OLD_REF.sub(sub,text)

    def expand(self, text):
        return FLAT_REF.sub(lambda m: ''.join(self.by_id[k] for k in m.group(1).split(',')),text)

    def footer(self):
        return FLAT_MARKER + js({
            'artifact_purpose':'SCORER_INPUT_ONLY; derived representation, not an original trajectory',
            'reference_notation':'[[SCORER_BLOCKS:B0001,B0002,...]]',
            'meaning':'Replace each marker by concatenating the listed complete original-text blocks in order, with no separator. Every block below is literal original text and contains no further references. All calls, retries, message occurrences, identities and ordering are preserved. Identical text sharing does not merge events or assert that they are the same action.',
            'definitions':[{'block_id':self.ids[h],'original_text':body} for h,body in sorted(self.blocks.items())]})

def checksum_set(folder):
    entries = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        expected, rel = line.split('  ',1); actual = sha((folder / rel).read_bytes())
        if actual != expected: raise ValueError(f'Frozen prior artifact changed: {rel}')
        entries[rel] = expected
    entries['SHA256SUMS'] = sha((folder / 'SHA256SUMS').read_bytes())
    return entries

def one(base):
    trace = Path(base['trace_directory'])
    inputs, records, profiles, checkpoint, graph = audit.build(base, OUT / '_never_written', {})
    if sha((js(inputs)+'\n').encode()) != base['input_sha256']: raise ValueError('Baseline input mismatch')
    for path,h in base['source_hashes'].items():
        if sha(Path(path).read_bytes()) != h: raise ValueError('Original source hash mismatch')
    calls = records['raw_llm_events.jsonl'][1]
    contents = [(m.get('role'),m['content']) for row in calls for m in (row.get('request') or {}).get('messages',[]) if isinstance(m.get('content'),str)]
    contents += [(p['message'].get('role'),p['message']['content']) for p in profiles if isinstance(p['message'].get('content'),str)]
    if any('[[SCORER_BLOCKS:' in t or FLAT_MARKER in t for _,t in contents): raise ValueError('Marker collision')
    nested = previous.Codec(contents,'combined')
    encoded_calls = copy.deepcopy(calls); encoded_profiles = copy.deepcopy(profiles)
    for row in encoded_calls:
        for m in (row.get('request') or {}).get('messages',[]):
            if isinstance(m.get('content'),str): m['content'] = nested.convert(m['content'])
    for p in encoded_profiles:
        if isinstance(p['message'].get('content'),str): p['message']['content'] = nested.convert(p['message']['content'])
    # Reproduce the frozen earlier research variant before changing its representation.
    nested_ledger = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in encoded_calls).encode()
    old_interactions = audit.fmt.block('raw_llm_events.jsonl',nested_ledger)+'\n'+audit.fmt.block('raw_tool_events.jsonl',records['raw_tool_events.jsonl'][0])
    old_copy = {d:dict(v) for d,v in inputs.items()}
    old_copy['planning']['results'] = old_interactions
    old_copy['planning']['agent_profiles'] = js(encoded_profiles)+nested.footer()
    old_copy['communication']['communications'] = old_interactions+nested.footer()
    frozen_old = (PREVIOUS / 'samples' / base['uid'] / 'combined.json.gz').read_bytes()
    if (js(old_copy)+'\n').encode() != gzip.decompress(frozen_old): raise ValueError('Previous candidate reproduction mismatch')
    del old_copy
    codec = FlatBlocks(nested.bodies)
    if any(OLD_REF.search(body) or FLAT_REF.search(body) for body in codec.blocks.values()): raise ValueError('Dictionary is not flat')
    for old,row in zip(calls,encoded_calls):
        for m in (row.get('request') or {}).get('messages',[]):
            if isinstance(m.get('content'),str): m['content'] = codec.convert(m['content'])
        restored = copy.deepcopy(row)
        for m in (restored.get('request') or {}).get('messages',[]):
            if isinstance(m.get('content'),str): m['content'] = codec.expand(m['content'])
        if restored != old: raise ValueError('Original event changed')
    for old,p in zip(profiles,encoded_profiles):
        if isinstance(p['message'].get('content'),str): p['message']['content'] = codec.convert(p['message']['content'])
        restored = copy.deepcopy(p)
        if isinstance(restored['message'].get('content'),str): restored['message']['content'] = codec.expand(restored['message']['content'])
        if restored != old: raise ValueError('Original profile changed')
    restored_calls = copy.deepcopy(encoded_calls)
    for row in restored_calls:
        for m in (row.get('request') or {}).get('messages',[]):
            if isinstance(m.get('content'),str): m['content'] = codec.expand(m['content'])
    restored_ledger = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in restored_calls).encode()
    if restored_ledger != records['raw_llm_events.jsonl'][0]: raise ValueError('Original JSONL bytes did not roundtrip')
    flat_ledger = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in encoded_calls).encode()
    flat_interactions = audit.fmt.block('raw_llm_events.jsonl',flat_ledger)+'\n'+audit.fmt.block('raw_tool_events.jsonl',records['raw_tool_events.jsonl'][0])
    copied = {d:dict(v) for d,v in inputs.items()}
    copied['planning']['results'] = flat_interactions
    copied['planning']['agent_profiles'] = js(encoded_profiles)+codec.footer()
    copied['communication']['communications'] = flat_interactions+codec.footer()
    if copied['planning']['agent_tasks'] != inputs['planning']['agent_tasks'] or copied['planning']['summary'] != inputs['planning']['summary'] or copied['communication']['task'] != inputs['communication']['task']: raise ValueError('Non-content field changed')
    dims = {}
    for d,fields in copied.items():
        prompt = audit.templates[d.title()]['prompt'].format(**fields)
        n = len(audit.enc.encode(prompt)); old = base['dimensions'][d]['local_content_tokens']
        dims[d] = {'tokens_including_complete_dictionary':n,'original_tokens':old,'reduction_percent':100*(1-n/old),
                   'eligible_estimated':math.ceil(n*1.15)+4096<=983616,'rendered_prompt_sha256':sha(prompt.encode())}
    folder = OUT / 'SCORER_INPUTS_ONLY' / base['uid']; folder.mkdir(parents=True,exist_ok=False)
    payload = (js(copied)+'\n').encode()
    gz(folder/'official_function_inputs.SCORER_ONLY.json.gz',payload)
    dictionary = [{'block_id':codec.ids[h],'original_utf8_sha256':h,'original_text':body} for h,body in sorted(codec.blocks.items())]
    gz(folder/'block_dictionary.SCORER_ONLY.json.gz',(js({'artifact_purpose':'SCORER_INPUT_ONLY','blocks':dictionary})+'\n').encode())
    result = {k:base[k] for k in ['uid','index','cohort','round','arm','actual_max_depth','agent_nodes','source_hashes']}
    result.update(artifact_purpose='SCORER_INPUT_ONLY',source_trace_directory=str(trace),original_input_sha256=base['input_sha256'],
        candidate_sha256=sha(payload),dimensions=dims,unique_literal_blocks=len(codec.blocks),reference_occurrences=codec.references,
        max_blocks_in_one_ordered_list=codec.max_blocks_per_reference,old_max_reference_levels=max(codec.depths.values(),default=0),
        new_max_reference_levels=1 if codec.references else 0,dictionary_nested_references=0,
        restored_original_ledger_sha256=sha(restored_ledger),original_llm_event_count=len(calls),copied_llm_event_count=len(encoded_calls),
        original_message_occurrence_count=sum(len((r.get('request') or {}).get('messages',[])) for r in calls),
        source_hashes_before_after_matched=all(sha(Path(path).read_bytes())==h for path,h in base['source_hashes'].items()),
        expanded_original_records_byte_exact=True,non_content_fields_unchanged=True,api_calls=0,scores=None)
    if not result['source_hashes_before_after_matched']: raise ValueError('Original source changed')
    write(folder/'manifest.SCORER_ONLY.json',result)
    return result

def main():
    if (OUT/'manifest.json').exists(): raise RuntimeError('Refuse overwrite of completed scorer copies')
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    old_hashes = checksum_set(PREVIOUS)
    selection = json.loads((PREVIOUS/'selection.json').read_text())
    previous_results = {r['uid']:r for r in json.loads((PREVIOUS/'results.json').read_text())}
    baseline = {r['uid']:r for r in json.loads((BASE/'trajectory_records.json').read_text())}
    entries = json.loads((BASE/'source_index_all_canonical_slots.json').read_text())['attempts']
    source = {f"q{e['index']:04d}_{e['cohort']}_{e['round']}_{e['arm']}":e for e in entries}
    uids = [p[a+'_uid'] for p in selection['pairs'] for a in ['BASE','V2']]
    tasks = [{**source[u],**baseline[u]} for u in uids]
    write(OUT/'selection.SCORER_ONLY.json',selection)
    rows = []
    with cf.ProcessPoolExecutor(max_workers=2,initializer=setup) as pool:
        for r in pool.map(one,tasks):
            rows.append(r)
            print(json.dumps({'done':len(rows),'total':len(tasks),'uid':r['uid'],'flat_depth':r['new_max_reference_levels'],'dimensions':r['dimensions'],'api_calls':0}),flush=True)
    write(OUT/'measurements.SCORER_ONLY.json',rows)
    by = {r['uid']:r for r in rows}; summary = {'sample_trajectories':len(rows),'sample_pairs':len(selection['pairs']),'dimensions':{},'api_calls':0}
    for d in ['planning','communication']:
        vals = [r['dimensions'][d]['reduction_percent'] for r in rows]
        old = sum(r['dimensions'][d]['original_tokens'] for r in rows); flat = sum(r['dimensions'][d]['tokens_including_complete_dictionary'] for r in rows)
        chain = sum(previous_results[r['uid']]['variants']['combined']['dimensions'][d]['tokens_including_complete_dictionary'] for r in rows)
        summary['dimensions'][d] = {'median_reduction_percent':statistics.median(vals),'min_reduction_percent':min(vals),'max_reduction_percent':max(vals),
            'old_chain_sum_tokens':chain,'flat_sum_tokens':flat,'flat_minus_chain_tokens':flat-chain,'flat_vs_chain_percent':100*(flat/chain-1)}
    def eligible(r): return all(x['eligible_estimated'] for x in r['dimensions'].values())
    summary['eligible_pairs_estimated'] = sum(all(eligible(by[p[a+'_uid']]) for a in ['BASE','V2']) for p in selection['pairs'])
    summary['eligible_trajectories_estimated'] = sum(eligible(r) for r in rows)
    summary['max_reference_levels'] = max(r['new_max_reference_levels'] for r in rows)
    summary['old_max_reference_levels'] = max(r['old_max_reference_levels'] for r in rows)
    summary['dictionary_nested_references'] = 0
    write(OUT/'summary.SCORER_ONLY.json',summary)
    if checksum_set(PREVIOUS) != old_hashes: raise ValueError('Previous artifacts modified')
    write(OUT/'preservation_verification.json',{'all_original_sources_unchanged':True,'original_source_files':len({p for r in rows for p in r['source_hashes']}),
        'prior_artifacts_unchanged':True,'prior_file_hashes':old_hashes,'all_original_jsonl_ledgers_byte_exact_after_expansion':True,
        'all_profile_occurrences_and_non_content_values_preserved':True,'event_rows_deleted':0,'source_write_operations':0,
        'old_research_script_sha256':sha((PREVIOUS/'estimate.py').read_bytes()),'native_formatter_sha256':sha((ROOT/'outputs/mab_native_format/format_inputs.py').read_bytes()),
        'borrowed_prompts_sha256':sha((ROOT/'work/MARBLE-community/marble/evaluator/evaluator_prompts.json').read_bytes())})
    write(OUT/'manifest.json',{'artifact_purpose':'SCORER_INPUT_ONLY','version':'flat-literal-block-lists-v1','started_at':started,'completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope':'Same frozen exploratory sample of 7 paired questions / 14 trajectories. Not a full-corpus conversion or scoring run.',
        'original_source_files_read_only':True,'prior_artifacts_read_only':True,'native_judge_code_prompts_and_parameters_unchanged':True,
        'nested_dictionary_references_allowed':False,'hashes_in_manifest_and_dictionary':True,'short_ids_only_name_text_blocks_not_agents':True,
        'api_calls':0,'scoring_started':False,'scores':None,'tokenizer':'Existing local qwen-turbo estimate; not exact Qwen3.7 token counts',
        'preflight_rule':'ceil(local_tokens * 1.15) + 4096 <= 983616 for all four paired inputs',
        'script_sha256':sha(Path(__file__).read_bytes()),'previous_selection_sha256':sha((PREVIOUS/'selection.json').read_bytes()),
        'limitation':'Lossless reconstruction verified; model scoring equivalence untested. Do not substitute these derived files for original trajectories.'})
    lines = ['# 仅供评分器使用：扁平原文块副本','', '**这些文件是 SCORER_INPUT_ONLY 派生输入，不是原始轨迹，也不是评分结果。** 原始文件和前一版研究副本均只读，禁止以本目录文件覆盖原始归档。','',
        '沿用前一版固定的 7 组 BASE/V2、14 条样本，未做全量转换或 API 评分。所有调用、重试、消息出现次数、身份、时间戳和顺序保留。正文块共享不表示事件合并。','',
        '## 表示方式','', '每个消息位置直接列出有序块编号，例如 `[[SCORER_BLOCKS:B0001,B0007,B0012]]`。按顺序拼接这些原文块，不插入分隔符。字典条目只存直接原文，条目之间不引用，不存在“上一轮引用上一轮”的长链。短编号只给正文块命名，不修改 agent/task/tool call ID；完整 SHA-256 另存字典和 manifest。','',
        '完整字典实际包含在每一个 Planning / Communication 输入里，无需外部检索。官方字段名、提示词和评分参数均未修改。哈希清单、恢复检查与尺寸测量结果留档。','',
        '## 离线测量','', '| 维度 | 扁平副本节省中位数 | 样本节省范围 | 相对旧链式输入总 token 变化 |','|---|---:|---:|---:|']
    for d,label in [('planning','Planning'),('communication','Communication')]:
        s = summary['dimensions'][d]
        lines.append(f"| {label} | {s['median_reduction_percent']:.1f}% | {s['min_reduction_percent']:.1f}–{s['max_reduction_percent']:.1f}% | {s['flat_vs_chain_percent']:+.2f}% |")
    lines += ['', f"最深引用由 {summary['old_max_reference_levels']} 层变成 {summary['max_reference_levels']} 层，字典内嵌套引用为 0。沿用原有预筛，{summary['eligible_trajectories_estimated']}/14 条、{summary['eligible_pairs_estimated']}/7 对通过；不是全量覆盖率。",'',
        '所有被替换正文恢复后，原始 raw_llm_events.jsonl 的完整字节与原文件一致；profile 原值、出现次数和非正文字段相同。原始源文件哈希以及已有研究档案的校验清单前后相同。','',
        '## 文件用途','', '`SCORER_INPUTS_ONLY/<uid>/official_function_inputs.SCORER_ONLY.json.gz`：仅供官方评分器使用的完整字段和字典；`block_dictionary.SCORER_ONLY.json.gz`：原文块与完整哈希；`manifest.SCORER_ONLY.json`：源文件、恢复检查、尺寸和版本。','',
        '本地 tokenizer 只作估算。字典和说明开销均计入。样本刻意包含长轨迹，不能外推全量收益。机械无损不等于评分不变；本轮 API 调用为 0，尚未验证模型对扁平表示的评分稳定性。']
    (OUT/'README.SCORER_ONLY.md').write_text('\n'.join(lines)+'\n')
    paths = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (OUT/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(OUT)}\n' for p in paths))
    print(json.dumps({'stage':'complete','summary':summary},ensure_ascii=False),flush=True)

if __name__ == '__main__': main()
