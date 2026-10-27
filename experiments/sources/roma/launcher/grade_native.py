"""Call ROMA SearchMetric.forward unchanged, recording inputs/raw history/native score."""
import argparse
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,timezone

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):('<REDACTED>'if any(z in str(k).lower()for z in ['api_key','authorization','password','secret'])else clean(v))for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    return x

def main():
    p=argparse.ArgumentParser();p.add_argument('study',type=Path);args=p.parse_args();study=args.study.resolve();plan=json.loads((study/'launch_plan.json').read_text())
    agent=Path(plan['agent_directory']);sys.path.insert(0,str(agent));sys.path.insert(0,str(agent/'src'))
    import dspy
    from prompt_optimization.config import LMConfig
    from prompt_optimization.metrics.search_metric import SearchMetric
    from prompt_optimization.prompts.grader_prompts import SEARCH_GRADER_PROMPT
    os.environ['OPENAI_API_KEY']=os.environ['QWEN_API_KEY'];os.environ['OPENAI_API_BASE']=os.environ['QWEN_BASE_URL'];os.environ['OPENAI_BASE_URL']=os.environ['QWEN_BASE_URL']
    out=study/'native_grading';out.mkdir(exist_ok=False);(out/'records').mkdir()
    mapping={r['selected80_loader_index_seed0']:r for r in [json.loads(x)for x in(study/'benchmark_snapshot/candidate80_index.jsonl').read_text().splitlines()]}
    work=[];excluded=[];sources={}
    for arm in ['BASE','V2']:
        state=json.loads((study/'state'/f'{arm}.json').read_text());archive=Path(state['archive']);source=archive/'outputs.jsonl';sources[str(source)]=sha(source)
        for row in [json.loads(x)for x in source.read_text().splitlines()]:
            index=int(row['question_index']);rec=mapping[index];assert row['goal']==rec['goal']
            rm=archive/'traces'/f'q-{index:04d}'/'recording_manifest.json';record=json.loads(rm.read_text())
            eligible=row['status']=='COMPLETED'and record.get('recorder_status')=='complete'and record.get('condition_validation')=='validated'and record.get('experiment_validation')=='validated'
            if eligible:work.append({'arm':arm,'official_task_id':rec['official_task_id'],'index':index,'archive':str(archive),
                'question':row['goal'],'gold_answer':row['ground_truth'],'predicted_answer':row['predicted_answer']})
            else:excluded.append({'arm':arm,'official_task_id':rec['official_task_id'],'index':index,'execution_status':row['status'],'recorder':record.get('recorder_status'),'experiment_validation':record.get('experiment_validation'),'score':None})
    (out/'prompt.txt').write_text(SEARCH_GRADER_PROMPT)
    manifest={'started_at':datetime.now(timezone.utc).isoformat(),'native_class':'prompt_optimization.metrics.search_metric.SearchMetric',
      'native_call':'forward(example, prediction)','metric_sha256':sha(agent/'prompt_optimization/metrics/search_metric.py'),
      'prompt_sha256':hashlib.sha256(SEARCH_GRADER_PROMPT.encode()).hexdigest(),'model':plan['model'],'temperature':0,'max_tokens':1024,'cache':True,
      'workers':16,'source_sha256':sources,'eligible':len(work),'excluded':excluded,'input_or_scoring_rewrites':False}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (out/'inputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in work))
    def score(r):
        metric=SearchMetric(LMConfig(model=plan['model'],temperature=0,max_tokens=1024,cache=True));value=None;err=None
        try:value=metric.forward(dspy.Example(goal=r['question'],answer=r['gold_answer']),dspy.Prediction(result_text=r['predicted_answer']))
        except Exception as exc:err={'type':type(exc).__name__,'message':str(exc)}
        history=clean(metric.lm.history)
        result={**r,'status':'success'if err is None else'error','score':value,'error':err,'native_lm_history':history}
        name=f"{r['arm']}_q{r['official_task_id']}.json";(out/'records'/name).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');return result
    results=[]
    with ThreadPoolExecutor(max_workers=16)as pool:
        for future in as_completed([pool.submit(score,r)for r in work]):
            r=future.result();results.append(r)
            with(out/'progress.jsonl').open('a')as f:f.write(json.dumps({k:r[k]for k in ['arm','official_task_id','index','status','score']})+'\n')
    (out/'results.json').write_text(json.dumps({'results':sorted(results,key=lambda r:(int(r['official_task_id']),r['arm'])),'excluded':excluded},ensure_ascii=False,indent=2,default=str)+'\n')
    for f,h in sources.items():assert sha(Path(f))==h
    (out/'SHA256SUMS').write_text(''.join(f'{sha(f)}  {f.relative_to(out)}\n'for f in sorted(out.rglob('*'))if f.is_file()and f.name!='SHA256SUMS'))
    print(json.dumps({'success':sum(r['status']=='success'for r in results),'errors':sum(r['status']=='error'for r in results),'excluded':len(excluded)}))

if __name__=='__main__':main()
