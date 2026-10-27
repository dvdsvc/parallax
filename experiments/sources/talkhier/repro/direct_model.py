"""Configure LangChain ChatOpenAI directly at the external benchmark entry."""
from contextlib import contextmanager
from types import SimpleNamespace

from dotenv import dotenv_values
from langchain_openai import ChatOpenAI


def connection(credential_file, base_url=None):
    values = dotenv_values(credential_file)
    api_key = values.get('QWEN_API_KEY') or values.get('OPENAI_API_KEY')
    endpoint = base_url or values.get('QWEN_BASE_URL') or values.get('OPENAI_BASE_URL')
    if not api_key or not endpoint:
        raise ValueError('The local credential file must contain an API key and an API base URL')
    return {'api_key': api_key, 'base_url': endpoint}


@contextmanager
def install(experiments, settings, model, timeout, max_retries, http_client=None):
    original = experiments.LLM
    def factory(config):
        kwargs = {'model': model, 'temperature': float(config['LLM']['temperature']),
                  'api_key': settings['api_key'], 'base_url': settings['base_url'],
                  'timeout': timeout, 'max_retries': max_retries}
        if http_client is not None:
            kwargs['http_client'] = http_client
        return SimpleNamespace(llm=ChatOpenAI(**kwargs))
    experiments.LLM = factory
    try:
        yield {'client': 'langchain_openai.ChatOpenAI', 'model': model,
               'base_url': settings['base_url'], 'request_timeout_seconds': timeout,
               'sdk_max_retries': max_retries, 'proxy_used': False,
               'structured_output_parser_modified': False, 'native_source_modified': False}
    finally:
        experiments.LLM = original
