"""Freeze the supplied eighty tasks and current runtime identities; no paid calls."""
import ast
import csv
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path
from datetime import datetime,timezone

HIRA=Path('external_archive/2026-09-12/hira')
SOURCE=Path('external_archive/2026-10-02/frames/outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames80_index_20261004')
REPO=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def main():
    for line in(SOURCE/'checksums.sha256').read_text().splitlines():
        h,n=line.split('  ',1);assert sha(SOURCE/n)==h,n
    index=[json.loads(x)for x in(SOURCE/'candidate80_index.jsonl').read_text().splitlines()]
    tasks=[json.loads(x)for x in(SOURCE/'candidate80_tasks_native.jsonl').read_text().splitlines()]
    with(SOURCE/'candidate80_native_test.tsv').open()as f:rows=list(csv.DictReader(f,delimiter='\t'))
    assert len(rows)==len(tasks)==len(index)==80 and len({r['official_task_id']for r in index})==80
    random.Random(0).shuffle(rows)
    for i in index:
        r=rows[i['selected80_loader_index_seed0']];t=next(t for t in tasks if str(t['task_id'])==i['official_task_id'])
        assert r['']==i['official_task_id'] and r['Prompt']==i['goal']==t['goal'] and r['Answer']==t['answer']
        assert hashlib.sha256(i['goal'].encode()).hexdigest()==i['goal_sha256']
    for file in REPO.glob('*.py'):ast.parse(file.read_text())
    assert not subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'])
    commit=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD']).decode().strip()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');study=SOURCE.parents[1]/f'frames80_BASE_V2_paper_{stamp}'
    study.mkdir(exist_ok=False)
    for d in ['config','benchmark_snapshot','source_snapshot','state','logs','results']: (study/d).mkdir()
    sample_files=['sampling_script_snapshot.py','selection_manifest.json','sampling_audit.json','sampling_review.md','strata80_quotas.csv',
      'candidate80_index.jsonl','candidate80_index.csv','candidate80_native_test.tsv','candidate80_tasks_native.jsonl','candidate80_official_ids.txt','command.txt','checksums.sha256']
    sample_hashes={}
    for name in sample_files:shutil.copyfile(SOURCE/name,study/'benchmark_snapshot'/name);sample_hashes[str(SOURCE/name)]=sha(SOURCE/name)
    roots={'agent':HIRA/'forammas','adapters':HIRA/'work/roma_v1_adapters','proxy':HIRA/'work/roma_litellm_proxy','controls':HIRA/'work/forammas_study','launcher':REPO}
    runtime={};identities={};snap=study/'source_snapshot'
    for name,root in roots.items():
        gitcommit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
        status=subprocess.check_output(['git','-C',str(root),'status','--porcelain']).decode().splitlines()
        identities[name]={'root':str(root),'commit':gitcommit,'status':status}
        files=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
        for rel in files:
            if not rel:continue
            src=root/rel
            if not src.is_file()or src.suffix=='.env':continue
            dest=snap/name/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
            runtime[str(src)]=sha(src)
        diff=subprocess.check_output(['git','-C',str(root),'diff','--binary','HEAD'])
        (snap/f'{name}.git.diff').write_bytes(diff)
    for name in ['agent','launcher']:
        subprocess.run(['git','-C',str(roots[name]),'bundle','create',str(snap/f'{name}.bundle'),'--all'],check=True,capture_output=True)
    for path in sample_hashes:runtime[path]=sample_hashes[path]
    write(snap/'manifest.json',{'created_at':datetime.now(timezone.utc).isoformat(),'repositories':identities,'tracked_source_sha256':runtime,
      'full_agent_git_bundle':'agent.bundle','launcher_git_bundle':'launcher.bundle','credential_files_included':False})
    common={'schema_version':1,'study_directory':str(study),'condition':'BASE','task_indices':list(range(80)),'workers':8,'max_depth':3,
      'model':'openai/qwen3.7-flash','temperature':0,'provider_label':'dashscope-compatible-via-litellm-proxy',
      'frames_tsv':str(study/'benchmark_snapshot/candidate80_native_test.tsv'),'frames_tasks_jsonl':str(study/'benchmark_snapshot/candidate80_tasks_native.jsonl'),
      'agent_directory':str(HIRA/'forammas'),'agent_python':str(HIRA/'forammas/.venv/bin/python'),'adapter_directory':str(HIRA/'work/roma_v1_adapters'),
      'mlflow_python':str(HIRA/'work/forammas_study/.venv/bin/python'),'mlflow_tracking_uri':'sqlite:///'+str(HIRA/'work/forammas_study/mlflow.db'),
      'mlflow_experiment':'ROMA-FRAMES80-BASE-V2','launcher_commit':commit,'runtime_sha256':runtime,
      'sampling_seed':20261003,'native_loader_seed':0,'task_count':80,'target_sampling_frame_N':783}
    for arm in ['BASE','V2']:
        config={**common,'arm':arm,'paper_run_id':f'frames80-{arm.lower()}-{stamp}',
          'interventions':{'organization_awareness_v2':arm=='V2','second_order':{'enabled':False,'layers':{}}}}
        write(study/'config'/f'{arm}.json',config)
    write(study/'launch_plan.json',{**common,'credential_file':'external_archive/env/glm_api.env',
      'runtime_sha256':{**runtime,**{str(study/'config'/f'{arm}.json'):sha(study/'config'/f'{arm}.json')for arm in ['BASE','V2']}},
      'total_attempts':160,'question_concurrency':16,'agent_commit':identities['agent']['commit'],'source_sampling_directory':str(SOURCE)})
    write(study/'preflight_verification.json',{'sample_files_sha256':sample_hashes,'IDs_goals_answers_loader_mapping_verified':True,
      'agent_source_modified_by_launch':False,'native_grader':'SearchMetric.forward','agent_commit':identities['agent']['commit'],'launcher_commit':commit})
    (study/'README.md').write_text('# FRAMES80 BASE/V2 paper run\n\n80 frozen questions, one execution per arm, 8+8 question concurrency. Official IDs map to the seed-0 native80 loader in benchmark_snapshot/candidate80_index.jsonl. Sampling seed 20261003 is distinct from loader seed 0. Both arms condition BASE; V2 alone enables the existing static organization-awareness block. Native SearchMetric.forward grading follows both executions. Original sampling archive remains unchanged. Agent/config/runtime snapshots and bundles live in source_snapshot and per-arm paper_runs.\n')
    print(study)

if __name__=='__main__':main()
