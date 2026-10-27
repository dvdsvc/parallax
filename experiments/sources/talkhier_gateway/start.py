"""Start the isolated, single-process LiteLLM gateway; secrets stay in memory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import secrets
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-file', default='external_archive/env/glm_api.env')
    parser.add_argument('--port', type=int, default=4005)
    parser.add_argument('--output-dir', help='External proxy diagnostics directory')
    args = parser.parse_args()
    from dotenv import dotenv_values
    values = dotenv_values(args.credential_file)
    key = values.get('QWEN_API_KEY') or values.get('OPENAI_API_KEY')
    endpoint = values.get('QWEN_BASE_URL') or values.get('OPENAI_BASE_URL')
    quota = json.loads((HERE / 'quota.json').read_text())
    if not key or not endpoint or endpoint.rstrip('/') != quota['upstream_base_url']:
        raise ValueError('Expected the existing Beijing Qwen credential and endpoint')
    directory = Path(args.output_dir).resolve() if args.output_dir else ROOT / '.local/gateway/events' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, QWEN_API_KEY=key, QWEN_BASE_URL=endpoint, TALKHIER_GATEWAY_KEY=key,
               TALKHIER_GATEWAY_LOG_DIR=str(directory), LITELLM_LOCAL_MODEL_COST_MAP='True',
               LITELLM_TELEMETRY='False', LITELLM_TPM_TOKEN_RESERVATION_ENABLED='true',
               PYTHONPATH=str(ROOT))
    # Validation-only quota overrides must never enter an actual gateway launch.
    for name in ['TALKHIER_GATEWAY_TESTING', 'TALKHIER_TEST_RPM', 'TALKHIER_TEST_TPM',
                 'LITELLM_MASTER_KEY', 'DATABASE_URL', 'REDIS_HOST', 'REDIS_PORT', 'REDIS_PASSWORD', 'REDIS_URL',
                 'LEGACY_MULTI_INSTANCE_RATE_LIMITING']:
        env.pop(name, None)
    # The CLI requires a strong administrative key even with custom auth.
    # Generate a separate unused key in memory; experiment keys still use
    # custom_auth and its native shared RPM/TPM limits, not master-key bypass.
    env['LITELLM_MASTER_KEY'] = 'sk-' + secrets.token_urlsafe(48)
    binary = ROOT / '.local/gateway/.venv/bin/litellm'
    command = [str(binary), '--config', str(HERE / 'config.yaml'), '--host', '127.0.0.1',
               '--port', str(args.port), '--num_workers', '1']
    launch = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'quota': quota, 'command': command,
              'credential_file': args.credential_file, 'secrets_persisted': False,
              'administrative_key': 'separate random key generated in memory; not used by experiment clients',
              'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file()},
              'gateway_api_base': f'http://127.0.0.1:{args.port}/v1'}
    (directory / 'launch.json').write_text(json.dumps(launch, indent=2) + '\n')
    print(json.dumps({'gateway_api_base': launch['gateway_api_base'], 'log_dir': str(directory), 'proxy_workers': 1}), flush=True)
    return subprocess.call(command, env=env, cwd=ROOT)


if __name__ == '__main__':
    sys.exit(main())
