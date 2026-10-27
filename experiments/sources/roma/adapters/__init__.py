"""External, optional tool adapters for the unmodified ROMA v1 checkout."""

from .zhipu_search import ZhipuSearchToolkit, register

__all__ = ["ZhipuSearchToolkit", "register"]
