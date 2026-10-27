"""Local LangChain callbacks, including native LangGraph node events and usage."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
import time

from langchain_core.callbacks import BaseCallbackHandler


def jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): '<REDACTED>' if any(x in str(k).lower() for x in
                ('api_key', 'authorization', 'password', 'secret')) else jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(x) for x in value]
    if hasattr(value, 'model_dump'):
        return jsonable(value.model_dump())
    return str(value)


class LocalTrace(BaseCallbackHandler):
    """Record framework events without enabling LangSmith or changing execution."""
    run_inline = True
    raise_error = True

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.active, self.calls = {}, []
        self.lock = RLock()
        self.sequence = 0
        self.event_counts = Counter()

    def emit(self, event, record):
        with self.lock:
            row = {'sequence': self.sequence, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                   'event': event, **record}
            self.sequence += 1
            self.event_counts[event] += 1
            with (self.directory / 'trace.jsonl').open('a') as stream:
                stream.write(json.dumps(jsonable(row), ensure_ascii=False) + '\n')
            if row.get('graph_node_event'):
                with (self.directory / 'graph_nodes.jsonl').open('a') as stream:
                    stream.write(json.dumps(jsonable(row), ensure_ascii=False) + '\n')

    def start(self, kind, serialized, run_id, parent_run_id, metadata, tags, kwargs, payload):
        name = kwargs.get('name') or (serialized or {}).get('name') or kind
        metadata = dict(metadata or {})
        record = {'run_id': str(run_id), 'parent_run_id': str(parent_run_id) if parent_run_id else None,
                  'kind': kind, 'name': name, 'metadata': metadata, 'tags': tags or [],
                  'role': metadata.get('talkhier_role'), 'phase': metadata.get('talkhier_phase'),
                  'graph_node_event': kind == 'chain' and name == metadata.get('langgraph_node')}
        with self.lock:
            self.active[str(run_id)] = {'record': record, 'started': time.monotonic()}
        self.emit(f'{kind}_start', {**record, **payload})

    def finish(self, kind, run_id, payload):
        with self.lock:
            start = self.active.pop(str(run_id), None)
        record = start['record'] if start else {'run_id': str(run_id), 'kind': kind}
        elapsed = time.monotonic() - start['started'] if start else None
        row = {**record, 'duration_seconds': elapsed, **payload}
        self.emit(f'{kind}_end' if payload.get('status') == 'success' else f'{kind}_error', row)
        if kind == 'model':
            with self.lock:
                self.calls.append(row)
                with (self.directory / 'model_calls.jsonl').open('a') as stream:
                    stream.write(json.dumps(jsonable(row), ensure_ascii=False) + '\n')

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        self.start('chain', serialized, run_id, parent_run_id, metadata, tags, kwargs, {'inputs': inputs})

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self.finish('chain', run_id, {'status': 'success', 'outputs': outputs})

    def on_chain_error(self, error, *, run_id, **kwargs):
        self.finish('chain', run_id, {'status': 'error', 'error_type': type(error).__name__, 'error': str(error)})

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        self.start('model', serialized, run_id, parent_run_id, metadata, tags, kwargs, {'messages': messages})

    def on_llm_end(self, response, *, run_id, **kwargs):
        messages = [g.message for group in response.generations for g in group if hasattr(g, 'message')]
        raw = (response.llm_output or {}).get('token_usage')
        if raw is None and len(messages) == 1:
            raw = (messages[0].response_metadata or {}).get('token_usage')
        normalized = [m.usage_metadata for m in messages if getattr(m, 'usage_metadata', None) is not None]
        if raw is not None:
            usage = {'input_tokens': raw.get('prompt_tokens'), 'output_tokens': raw.get('completion_tokens'),
                     'total_tokens': raw.get('total_tokens'),
                     'cached_input_tokens': (raw.get('prompt_tokens_details') or {}).get('cached_tokens'),
                     'reasoning_output_tokens': (raw.get('completion_tokens_details') or {}).get('reasoning_tokens')}
        elif len(normalized) == 1:
            u = normalized[0]
            usage = {'input_tokens': u.get('input_tokens'), 'output_tokens': u.get('output_tokens'),
                     'total_tokens': u.get('total_tokens'),
                     'cached_input_tokens': (u.get('input_token_details') or {}).get('cache_read'),
                     'reasoning_output_tokens': (u.get('output_token_details') or {}).get('reasoning')}
        else:
            usage = None
        self.finish('model', run_id, {'status': 'success', 'outputs': messages,
                    'raw_llm_output': response.llm_output, 'raw_token_usage': raw,
                    'usage_metadata': normalized, 'usage': usage})

    def on_llm_error(self, error, *, run_id, **kwargs):
        self.finish('model', run_id, {'status': 'error', 'error_type': type(error).__name__,
                                    'error': str(error), 'usage': None})

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        self.start('tool', serialized, run_id, parent_run_id, metadata, tags, kwargs,
                   {'input_str': input_str, 'inputs': kwargs.get('inputs')})

    def on_tool_end(self, output, *, run_id, **kwargs):
        self.finish('tool', run_id, {'status': 'success', 'outputs': output})

    def on_tool_error(self, error, *, run_id, **kwargs):
        self.finish('tool', run_id, {'status': 'error', 'error_type': type(error).__name__, 'error': str(error)})

    def finalize(self):
        metrics = ('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens', 'reasoning_output_tokens')
        with self.lock:
            calls = list(self.calls)
            active_models = [v['record'] for v in self.active.values() if v['record']['kind'] == 'model']
        def group(items):
            result = {'model_calls_finished': len(items), 'model_successes': sum(x['status'] == 'success' for x in items),
                      'model_errors': sum(x['status'] == 'error' for x in items),
                      'calls_without_usage': sum(x.get('usage') is None for x in items)}
            for key in metrics:
                values = [x['usage'][key] for x in items if x.get('usage') and x['usage'].get(key) is not None]
                result[f'observed_{key}'] = sum(values) if values else None
                result[f'calls_with_{key}'] = len(values)
            return result
        report = {**group(calls), 'unfinished_model_calls': active_models,
                  'event_counts': dict(self.event_counts),
                  'by_role': {role: group([x for x in calls if (x.get('role') or 'unknown') == role])
                              for role in sorted({x.get('role') or 'unknown' for x in calls})},
                  'meaning': 'LangChain logical calls and observed returned usage; not SDK HTTP-attempt counts or complete provider billing.',
                  'cached_and_reasoning_tokens_are_subsets': True, 'langsmith_enabled': False}
        (self.directory / 'token_usage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        return report
