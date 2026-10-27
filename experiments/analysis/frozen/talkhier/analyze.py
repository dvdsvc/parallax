"""Offline, read-only TalkHier behavior audit. No model calls or cost accounting."""
import csv, hashlib, json, math, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path('external_archive/2026-10-02/x/work/talkhier')
PRIMARY = ROOT / '.local/batches/20261006T090617775637Z_mmlu_pro_physics_n100_seed42_tb8192_mc16384_gw16x16'
SECONDARY = ROOT / '.local/batches/20261006T045520595135Z_college_physics_n50_seed42_tb8192_mc16384'
SCORE = ROOT / '.local/evaluations/20261006T090617775637Z_mmlu_pro_exact_match'
SECONDARY_SCORE = ROOT / '.local/scoring/20261006T045520595135Z/20261006T065810680638Z'
ROLES = ['Default Supervisor', 'Answer Generator', 'Evaluator Supervisor', 'Physics', 'Mathematics', 'Revisor']
FIELDS = ['input_tokens', 'output_tokens', 'total_tokens', 'reasoning_output_tokens', 'cached_input_tokens']
RNG_SEED, BOOTSTRAPS = 20261006, 20000

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(2**20), b''): h.update(chunk)
    return h.hexdigest()

def verify_archive(path):
    checked, bad = 0, []
    for line in (path/'checksums.sha256').read_text().splitlines():
        digest, rel = line.split('  ', 1)
        target = path/rel
        if not target.is_file() or sha(target) != digest: bad.append(rel)
        checked += 1
    return {'directory': str(path), 'files_checked': checked, 'mismatches': bad,
            'checksum_manifest_sha256': sha(path/'checksums.sha256')}

def lines(path):
    if not path.exists(): return
    with path.open('rb') as f:
        for raw in f:
            if not raw.endswith(b'\n'): raise ValueError(f'Sealed file has incomplete tail: {path}')
            yield json.loads(raw)

def role(e):
    m = e.get('metadata') or {}
    explicit = m.get('talkhier_role') or e.get('role')
    ns = m.get('langgraph_checkpoint_ns') or m.get('checkpoint_ns') or ''
    native = [s.split(':')[0] for s in ns.split('|') if s.split(':')[0] in ROLES]
    return explicit or (native[-1] if native else m.get('langgraph_node') if m.get('langgraph_node') in ROLES else 'unknown')

def write_json(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def write_csv(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/name).open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f, fieldnames=fields);w.writeheader();w.writerows(rows)

def distribution(values):
    a=np.asarray(values,dtype=float)
    if len(a)==0:return {'n':0}
    return {'n':len(a),'mean':float(a.mean()),'median':float(np.median(a)),
            'p90':float(np.quantile(a,.9)),'p95':float(np.quantile(a,.95)),
            'min':float(a.min()),'max':float(a.max())}

def paired_metric(pairs, field):
    a=np.array([p[0][field] for p in pairs],float);b=np.array([p[1][field] for p in pairs],float)
    if not len(a):return {'n':0}
    d=b-a;idx=np.random.default_rng(RNG_SEED).integers(0,len(a),size=(BOOTSTRAPS,len(a)))
    ad=a[idx].mean(1);bd=b[idx].mean(1);boot_d=bd-ad
    ratio=np.divide(bd,ad,out=np.full_like(bd,np.nan),where=ad!=0)
    good=ratio[np.isfinite(ratio)]
    ratios=np.divide(b,a,out=np.full_like(b,np.nan),where=a!=0);ratios=ratios[np.isfinite(ratios)]
    return {'n':len(a),'BASE':distribution(a),'V2':distribution(b),'difference_V2_minus_BASE':distribution(d),
        'ratio_of_means':float(b.mean()/a.mean()) if a.mean()!=0 else None,
        'median_question_ratio':float(np.median(ratios)) if len(ratios) else None,
        'delta_mean_95ci':[float(x) for x in np.quantile(boot_d,[.025,.975])],
        'ratio_of_means_95ci':[float(x) for x in np.quantile(good,[.025,.975])] if len(good) else None,
        'increased':int((d>0).sum()),'decreased':int((d<0).sum()),'tied':int((d==0).sum())}

def examine_question(batch, arm, qid, official=None, verify=True, folder=None):
    folder=folder or batch/arm/f'q{qid}';manifest=json.loads((folder/'manifest.json').read_text())
    verification=verify_archive(folder) if verify else None
    cfg=json.loads((folder/'startup/effective_configuration.json').read_text())
    native=list(csv.DictReader((folder/'native_results.csv').open())) if (folder/'native_results.csv').exists() else []
    usable=native[0] if len(native)==1 and manifest['status']=='completed' else None
    pred=gold=pre=None
    if usable:
        pred,gold=int(usable['Answer']),int(usable['Correct Answer'])
        try: pre=int(usable['Pre-Revision']);pre=pre if pre>=0 else None
        except ValueError: pass
    row={'benchmark':'MMLU-Pro Physics' if batch==PRIMARY else 'MMLU college_physics',
        'condition':arm,'problem_id':qid,'official_question_id':official,'status':manifest['status'],
        'gold_index':gold,'pred_index':pred,'correct':int(pred==gold) if pred is not None else None,
        'pre_revision_index':pre,'pre_revision_correct':int(pre==gold) if pre is not None else None,
        'elapsed_seconds':manifest.get('elapsed_seconds'),'directory':str(folder),
        'terminal_error_type':(manifest.get('error') or {}).get('type'),
        'terminal_error_message':(manifest.get('error') or {}).get('message')}
    calls={e['run_id']:e for e in lines(folder/'model_calls.jsonl')}
    chains={};roots={};starts={};tool_events={};nodes={};injection=Counter();parent_links={}
    for e in lines(folder/'trace.jsonl'):
        rid=e.get('run_id');event=e['event'];m=e.get('metadata') or {}
        if event=='chain_start':
            parent_links[rid]=e.get('parent_run_id')
            if e.get('name')=='LangGraph' and not m.get('langgraph_node'):
                roots[rid]={'status':'unfinished','error_type':None,'started_at':e['timestamp_utc']}
            if e.get('graph_node_event') and e.get('name') in ROLES and e.get('name')==m.get('langgraph_node'):
                nodes[rid]=e.get('name')
        elif event in ('chain_end','chain_error') and rid in roots:
            roots[rid].update(status='success' if event=='chain_end' else 'error',error_type=e.get('error_type'),finished_at=e['timestamp_utc'])
        elif event=='model_start':
            starts[rid]={'parent_run_id':e.get('parent_run_id'),'timestamp_utc':e['timestamp_utc']}
            parent_links[rid]=e.get('parent_run_id')
            batches=e.get('messages') or []
            if batches and isinstance(batches[0],dict):batches=[batches]
            for messages in batches:
                if not isinstance(messages,list):continue
                marker='[TALKHIER GLOBAL ORGANIZATIONAL ARCHITECTURE]'
                count=sum(marker in str(x.get('content','')) for x in messages if isinstance(x,dict))
                injection['model_starts']+=1
                injection['with_global_org']+=int(count>0)
                injection['duplicate_org']+=int(count>1)
                injection['first_system_global_org']+=int(bool(messages) and isinstance(messages[0],dict) and marker in str(messages[0].get('content','')) and messages[0].get('type')=='system')
        elif event.startswith('tool_'):
            t=tool_events.setdefault(rid,{'name':e.get('name'),'role':role(e)})
            t[event]=True
    def root_id(rid):
        seen=set()
        while rid and rid not in seen:
            if rid in roots:return rid
            seen.add(rid);rid=parent_links.get(rid)
        return None
    errors=Counter();role_rows=defaultdict(Counter);call_rows=[];anomalies=[]
    totals=Counter();failed_prefix_tokens=0;normal_count=0;ordinary_length=0;empty_return=0;missing=0;unknown_root=0
    requested_tools=Counter()
    length_ids=[];reasoning_excess=0
    for rid,c in calls.items():
        outputs=c.get('outputs') or [];usage=c.get('usage') or {};rn=role(c);root=root_id(rid)
        for o in outputs:
            if isinstance(o,dict):
                requested_tools.update(t.get('name','unknown') for t in o.get('tool_calls') or [])
        length=any((o.get('response_metadata') or {}).get('finish_reason')=='length' for o in outputs if isinstance(o,dict))
        valid_body=any(bool(o.get('content')) or bool(o.get('tool_calls')) for o in outputs if isinstance(o,dict))
        empty=c.get('status')=='success' and not length and not valid_body
        normal=c.get('status')=='success' and not length and valid_body
        ordinary_length+=int(length);empty_return+=int(empty);missing+=int(not usage)
        if length:length_ids.append(rid)
        if c.get('status')=='error':errors[c.get('error_type','Unknown')]+=1
        if normal:
            normal_count+=1;role_rows[rn]['normal_calls']+=1
            for field in FIELDS:
                if isinstance(usage.get(field),(int,float)):
                    totals[field]+=usage[field];role_rows[rn][field]+=usage[field]
                else:role_rows[rn]['missing_'+field]+=1
            if root and roots[root]['status']=='error':failed_prefix_tokens+=usage.get('total_tokens') or 0
        if root is None:unknown_root+=1
        reasoning_excess+=int(isinstance(usage.get('reasoning_output_tokens'),(int,float)) and usage['reasoning_output_tokens']>8192)
        cr={'benchmark':row['benchmark'],'condition':arm,'problem_id':qid,'run_id':rid,'role':rn,
            'status':c.get('status'),'normal_valid_return':int(normal),'finish_length':int(length),'empty_return':int(empty),
            'error_type':c.get('error_type'),'duration_seconds':c.get('duration_seconds'),
            'root_attempt_id':root,'root_attempt_status':roots.get(root,{}).get('status'),
            **{field:usage.get(field) for field in FIELDS}}
        call_rows.append(cr)
        if not normal:anomalies.append(cr)
    tools=Counter(t['name'] for t in tool_events.values() if t.get('tool_start'))
    tool_errors=sum(t.get('tool_error',False) for t in tool_events.values())
    tool_roles=Counter(t['role'] for t in tool_events.values() if t.get('tool_start') and t['name']=='output_tool')
    events={};gateway_counts=Counter();waiting=0.;http_status=Counter()
    for e in lines(folder/'infrastructure/gateway_events.jsonl'):
        key=(e.get('logical_call_id'),e.get('attempt'),e.get('event'))
        events[key]=e
    for e in events.values():
        gateway_counts[e['event']]+=1
        if e['event']=='http_return':
            waiting+=float(e.get('waiting_seconds') or 0);http_status[str(e.get('status_code'))]+=1
    failed_roots=Counter(v.get('error_type') or 'Unknown' for v in roots.values() if v['status']=='error')
    node_counts=Counter(nodes.values())
    row.update(normal_calls=normal_count,model_calls_finished=len(calls),model_errors=sum(errors.values()),
        missing_usage_calls=missing,ordinary_length=ordinary_length,empty_returns=empty_return,
        root_attempts=len(roots),root_failed_attempts=sum(failed_roots.values()),
        graph_recursion_failures=failed_roots['GraphRecursionError'],unfinished_roots=sum(v['status']=='unfinished' for v in roots.values()),
        normal_tokens_in_failed_root_attempts=failed_prefix_tokens,output_tool_calls=tools['output_tool'],
        other_tool_attempts=sum(v for k,v in tools.items() if k!='output_tool'),tool_errors=tool_errors,
        gateway_wait_seconds=waiting,gateway_429=sum(v for k,v in gateway_counts.items() if '429' in k),
        reasoning_above_budget=reasoning_excess,unassigned_model_roots=unknown_root,
        **{'normal_'+field:totals[field] for field in FIELDS},
        **{'visits_'+r.replace(' ','_'):node_counts[r] for r in ROLES})
    row['clean']=int(row['model_errors']==0 and ordinary_length==0 and empty_return==0 and row['root_failed_attempts']==0 and row['unfinished_roots']==0)
    role_summary=[{'benchmark':row['benchmark'],'condition':arm,'problem_id':qid,'role':r,
                   'native_node_visits':node_counts[r],'output_tool_calls':tool_roles[r],**dict(role_rows[r])} for r in ROLES+['unknown']]
    detail={'model_errors':dict(errors),'root_failures':dict(failed_roots),'tool_names':dict(tools),'model_requested_tools':dict(requested_tools),
            'gateway_events':dict(gateway_counts),'http_status':dict(http_status),'injection_audit':dict(injection),
            'roots':roots,'configuration':cfg}
    final_calls=[c for c in call_rows if c['normal_valid_return'] and c['root_attempt_status']=='success']
    row['successful_root_normal_tokens']=sum(c['total_tokens'] or 0 for c in final_calls)
    row['successful_root_normal_calls']=len(final_calls)
    return row,call_rows,role_summary,anomalies,detail,verification

def summarize(rows, calls, roles, details):
    groups={}
    for arm in ['BASE','V2']:
        qs=[r for r in rows if r['condition']==arm];cc=[c for c in calls if c['condition']==arm];normal=[c for c in cc if c['normal_valid_return']]
        totals={field:sum(c.get(field) or 0 for c in normal) for field in FIELDS}
        groups[arm]={'planned':len(qs),'statuses':dict(Counter(q['status'] for q in qs)),
            'scored':sum(q['correct'] is not None for q in qs),'correct':sum(q['correct'] or 0 for q in qs),
            'normal_usage':totals,'normal_calls':len(normal),'model_calls_finished':len(cc),
            'normal_missing_usage':sum(c['total_tokens'] is None for c in normal),
            'model_errors':dict(Counter(c['error_type'] for c in cc if c['status']=='error')),
            'ordinary_length':sum(c['finish_length'] for c in cc),'empty_returns':sum(c['empty_return'] for c in cc),
            'missing_usage_calls':sum(c['total_tokens'] is None for c in cc),
            'root_attempts':sum(q['root_attempts'] for q in qs),'root_failed_attempts':sum(q['root_failed_attempts'] for q in qs),
            'root_failure_types':dict(sum((Counter(details[(arm,q['problem_id'])]['root_failures']) for q in qs),Counter())),
            'normal_tokens_in_failed_root_attempts':sum(q['normal_tokens_in_failed_root_attempts'] for q in qs),
            'tool_names':dict(sum((Counter(details[(arm,q['problem_id'])]['tool_names']) for q in qs),Counter())),
            'model_requested_tools':dict(sum((Counter(details[(arm,q['problem_id'])]['model_requested_tools']) for q in qs),Counter())),
            'gateway_events':dict(sum((Counter(details[(arm,q['problem_id'])]['gateway_events']) for q in qs),Counter())),
            'http_status':dict(sum((Counter(details[(arm,q['problem_id'])]['http_status']) for q in qs),Counter())),
            'gateway_wait_seconds':sum(q['gateway_wait_seconds'] for q in qs),
            'injection_audit':dict(sum((Counter(details[(arm,q['problem_id'])]['injection_audit']) for q in qs),Counter())),
            'reasoning_above_budget':sum(q['reasoning_above_budget'] for q in qs),
            'normal_call_duration_seconds':distribution([c['duration_seconds'] for c in normal if c['duration_seconds'] is not None]),
            'normal_long_calls_over_300_seconds':sum(c.get('duration_seconds',0)>300 for c in normal),
            'clean_questions':sum(q['clean'] for q in qs),
            'revision_change':dict(Counter(f"{q['pre_revision_correct']}->{q['correct']}" for q in qs if q['pre_revision_correct'] is not None)),
            'pre_revision_missing':sum(q['pre_revision_correct'] is None for q in qs if q['correct'] is not None)}
    keyed={(r['condition'],r['problem_id']):r for r in rows};ids=sorted({r['problem_id'] for r in rows})
    pairs=[(keyed['BASE',qid],keyed['V2',qid]) for qid in ids if keyed['BASE',qid]['correct'] is not None and keyed['V2',qid]['correct'] is not None]
    clean=[p for p in pairs if p[0]['clean'] and p[1]['clean']]
    transitions=Counter(f"{a['correct']}->{b['correct']}" for a,b in pairs)
    up,down=transitions['0->1'],transitions['1->0'];n=up+down
    pvalue=min(1.,2*sum(math.comb(n,k) for k in range(min(up,down)+1))/2**n) if n else 1.
    metrics=['correct','normal_total_tokens','normal_input_tokens','normal_output_tokens','normal_reasoning_output_tokens',
             'normal_cached_input_tokens','normal_calls','output_tool_calls','elapsed_seconds','root_attempts',
             'successful_root_normal_tokens','successful_root_normal_calls']
    metrics += ['visits_'+r.replace(' ','_') for r in ROLES]
    pm={f:paired_metric(pairs,f) for f in metrics};cm={f:paired_metric(clean,f) for f in metrics}
    tail=sorted([{'problem_id':a['problem_id'],'official_question_id':a['official_question_id'],
                  'BASE_normal_tokens':a['normal_total_tokens'],'V2_normal_tokens':b['normal_total_tokens'],
                  'delta':b['normal_total_tokens']-a['normal_total_tokens'],'BASE_calls':a['normal_calls'],'V2_calls':b['normal_calls'],
                  'BASE_root_failed':a['root_failed_attempts'],'V2_root_failed':b['root_failed_attempts'],
                  'BASE_correct':a['correct'],'V2_correct':b['correct']} for a,b in pairs],key=lambda x:x['delta'],reverse=True)
    net=sum(t['delta'] for t in tail);positive=sum(max(t['delta'],0) for t in tail)
    role_totals=[]
    pair_ids={a['problem_id'] for a,b in pairs};clean_ids={a['problem_id'] for a,b in clean}
    for scope,scope_ids in [('all_questions',set(ids)),('paired_completed',pair_ids),('clean_pairs',clean_ids)]:
        for r in ROLES+['unknown']:
            z={'scope':scope,'role':r,'questions_per_condition':len(scope_ids)}
            for arm in ['BASE','V2']:
                rr=[x for x in roles if x['condition']==arm and x['role']==r and x['problem_id'] in scope_ids]
                for f in ['normal_calls','native_node_visits','output_tool_calls']+FIELDS:z[arm+'_'+f]=sum(x.get(f,0) for x in rr)
                z[arm+'_questions_visited']=sum(x['native_node_visits']>0 for x in rr)
            role_totals.append(z)
    pair_rows=[]
    for qid in ids:
        a,b=keyed['BASE',qid],keyed['V2',qid];valid=a['correct'] is not None and b['correct'] is not None
        p={'problem_id':qid,'official_question_id':a['official_question_id'],'gold_index':a['gold_index'] if a['gold_index'] is not None else b['gold_index'],
           'paired_valid':int(valid),'both_clean':int(valid and a['clean'] and b['clean'])}
        for arm,q in [('BASE',a),('V2',b)]:
            for f in ['status','pred_index','correct','normal_total_tokens','normal_input_tokens','normal_output_tokens','normal_reasoning_output_tokens',
                      'normal_calls','output_tool_calls','root_failed_attempts','model_errors','ordinary_length','empty_returns','elapsed_seconds']:
                p[arm+'_'+f]=q[f]
        p['paired_delta_normal_tokens']=b['normal_total_tokens']-a['normal_total_tokens'] if valid else None
        p['paired_delta_correct']=b['correct']-a['correct'] if valid else None
        pair_rows.append(p)
    return {'groups':groups,'paired_count':len(pairs),'clean_pair_count':len(clean),'transitions':dict(transitions),
            'exact_McNemar_p':pvalue,'paired_metrics':pm,'clean_pair_metrics':cm,
            'tail':tail,'top5_share_net_delta':sum(t['delta'] for t in tail[:5])/net if net else None,
            'top5_share_positive_delta':sum(max(t['delta'],0) for t in tail[:5])/positive if positive else None,
            'failures':[r for r in rows if r['status']!='completed']},role_totals,pair_rows

def main():
    verified=[];results={};all_q=[];all_calls=[];all_roles=[];all_anomalies=[];all_details={}
    official={(r['condition'],int(r['problem_id'])):r for r in csv.DictReader((SCORE/'per_question_scores.csv').open())}
    for batch,label in [(PRIMARY,'primary'),(SECONDARY,'secondary')]:
        parent=json.loads((batch/'manifest.json').read_text());assert parent['status']=='completed_with_errors'
        verified.append(verify_archive(batch));rows=[];calls=[];roles=[];anomalies=[];details={};configs=[]
        for arm in ['BASE','V2']:
            folders=sorted((batch/arm).glob('q*'),key=lambda p:int(p.name[1:]))
            for i,q in enumerate(folders):
                qid=int(q.name[1:]);sr=official.get((arm,qid)) if label=='primary' else None
                row,cc,rr,aa,dd,vv=examine_question(batch,arm,qid,int(sr['official_question_id']) if sr else None,folder=q)
                if sr:
                    assert row['status']==sr['status']
                    assert row['correct']==(int(sr['correct']) if sr['correct'] else None)
                    if row['correct'] is not None:assert row['pred_index']==int(sr['answer_index']) and row['gold_index']==int(sr['gold_index'])
                rows.append(row);calls+=cc;roles+=rr;anomalies+=aa;details[arm,qid]=dd;verified.append(vv);configs.append(dd['configuration'])
                if (i+1)%25==0:print(f'{label} {arm} {i+1}/{len(folders)} audited',flush=True)
        result,role_totals,pair_rows=summarize(rows,calls,roles,details)
        allowed={'condition','organization_awareness_v2'}
        commonkeys=set(configs[0]);differences={k:sorted(set(json.dumps(c.get(k),sort_keys=True) for c in configs)) for k in commonkeys if len(set(json.dumps(c.get(k),sort_keys=True) for c in configs))>1}
        result['configuration_differences']=differences;result['configuration_unexpected_differences']={k:v for k,v in differences.items() if k not in allowed}
        result['source_commit']=parent['workspace_commit'];result['batch']=str(batch)
        results[label]=result;all_q+=rows;all_calls+=calls;all_roles+=roles;all_anomalies+=anomalies
        write_csv(label+'_pairs.csv',pair_rows);write_csv(label+'_role_summary.csv',role_totals)
        write_json(label+'_role_summary.json',role_totals)
    verified.append(verify_archive(SCORE));verified.append(verify_archive(SECONDARY_SCORE))
    assert all(not v['mismatches'] for v in verified)
    assert not results['primary']['configuration_unexpected_differences']
    write_csv('question_metrics.csv',all_q);write_csv('model_calls_audit.csv',all_calls);write_csv('role_question_metrics.csv',all_roles);write_csv('anomalies.csv',all_anomalies)
    results['protocol']={'main':'Normal valid model returns on mutually completed question pairs; status=success, no finish_reason=length, content or tool_calls present.',
      'token_fields':'Only usage of normal valid returns; no recovery from exception text; unknown is not imputed.',
      'clean_sensitivity':'Post-hoc diagnostic: both arms completed, no model error, no ordinary length/empty return, no failed or unfinished root graph attempt.',
      'native_graph':'Root LangGraph chain event with metadata lacking langgraph_node; callbacks propagated to leaf/parent are not extra root attempts.',
      'role':'talkhier_role when present; otherwise last native role in full langgraph_checkpoint_ns.',
      'tool':'output_tool writes model text and returns empty string; no external resource tool is enabled by Physics prompt [4].',
      'inference':'No inference/grader/API/cost accounting. Fixed100 is not full benchmark or official few-shot inference.',
      'bootstrap':{'seed':RNG_SEED,'resamples':BOOTSTRAPS,'unit':'question pair','interval':'percentile 95%; one run per arm; not provider-randomness replication'},
      'latency':'Whole child elapsed time; V2 scheduler capacity changed16→32 late in run; no causal concurrency/latency inference.'}
    results['official_scoring']=json.loads((SCORE/'score_summary.json').read_text())
    results['secondary_scoring']=json.loads((SECONDARY_SCORE/'score_summary.json').read_text())
    write_json('analysis_summary.json',results)
    write_json('input_verification.json',{'verified_at_utc':datetime.now(timezone.utc).isoformat(),'all_verified':True,'archives':verified,'input_archives':len(verified),'files_checked':sum(v['files_checked'] for v in verified)})
    write_json('analysis_manifest.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),'primary_batch':str(PRIMARY),'primary_scoring':str(SCORE),
      'secondary_batch':str(SECONDARY),'secondary_scoring':str(SECONDARY_SCORE),'analysis_script_sha256':sha(Path(__file__)),
      'sampling_seed':42,'bootstrap_seed':RNG_SEED,'bootstrap_resamples':BOOTSTRAPS,'original_archives_read_only':True,
      'new_model_calls':0,'cost_accounting':False,'excluded_from_primary':['model errors','ordinary length','empty return without tool calls'],
      'primary_input_checksums_sha256':sha(PRIMARY/'checksums.sha256'),'score_input_checksums_sha256':sha(SCORE/'checksums.sha256')})
    for label,result in results.items():
        if label in ['primary','secondary']:
            print(label,json.dumps({k:result[k] for k in ['paired_count','clean_pair_count','transitions','exact_McNemar_p']},ensure_ascii=False))
            print('normal token metric',json.dumps(result['paired_metrics']['normal_total_tokens']))

if __name__=='__main__':main()
