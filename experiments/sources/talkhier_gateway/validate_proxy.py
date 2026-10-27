"""Exercise the actual LiteLLM native limiter against a local fake upstream."""
import asyncio
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


async def main():
    directory = ROOT / '.local/gateway/validation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_proxy')
    directory.mkdir(parents=True)
    entered, release = Event(), Event()
    records, lock, mode = [], Lock(), {'hold': False, '429': False}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock:
                records.append(body)
            if mode['hold']:
                entered.set()
                release.wait(10)
            if mode['429']:
                self.send_response(429)
                self.send_header('retry-after', '1')
                payload = {'error': {'message': 'Requests rate limit exceeded', 'type': 'rate_limit_error', 'code': 'Throttling'},
                           'request_id': 'offline-upstream-429'}
            else:
                self.send_response(200)
                payload = {'id': 'chatcmpl-offline-proxy', 'object': 'chat.completion', 'created': 0, 'model': 'qwen3.7-flash',
                    'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 7, 'completion_tokens': 13, 'total_tokens': 20,
                              'completion_tokens_details': {'reasoning_tokens': 5}}}
            encoded = json.dumps(payload).encode()
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    upstream = f'http://127.0.0.1:{server.server_port}/v1'
    os.environ.update(QWEN_BASE_URL=upstream, QWEN_API_KEY='sk-offline-provider', TALKHIER_GATEWAY_KEY='sk-offline-tpm',
        TALKHIER_GATEWAY_TESTING='1', TALKHIER_TEST_RPM='30000', TALKHIER_TEST_TPM='20000',
        TALKHIER_GATEWAY_LOG_DIR=str(directory), LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False',
        LITELLM_TPM_TOKEN_RESERVATION_ENABLED='true')
    import yaml
    import httpx
    from litellm.proxy import proxy_server
    config = yaml.safe_load((ROOT / 'repro/gateway/config.yaml').read_text())
    config_path = directory / 'offline_config.yaml'
    config_path.write_text(yaml.safe_dump(config))
    await proxy_server.initialize(config=str(config_path))
    # ASGITransport does not run the server lifespan. Invoke the same native
    # callback-registration stage used by the CLI startup, including its limiter.
    proxy_server.proxy_logging_obj.startup_event(llm_router=proxy_server.llm_router, redis_usage_cache=None)
    body = {'model': 'qwen3.7-flash', 'messages': [{'role': 'user', 'content': 'offline quota check'}],
            'temperature': 0, 'max_completion_tokens': 16384, 'enable_thinking': True, 'thinking_budget': 8192}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy_server.app), base_url='http://offline-proxy') as client:
        async def send(key='sk-offline-tpm', **headers):
            return await client.post('/v1/chat/completions', headers={'authorization': 'Bearer ' + key,
                'x-talkhier-logical-call-id': key.removeprefix('sk-'), **headers}, json=body)
        mode['hold'] = True
        first = asyncio.create_task(send())
        ok = await asyncio.to_thread(entered.wait, 10)
        if not ok:
            if first.done():
                result = first.result()
                raise AssertionError(f'First upstream not entered: {result.status_code}: {result.text[:1000]}')
            raise AssertionError('First provider was not reached')
        rejected = await asyncio.gather(*(send() for _ in range(99)))
        assert all(second.status_code == 429 for second in rejected)
        assert all(second.headers.get('x-talkhier-rate-limit-origin') == 'litellm_local' for second in rejected)
        assert len(records) == 1, 'Rejected reservation must not reach upstream'
        release.set()
        result = await first
        assert result.status_code == 200, result.text
        mode['hold'] = False
        await asyncio.sleep(0.25)
        reconciled = await send()
        assert reconciled.status_code == 200, (reconciled.status_code, reconciled.text)
        assert len(records) == 2, 'Actual usage correction must free the unused reservation'
        assert records[0]['max_completion_tokens'] == 16384 and 'max_tokens' not in records[0], records[0]
        assert records[0]['enable_thinking'] is True and records[0]['thinking_budget'] == 8192, records[0]

        os.environ.update(TALKHIER_GATEWAY_KEY='sk-offline-rpm', TALKHIER_TEST_RPM='1')
        before = len(records)
        rpm_first, rpm_second = await send('sk-offline-rpm'), await send('sk-offline-rpm')
        assert rpm_first.status_code == 200 and rpm_second.status_code == 429
        assert rpm_second.headers.get('x-talkhier-rate-limit-origin') == 'litellm_local'
        assert len(records) == before + 1

        os.environ.update(TALKHIER_GATEWAY_KEY='sk-offline-upstream', TALKHIER_TEST_RPM='30000')
        mode['429'] = True
        provider_limit = await send('sk-offline-upstream')
        assert provider_limit.status_code == 429, provider_limit.text
        assert provider_limit.headers.get('x-talkhier-rate-limit-origin') == 'qwen_upstream', dict(provider_limit.headers)
        assert provider_limit.headers.get('retry-after') == '1', dict(provider_limit.headers)
    release.set()
    server.shutdown()
    server.server_close()
    report = {'validated_at_utc': datetime.now(timezone.utc).isoformat(), 'output': str(directory),
        'native_LiteLLM_TPM_reservation_blocks_second_inflight_call': True,
        'native_inflight_stress_concurrency': 100, 'native_locally_rejected_concurrent_requests': 99,
        'rejected_local_429_never_reaches_provider': True, 'native_usage_reconciliation_frees_reservation': True,
        'native_RPM_limit_verified': True, 'local_429_origin': 'litellm_local', 'upstream_429_origin': 'qwen_upstream',
        'upstream_Retry_After_preserved': True, 'thinking_and_max_completion_tokens_preserved': True,
        'mock_upstream_requests': len(records), 'real_provider_calls': 0}
    (directory / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    asyncio.run(main())
