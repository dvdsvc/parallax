# Supplementary Material

Supporting material for **Functionally Sufficient, Informationally Incomplete: The Marginal Value of Organizational Visibility in Hierarchical LLM Agents**.

Read `supplement.pdf` for the experimental protocols, visibility audit, scoring definitions, complete-run measures, supporting analyses, exact intervention texts and AI-preparation disclosure. The editable text is `supplement.md`. Historical `V2` labels in retained data mean the paper condition `ORG-DESC`; ROMA archive labels can remain `BASE` in both conditions, with the actual treatment recorded by `organization_awareness_v2`.

## Offline verification

From this directory, run:

```sh
python3 analysis/reproduce_tables.py
```

This standard-library entry point verifies `SHA256SUMS` and independently recomputes the principal Table 2 accuracy means, three-attempt reliability, Table 3 execution means and Table 4 collaboration means. It requires no account, API key, network access or new experiment. It prints the results as JSON. Intervals remain the original frozen derivations.

## Layout and scope

| Directory | Contents |
| --- | --- |
| `data/` | Complete primary question panels, failure statuses, role summaries, existing structural/predictive outputs and frozen uncertainty |
| `prompts/` | Exact ROMA and TalkHier intervention texts, native Graph rubrics and full MARBLE template file |
| `samples/` | Fixed Physics100 question pack; FRAMES candidate80 data and the budget-reduced selection50 manifest |
| `context_examples/` | Existing representative actual model inputs; not additional primary trials |
| `configs/` | Archived decoding, data, provider and per-run configuration, with personal paths anonymized |
| `sources/roma/` | Frozen native source and external runtime snapshots, separated by historical archive |
| `sources/talkhier/` | Startup-frozen native source, compatibility boundary, intervention adapter, sampling and archival tools |
| `sources/mmlu_pro_scoring/` | Pinned official exact-match scoring source and license |
| `analysis/frozen/` | Existing analysis and full-run MARBLE conversion implementations |
| `provenance/` | Manuscript hash, source and submitted-file hashes, fresh record/code verification, retained AI prompt excerpts |

Primary scope is SEAL-0 H/R1/R2 (94 questions, 272 matched rounds), FRAMES50 (47 valid pairs) and Physics100 (94 valid pairs). Earlier 111/011 interventions, the College Physics pilot, extra N rounds and later FRAMES150 do not enter the principal comparisons. Existing secondary/sensitivity fields in source JSON remain explicitly labeled as such. Blocks, timeouts and errors are not assigned incorrect-answer scores.

## Code reuse and fresh execution

The source directories are historical code snapshots. Personal path replacements are explicitly tracked by original and package hashes in `provenance/source_manifest.json`; exact intervention and scoring prompt bytes are preserved. Paths beginning `external_archive/`, `external_home/` and archived `sources/` paths in frozen configurations are anonymous locators and may require relocation. These are not guarantees that every archival script is runnable without configuration.

For ROMA, install the native snapshot with its `pyproject.toml` and recorded dependency lock, stage the appropriate external runner/proxy/control snapshot for the chosen source archive, and supply independently configured provider, search and sandbox credentials. Recreate native task IDs and budgets using the individual archived configuration, retain `condition=BASE` in both arms, and change only `organization_awareness_v2`. Later 4096/8192 pilot budgets are not the historical main-study budgets. SEAL-0 histories have distinct budgets and protocols; do not run all historical rounds with one default. `configs/roma_seal0_archives/` and the archive catalog preserve those differences. The FRAMES selected loader indices, official IDs, candidate80 input and selection50 manifest must be used together.

For TalkHier, stage `sources/talkhier/` as the repository root and install its `repro/requirements.mmlu.lock.txt` and interface requirements using a separate environment. The primary batch uses the native Physics team through the MMLU-Pro adapter, scope `all_roles`, thinking budget 8192, completion cap 16384, temperature zero, seed-42 sampling and 3600-second per-question timeout. Use the packaged question IDs and manifests. Configure a compatible provider independently; the archived localhost gateway requires explicit setup. Native retry/graph behavior and structured-output compatibility changes are common to both arms. Preflight validation can inspect configuration without agent calls, but fresh inference and native semantic grading require external services and incur their usual costs. No such calls were made while preparing this package.

A fresh API run is distinct from offline reproduction of archived numbers. Model service changes and stochastic execution can change newly obtained outcomes. The supplied offline entry point targets the archived evidence reported in the paper.

## Data and source attribution

Original ROMA, TalkHier, MARBLE and MMLU-Pro license files are retained with their source directories. Benchmark resources are attributed in the sample/configuration manifests and supplementary references. These third-party credits identify upstream projects rather than the submitting authors. No Git repository history, submitting-author identity, local credentials or main-paper source is included. The 2.27 GB complete raw-log inventory is represented by fresh verification hashes and quantitative panels rather than copied in full.

The material is a single anonymous ZIP below 25 MB, as specified by [AAMAS 2027 Submission Instructions](https://warwick.ac.uk/fac/sci/dcs/aamas2027/guidelines-and-policies/instructions/). It supports the submitted paper and does not replace or extend that paper. Reviewers may consult it at their discretion. Accepted-paper archival publication of this supplement is a later author action.
