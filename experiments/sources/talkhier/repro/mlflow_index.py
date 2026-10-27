"""Local MLflow metadata/artifact index, run in a separate installed environment."""
import json
import os
from pathlib import Path
import sys


def main():
    request = json.load(sys.stdin)
    os.environ['MLFLOW_DISABLE_TELEMETRY'] = 'true'
    import mlflow
    from mlflow.tracking import MlflowClient
    client = MlflowClient(tracking_uri=request['tracking_uri'])
    action = request['action']
    if action == 'start':
        experiment = client.get_experiment_by_name(request['experiment'])
        if experiment is None:
            path = Path(request['artifact_root']).resolve()
            path.mkdir(parents=True, exist_ok=True)
            try:
                experiment_id = client.create_experiment(request['experiment'], artifact_location=path.as_uri())
            except mlflow.exceptions.MlflowException:
                experiment = client.get_experiment_by_name(request['experiment'])
                if experiment is None:
                    raise
                experiment_id = experiment.experiment_id
        else:
            experiment_id = experiment.experiment_id
        tags = {'mlflow.runName': request['run_name'], 'archive_status': 'starting',
                'local_archive': request['archive'], **request.get('tags', {})}
        run = client.create_run(experiment_id, tags={k: str(v) for k, v in tags.items()})
        run_id = run.info.run_id
        try:
            for key, value in request.get('params', {}).items():
                if value is not None:
                    client.log_param(run_id, key, str(value))
        except BaseException:
            client.set_terminated(run_id, status='FAILED')
            raise
        print(json.dumps({'run_id': run_id, 'experiment_id': experiment_id,
              'tracking_uri': request['tracking_uri'], 'mlflow_version': mlflow.__version__,
              'index_python': sys.executable, 'artifact_uri': run.info.artifact_uri,
              'telemetry_enabled': False}))
        return
    run_id = request['run_id']
    if action == 'update':
        for key, value in request.get('params', {}).items():
            if value is not None:
                client.log_param(run_id, key, json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value))
        for key, value in request.get('tags', {}).items():
            client.set_tag(run_id, key, str(value))
        if request.get('startup_directory'):
            client.log_artifacts(run_id, request['startup_directory'], artifact_path='startup')
    elif action == 'finish':
        archive = Path(request['archive'])
        # Parent launches contain worker archives; index each worker under its
        # own run and keep references in the parent rather than duplicate them.
        exclude = set(request.get('exclude_children', []))
        for path in sorted(archive.iterdir()):
            if path.name in exclude:
                continue
            if path.is_dir():
                client.log_artifacts(run_id, str(path), artifact_path=f'run_archive/{path.name}')
            else:
                client.log_artifact(run_id, str(path), artifact_path='run_archive')
        for key, value in request.get('metrics', {}).items():
            if value is not None and isinstance(value, (int, float)):
                client.log_metric(run_id, key, float(value))
        for key, value in request.get('tags', {}).items():
            client.set_tag(run_id, key, str(value))
        client.set_terminated(run_id, status=request['mlflow_status'])
    elif action == 'inspect':
        run = client.get_run(run_id)
        print(json.dumps({'run_id': run.info.run_id, 'status': run.info.status,
                         'params': dict(run.data.params), 'metrics': dict(run.data.metrics), 'tags': dict(run.data.tags),
                         'artifact_names': [x.path for x in client.list_artifacts(run_id, 'run_archive')]}))
        return
    else:
        raise ValueError(f'Unknown index action: {action}')
    print(json.dumps({'run_id': run_id, 'action': action, 'success': True}))


if __name__ == '__main__':
    main()
