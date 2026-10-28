<img src="assets/mark.svg" width="68" alt="Organizational visibility mark">

# Organizational Visibility in Hierarchical Multi-Agent Systems

**A controlled study of how a static global organizational description changes agent behavior, task outcomes and computational work in ROMA and TalkHier.**

**Paper status: AAMAS 2027 — Under Review.** Local author-identified manuscript; no acceptance or external publication is asserted.

**English** · [简体中文](README.zh-CN.md)

Paper: *How Much of the Organization Should Agents Know? The Marginal Value of Global Topology Awareness in Hierarchical Multi-Agent Systems* — Haoyan Xu, China University of Geosciences (Beijing).

[Manuscript PDF](paper/organizational_visibility_preprint.pdf) · [Methods](docs/methods.md) · [Results](docs/results.md) · [Offline reproduction](docs/reproduction.md) · [Report index](index/reports.md) · [Run archives](index/runs.md)

## Research question

An agent system can implement a hierarchy while each model call sees only a partial account of that organization. Does adding a global static description help agents use an existing organization more effectively? This study compares native input (**BASE**) with an architecture-specific description of roles, relationships and information flow (**ORG-DESC**, stored as `V2`), retaining native execution interfaces within each comparison.

ROMA recursively reuses Atomizer, Planner, Executor and Aggregator functions across task depths. TalkHier Physics uses a configured six-role hierarchy. These are two different organizational mechanisms; their native input boundaries are audited separately. The intervention describes the existing organization and can clarify or repeat local information as well as disclose remote relationships.

## Research contributions and code ownership

The research work comprises the visibility audit, external intervention and verification adapters, paired experiment design and archival workflow, and question-level analysis of utility, behavior, reliability and collaboration. The repository preserves the native frameworks and their attribution. It does not present ROMA, TalkHier, provider SDKs or external scoring rubrics as newly invented algorithms.

| Research component | Evidence to inspect |
|---|---|
| Native context boundaries and role-specific model inputs | [Current architecture audit](paper_evidence/architecture_audit/README.md), [claim/code map](paper_evidence/architecture_audit/claim_code_map.json) |
| Static organizational descriptions | [ROMA](experiments/prompts/roma_global_description.txt), [TalkHier Physics](experiments/prompts/talkhier_physics_global_description.txt) |
| ROMA external injection and request audit | [Context bridge](experiments/sources/roma/adapters/current_node_context.py), [proxy observer](experiments/sources/roma/proxy/custom_hook.py), [controls](experiments/sources/roma/controls/README.md) |
| TalkHier reversible model boundary and frozen-source verification | [Adapter](experiments/sources/talkhier/repro/org_v2/adapter.py), [runner](experiments/sources/talkhier/repro/run_mmlu.py) |
| Sampling, archival configurations and paired analysis | [Samples](experiments/samples), [configs](experiments/configs), [reproduction script](experiments/analysis/reproduce_tables.py) |
| Whole-tree and structural-outcome supporting analysis | [Method snapshots](paper_evidence/method_sources), [evidence ledger](paper_evidence/evidence_ledger.md) |

See [the contribution and provenance guide](docs/provenance.md) for upstream boundaries, historical commits and known licensing checks before publication.

## Main observations

| Primary paired panel | BASE → ORG-DESC utility | Accompanying behavior |
|---|---|---|
| ROMA / SEAL-0: 94 questions, 272 matched rounds | 35.64% → 35.46% | Expanded tasks −15.80%; recorded total tokens −1.34% |
| ROMA / FRAMES: 47 valid pairs from 50 planned questions | 34/47 → 38/47 (72.34% → 80.85%) | Expanded tasks −18.75%; recorded total tokens +3.66% |
| TalkHier / MMLU-Pro Physics: 94 valid pairs from 100 planned questions | 88/94 → 90/94 (93.62% → 95.74%) | Normal-return model calls +34.57%; normal-return tokens +64.96% |

The organizational description changes execution, but the observed behavioral changes do not establish a reliable general accuracy benefit. The FRAMES paired difference is +8.51 percentage points with the frozen interval crossing zero. SEAL-0 uses **within-question averaging over matched repeats, followed by equal weighting of questions**. Blocked, failed and missing records retain their statuses. ROMA recorded totals and TalkHier normal-return totals have different accounting boundaries and are not a cross-system cost ranking. [Results and uncertainty](docs/results.md).

## Reproduce the archived aggregates

Python 3.12+ and the standard library suffice. No model credentials, inference or new scoring is required:

```sh
uv run --offline --no-project --python python3.12 scripts/reproduce_paper.py
uv run --offline --no-project --python python3.12 scripts/check_repository.py
```

Use an installed Python 3.12 interpreter path if `python3.12` is unavailable. Without uv, the same scripts accept `python3.12 scripts/reproduce_paper.py`. The first command verifies the historical bundle checksums and recomputes principal aggregates; the second validates copied artifacts, metadata, curated links and publication-sensitive file patterns. Neither command launches agents or writes experimental results. [Detailed reproduction and runtime setup](docs/reproduction.md) · [Local validation](docs/validation.md).

## Repository map

| Directory | Contents |
|---|---|
| `paper/` | Existing author-identified manuscript PDF and minimal TeX sources |
| `paper_evidence/` | Current manuscript-aligned evidence, intervention texts, architecture audit and AI-use disclosure |
| `experiments/` | Intact historical full supplement: native source snapshots, adapters, configuration, samples and offline verifier |
| `reports/` | 19 selected report bodies and linked small figures, with filesystem references relocated |
| `index/` | 260-report catalogue, 69-run manifest index and version relations |
| `scripts/` | Thin offline entry points added for this showcase |
| `provenance/` | Source/package hashes and index provenance |

The historical supplement has an older title and table numbering. Its Table 3 / 2 / 4 correspond semantically to the current paper's **behavior / utility / ratings** (Tables 1 / 2 / 3). Original scientific artifacts are preserved; the new wrapper supplies semantic names. The later FRAMES150 runs, old 111/011 conditions and pilots remain historical context outside the main panels.

## Runtime and publication notes

Fresh inference requires separate ROMA and TalkHier environments, frozen datasets, provider/search/sandbox services where applicable, and relocation of archived paths. Start with [runtime guidance](docs/runtime.md); the default offline checks do not validate a fresh end-to-end agent run. The repository does not include the full multi-gigabyte raw transcript archive.

Upstream notices are retained. The owner has not yet selected a blanket license for the research additions or manuscript. Benchmark redistribution and the historical ROMA license gap are recorded in [third-party notices](THIRD_PARTY_NOTICES.md). This is a local review candidate; publication requires the owner's separate confirmation.

Configuration: [Environment variables](docs/security.md).
