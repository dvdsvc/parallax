"""Start BASE and V2 together at 8 workers each; then run native grading once."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime,timezone

study=Path(sys.argv[1]).resolve();plan=json.loads((study/'launch_plan.json').read_text());state_path=study/'execution_state.json'
if state_path.exists():raise SystemExit('Refuse duplicate study launch')
for file,h in plan['runtime_sha256'].items():assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==h,file
state={'status':'starting','pid':os.getpid(),'max_question_concurrency':16,'workers_per_arm':8,'runs':[],'started_at':datetime.now(timezone.utc).isoformat()}
def save():
    state['updated_at']=datetime.now(timezone.utc).isoformat();tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(state_path)
processes=[];logs=[];stop_requested=False
def stop(signum,frame):
    global stop_requested
    stop_requested=True
    for proc in processes:
        if proc.poll()is None:proc.send_signal(signal.SIGINT)
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop);save()
env={**os.environ,'PYTHONUNBUFFERED':'1','PYTHONHASHSEED':'0','MLFLOW_DISABLE_AGENT_HINT':'1'}
try:
    for arm in ['BASE','V2']:
        f=(study/'logs'/f'{arm}.log').open('x');logs.append(f)
        cmd=[plan['agent_python'],str(Path(__file__).parent/'run_arm.py'),str(study/'config'/f'{arm}.json')]
        proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env);processes.append(proc)
        state['runs'].append({'arm':arm,'pid':proc.pid,'command':cmd,'exit_code':None});save()
    state['status']='agent_runs_running';save()
    while any(p.poll()is None for p in processes):
        for proc,r in zip(processes,state['runs']):r['exit_code']=proc.poll()
        save();time.sleep(10)
    for proc,r in zip(processes,state['runs']):r['exit_code']=proc.returncode
    if stop_requested or any(r['exit_code']!=0 for r in state['runs']):state['status']='needs_attention';save();raise SystemExit(1)
    state['status']='native_grading_running';save()
    # Trusted credential loading stays in the grader process; no values are logged or archived.
    import shlex
    cmd=['/bin/zsh','-c','set -e; set -a; source '+shlex.quote(plan['credential_file'])+'; set +a; exec '+shlex.join([plan['agent_python'],str(Path(__file__).parent/'grade_native.py'),str(study)])]
    with(study/'logs'/'grading.log').open('x')as f:
        proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env);processes.append(proc)
        state['grader_pid']=proc.pid;save();code=proc.wait()
    state.update(status='finished'if code==0 else'needs_attention',grader_exit_code=code);save()
finally:
    for f in logs:f.close()
