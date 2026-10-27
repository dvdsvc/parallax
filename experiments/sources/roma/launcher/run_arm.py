"""Invoke the existing FRAMES paper-run interface; add archive/MLflow lifecycle only."""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
from argparse import Namespace
from pathlib import Path

def write(p,x):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

def main():
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);ns=p.parse_args();c=json.loads(ns.config.read_text());study=Path(c['study_directory'])
    for path,h in c['runtime_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
    assert c['condition']=='BASE' and c['workers']==8 and c['task_indices']==list(range(80))
    os.environ.update(ROMA_MODEL_OVERRIDE=c['model'],ROMA_TEMPERATURE_OVERRIDE=str(c['temperature']),
      ROMA_PROVIDER_LABEL=c['provider_label'],ROMA_ORG_AWARENESS_V2='1'if c['interventions']['organization_awareness_v2']else'0',
      ROMA_PROXY_ORG_AWARENESS_V2='0',ROMA_PROXY_SECOND_ORDER='0',ROMA_PROXY_SECOND_ORDER_LAYERS='{}',
      PYTHONHASHSEED='0',MLFLOW_DISABLE_AGENT_HINT='1')
    sys.path.insert(0,c['adapter_directory']);import run_isolated_frames as frames
    base=frames.base
    args=Namespace(frames_tsv=c['frames_tsv'],frames_tasks_jsonl=c['frames_tasks_jsonl'],selected_indices=c['task_indices'],
      workers=c['workers'],max_depth=c['max_depth'],condition=c['condition'],project_root=c['agent_directory'],python=c['agent_python'],
      paper_run=True,paper_runs_root=str(study/'paper_runs'),paper_run_id=c['paper_run_id'],output=str(study/'results'/f"{c['arm']}.csv"),
      paper_run_config_path=ns.config.resolve(),profile='general',benchmark='FRAMES',mlflow_python=c['mlflow_python'],
      mlflow_tracking_uri=c['mlflow_tracking_uri'],mlflow_experiment=c['mlflow_experiment'])
    base.validate_external_model_settings();base.ensure_git_provenance(args);base.ensure_mlflow_ready(args)
    archive_cls=frames.FramesPaperRunArchive
    state_path=study/'state'/f"{c['arm']}.json"
    if state_path.exists():raise FileExistsError('Refuse duplicate arm launch')
    class LoggedArchive(archive_cls):
        @classmethod
        def create(cls,**kwargs):
            a=super().create(**kwargs)
            try:rid=base.start_mlflow_record(a,args)
            except Exception as exc:a.mark_preflight_failure(str(exc));raise
            # Full agent commit bundle + byte-exact tracked runtime snapshot are captured once at study scope.
            write(a.root/'code_state'/'study_snapshot_reference.json',{'study':str(study),'source_snapshot':str(study/'source_snapshot'),
              'snapshot_manifest_sha256':hashlib.sha256((study/'source_snapshot'/'manifest.json').read_bytes()).hexdigest(),
              'launcher_commit':c['launcher_commit'],'arm':c['arm']})
            shutil.copyfile(__file__,a.root/'code_state'/'run_arm.snapshot.py')
            write(state_path,{'status':'running','archive':str(a.root),'mlflow_run_id':rid,'arm':c['arm'],'pid':os.getpid()})
            return a
        def finalize(self,**kwargs):
            self.set_worker_root(kwargs['worker_root'],model_visible_path_policy='opaque_run_id_v1',worker_python_hash_seed='0',tool_order_policy='fixed_python_hash_seed_v1')
            super().finalize(**kwargs)
            rid=json.loads(state_path.read_text())['mlflow_run_id']
            base.index_paper_archive(self,args,rid)
            write(state_path,{'status':'finished','archive':str(self.root),'worker_root':str(kwargs['worker_root']),
              'mlflow_run_id':rid,'arm':c['arm'],'controller':kwargs['controller_state'],'pid':os.getpid()})
    frames.FramesPaperRunArchive=LoggedArchive
    asyncio.run(frames.main_async(args))

if __name__=='__main__':main()
