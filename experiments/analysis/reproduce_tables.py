#!/usr/bin/env python3
"""Verify the submitted archive and recompute primary tables without API calls."""
from pathlib import Path
import json,csv,hashlib,statistics,math
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'data'/name).read_text())
def mean(xs):return statistics.mean(xs)
def close(actual,expected):assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10),(actual,expected)
def verify():
 checksum=ROOT/'SHA256SUMS'
 assert checksum.exists(),'Missing package checksums'
 n=0
 for line in checksum.read_text().splitlines():
  expected,path=line.split('  ',1);f=ROOT/path
  assert f.is_file(),path
  assert hashlib.sha256(f.read_bytes()).hexdigest()==expected,path
  n+=1
 return n
verified=verify();out={'package_files_verified':verified,'difference_direction':'ORG-DESC minus BASE','tables':{}}
# Table 2: average the same valid rounds within question, then weight questions equally.
seal=read('seal0_results.json');qs=seal['per_question'];assert len(qs)==94
assert sum(len(q['rounds']) for q in qs)==272
scores=[mean(mean(q['y'][a]) for q in qs) for a in [0,1]]
for a,k in enumerate(['BASE','V2']):close(scores[a],seal['all94']['accuracy'][k]['mean'])
full=[q for q in qs if len(q['rounds'])==3];assert len(full)==86
reliability={k:{'pass_at_3_count':sum(any(q['y'][a]) for q in full),'pass_all_3_count':sum(all(q['y'][a]) for q in full),'questions':86} for a,k in enumerate(['BASE','ORG-DESC'])}
frames=read('frames_question_metrics.json');paired=[q for q in frames if q['primary_valid_pair']];assert len(frames)==50 and len(paired)==47
fs=[mean(q['arms'][k]['score'] for q in paired) for k in ['BASE','V2']]
with (ROOT/'data/talkhier_primary_pairs.csv').open(encoding='utf-8-sig') as f:tp=list(csv.DictReader(f))
tp=[q for q in tp if q['paired_valid']=='1'];assert len(tp)==94
ts=[mean(int(q[k+'_correct']) for q in tp) for k in ['BASE','V2']]
ref=read('whole_experiment_reconciliation.json')
for k,a in enumerate(['BASE','V2']):
 close(fs[k],ref['FRAMES']['correct'][a]/47);close(ts[k],ref['TalkHier']['mean_metrics'][a]['correct'])
for setting,s in [('ROMA SEAL-0',scores),('ROMA FRAMES',fs),('TalkHier Physics',ts)]:
 out['tables'].setdefault('Table 2',{})[setting]={'BASE':s[0],'ORG-DESC':s[1],'difference_percentage_points':100*(s[1]-s[0])}
out['reliability_complete86']=reliability
# Table 3: use independent question panels, not a rounded manuscript table.
rec=read('roma_recursion.json')['primary_all94_question_equal']['panel'];assert len(rec)==94
metrics={}
for setting,source in [('ROMA SEAL-0',rec),('ROMA FRAMES',paired)]:
 for metric in ['nodes','expanded','total_tokens']:
  vals=[]
  for arm,a in enumerate(['BASE','V2']):
   if setting=='ROMA SEAL-0':
    val=mean(mean(q['t'][arm]) for q in qs) if metric=='total_tokens' else mean(q['metrics'][metric][a] for q in source)
   else:
    key={'nodes':'agent_nodes','expanded':'expanded_nodes','total_tokens':'total_tokens'}[metric]
    val=mean(q['behavior'][a][key] for q in source)
   close(val,ref['SEAL0' if setting=='ROMA SEAL-0' else 'FRAMES']['mean_trees'][a][metric]);vals.append(val)
  metrics[setting+' / '+metric]={'BASE':vals[0],'ORG-DESC':vals[1],'relative_change_percent':100*(vals[1]/vals[0]-1)}
for field,refkey in [('normal_calls','normal_calls'),('normal_total_tokens','total_tokens'),('output_tool_calls','output_tool')]:
 vals=[mean(int(q[a+'_'+field]) for q in tp) for a in ['BASE','V2']]
 for a,k in enumerate(['BASE','V2']):close(vals[a],ref['TalkHier']['mean_metrics'][k][refkey])
 metrics['TalkHier Physics / '+field]={'BASE':vals[0],'ORG-DESC':vals[1],'relative_change_percent':100*(vals[1]/vals[0]-1)}
out['tables']['Table 3']=metrics
# Table 4: require the same common panel for both dimensions.
collab=read('collaboration_derivation.json');cp=collab['question_panel'];assert len(cp)==86 and collab['round_pairs']==227
cm={}
for dim in ['planning','communication','composite']:
 vals=[mean(q[a][dim] for q in cp) for a in ['BASE','V2']]
 for k,a in enumerate(['BASE','V2']):close(vals[k],collab['metrics'][dim][a])
 cm[dim]={'BASE':vals[0],'ORG-DESC':vals[1],'difference':vals[1]-vals[0],'frozen_paired_95_interval':collab['metrics'][dim]['paired_95_interval']}
out['tables']['Table 4']=cm
out['uncertainty']='Existing frozen intervals are retained; this script does not create new inferential analyses.'
out['passed']=True
print(json.dumps(out,indent=2))
