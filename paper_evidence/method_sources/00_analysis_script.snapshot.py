"""Outcome-blind PCA of paired behavior changes, then native-performance associations."""
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR','/private/tmp/roma-behavior-pca-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

ROOT = Path('archive-ref-f890ecf40fc114c9')
FRAMES_STUDY = Path('archive-ref-c0dea8485ea881ea')
ASSOC = ROOT/'outputs/seal0_frames_associations_20261004T154431Z'
NATIVE = Path('archive-ref-0bc1de2547a3cf1d')
MAB = ROOT/'outputs/mab_native_aligned_all94_20261004_trial1/aligned_results.json'
SEED, BOOT, PERM, PA = 20261005, 10000, 10000, 1000
SOURCES = {}
ABSENT_TOOL_LEDGERS = []
SUMMARY_DIFFERENCES = []
CANDIDATES = ['weighted_depth', 'max_depth', 'nodes', 'expanded', 'leaves', 'max_width',
              'mean_branching', 'max_branching', 'depth3_node_share', 'leaf_share',
              'tokens', 'tools', 'llm_calls', 'wall_time', 'search_share',
              'tools_per_E', 'llm_per_node', 'tokens_per_llm', 'output_token_share',
              'cached_input_share', 'tool_failure_share', 'llm_failure_share', 'retries',
              'planning', 'communication']
BEHAVIOR = [k for k in CANDIDATES if k not in ['planning', 'communication']]
NARROW = ['weighted_depth','max_depth','expanded','leaves','tokens','tools','planning','communication']


def sha(p):
    hh = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            hh.update(block)
    return hh.hexdigest()


def read(p):
    SOURCES[str(p)] = sha(p)
    return json.loads(p.read_text())


def write(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def ledger(p, expected, require_prior_hash=True):
    hh = sha(p)
    key = str(p) if str(p) in expected else str(p.resolve())
    if require_prior_hash or key in expected:
        assert key in expected and expected[key] == hh, str(p)
    SOURCES[str(p)] = hh
    return [json.loads(line) for line in p.open() if line.strip()]


def measures(trace, expected_hashes, archived):
    tree = ledger(trace/'tree_events.jsonl', expected_hashes)
    llm = ledger(trace/'llm_events.jsonl', expected_hashes)
    if (trace/'tool_events.jsonl').exists():
        tools = ledger(trace/'tool_events.jsonl', expected_hashes)
    else:
        assert archived['tool_calls']==0,str(trace)
        assert str(trace/'tool_events.jsonl') not in expected_hashes
        ABSENT_TOOL_LEDGERS.append(str(trace/'tool_events.jsonl'))
        tools=[]
    runs = ledger(trace/'run_events.jsonl', expected_hashes,require_prior_hash=False)
    nodes, executor, parents = {}, {}, set()
    for e in tree:
        if e.get('event') != 'node_start':
            continue
        key, d = e['task_id'], int(e.get('depth') or 0)
        assert key not in nodes or nodes[key] == d
        nodes[key] = d
        if e.get('parent_id'):
            parents.add(e['parent_id'])
        if e.get('agent_type') == 'executor':
            executor[key] = d
    leaves = set(nodes)-parents
    child_counts = Counter()
    unique = {}
    for e in tree:
        if e.get('event')=='node_start':unique.setdefault(e['task_id'],e)
    for e in unique.values():
        if e.get('parent_id') in nodes:child_counts[e['parent_id']]+=1
    starts=[datetime.fromisoformat(e['timestamp']) for e in runs if e.get('event')=='run_start']
    ends=[datetime.fromisoformat(e['timestamp']) for e in runs if e.get('event')=='run_end']
    wall=(ends[-1]-starts[0]).total_seconds() if starts and ends else None
    if wall is not None and archived.get('wall_time') is not None:
        assert np.isclose(wall,archived['wall_time'],rtol=0,atol=1e-3),(str(trace),'wall_time')
    input_tokens=sum(int(e.get('input_tokens')or 0) for e in llm)
    output_tokens=sum(int(e.get('output_tokens')or 0) for e in llm)
    token_total=sum(int(e.get('total_tokens')or 0) for e in llm)
    cache_known=all(e.get('cached_input_tokens') is not None for e in llm if e.get('status')!='failure')
    cached=sum(int(e.get('cached_input_tokens')or 0) for e in llm)
    result = {'weighted_depth': sum(nodes.values())/len(nodes), 'E_depth': sum(executor.values())/len(executor),
              'max_depth': max(nodes.values()), 'nodes': len(nodes), 'expanded': len(nodes)-len(leaves), 'leaves': len(leaves),
              'tokens': token_total, 'tools': len(tools), 'llm_calls':len(llm), 'wall_time':wall,
              'max_width':max(Counter(nodes.values()).values()),
              'mean_branching':sum(child_counts.values())/len(child_counts) if child_counts else 0,
              'max_branching':max(child_counts.values(),default=0),
              'depth3_node_share':sum(d>=3 for d in nodes.values())/len(nodes), 'leaf_share':len(leaves)/len(nodes),
              'search_share':sum(bool(e.get('is_search')) for e in tools)/len(tools) if tools else 0,
              'tools_per_E':len(tools)/len(executor), 'llm_per_node':len(llm)/len(nodes),
              'tokens_per_llm':token_total/len(llm),
              'output_token_share':output_tokens/(input_tokens+output_tokens) if input_tokens+output_tokens else None,
              'cached_input_share':cached/input_tokens if input_tokens and cache_known else None,
              'tool_failure_share':sum(not e.get('success',False) for e in tools)/len(tools) if tools else 0,
              'llm_failure_share':sum(e.get('status')=='failure' for e in llm)/len(llm),
              'retries':sum(int(e.get('retry_count')or 0)for e in llm),
              'unknown_usage_events': sum(e.get('total_tokens') is None for e in llm)}
    assert result['nodes'] == result['expanded']+result['leaves']
    for ours, theirs in [('nodes','agent_nodes'),('leaves','leaf_nodes'),('max_depth','actual_max_depth')]:
        assert result[ours] == archived[theirs], (str(trace), ours, result[ours], archived[theirs])
    expected_tokens=archived.get('whole_ledger_tokens',archived['total_tokens'])
    assert result['tokens']==expected_tokens,(str(trace),'whole recorded tokens',result['tokens'],expected_tokens)
    for ours,theirs in [('tokens','total_tokens'),('tools','tool_calls'),('llm_calls','llm_calls')]:
        if result[ours]!=archived[theirs]:
            SUMMARY_DIFFERENCES.append({'trace':str(trace),'metric':ours,'earlier_summary':archived[theirs],
                'whole_ledger_recomputed':result[ours],'late_events_after_run_end':sum(datetime.fromisoformat(e['timestamp'])>ends[-1]for e in (tools if ours=='tools' else llm)) if ends else None})
    return result


def aggregate(rows, features, require_scores=False, E=False, logtokens=False):
    by = defaultdict(list)
    for r in rows:
        if require_scores and not all(k in r[a] for a in ['BASE','V2'] for k in ['planning','communication']):
            continue
        by[r['question_id']].append(r)
    panel = []
    for q, rs in sorted(by.items()):
        deltas = {}
        for k in features:
            kk = 'E_depth' if E and k == 'weighted_depth' else k
            if any(r[a].get(kk) is None for r in rs for a in ['BASE','V2']):
                deltas[k]=None
                continue
            deltas[k] = float(np.mean([
                np.log1p(r['V2'][kk])-np.log1p(r['BASE'][kk]) if logtokens and k in ['tokens','tokens_per_llm']
                else r['V2'][kk]-r['BASE'][kk] for r in rs]))
        panel.append({'question_id': q, 'rounds': [r['round'] for r in rs], 'paired_rounds': len(rs), 'deltas_V2_minus_BASE': deltas})
    return panel


def fit_pca(panel, features, prune=True):
    # This function receives no correctness values or performance-based filters.
    missing={k:sum(q['deltas_V2_minus_BASE'].get(k) is None for q in panel)for k in features}
    available=[k for k in features if missing[k]==0]
    raw = np.array([[q['deltas_V2_minus_BASE'][k] for k in available] for q in panel])
    mean, sd = raw.mean(axis=0), raw.std(axis=0, ddof=1)
    active = sd > 1e-12
    keys = [k for k,a in zip(available, active) if a]
    z = (raw[:,active]-mean[active])/sd[active]
    selection=[]
    if prune:
        retained=[]
        for j,key in enumerate(keys):
            if retained and np.linalg.matrix_rank(z[:,retained+[j]],tol=1e-9)==len(retained):
                selection.append({'feature':key,'reason':'Exact linear dependence on retained standardized variables'})
                continue
            if retained:
                cs=np.corrcoef(z[:,retained+[j]],rowvar=False)[-1,:-1]
                if np.max(abs(cs))>=.95:
                    pos=int(np.argmax(abs(cs)));selection.append({'feature':key,'reason':'Absolute pairwise correlation >=0.95',
                        'with':keys[retained[pos]],'r':float(cs[pos])})
                    continue
            retained.append(j)
        z=z[:,retained];keys=[keys[j]for j in retained]
    _, singular, v = np.linalg.svd(z, full_matrices=False)
    for j in range(len(v)):
        if v[j, np.argmax(abs(v[j]))] < 0:
            v[j] *= -1
    scores = z @ v.T
    eigen = singular**2/(len(z)-1)
    proportion = eigen/eigen.sum()
    # Column-wise permutations preserve marginals while destroying between-feature association.
    rng = np.random.default_rng(SEED)
    null = []
    for _ in range(PA):
        zz = np.column_stack([rng.permutation(z[:,j]) for j in range(z.shape[1])])
        ss = np.linalg.svd(zz, compute_uv=False)
        null.append(ss**2/(len(z)-1))
    threshold = np.quantile(null, .95, axis=0)
    leading = 0
    for e,t in zip(eigen, threshold):
        if e <= t:
            break
        leading += 1
    rank = int((eigen > 1e-10).sum())
    assert np.allclose(z, scores@v, atol=1e-10)
    result = {'questions':len(panel), 'paired_rounds':sum(q['paired_rounds'] for q in panel),
        'features':keys,'candidate_features':features,
        'missing_feature_question_counts':missing,
        'dropped_zero_variance_features':[k for k,a in zip(available,active) if not a],
        'redundancy_exclusions':selection,'redundancy_pruning':prune,
        'standardization':{k:{'mean_delta':float(m),'sample_sd_delta':float(s)} for k,m,s in zip(available,mean,sd)},
        'matrix_rank':rank,'covariance_eigenvalues':eigen.tolist(),'explained_variance_ratio':proportion.tolist(),
        'cumulative_explained_variance':np.cumsum(proportion).tolist(),
        'parallel_analysis':{'column_permutations':PA,'seed':SEED,'eigenvalue_threshold95':threshold.tolist(),
                             'leading_retained_axes':leading,'all_eigenvalues_above_threshold':[int(i+1) for i,(e,t) in enumerate(zip(eigen,threshold)) if e>t]},
        'components_coefficients':v.tolist(), 'variable_component_correlations':(v.T*np.sqrt(np.maximum(eigen,0))).tolist(),
        'sign_rule':'Largest absolute coefficient positive; no correctness information used.',
        'question_scores':[{'question_id':q['question_id'],'scores':s.tolist()} for q,s in zip(panel,scores)],
        'feature_correlation_matrix':np.corrcoef(z,rowvar=False).tolist()}
    return result


def performance(pca, panel, outcome_lookup):
    # Called only after every PCA result and behavior-only input have been frozen on disk.
    y, b, vv = [], [], []
    for q in panel:
        rs = [outcome_lookup[q['question_id'],r] for r in q['rounds']]
        bb, v = np.mean([r['BASE'] for r in rs]), np.mean([r['V2'] for r in rs])
        b.append(float(bb)); vv.append(float(v)); y.append(float(bb-v))
    y = np.array(y)
    scores = np.array([q['scores'] for q in pca['question_scores']])[:,:pca['matrix_rank']]
    x = scores/scores.std(axis=0,ddof=1)
    yc = y-y.mean(); denom = np.sqrt(np.sum(x*x,axis=0)*np.sum(yc*yc))
    observed = np.sum(x*yc[:,None],axis=0)/denom
    rng = np.random.default_rng(SEED)
    permutations = np.array([rng.permutation(yc) for _ in range(PERM)])
    null = permutations@x/denom
    maxnull = np.max(abs(null),axis=1)
    idx = rng.integers(0,len(y),size=(BOOT,len(y)))
    xx = x[idx]; yy = y[idx]; xx = xx-xx.mean(axis=1,keepdims=True); yy = yy-yy.mean(axis=1,keepdims=True)
    d = np.sqrt(np.sum(xx*xx,axis=1)*np.sum(yy*yy,axis=1)[:,None])
    samples = np.divide(np.sum(xx*yy[:,:,None],axis=1),d,out=np.full_like(d,np.nan),where=d>0)
    axes = []
    for j,r in enumerate(observed):
        slope = float(np.sum(x[:,j]*yc)/np.sum(x[:,j]**2))
        axes.append({'PC':j+1,'pearson_r':float(r),'ci95_fixed_axis_question_bootstrap':np.nanquantile(samples[:,j],[.025,.975]).tolist(),
            'spearman_r':float(np.corrcoef(rankdata(x[:,j]),rankdata(y))[0,1]),
            'p_permutation_unadjusted':float((1+(abs(null[:,j])>=abs(r)).sum())/(PERM+1)),
            'p_max_abs_r_within_model_all_axes':float((1+(maxnull>=abs(r)).sum())/(PERM+1)),
            'slope_delta_pp_per_1SD_axis':100*slope,'in_sample_single_axis_R_squared':float(r*r)})
    k = pca['parallel_analysis']['leading_retained_axes']
    if k:
        fitted = x[:,:k]@np.linalg.lstsq(x[:,:k],yc,rcond=None)[0]
        r2 = float(np.sum(fitted*fitted)/np.sum(yc*yc))
        null_r2 = np.sum(null[:,:k]**2,axis=1)
        retained = {'axes':list(range(1,k+1)),'in_sample_R_squared':r2,
                    'p_permutation_joint':float((1+(null_r2>=r2).sum())/(PERM+1))}
        assert np.isclose(r2,sum(r['in_sample_single_axis_R_squared'] for r in axes[:k]))
    else:
        retained = {'axes':[],'in_sample_R_squared':None,'p_permutation_joint':None}
    return {'performance_definition':'mean matched BASE_correct - V2_correct within question, same rounds as behavior inputs',
            'BASE_accuracy':float(np.mean(b)),'V2_accuracy':float(np.mean(vv)),'mean_delta_BASE_minus_V2':float(y.mean()),
            'axes':axes,'retained_axes_joint_fit':retained,
            'question_outcomes':[{'question_id':q['question_id'],'BASE_accuracy':bb,'V2_accuracy':v,'delta_BASE_minus_V2':float(d)} for q,bb,v,d in zip(panel,b,vv,y)]}


def plots(out, name, pca, perf):
    corr = np.array(pca['variable_component_correlations'])
    shown = min(4,pca['matrix_rank'])
    fig,(ax1,ax2) = plt.subplots(1,2,figsize=(11,5),gridspec_kw={'width_ratios':[1,1.3]})
    nums = np.arange(1,len(pca['covariance_eigenvalues'])+1)
    ax1.plot(nums,pca['covariance_eigenvalues'],'o-',label='Observed')
    ax1.plot(nums,pca['parallel_analysis']['eigenvalue_threshold95'],'o--',label='95% column-permutation null')
    ax1.set(xlabel='Principal component',ylabel='Standardized covariance eigenvalue',title='Outcome-blind scree / parallel analysis')
    ax1.legend(fontsize=8); ax1.grid(alpha=.15)
    im = ax2.imshow(corr[:,:shown],vmin=-1,vmax=1,cmap='RdBu_r',aspect='auto')
    ax2.set_yticks(range(len(pca['features'])),pca['features'])
    ax2.set_xticks(range(shown),[f'PC{i+1}\n{100*pca["explained_variance_ratio"][i]:.1f}%' for i in range(shown)])
    for i in range(corr.shape[0]):
        for j in range(shown):ax2.text(j,i,f'{corr[i,j]:+.2f}',ha='center',va='center',fontsize=9,color='white' if abs(corr[i,j])>.65 else 'black')
    ax2.set_title('Correlation of variable with component')
    fig.colorbar(im,ax=ax2,fraction=.04,pad=.04)
    fig.suptitle(f'{name}: {pca["questions"]} question-equal observations')
    fig.tight_layout();fig.savefig(out/f'{name}_pca.png',dpi=180);fig.savefig(out/f'{name}_pca.svg');plt.close(fig)
    fig,ax = plt.subplots(figsize=(7,4.5))
    rs = perf['axes'];r = np.array([a['pearson_r'] for a in rs]);ci=np.array([a['ci95_fixed_axis_question_bootstrap'] for a in rs])
    ax.errorbar(range(1,len(rs)+1),r,yerr=np.stack([r-ci[:,0],ci[:,1]-r]),fmt='o',capsize=4,color='#255b92')
    ax.axhline(0,color='#888',linestyle='--');ax.set(xlabel='Behavior-only principal component',ylabel='r with BASE minus V2 accuracy',title=f'{name}: performance joined after PCA')
    ax.set_xticks(range(1,len(rs)+1));ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(out/f'{name}_performance.png',dpi=180);fig.savefig(out/f'{name}_performance.svg');plt.close(fig)


def main():
    out = ROOT/'outputs'/('behavior_pca_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir()
    prior = read(ASSOC/'analysis.json')
    native = read(NATIVE)
    assert SOURCES[str(NATIVE)] == prior['source_sha256'][str(NATIVE)]
    mab = read(MAB)
    assert SOURCES[str(MAB)] == prior['source_sha256'][str(MAB)]
    frame_path = FRAMES_STUDY/'analysis_report/report.json'
    frames = read(frame_path)
    assert SOURCES[str(frame_path)] == prior['source_sha256'][str(frame_path)]
    frame_hashes = read(FRAMES_STUDY/'analysis_report/source_sha256.json')
    attempts = {(r['index'],r['cohort'],r['round'],r['arm']):r for r in native['attempts']}
    mab_lookup = {(r['question_index'],r['question_group'],r['run_source']):r for r in mab['rows']}
    core = [r for r in read(ASSOC/'joined_pairs.json') if r['round'] in ['H','R1','R2']]
    seal_rows = []
    for r in core:
        key = r['question_index'],r['cohort'],r['round']
        item = {'question_id':key[0],'cohort':key[1],'round':key[2]}
        for arm in ['BASE','V2']:
            a = attempts[(*key,arm)]
            m = measures(Path(a['trace_directory']),native['source_hashes'],a)
            for dim in ['planning','communication']:
                score = mab_lookup[key]['arms'][arm][dim]
                if score['status'] == 'success':
                    assert score['score'] == r[arm][dim]
                    m[dim] = score['score']
            item[arm] = m
        seal_rows.append(item)
    frame_rows = []
    for q in frames['per_question']:
        if not q['primary_valid_pair']:
            continue
        item = {'question_id':q['official_task_id'],'round':'single'}
        for arm in ['BASE','V2']:
            trace=FRAMES_STUDY/f"accounting_inputs/{arm}/traces/q-{q['loader_index_seed0']:04d}/trace"
            item[arm]=measures(trace,frame_hashes,q['behavior'][arm])
        frame_rows.append(item)
    write(out/'analysis_plan.json',{'behavior_deltas':'V2 minus BASE, raw differences; log-token sensitivity explicitly separate',
        'performance_delta':'BASE minus V2, joined only after all PCA variants frozen',
        'unit':'same valid matched rounds averaged within question, then equal questions',
        'candidate_pool25':CANDIDATES,'behavior_pool23':BEHAVIOR,'narrow8_sensitivity':NARROW,
        'redundancy':'Outcome-blind candidate order; remove incomplete/constant features, exact linear dependencies, then pairwise absolute r>=.95. Full pool retained as sensitivity.',
        'constructed_features':'depth3 node share, leaf share, search share, tools per E, LLM per node, tokens per LLM, output token share, cached-input share, tool/LLM failure shares',
        'missingness':'no imputation; both MAB scores required on both arms in each joint round; excluded rounds remain missing',
        'standardization':'sample mean0 / sample SD1 across question deltas, ddof1',
        'axis_retention':'leading observed eigenvalues above 95% independent-column-permutation null, 1000 replicates',
        'outcome_tests':'all nonzero PCs, 10000 performance permutations with within-model maximum-absolute-r correction',
        'bootstrap':'10000 paired-question resamples, fixed fitted axes; PCA estimation uncertainty not included',
        'seed':SEED,'no_correctness_feature_or_outcome_axis_selection':True})
    panels = {}
    panels['SEAL0_joint_independent'] = (aggregate(seal_rows,CANDIDATES,True),CANDIDATES)
    panels['SEAL0_joint_candidate_pool'] = (aggregate(seal_rows,CANDIDATES,True),CANDIDATES)
    panels['SEAL0_behavior_independent_all94'] = (aggregate(seal_rows,BEHAVIOR),BEHAVIOR)
    panels['FRAMES_behavior_independent'] = (aggregate(frame_rows,BEHAVIOR),BEHAVIOR)
    panels['SEAL0_joint_Edepth_sensitivity'] = (aggregate(seal_rows,CANDIDATES,True,E=True),CANDIDATES)
    panels['SEAL0_joint_logtoken_sensitivity'] = (aggregate(seal_rows,CANDIDATES,True,logtokens=True),CANDIDATES)
    panels['FRAMES_logtoken_sensitivity'] = (aggregate(frame_rows,BEHAVIOR,logtokens=True),BEHAVIOR)
    three_joint_ids = {q['question_id'] for q in panels['SEAL0_joint_independent'][0] if q['paired_rounds'] == 3}
    panels['SEAL0_joint_complete3_sensitivity'] = (aggregate([r for r in seal_rows if r['question_id'] in three_joint_ids],CANDIDATES,True),CANDIDATES)
    panels['SEAL0_joint_narrow8_sensitivity'] = (aggregate(seal_rows,NARROW,True),NARROW)
    phase1 = {}
    for name,(panel,features) in panels.items():
        write(out/f'{name}_behavior_inputs.json',panel)
        phase1[name] = fit_pca(panel,features,prune=name!='SEAL0_joint_candidate_pool')
        write(out/f'{name}_pca_only.json',phase1[name])
    assert phase1['SEAL0_joint_candidate_pool']['matrix_rank'] < len(phase1['SEAL0_joint_candidate_pool']['features'])
    freeze = {'frozen_before_performance':True,'created_at':datetime.now(timezone.utc).isoformat(),
              'files':{p.name:sha(p) for p in sorted(out.glob('*json'))}}
    write(out/'phase1_pca_freeze.json',freeze)
    print(json.dumps({'phase':'PCA frozen before performance','output':str(out),
        'models':{k:{'n':v['questions'],'rounds':v['paired_rounds'],'retained':v['parallel_analysis']['leading_retained_axes'],
                    'variance_first3':v['explained_variance_ratio'][:3]} for k,v in phase1.items()}},ensure_ascii=False),flush=True)
    seal_outcomes = {}
    for r in core:
        key=r['question_index'],r['cohort'],r['round']
        seal_outcomes[key[0],key[2]]={a:attempts[(*key,a)]['score'] for a in ['BASE','V2']}
    frame_outcomes={(q['official_task_id'],'single'):{a:q['arms'][a]['score'] for a in ['BASE','V2']} for q in frames['per_question'] if q['primary_valid_pair']}
    phase2={}
    for name,(panel,_) in panels.items():
        phase2[name]=performance(phase1[name],panel,frame_outcomes if name.startswith('FRAMES') else seal_outcomes)
        write(out/f'{name}_performance.json',phase2[name])
    for name in ['SEAL0_joint_independent','SEAL0_behavior_independent_all94','FRAMES_behavior_independent']:
        plots(out,name,phase1[name],phase2[name])
    coverage={'native_pairs':len(core),'native_questions':len({r['question_id'] for r in seal_rows}),
        'joint_pairs':phase1['SEAL0_joint_independent']['paired_rounds'],'joint_questions':phase1['SEAL0_joint_independent']['questions'],
        'joint_rounds_per_question':dict(Counter(q['paired_rounds'] for q in panels['SEAL0_joint_independent'][0])),
        'joint_missing_question_ids':sorted({r['question_id'] for r in seal_rows}-{q['question_id'] for q in panels['SEAL0_joint_independent'][0]}),
        'excluded_joint_rounds':[{'question_id':r['question_id'],'round':r['round'],
            'missing':[a+'.'+k for a in ['BASE','V2'] for k in ['planning','communication'] if k not in r[a]]}
            for r in seal_rows if not all(k in r[a] for a in ['BASE','V2'] for k in ['planning','communication'])],
        'unknown_recorded_token_usage_events':sum(r[a]['unknown_usage_events'] for r in seal_rows+frame_rows for a in ['BASE','V2']),
        'MAB_ceiling_both_arms5':{k:sum(all(r[a].get(k)==5 for a in ['BASE','V2']) for r in seal_rows if all(d in r[a] for a in ['BASE','V2'] for d in ['planning','communication'])) for k in ['planning','communication']}}
    write(out/'coverage.json',coverage)
    write(out/'native_summary_differences.json',SUMMARY_DIFFERENCES)
    write(out/'analysis.json',{'phase1_behavior_only_PCA':phase1,'phase2_native_performance':phase2,'coverage':coverage})
    lines=['# 行为变化量PCA：先行为、后performance', '',
        '全部行为Δ=V2−BASE；performance Δ=BASE−V2。PCA未使用正确率，不按正确率选题或选轴；所有行为输入、均值/标准差、主轴、解释率先冻结，再关联原生正确率。原始轨迹/分数均不改，零Agent/评分调用。', '',
        '用户澄清不固定九项，故扩展到25项候选：深度与树规模/宽度/分支、资源量、每执行节点工具强度、每节点LLM强度、单次LLM token量、搜索/输出token/缓存/失败构成、耗时及两项MAB分数。PCA输入本身不要求正交，主成分正交。主分析先只依据行为量去除缺失列、常量、精确线性依赖和绝对相关≥0.95的重复列；候选优先顺序冻结，去除记录全部公开。未去冗余候选池和原8项仅作敏感性，不按正确率挑变量。', '',
        f"SEAL0全94题272轮次：同时具有双方Planning/Communication的共同有效轮次{coverage['joint_pairs']}组，覆盖{coverage['joint_questions']}题；题内轮数分布{coverage['joint_rounds_per_question']}。缺失不填零，完整三轮共同有效{len(three_joint_ids)}题作为敏感性。FRAMES47题没有MAB分数，从23项行为候选量构造PCA。两benchmark分别拟合，不把同名PC当作同一轴。", '',
        '每个指标先在同一组有效轮次内计算V2−BASE并题内平均，再题目等权。标准化在题级差值上用样本均值/样本SD。深度根0、task_id唯一逻辑节点；E深度另作替代敏感性。工具动作不去重；token为完整账本已记录原生usage，包含缓存输入及run_end后的晚到请求，不是日志长度或账单；与旧摘要的差异另列native_summary_differences.json，不覆盖来源。没有工具时search_share/工具失败比例约定0；没有展开节点时分支量约定0；未知缓存usage为缺失、该候选列不插补。', '',
        '## Outcome-blind维度结构', '', '| 模型 | 题数/轮次 | 列数/秩 | PC1 | PC2 | PC3 | 前3累计 | 并行分析保留前几轴 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,p in phase1.items():
        ev=p['explained_variance_ratio'];lines.append(f"| {name} | {p['questions']}/{p['paired_rounds']} | {len(p['features'])}/{p['matrix_rank']} | {100*ev[0]:.2f}% | {100*ev[1]:.2f}% | {100*ev[2]:.2f}% | {100*sum(ev[:3]):.2f}% | {p['parallel_analysis']['leading_retained_axes']} |")
    for name in ['SEAL0_joint_independent','SEAL0_behavior_independent_all94','FRAMES_behavior_independent']:
        p,perf=phase1[name],phase2[name]
        lines += ['',f'## {name}: 主轴载荷与performance', '',f'![PCA结构]({out}/{name}_pca.png)', '',
            f"未纳入缺失列：{ {k:n for k,n in p['missing_feature_question_counts'].items() if n} }；常量列：{p['dropped_zero_variance_features']}；行为去冗余：{p['redundancy_exclusions']}。", '',
            '下表载荷是原标准化变量与主成分的相关；正/负为同向/反向，不是对正确率的影响系数。PC正负号按最大绝对系数朝正固定，与正确率无关。', '',
            '| 指标 | PC1 | PC2 | PC3 |', '|---|---:|---:|---:|']
        for key,cs in zip(p['features'],p['variable_component_correlations']):lines.append(f'| {key} | {cs[0]:+.3f} | {cs[1]:+.3f} | {cs[2]:+.3f} |')
        lines += ['', f"同一有效集合准确率{perf['BASE_accuracy']*100:.2f}%→{perf['V2_accuracy']*100:.2f}%。", '',
            '| PC | 行为方差占比 | 与BASE−V2的r | 固定轴95%区间 | Spearman | 单项置换p | 全轴max-r校正p | Δ百分点/1SD轴 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
        for a in perf['axes']:
            j=a['PC'];lo,hi=a['ci95_fixed_axis_question_bootstrap'];lines.append(f"| {j} | {100*p['explained_variance_ratio'][j-1]:.2f}% | {a['pearson_r']:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {a['spearman_r']:+.3f} | {a['p_permutation_unadjusted']:.4f} | {a['p_max_abs_r_within_model_all_axes']:.4f} | {a['slope_delta_pp_per_1SD_axis']:+.2f} |")
        joint=perf['retained_axes_joint_fit']
        lines += ['',f"仅用并行分析保留的轴{joint['axes']}拟合performance：样本内R²={joint['in_sample_R_squared']}，联合置换p={joint['p_permutation_joint']}。这不是因果解释率或验证集预测分数。", '',f'![performance关联]({out}/{name}_performance.png)']
    lines += ['', '## 敏感性摘要：先冻结各自PCA再看performance', '', '| 模型 | 保留轴 | 样本内联合R² | 联合置换p | 最强绝对关联PC/r/max-r校正p |', '|---|---|---:|---:|---|']
    for name,perf in phase2.items():
        j=perf['retained_axes_joint_fit'];a=max(perf['axes'],key=lambda a:abs(a['pearson_r']))
        lines.append(f"| {name} | {j['axes']} | {j['in_sample_R_squared']} | {j['p_permutation_joint']} | PC{a['PC']}/{a['pearson_r']:+.3f}/{a['p_max_abs_r_within_model_all_axes']:.4f} |")
    lines += ['', '## 解释边界', '',
        'PCA最大化行为方差，不最大化performance预测力；高方差轴未必与答题相关，低方差轴也可能有关。PCA主轴是描述统计方向，不证明潜在机制或因果中介。节点代数冗余、两项评分近满分、原始token的极端值、MAB可评分筛选均会影响轴；因此保留未去冗余池、无评分全94题、仅E、log-token、完整三轮及窄8项敏感性，不删极端题。log-token敏感性同时对total tokens和tokens per LLM做逐运行log1p再取V2−BASE，其他变量不变。并行分析的保留数只是一个无监督启发式，不是确定的真实潜在维度数。', '',
        '所有非零轴均关联performance；置换max-r只校正同一模型内看多个轴，不能校正尝试多个敏感性模型。区间为固定本次PCA轴的题目bootstrap，没有包含PCA轴估计的不确定性；一次性的FRAMES预算样本和原生判分疑点继续限制推断。没有因结果不显著而改变量、方向、门槛或重评分。']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    detail=['# 逐题主成分与原生performance', '', '| 数据集 | 题号 | 共同轮数 | PC1 | PC2 | PC3 | BASE准确率 | V2准确率 | BASE−V2，百分点 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name in ['SEAL0_joint_independent','SEAL0_behavior_independent_all94','FRAMES_behavior_independent']:
        for q,sc,oc in zip(panels[name][0],phase1[name]['question_scores'],phase2[name]['question_outcomes']):
            ss=sc['scores'];detail.append(f"| {name} | {q['question_id']} | {q['paired_rounds']} | {ss[0]:+.4f} | {ss[1]:+.4f} | {ss[2]:+.4f} | {100*oc['BASE_accuracy']:.2f}% | {100*oc['V2_accuracy']:.2f}% | {100*oc['delta_BASE_minus_V2']:+.2f} |")
    (out/'per_question.md').write_text('\n'.join(detail)+'\n')
    for name,hh in freeze['files'].items():assert sha(out/name)==hh
    repo=Path(__file__).resolve().parent
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    shutil.copyfile(__file__,out/'analysis_script.snapshot.py')
    subprocess.run(['git','bundle','create',str(out/'analysis_scripts.bundle'),'HEAD'],cwd=repo,check=True)
    for p,hh in SOURCES.items():assert sha(Path(p))==hh,p
    assert all(not Path(p).exists()for p in ABSENT_TOOL_LEDGERS)
    write(out/'source_sha256.json',SOURCES)
    write(out/'manifest.json',{'script_commit':commit,'phase1_frozen_before_performance':True,'source_files_verified':len(SOURCES),
        'original_records_modified':False,'scores_modified':False,'agent_calls':0,'grader_calls':0,
        'absent_tool_ledgers_with_verified_zero_native_tool_calls':ABSENT_TOOL_LEDGERS})
    sums={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'SHA256SUMS').write_text(''.join(f'{hh}  {n}\n' for n,hh in sums.items()))
    assert all(sha(out/n)==hh for n,hh in sums.items())
    print(json.dumps({'output':str(out),'coverage':{k:v for k,v in coverage.items() if k!='excluded_joint_rounds'},
        'models':{name:{'variance_first3':phase1[name]['explained_variance_ratio'][:3],
                       'retained':phase1[name]['parallel_analysis']['leading_retained_axes'],
                       'axes':perf['axes'],'joint':perf['retained_axes_joint_fit']} for name,perf in phase2.items()}},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
