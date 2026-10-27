"""LiteLLM native auth/limits plus measured 429-origin headers and sidecar logs."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.common_utils.proxy_rate_limit_error import ProxyRateLimitError

HERE = Path(__file__).resolve().parent
QUOTA = json.loads((HERE / 'quota.json').read_text())


async def authenticate(request: Request, api_key: str) -> UserAPIKeyAuth:
    expected = os.environ.get('TALKHIER_GATEWAY_KEY')
    if not expected or not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail='Invalid gateway credential')
    rpm, tpm = QUOTA['rpm'], QUOTA['tpm']
    if os.environ.get('TALKHIER_GATEWAY_TESTING') == '1':
        rpm = int(os.environ.get('TALKHIER_TEST_RPM', rpm))
        tpm = int(os.environ.get('TALKHIER_TEST_TPM', tpm))
    body = await request.json() if request.method == 'POST' else {}
    if body.get('model', QUOTA['model']) != QUOTA['model']:
        raise HTTPException(status_code=400, detail='This experiment gateway permits only qwen3.7-flash')
    # BASE and V2 deliberately use the same authenticated key/counter scope.
    return UserAPIKeyAuth(api_key=api_key, rpm_limit=rpm, tpm_limit=tpm)


def classify_rate_limit(error):
    if isinstance(error, ProxyRateLimitError):
        return 'litellm_local', 'native_ProxyRateLimitError'
    upstream = urlsplit(os.environ.get('QWEN_BASE_URL', QUOTA['upstream_base_url'])).netloc
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        response = getattr(error, 'response', None)
        try:
            request = response.request if response is not None else getattr(error, 'request', None)
        except RuntimeError:
            request = None
        if request is not None:
            if str(getattr(request, 'method', '')).lower() == 'tpm_rpm_limits':
                return 'litellm_local', 'native_router_tpm_rpm_method'
            if response is not None and getattr(response, 'status_code', None) == 429 and urlsplit(str(request.url)).netloc == upstream:
                return 'qwen_upstream', 'HTTP_429_response_from_configured_upstream'
        error = getattr(error, '__cause__', None) or getattr(error, '__context__', None)
    return 'unknown', 'no_definitive_upstream_or_native_limiter_evidence'


def request_identity(data):
    proxy = (data.get('litellm_params') or {}).get('proxy_server_request') or data.get('proxy_server_request') or {}
    headers = {str(k).lower(): v for k, v in (proxy.get('headers') or {}).items()}
    return {'logical_call_id': headers.get('x-talkhier-logical-call-id'),
            'http_attempt': headers.get('x-talkhier-http-attempt'),
            'litellm_call_id': data.get('litellm_call_id'), 'model': data.get('model')}


class GatewayAudit(CustomLogger):
    def __init__(self):
        super().__init__()
        self.lock = Lock()

    def emit(self, event, **fields):
        directory = Path(os.environ.get('TALKHIER_GATEWAY_LOG_DIR', str(HERE.parents[1] / '.local/gateway/events')))
        directory.mkdir(parents=True, exist_ok=True)
        with self.lock, (directory / 'proxy_events.jsonl').open('a') as stream:
            stream.write(json.dumps({'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}, default=str) + '\n')

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        self.emit('proxy_incoming', **request_identity(data),
                  output_reservation_limit=data.get('max_completion_tokens', data.get('max_tokens')))
        return None

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        usage = getattr(response, 'usage', None)
        self.emit('proxy_success', **request_identity(data),
                  usage=usage.model_dump() if usage is not None and hasattr(usage, 'model_dump') else None)

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict, traceback_str=None):
        status = getattr(original_exception, 'status_code', None)
        if status != 429:
            self.emit('proxy_failure', **request_identity(request_data), status_code=status, error_type=type(original_exception).__name__)
            return None
        origin, evidence = classify_rate_limit(original_exception)
        headers = dict(getattr(original_exception, 'headers', None) or {})
        response = getattr(original_exception, 'response', None)
        if response is not None:
            for name in ['retry-after', 'x-request-id', 'request-id']:
                if response.headers.get(name) is not None:
                    headers[name] = response.headers[name]
        # LiteLLM may synthesize a response on its wrapper exception. The
        # original provider response (and Retry-After) can remain on its cause.
        error, seen = original_exception, set()
        upstream = urlsplit(os.environ.get('QWEN_BASE_URL', QUOTA['upstream_base_url'])).netloc
        while error is not None and id(error) not in seen:
            seen.add(id(error))
            original_response = getattr(error, 'response', None)
            try:
                matches_upstream = original_response is not None and urlsplit(str(original_response.request.url)).netloc == upstream
            except RuntimeError:
                matches_upstream = False
            if matches_upstream and original_response.headers.get('retry-after'):
                headers['retry-after'] = original_response.headers['retry-after']
                break
            error = getattr(error, '__cause__', None) or getattr(error, '__context__', None)
        has_retry_after = any(str(k).lower() == 'retry-after' for k in headers)
        if not has_retry_after:
            headers['retry-after'] = '60'
        headers['x-talkhier-rate-limit-origin'] = origin
        self.emit('proxy_429', **request_identity(request_data), origin=origin, evidence=evidence,
                  error_type=type(original_exception).__name__, retry_after_source='native_or_upstream' if has_retry_after else 'gateway_default',
                  retry_after=headers.get('retry-after', headers.get('Retry-After')))
        # Transform only the HTTP error envelope; request/model response content is unchanged.
        return HTTPException(status_code=429, headers=headers,
                             detail={'error': {'message': f'Rate limit exceeded; origin={origin}',
                                               'type': 'rate_limit_error', 'origin': origin}})


audit = GatewayAudit()
