"""Provider JSON Schema output with a dict-to-attributes boundary only."""
from copy import deepcopy
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda


def response_fields(value):
    if not isinstance(value, dict):
        raise TypeError('Provider structured output must be a dictionary')
    return SimpleNamespace(**value)


def structured_response(model, schema):
    # Existing declarations supply field descriptions/types/enums only.
    # No response is instantiated or validated as a Pydantic model.
    json_schema = deepcopy(schema) if isinstance(schema, dict) else schema.model_json_schema()
    return model.with_structured_output(
        json_schema, method='json_schema', strict=True
    ) | RunnableLambda(response_fields)
