"""One recorded, minimal API compatibility check; no agent or parser changes."""
import argparse
from datetime import datetime, timezone
import sys

from langchain_openai import ChatOpenAI

from common import ROOT, workspace_environment
from direct_model import connection
from local_trace import LocalTrace, jsonable
from run_archive import RunArchive, write


PROBE_SCHEMA = {'title': 'ProbeAnswer', 'type': 'object',
    'properties': {'value': {'type': 'integer', 'description': 'The integer requested by the user'}},
    'required': ['value']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-file', default='external_archive/env/glm_api.env')
    parser.add_argument('--model', default='qwen3.7-flash')
    args = parser.parse_args()
    workspace_environment(offline=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = ROOT / '.local' / 'probes' / stamp
    archive = RunArchive(target, kind='provider_protocol_probe', parameters=vars(args),
                         command=[sys.executable, *sys.argv])
    trace = LocalTrace(target)
    status, failure = 'error', None
    prompt = 'Return the integer 7 using the specified JSON schema.'
    try:
        settings = connection(args.credential_file)
        effective = {'model': args.model, 'base_url': settings['base_url'], 'temperature': 0,
            'enable_thinking': True, 'thinking_budget': 8192, 'method': 'json_schema', 'strict': True,
            'pydantic_response_validation': False,
            'max_completion_tokens': 16384, 'max_tokens': None, 'output_limit_scope': 'thinking_plus_final_response',
            'request_timeout_seconds': 60, 'sdk_max_retries': 0,
            'langsmith_enabled': False, 'benchmark_result': False}
        archive.freeze_inputs(questions=[('protocol_probe', {'prompt': prompt, 'expected': 7})],
                              effective_configuration=effective)
        model = ChatOpenAI(model=args.model, api_key=settings['api_key'],
            base_url=settings['base_url'], temperature=0, timeout=60, max_retries=0,
            max_completion_tokens=16384, extra_body={'enable_thinking': True, 'thinking_budget': 8192})
        response = model.with_structured_output(PROBE_SCHEMA, method='json_schema', strict=True,
            include_raw=True).invoke(prompt, config={'callbacks': [trace],
            'metadata': {'launch_id': archive.uid, 'mlflow_run_id': archive.run_id}})
        write(target / 'response.json', jsonable(response))
        parsed = response['parsed']
        passed = response['parsing_error'] is None and isinstance(parsed, dict) and parsed.get('value') == 7
        write(target / 'result.json', {'passed': passed,
            'tool_calls': len(response['raw'].tool_calls), 'parsed_value': parsed.get('value') if parsed else None,
            'parsed_type': type(parsed).__name__, 'method': 'json_schema',
            'parsing_error': str(response['parsing_error']) if response['parsing_error'] else None})
        if not passed:
            raise RuntimeError('Minimal provider JSON Schema response did not produce the expected dictionary')
        status = 'completed'
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        summary = trace.finalize()
        metrics = {key: value for key, value in summary.items()
                   if isinstance(value, (int, float)) and not isinstance(value, bool)}
        archive.finalize(status, metrics=metrics, error=failure)
    print({'status': status, 'archive': str(target), 'mlflow_run_id': archive.run_id})


if __name__ == '__main__':
    main()
