"""Small external Qwen prompt-cache adapter.

This process is deliberately outside ROMA and outside LiteLLM's callback.  It
does not replay responses, reorder tools, rewrite messages, or add cache
markers.  It only adds the provider's session-cache header and the stable
Qwen-Code-style prompt cache key before forwarding the original OpenAI
request to DashScope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return str(value)


class QwenCacheAdapter:
    def __init__(self, upstream_base_url: str, trace_dir: Path | None = None) -> None:
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self.trace_dir = trace_dir
        self.session_key = os.environ.get("ROMA_CACHE_SESSION_ID") or os.environ.get(
            "ROMA_RUN_ID", "roma-session"
        )
        self.condition = os.environ.get("ROMA_PROXY_CONDITION", "BASE")
        self.partition = os.environ.get("ROMA_CACHE_KEY_PARTITION", self.condition)
        self.cache_key = f"qwen-code:{self.session_key}:{self.partition}"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=30.0))

    def _endpoint(self, request_path: str) -> str:
        # Qwen's compatible endpoint is normally already /v1.  Avoid creating
        # /v1/v1/chat/completions when LiteLLM calls this adapter at /v1/....
        if self.upstream_base_url.endswith("/v1"):
            suffix = request_path.removeprefix("/v1").lstrip("/")
            return f"{self.upstream_base_url}/{suffix}"
        return f"{self.upstream_base_url}{request_path}"

    def _event_path(self) -> Path | None:
        if not self.trace_dir:
            return None
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        return self.trace_dir / "cache_adapter_events.jsonl"

    def _write_event(self, event: dict[str, Any]) -> None:
        path = self._event_path()
        if path is None:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_jsonable(event), ensure_ascii=False) + "\n")

    def _cache_body(self, body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        forwarded = dict(body)
        # Qwen Code's OpenAI-compatible path uses a stable session key.  Keep
        # this top-level metadata separate from messages and never add cache
        # markers to system/user/tool content.
        if os.environ.get("ROMA_QWEN_CACHE_PROMPT_KEY", "1").strip().lower() in {
            "1", "true", "yes", "on"
        }:
            forwarded.setdefault("prompt_cache_key", self.cache_key)
        audit = {
            "prompt_cache_key": forwarded.get("prompt_cache_key"),
            "messages_sha256": _digest(body.get("messages")),
            "tools_sha256": _digest(body.get("tools")),
            "message_count": len(body.get("messages", [])) if isinstance(body.get("messages"), list) else None,
            "tool_count": len(body.get("tools", [])) if isinstance(body.get("tools"), list) else None,
            "messages_changed": body.get("messages") != forwarded.get("messages"),
            "tools_changed": body.get("tools") != forwarded.get("tools"),
        }
        return forwarded, audit

    async def close(self) -> None:
        await self.client.aclose()

    async def health(self) -> JSONResponse:
        return JSONResponse({"status": "ok", "adapter": "qwen-external-cache", "upstream": self.upstream_base_url})

    async def chat_completions(self, request: Request) -> Response:
        started = time.monotonic()
        try:
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse({"error": "request body must be a JSON object"}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": f"invalid JSON request: {exc}"}, status_code=400)

        forwarded, audit = self._cache_body(body)
        headers = {
            "content-type": "application/json",
            # This is the provider-native session/implicit cache switch.  It
            # is mutually exclusive with explicit cache_control markers, so
            # this adapter intentionally does not add those markers.
            "x-dashscope-session-cache": "enable",
        }
        api_key = os.environ.get("QWEN_API_KEY")
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        for name in ("x-request-id", "user-agent"):
            value = request.headers.get(name)
            if value:
                headers[name] = value

        url = self._endpoint(request.url.path)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "upstream_request",
            "url": url,
            "model": body.get("model"),
            "stream": bool(body.get("stream")),
            "condition": self.condition,
            "cache_mode": "qwen_session_cache",
            **audit,
        }
        try:
            if body.get("stream"):
                upstream = await self.client.stream("POST", url, headers=headers, json=forwarded).__aenter__()

                async def stream_body():
                    try:
                        async for chunk in upstream.aiter_bytes():
                            yield chunk
                    finally:
                        await upstream.aclose()

                self._write_event({**event, "status_code": upstream.status_code, "latency_ms": round((time.monotonic() - started) * 1000, 3)})
                return StreamingResponse(
                    stream_body(),
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type", "text/event-stream"),
                )

            upstream = await self.client.post(url, headers=headers, json=forwarded)
            self._write_event({
                **event,
                "status_code": upstream.status_code,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "response_usage": (upstream.json().get("usage") if upstream.headers.get("content-type", "").startswith("application/json") else None),
            })
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type="application/json",
            )
        except Exception as exc:
            self._write_event({
                **event,
                "status_code": 502,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": f"{type(exc).__name__}: {exc}",
            })
            return JSONResponse({"error": {"message": str(exc), "type": type(exc).__name__}}, status_code=502)


def build_app(adapter: QwenCacheAdapter) -> FastAPI:
    app = FastAPI(title="ROMA external Qwen cache adapter")
    app.add_api_route("/health", adapter.health, methods=["GET"])
    app.add_api_route("/health/readiness", adapter.health, methods=["GET"])
    app.add_api_route("/v1/chat/completions", adapter.chat_completions, methods=["POST"])
    app.add_api_route("/chat/completions", adapter.chat_completions, methods=["POST"])

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await adapter.close()

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4010)
    parser.add_argument("--upstream-base-url", default=os.environ.get("QWEN_BASE_URL"))
    args = parser.parse_args()
    if not args.upstream_base_url:
        raise SystemExit("QWEN_BASE_URL or --upstream-base-url is required")
    adapter = QwenCacheAdapter(
        args.upstream_base_url,
        Path(os.environ["ROMA_PROXY_TRACE_DIR"]) if os.environ.get("ROMA_PROXY_TRACE_DIR") else None,
    )
    uvicorn.run(build_app(adapter), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
