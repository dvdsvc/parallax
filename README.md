# Parallax

**Studying How Organizational Visibility Affects Hierarchical Multi-Agent Systems.**

**Paper status: AAMAS 2027 — Under Review.**

**English** · [简体中文](README.zh-CN.md)

[Manuscript PDF](paper/organizational_visibility_preprint.pdf) · [Methods](docs/methods.md) · [Results](docs/results.md) · [Offline reproduction](docs/reproduction.md) · [Report index](index/reports.md) · [Run archives](index/runs.md)

## Research question

An agent system can implement a hierarchy while each model call sees only a partial account of that organization. Does adding a global static description help agents use an existing organization more effectively? This study compares native input (**BASE**) with an architecture-specific description of roles, relationships and information flow (**ORG-DESC**, stored as `V2`), retaining native execution interfaces within each comparison.

ROMA recursively reuses Atomizer, Planner, Executor and Aggregator functions across task depths. TalkHier Physics uses a configured six-role hierarchy. These are two different organizational mechanisms; their native input boundaries are audited separately. The intervention describes the existing organization and can clarify or repeat local information as well as disclose remote relationships.

## Main Results from the Paper

The following findings are adapted from the manuscript's main text, highlighting how organizational visibility affects execution, task outcomes and computational work. BASE and ORG-DESC are compared within each native framework, with model configuration matched within each paired experiment.

### Execution: less recursive expansion or more work within roles

ROMA reduces recursive expansion in both tasks: mean expanded tasks fall by **15.80%** on SEAL-0 and **18.75%** on FRAMES. In FRAMES, mean search calls also decline from 21.06 to 18.32, while all 47 paired questions still use search in both conditions. The organizational description changes how agents exercise the existing recursive mechanism.

TalkHier retains its fixed role hierarchy, with changes concentrated in expert participation and work within role invocations. Mathematics participates in **94/94 questions, up from 74/94**. Physics visits decline from 135 to 120 across the panel, while its normal returned model calls increase from 390 to 653: calls per visit rise from 2.89 to 5.44. Role visits and the work performed within a visit capture different aspects of execution.

| System and task | Measure, mean per question | BASE | ORG-DESC | Relative change |
|---|---|---:|---:|---:|
| ROMA / SEAL-0 | Expanded tasks | 1.49 | 1.26 | −15.80% |
| ROMA / FRAMES | Expanded tasks | 5.45 | 4.43 | −18.75% |
| ROMA / SEAL-0 | Recorded total tokens | 894,741 | 882,762 | −1.34% |
| ROMA / FRAMES | Recorded total tokens | 2,441,302 | 2,530,584 | +3.66% |
| TalkHier / Physics | Normal returned model calls | 22.10 | 29.73 | +34.57% |
| TalkHier / Physics | Normal-return tokens | 171,689 | 283,212 | +64.96% |

Relative changes use unrounded means. ROMA uses archived recorded totals and TalkHier uses normal-return usage; resource comparisons are made within each system.

### Task outcomes: behavioral changes and task value move differently

| Primary paired panel | BASE | ORG-DESC | Difference, pp | Paired 95% interval, pp |
|---|---:|---:|---:|---:|
| ROMA / SEAL-0: 94 questions, 272 matched rounds | 35.64% | 35.46% | −0.18 | [−6.38, +5.67] |
| ROMA / FRAMES: 47 valid pairs from 50 planned questions | 34/47 (72.34%) | 38/47 (80.85%) | +8.51 | [−6.38, +23.40] |
| TalkHier / MMLU-Pro Physics: 94 valid pairs from 100 planned questions | 88/94 (93.62%) | 90/94 (95.74%) | +2.13 | [0.00, +5.32] |

SEAL-0's mean utility remains nearly unchanged. FRAMES has eight improvements and four regressions, yielding an estimated +8.51 percentage points with an interval crossing zero. TalkHier answers two additional questions correctly while using about 65% more normal-return tokens. Fewer expanded tasks also need not mean fewer tokens: FRAMES uses slightly more tokens despite less recursive expansion.

SEAL-0 averages matched rounds within each question before weighting questions equally; intervals use question-level paired bootstrap resampling. Failed, blocked and missing records retain their statuses, and the main tables use common valid paired records.

### Repeat success and research conclusion

On the 86 SEAL-0 questions with three complete matched rounds, at-least-one-success counts are **48 → 46**, while all-three-success counts remain **18** in both conditions. Mean external planning and communication ratings also change little.

The main finding is that **a broader organizational view changes how agents participate in collaboration, with task benefits and computational consequences depending on the system and task.** ROMA uses less recursive delegation; TalkHier broadens expert participation and increases work within roles. Organizational implementation and the organizational information visible to agents are two design dimensions to consider together.

These results correspond to the manuscript's execution and task-utility tables and accompanying analysis. [Manuscript PDF](paper/organizational_visibility_preprint.pdf) · [Full results and statistical definitions](docs/results.md) · [Paper evidence](paper_evidence/data)

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
