# TalkHier shared inference gateway

This is external infrastructure. Native `src/`, graph, role prompts, tools, organization injection and integer-choice scoring remain unchanged. LiteLLM **1.104.0** is isolated in `.local/gateway/.venv`; the existing TalkHier environment is not upgraded. `requirements.lock.txt` freezes the gateway dependencies.

The user requested official Qwen defaults. For Beijing `qwen3.7-flash`, the checked defaults on 2026-10-06 are **30,000 RPM / 5,000,000 TPM** ([model information](https://help.aliyun.com/zh/model-studio/qwen3-7-flash)). Provider limits are account/model-wide and may also enforce shorter burst windows ([rate-limit rules](https://help.aliyun.com/zh/model-studio/rate-limit)); traffic bypassing this gateway is outside its counters. `quota.json` records source, model, region, and budget parameters.

## Limiting and request fidelity

The native LiteLLM custom-auth mechanism returns `UserAPIKeyAuth` with one shared key-scoped RPM/TPM limit for both conditions. Native TPM reservation is explicitly enabled: input estimate plus declared `max_completion_tokens`, then reconciliation against returned total usage. In version 1.104.0 the shared combined-TPM input estimate uses characters divided by four; it is not a Qwen-specific tokenizer. The generic token counter also defaults to tiktoken for this model. No custom estimator or limiter is implemented here. Generation remains `enable_thinking=true`, `thinking_budget=8192`, `max_completion_tokens=16384`; `max_tokens` is absent. The prompt, schema, temperature and model are not rewritten. No fallback model or response cache is configured.

Run one proxy worker. Its in-memory native limiter coordinates all worker requests; this setup does not support multiple proxy replicas without shared coordination. No database, Redis daemon or remote tracing service is required. Native router/SDK retries are disabled so the external HTTP transport is the sole 429 retry owner.

## Diagnostics and logical traces

Temporary 429s are recorded in `infrastructure/gateway_events.jsonl` and proxy `proxy_events.jsonl`, with stable logical-call ID, attempt, LiteLLM call ID, wait, status and source. They do not add model errors, node executions or whole-question retries to the native LangChain trace. Source is one of:

* `litellm_local`: verified native proxy limiter exception or native router-limit request marker.
* `qwen_upstream`: observed HTTP 429 response from the configured upstream URL, including wrapped causes.
* `unknown`: insufficient evidence; never guess the source from status alone.

`Retry-After` seconds or HTTP-date is honored. If the upstream supplies none, the proxy explicitly records a gateway-generated 60-second fallback. The same request bytes are retried within one LangChain logical call. If the wait budget is exhausted, `GatewayRetryExhausted` escapes native `except Exception` retry loops, ending that question as an infrastructure failure. The final failure remains in the native trace with `failure_domain=infrastructure` and its source; it is not deleted or mislabeled as agent reasoning failure.

Native model duration and the external question wall limit include gateway waits. Sidecar waits allow that contribution to be reported separately; they cannot measure provider-internal queueing. Usage is counted from logical model returns once; proxy copies are diagnostic, not additional usage. Missing usage stays unknown. This adapter supports the native synchronous `.invoke` path; asynchronous model invocation is not enabled through this transport.

## Launch and frozen inputs

```sh
.venv/bin/python repro/gateway/start.py
.venv/bin/python repro/run_subset.py \
  --subset repro/subsets/mmlu_pro_physics_test_n100_seed42 \
  --task-concurrency 32 \
  --gateway-url http://127.0.0.1:4005/v1
```

These commands describe the launch; gateway preparation itself made no real provider calls. Total concurrency 32 is **BASE 16 + V2 16**. The October 6 launch uses this bound because the machine has 16 GiB RAM and a native worker's import-only peak RSS was approximately 208 MiB. A requested total concurrency of 100 would create 50 + 50 independent native workers. The provider limiter is shared, not 5 million TPM separately per condition. Native graph calls may have their own nested concurrency, so task slots are not identical to active HTTP requests.

Native priority-queue testing confirmed that adding `priority=1` does not turn the shared key TPM limiter into a wait queue: over-limit requests are rejected before the router scheduler. This deployment uses native admission limits plus external 429 waiting, not a custom automatic-saturation scheduler.

The fixed MMLU-Pro sample is consumed by `repro/benchmark_data.py`: `question -> question`, `options -> choices`, `answer_index -> answer`; original full-test row index is the native `Problem ID`, while official `question_id` is separately preserved in archive and callback metadata. All source options and their order are preserved. Official `cot_content` is archival only and is not included in the native task mapping. The graph remains the original `college_physics` Physics/Mathematics graph; this is not the benchmark author's separate few-shot inference script. Native CSV final-choice equality is the scoring channel.

Batch/child startup records freeze gateway configuration, dependency lock and source, quota hash, SDK retry count, dataset and wall-time policy. The model HTTP client is supplied by an external context at native model construction. Native source and LangChain installed code are not patched.

## Offline verification

```sh
.venv/bin/python repro/gateway/validate_client.py
LITELLM_LOCAL_MODEL_COST_MAP=True .local/gateway/.venv/bin/python repro/gateway/validate_proxy.py
```

The first exercises real LangChain/native model construction at 100-thread concurrency, immutable request replay, native JSON Schema dict responses, logical IDs and final infrastructure failure. The second exercises actual LiteLLM native token reservation at 100 concurrent ASGI requests with a local fake provider, usage reconciliation, RPM and two measured 429 origins. Both use dummy credentials and **zero real provider calls**. Small BASE/V2 queue/archive preflights additionally verify configuration propagation; those are not benchmark outcomes.
