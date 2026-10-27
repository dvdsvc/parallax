# Historical runtime entry points

[Home](../README.md) · [Offline reproduction](reproduction.md)

The offline quick start is ready for aggregate checking. Fresh agent execution requires deliberate restoration of the historical runtime, datasets and service configuration. Archived `external_archive/`, `external_home/` and `sources/` locators need relocation; a copied Git SHA is evidence of a historical identity, not a newly initialized clone of that identity.

## ROMA

Native source: [pyproject](../experiments/sources/roma/native/pyproject.toml) and [uv lock](../experiments/sources/roma/native/uv.lock), Python ≥3.12. Additional [controls environment](../experiments/sources/roma/controls/pyproject.toml) and [lock](../experiments/sources/roma/controls/uv.lock) are separate. The native framework uses DSPy and optional provider, search, sandbox and archival services; install the extras required by the chosen frozen configuration rather than every optional integration.

Read [controls](../experiments/sources/roma/controls/README.md), [SEAL runner](../experiments/sources/roma/adapters/run_isolated_seal0.py), [FRAMES launcher snapshot](../experiments/sources/roma/launcher) and [SEAL archive catalogue](../experiments/provenance/roma_seal0_archive_catalog.json). Each historical archive can retain its own runner, control and configuration snapshots. Main SEAL rounds must use their recorded indices/budgets/protocols. Keep the clean `BASE` condition label in both arms and toggle only `organization_awareness_v2`; old intent/plan controls are not equivalent.

The native dataset loader, external proxy/control roots, isolated interpreter, provider/search keys and E2B where configured must exist. Run archival tooling with meaningful Git source identities, output directories and MLflow storage; do not fabricate the pinned commit by initializing this showcase as a new source repo. Preserve requested/effective condition audits. The proxy checks the exact organization prefix before provider forwarding.

## TalkHier

Treat [the TalkHier snapshot](../experiments/sources/talkhier) as a separate runtime root. Its [environment notes](../experiments/sources/talkhier/ENVIRONMENT.md), [bootstrap](../experiments/sources/talkhier/repro/bootstrap.sh), [locked dependencies](../experiments/sources/talkhier/repro/requirements.mmlu.lock.txt) preserve Python 3.12 / LangChain 0.3 compatibility. The historical notes refer to an interface-upgrade input file that is not included in this frozen bundle; use the actual retained lock and manifests when restoring the environment. The older broad upstream `requirements.txt` includes unrelated local/CUDA dependencies; it is preserved for provenance.

The primary Physics100 batch uses the native Physics team via the MMLU-Pro adaptation, not the College Physics pilot. See [runner](../experiments/sources/talkhier/repro/run_mmlu.py), [frozen effective configuration](../experiments/configs/talkhier_effective_configuration.json), [sampling files](../experiments/samples) and [flow audit](../experiments/sources/talkhier/repro/org_v2/FLOW_AUDIT.md). Use the exact seed-42 question pack and original IDs, `all_roles`, temperature zero, thinking budget 8192, completion cap 16384 and the archived primary 3600-second question timeout. The runner's generic 900-second default is not the primary batch setting. Provider and optional localhost gateway setup must match the chosen archive.

The runner accepts BASE/V2, sample directory, configuration paths and new/empty output directory. BASE takes the native path; V2 installs the static organization wrapper. Freeze inputs/config/source before work, and archive trace/callback/score files afterward. Credential files must remain external. Preflight itself creates archival records and depends on configuration/data/Git/MLflow; it is not substituted for the safe no-dependency offline commands in this showcase.

## Scoring and fresh runs

TalkHier MMLU-Pro answers use pinned official exact-match scoring with native index-to-letter mapping. ROMA semantic grading and fresh inference can require external services. The historical evidence separates source manifests, raw execution, grading and later analysis. This packaging ran only the aggregate/checksum verification and did not create new agent answers, scores or billing data.
