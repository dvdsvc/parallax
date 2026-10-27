"""SCORER_INPUT_ONLY preparation. Reuse frozen codecs; original sources read-only."""
import copy
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[2]
SAMPLE=ROOT/'outputs/mab_scorer_only_flat_blocks_20261004_trial1'
COVERAGE=ROOT/'outputs/mab_scorer_only_flat_coverage_all94_20261004_trial1'
BASE=ROOT/'outputs/mab_native_coverage_all94_20261003'

def sha(b):return hashlib.sha256(b).hexdigest()
def js(x):return json.dumps(x,ensure_ascii=False,indent=2)
def write(p,x):p.write_text(js(x)+'\n')

def initialize():
    global flat, coverage_by_uid, baseline_by_uid
    spec=importlib.util.spec_from_file_location('frozen_flat_codec',SAMPLE/'build_flat_scorer_copies.py')
    flat=importlib.util.module_from_spec(spec);spec.loader.exec_module(flat);flat.setup()
    coverage_by_uid={r['uid']:r for r in json.loads((COVERAGE/'trajectory_records.json').read_text())}
    baseline_by_uid={r['uid']:r for r in json.loads((BASE/'trajectory_records.json').read_text())}

def prepare(entry,inputs_dir,preflight):
    uid=f"q{entry['index']:04d}_{entry['cohort']}_{entry['round']}_{entry['arm']}"
    expected=coverage_by_uid[uid]
    baseline=baseline_by_uid[uid]
    assert expected['input_complete'] and expected['runtime_record_complete']
    assert entry['selected_dimensions']
    for path,h in expected['source_hashes'].items():assert sha(Path(path).read_bytes())==h
    original,records,profiles,cp,graph=flat.audit.build(entry,inputs_dir/'_never_written',{})
    assert sha((js(original)+'\n').encode())==baseline['input_sha256']
    calls=records['raw_llm_events.jsonl'][1]
    contents=[(m.get('role'),m['content']) for row in calls for m in (row.get('request')or{}).get('messages',[]) if isinstance(m.get('content'),str)]
    contents += [(p['message'].get('role'),p['message']['content']) for p in profiles if isinstance(p['message'].get('content'),str)]
    assert not any('[[SCORER_BLOCKS:' in t or flat.FLAT_MARKER in t for _,t in contents)
    nested=flat.previous.Codec(contents,'combined')
    copied_calls=copy.deepcopy(calls);copied_profiles=copy.deepcopy(profiles)
    for row in copied_calls:
        for m in (row.get('request')or{}).get('messages',[]):
            if isinstance(m.get('content'),str):m['content']=nested.convert(m['content'])
    for p in copied_profiles:
        if isinstance(p['message'].get('content'),str):p['message']['content']=nested.convert(p['message']['content'])
    codec=flat.FlatBlocks(nested.bodies)
    assert not any(flat.OLD_REF.search(b) or flat.FLAT_REF.search(b) for b in codec.blocks.values())
    restored=[]
    for old,row in zip(calls,copied_calls):
        for m in (row.get('request')or{}).get('messages',[]):
            if isinstance(m.get('content'),str):m['content']=codec.convert(m['content'])
        recovered=copy.deepcopy(row)
        for m in (recovered.get('request')or{}).get('messages',[]):
            if isinstance(m.get('content'),str):m['content']=codec.expand(m['content'])
        assert recovered==old
        restored.append(json.dumps(recovered,ensure_ascii=False)+'\n')
    assert ''.join(restored).encode()==records['raw_llm_events.jsonl'][0]
    for old,p in zip(profiles,copied_profiles):
        if isinstance(p['message'].get('content'),str):p['message']['content']=codec.convert(p['message']['content'])
        recovered=copy.deepcopy(p)
        if isinstance(recovered['message'].get('content'),str):recovered['message']['content']=codec.expand(recovered['message']['content'])
        assert recovered==old
    ledger=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in copied_calls).encode()
    interactions=flat.audit.fmt.block('raw_llm_events.jsonl',ledger)+'\n'+flat.audit.fmt.block('raw_tool_events.jsonl',records['raw_tool_events.jsonl'][0])
    copied={d:dict(v) for d,v in original.items()}
    copied['planning']['results']=interactions
    copied['planning']['agent_profiles']=js(copied_profiles)+codec.footer()
    copied['communication']['communications']=interactions+codec.footer()
    payload=(js(copied)+'\n').encode();assert sha(payload)==expected['input_sha256']
    for dim,fields in copied.items():
        prompt=flat.audit.templates[dim.title()]['prompt'].format(**fields)
        assert sha(prompt.encode())==expected['dimensions'][dim]['prompt_sha256']
        if dim in entry['selected_dimensions']:
            assert expected['dimensions'][dim]['guarded_input_tokens']<=983616
    for path,h in expected['source_hashes'].items():assert sha(Path(path).read_bytes())==h
    folder=inputs_dir/uid;folder.mkdir(exist_ok=False)
    (folder/'official_function_inputs.SCORER_ONLY.json.gz').write_bytes(gzip.compress(payload,mtime=0))
    dictionary={'artifact_purpose':'SCORER_INPUT_ONLY','blocks':[{'block_id':codec.ids[h],'original_utf8_sha256':h,'original_text':body} for h,body in sorted(codec.blocks.items())]}
    (folder/'block_dictionary.SCORER_ONLY.json.gz').write_bytes(gzip.compress((js(dictionary)+'\n').encode(),mtime=0))
    manifest={'artifact_purpose':'SCORER_INPUT_ONLY','uid':uid,'question_index':entry['index'],'question':entry['question'],
        'cohort':entry['cohort'],'arm':entry['arm'],'repeat':entry['round'],'depth_group':entry['depth_group'],
        'actual_max_depth':entry['actual_max_depth'],'agent_nodes':entry['agent_nodes'],
        'selected_dimensions':entry['selected_dimensions'],
        'input_sha256':sha(payload),'original_input_sha256':baseline['input_sha256'],
        'source_trace_directory':entry['trace_directory'],'source_hashes':expected['source_hashes'],
        'size_checks':expected['dimensions'],'expanded_original_ledger_byte_exact':True,'source_hashes_before_after_matched':True,
        'event_deletions':0,'dictionary_nested_references':0,'max_reference_levels':1,
        'formatter_sha256':sha((ROOT/'outputs/mab_native_format/format_inputs.py').read_bytes()),
        'flat_codec_sha256':sha((SAMPLE/'build_flat_scorer_copies.py').read_bytes()),'preflight':preflight}
    write(folder/'manifest.json',manifest)
    return manifest
