# Forammas study control and provenance layer

This directory is external to the pristine ROMA checkout at `../../forammas`.
It stores canonical condition definitions, formal run configuration, provenance
capture, and MLflow integration; it must not patch ROMA's agent source or prompts.

## Conditions and switches

The only organization-awareness switch is `interventions.organization_awareness_v2`.
When enabled, the external worker adapter prepends the exact text in
`prompts/global_organizational_architecture_v2.txt` as a static system message
before the request enters LiteLLM. It is role-independent and does not inspect
ROMA role metadata. LiteLLM Proxy only audits whether the exact block arrived;
it does not inject or alter this V2 block. When disabled, that block is absent.
There is no dynamic current-position organization switch.

`condition` is `BASE` or a two-bit code ordered `intent/plan`; organization
awareness is independent. The four readable factorial cells are defined in
`condition_registry.json`. Plan is on in those cells, and second-order visibility
is off unless explicitly enabled in a run config. Only `BASE` or a two-bit
intent/plan code is accepted. Native `BASE` means no intent/plan rewrite; it is not
silently relabeled as a coded condition.

For a clean BASE-versus-organization-awareness comparison, use `condition: "BASE"`
in both run configs and keep model, temperature, task IDs, depth, concurrency,
and all other settings fixed. The sole difference is
`interventions.organization_awareness_v2: false` versus `true`.

Resolve a cell with `python conditions.py intent_on__architecture_on`. A worker's
proxy trace must match the requested/effective intent-plan condition and the
organization-awareness switch, with no guard errors. Mismatch invalidates the
run rather than silently relabeling it.

## Provenance and formal runs

The ROMA clone remains pinned to its official commit and clean. Record separate
identities for the Agent, this control layer, LiteLLM hook, runner, benchmark data,
and grader. ROMA's native per-question event traces remain the raw behavioral
record. MLflow indexes run metadata and artifacts; it does not replace or mutate
the native traces.

The formal entry point is `run_isolated_seal0.py --paper-run-config <json>`. It
refuses to start unless ROMA and all experiment-control repositories have a Git
commit and MLflow can create a tracking run. Dirty working trees are not committed
automatically: their HEAD, diff, status, and relevant untracked files are captured
in the unique run archive. It writes a unique,
non-overwriting local archive and creates the MLflow `RUNNING` record before
starting benchmark workers. On completion it attaches the finalized archive to
that same MLflow run, records the manifest hash, and writes a checksum list. A
preflight failure is archived as `failed_preflight`. Keep credentials in the
external environment; never put them in config, manifests, logs, or artifacts.

Example config (choose a matching readable condition and intervention values):

```json
{
  "schema_version": 1,
  "condition": "11",
  "task_indices": [0],
  "workers": 1,
  "max_depth": 3,
  "model": "openai/qwen3.7-flash",
  "temperature": 0.0,
  "provider_label": "qwen-compatible-via-litellm",
  "interventions": {
    "organization_awareness_v2": true,
    "second_order": {"enabled": false, "layers": {}}
  }
}
```

Launch with the prepared Agent interpreter:

```bash
/absolute/path/to/forammas/.venv/bin/python \
  /absolute/path/to/work/roma_v1_adapters/run_isolated_seal0.py \
  --paper-run-config /absolute/path/to/run-config.json
```

The pristine Agent, adapter, proxy, and study-control Git identities are stored
separately beside the benchmark hash, run-config hash, effective request
settings, and task IDs. Native ROMA traces are copied byte-for-byte; proxy traces
and derived metrics are stored alongside them. The checksummed local archive is
the source of truth; MLflow is the index/comparison surface.

Install the isolated tracking dependency with `uv sync`. Use a local SQLite
tracking URI such as
`sqlite:////absolute/path/to/forammas_study/mlflow.db`.

## Architecture prompt scope

V2 injects `prompts/global_organizational_architecture_v2.txt` verbatim. The
file is the supplied prompt text; no extra role-specific context is added by
the V2 switch.

## External model and decoding overrides

`ROMA_MODEL_OVERRIDE` sets every ROMA role's model through the runner's in-memory
`ConfigManager` overrides; `ROMA_TEMPERATURE_OVERRIDE` does the same for decoding
temperature. Neither writes to the Agent checkout. The external proxy config and
credential environment select the active model alias/upstream. Raw ROMA requests
record the effective model and temperature. Formal comparisons must use identical
overrides across cells.
