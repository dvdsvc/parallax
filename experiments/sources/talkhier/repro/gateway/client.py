"""HTTP-only 429 waiting, separate diagnostics, and native LangChain correlation."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import importlib
import json
from pathlib import Path
import random
from threading import Lock
import time
import uuid

import httpx

CURRENT_CALL = ContextVar('talkhier_gateway_logical_call', default=None)


class GatewayRetryExhausted(BaseException):
    """Stop one question on infrastructure exhaustion; native Exception retry loops cannot swallow it."""
    failure_domain = 'infrastructure'
    status_code = 429

    def __init__(self, origin, logical_call_id):
        self.rate_limit_origin = origin
        self.logical_call_id = logical_call_id
        super().__init__(f'Gateway 429 wait budget exhausted; origin={origin}; logical_call_id={logical_call_id}')


def retry_after(value, attempt, wall_clock=time.time):
    if value:
        try:
            seconds = float(value)
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                seconds = date.timestamp() - wall_clock()
            except (ValueError, TypeError, OverflowError):
                seconds = -1
        if seconds >= 0 and seconds != float('inf'):
            return max(0.05, seconds)
    return min(60.0, 2 ** min(attempt, 6)) + random.uniform(0, 0.5)


def origin_from_headers(headers):
    value = headers.get('x-talkhier-rate-limit-origin', 'unknown')
    return value if value in {'litellm_local', 'qwen_upstream', 'unknown'} else 'unknown'


class GatewayRetryTransport(httpx.BaseTransport):
    """Retry only 429, preserving request bytes and one logical LangChain call."""
    def __init__(self, directory, transport=None, max_wait_seconds=900, sleep=time.sleep, clock=time.monotonic):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.transport = transport or httpx.HTTPTransport(retries=0)
        self.max_wait_seconds, self.sleep, self.clock = max_wait_seconds, sleep, clock
        self.lock = Lock()

    def emit(self, event, **fields):
        record = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
        with self.lock, (self.directory / 'gateway_events.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def handle_request(self, request):
        call = dict(CURRENT_CALL.get() or {})
        logical_id = call.get('run_id') or str(uuid.uuid4())
        body = request.read()
        body_sha = hashlib.sha256(body).hexdigest()
        attempt, waiting, started = 0, 0.0, self.clock()
        while True:
            attempt += 1
            headers = request.headers.copy()
            headers['x-talkhier-logical-call-id'] = logical_id
            headers['x-talkhier-http-attempt'] = str(attempt)
            sent = httpx.Request(request.method, request.url, headers=headers, content=body, extensions=request.extensions)
            response = self.transport.handle_request(sent)
            common = {'logical_call_id': logical_id, 'attempt': attempt, 'request_body_sha256': body_sha,
                      'condition': call.get('condition'), 'problem_id': call.get('problem_id'),
                      'gateway_call_id': response.headers.get('x-litellm-call-id'),
                      'status_code': response.status_code}
            if response.status_code != 429:
                self.emit('http_return', **common, waiting_seconds=waiting, duration_seconds=self.clock() - started)
                return response
            origin = origin_from_headers(response.headers)
            delay = retry_after(response.headers.get('retry-after'), attempt)
            response.read()
            response.close()
            self.emit('rate_limit', **common, origin=origin, retry_after_seconds=delay)
            # This is a per-logical-call wall limit; the question's external wall limit still applies.
            if self.clock() - started + delay >= self.max_wait_seconds:
                self.emit('retry_exhausted', **common, origin=origin, waiting_seconds=waiting)
                raise GatewayRetryExhausted(origin, logical_id)
            self.sleep(delay)
            waiting += delay

    def close(self):
        self.transport.close()


def trace_handler(directory):
    """Build the same native callback recorder, with infrastructure failure tags."""
    from local_trace import LocalTrace

    class GatewayTrace(LocalTrace):
        def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
            context = dict(metadata or {})
            context['run_id'] = str(run_id)
            CURRENT_CALL.set(context)
            return super().on_chat_model_start(serialized, messages, run_id=run_id, parent_run_id=parent_run_id,
                                              tags=tags, metadata=metadata, **kwargs)

        def on_llm_end(self, response, *, run_id, **kwargs):
            try:
                return super().on_llm_end(response, run_id=run_id, **kwargs)
            finally:
                CURRENT_CALL.set(None)

        def on_llm_error(self, error, *, run_id, **kwargs):
            self.finish('model', run_id, {'status': 'error', 'error_type': type(error).__name__, 'error': str(error),
                'usage': None, 'failure_domain': getattr(error, 'failure_domain', 'model_or_provider'),
                'rate_limit_origin': getattr(error, 'rate_limit_origin', None)})
            CURRENT_CALL.set(None)

        def on_chain_error(self, error, *, run_id, **kwargs):
            self.finish('chain', run_id, {'status': 'error', 'error_type': type(error).__name__, 'error': str(error),
                'failure_domain': getattr(error, 'failure_domain', 'agent_or_model'),
                'rate_limit_origin': getattr(error, 'rate_limit_origin', None)})

        def finalize(self):
            report = super().finalize()
            infrastructure = sum(row.get('failure_domain') == 'infrastructure' for row in self.calls if row['status'] == 'error')
            report.update(infrastructure_model_errors=infrastructure,
                          model_or_provider_errors=report['model_errors'] - infrastructure,
                          temporary_429_excluded_from_model_errors=True,
                          gateway_log='infrastructure/gateway_events.jsonl',
                          duration_seconds_includes_gateway_wait=True)
            (self.directory / 'token_usage.json').write_text(json.dumps(report, indent=2) + '\n')
            return report

    return GatewayTrace(directory)


@contextmanager
def model_boundary(http_client):
    """Only supply the HTTP client at native model construction, via external context."""
    module = importlib.import_module('multiagent.llm')
    original = module.ChatOpenAI

    def create(*args, **kwargs):
        kwargs.update(http_client=http_client, max_retries=0, include_response_headers=True)
        return original(*args, **kwargs)

    module.ChatOpenAI = create
    try:
        yield {'transport': 'GatewayRetryTransport', 'sdk_max_retries': 0,
               'native_source_modified': False, 'request_payload_modified': False,
               'async_supported': False, 'temporary_429_log': 'gateway_events.jsonl'}
    finally:
        module.ChatOpenAI = original
