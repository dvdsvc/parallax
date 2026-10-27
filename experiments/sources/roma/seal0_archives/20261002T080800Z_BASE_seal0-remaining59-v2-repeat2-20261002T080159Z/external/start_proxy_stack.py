"""Supervise LiteLLM and the external Qwen cache adapter as one proxy process."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = Path(os.environ.get("PROXY_VENV", str(ROOT / ".venv_native")))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/readiness", timeout=1.0) as response:
            return response.status < 500
    except Exception:
        return False


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    upstream = os.environ.get("QWEN_BASE_URL")
    api_key = os.environ.get("QWEN_API_KEY")
    if not upstream or not api_key:
        raise SystemExit("QWEN_BASE_URL and QWEN_API_KEY are required")
    proxy_port = int(os.environ.get("LITELLM_PROXY_PORT", "4000"))
    cache_enabled = os.environ.get("ROMA_EXTERNAL_QWEN_CACHE", "1").strip().lower() in {
        "1", "true", "yes", "on"
    }
    adapter_port = free_port()
    adapter = None
    if cache_enabled:
        adapter_cmd = [
            sys.executable,
            str(ROOT / "qwen_cache_adapter.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(adapter_port),
            "--upstream-base-url",
            upstream,
        ]
        adapter = subprocess.Popen(adapter_cmd, cwd=str(ROOT), env=os.environ.copy())
    proxy: subprocess.Popen | None = None
    stopping = False

    def handle_signal(signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    try:
        deadline = time.monotonic() + 30
        if cache_enabled:
            while time.monotonic() < deadline and not stopping:
                if adapter is None or adapter.poll() is not None:
                    return (adapter.returncode if adapter is not None else 1) or 1
                if ready(adapter_port):
                    break
                time.sleep(0.1)
            else:
                return 1

        proxy_env = os.environ.copy()
        if cache_enabled:
            proxy_env["QWEN_BASE_URL"] = f"http://127.0.0.1:{adapter_port}/v1"
            proxy_env["ROMA_QWEN_REAL_BASE_URL"] = upstream
        proxy = subprocess.Popen(
            [
                str(VENV / "bin" / "litellm"),
                "--config",
                str(ROOT / "config.yaml"),
                "--host",
                "127.0.0.1",
                "--port",
                str(proxy_port),
            ],
            cwd=str(ROOT),
            env=proxy_env,
        )
        while not stopping:
            if proxy.poll() is not None:
                return proxy.returncode or 1
            if cache_enabled and (adapter is None or adapter.poll() is not None):
                return 1
            time.sleep(0.2)
        return 0
    finally:
        stop(proxy)
        stop(adapter)


if __name__ == "__main__":
    raise SystemExit(main())
