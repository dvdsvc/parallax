# Parallax

**Studying How Organizational Visibility Affects Hierarchical Multi-Agent Systems.**

**Paper status: AAMAS 2027 — Under Review.**

**English** · [简体中文](README.zh-CN.md)

[Manuscript PDF](paper/organizational_visibility_preprint.pdf) · [Methods](docs/methods.md) · [Results](docs/results.md) · [Offline reproduction](docs/reproduction.md) · [Report index](index/reports.md) · [Run archives](index/runs.md)

## Research Question: Implementation Is Not Visibility

A multi-agent system can enforce an organization without making that organization fully visible to its agents. Native role instructions and local interfaces may already support coordinated execution, but **functional sufficiency does not establish informational adequacy**. The organization implemented by a system and the organizational view supplied to a member are distinct.

**When members gain access to a broader organizational view, how does their participation in that organization change?**

The paper compares **BASE**, using each system's native context, and **ORG-DESC** (archived as V2), adding a static global account of existing roles, relationships, and information flows. Native role contracts, tools, routing interfaces, and execution rules are preserved. ROMA uses a recursive task-processing template; TalkHier Physics uses a fixed six-role hierarchy. The description explains existing mechanisms without granting permissions or revealing a complete live task tree.

The manuscript separates **RQ1: How does a broader organizational view change execution within an existing organization?** from **RQ2: What practical value and computational consequences accompany those responses?** RQ1 is the main behavioral question; task outcomes and external ratings assess the significance of changed behavior, not a goal of maximizing accuracy.

The paired studies cover ROMA on SEAL-0 (94 questions, 272 matched question-round pairs) and FRAMES (47 valid pairs), and TalkHier on MMLU-Pro Physics (94 valid pairs). These are studied samples, not full-benchmark estimates. The [paper](paper/organizational_visibility_preprint.pdf) and [methods](docs/methods.md) document native input boundaries and the intervention.

## RQ1: Execution Responses to Organizational Visibility

### ROMA: reduced recursive expansion

In ROMA, Atomizer, Planner, Executor and Aggregator are functional modules reused across recursive depths, not four management levels. Under ORG-DESC, SEAL-0 mean logical tasks decrease from **5.09 to 4.76** and expanded tasks from **1.49 to 1.26 (−15.8%)**. Executions reaching depth three fall from **23.94% to 18.44%**.

FRAMES logical tasks decrease from **17.55 to 14.57**, expanded tasks from **5.45 to 4.43 (−18.8%)**, and mean maximum depth from **2.64 to 2.45**. Existing paired intervals for absolute expansion differences are **[−0.47, −0.02]** and **[−1.79, −0.28]**. Mean FRAMES search calls fall from **21.06 to 18.32**, but all 47 paired questions still use search in both conditions. The system changes how it exercises its available recursive template.

**Whole-tree evidence complements node counts.** The analysis reconstructs **544 SEAL-0 trees and 94 FRAMES trees**, comparing structures through tree edit distance and question-blocked PERMANOVA. SEAL-0 shows weak separation: condition accounts for **0.20%** of tree variation (unadjusted permutation **p = 0.5308**). FRAMES shows a modest separation: **1.48%** overall and **3.68%** within questions, with adjusted permutation **p = 0.0426**. Reduced expansion is therefore the clearest shared ROMA response. Complete-tree comparisons also detect modest redistribution in FRAMES, not a large global shift in both settings.

### TalkHier: more work and wider expert participation inside a fixed hierarchy

TalkHier retains its configured role tree and dispatch interfaces. Behavior changes through **expert participation and work within each visit**.

Across 94 valid pairs, Physics visits fall from **135 to 120**, while normal returned model calls increase from **390 to 653**. Calls per visit rise from **2.89 to 5.44**. A role can do more work inside an invocation even when its supervisor invokes it less often.

Mathematics participates in **94/94 questions, up from 74/94**, while normal calls increase from **310 to 627**. Executed internal analysis tools increase from **293 to 881**, including Physics actions rising from **124 to 421** and Mathematics actions from **128 to 411**. These tools write local analysis; they are not retrieval, browsing, or code execution. The increase reflects more internal analytical activity, not expanded access to the environment.

The two experts account for **72.8%** of the net normal-token increase. Output and reasoning tokens also grow, so the change is not simply the longer initial input. These traces locate additional work without establishing that each action improves reasoning or that models explicitly understand topology.

### Behavioral and model-work responses — manuscript Table 1

| Setting | Measure, mean per question | BASE | ORG-DESC | Relative change |
|---|---|---:|---:|---:|
| ROMA / SEAL-0 | Logical tasks | 5.09 | 4.76 | −6.4% |
| ROMA / SEAL-0 | Expanded tasks | 1.49 | 1.26 | −15.8% |
| ROMA / SEAL-0 | Recorded total tokens | 894,741 | 882,762 | −1.3% |
| ROMA / FRAMES | Logical tasks | 17.55 | 14.57 | −17.0% |
| ROMA / FRAMES | Expanded tasks | 5.45 | 4.43 | −18.8% |
| ROMA / FRAMES | Recorded total tokens | 2,441,302 | 2,530,584 | +3.7% |
| TalkHier / Physics | Normal returned model calls | 22.10 | 29.73 | +34.6% |
| TalkHier / Physics | Normal-return tokens | 171,689 | 283,212 | +65.0% |
| TalkHier / Physics | Executed internal analysis tools | 3.12 | 9.37 | +200.7% |

**The two systems adapt along different dimensions: ROMA uses less recursive delegation, while TalkHier broadens expert participation and increases work within visits.** Neither a smaller delegation tree nor more expert activity is intrinsically beneficial. ROMA recorded totals and TalkHier normal-return totals have different definitions and should not be used for cross-system token comparisons.

## RQ2: Computational Consequences and Collaboration Ratings

### Execution size and computational work can move independently

On SEAL-0, ROMA's tokens decline by only **1.3%** despite reduced expansion. On FRAMES, logical and expanded tasks decrease while tokens **increase by 3.7%**. Task count alone is an incomplete resource measure.

TalkHier's normal-return tokens increase by a mean of **111,523 per question (+65.0%)**, with a paired 95% interval of **[61,256, 161,955]**. Of 94 questions, **75** use more tokens and **19** use fewer. Extra expert work has a resource cost but does not establish greater collaboration quality or practical value. Tokens quantify computation here, not financial cost.

### External planning and communication ratings — manuscript Table 3

Existing MARBLE / MultiAgentBench planning and communication rubrics provide a complementary view of ROMA SEAL-0's full recursive execution. The common panel has **86 questions and 227 matched rounds**; rounds are averaged within each question before weighting questions equally.

| External 1–5 rating | BASE | ORG-DESC | Paired difference | Paired 95% interval |
|---|---:|---:|---:|---:|
| Planning | 4.847 | 4.878 | +0.031 | [−0.031, +0.097] |
| Communication | 4.899 | 4.890 | −0.010 | [−0.076, +0.050] |
| Composite (equal-weight derived mean) | 4.873 | 4.884 | +0.011 | [−0.042, +0.065] |

Planning and communication ratings change little despite changed recursive execution. These secondary model-based ratings are close to the scale ceiling and evaluate converted runs; they are not blinded measurements of pure inter-agent communication. They provide complementary evidence that **execution responses and evaluated collaboration quality need not move together**.

## Discussion: Organizational Implementation and Presentation Are Distinct

Organizational implementation determines permitted participation; organizational presentation determines the account of that participation supplied to models. The latter changes realized behavior even while the former remains fixed. The paper hypothesizes that the effect of broader visibility depends both on what members already see and on which actions the system permits: recursive organizations can change delegation, while fixed role hierarchies can change member selection and internal work. This is consistent with the observations but is not a separately established causal mechanism.

ORG-DESC combines topology, responsibilities, workflow, clarification and some repeated information. Its estimated effect belongs to the **entire static description**, not one isolated component. **Organizational information completeness and practical utility are distinct properties.** Organizational visibility should be evaluated through the collaboration it elicits, the outcomes it produces, and the resources it consumes.

The narrative and numbers above are selected and condensed from the submitted manuscript's Introduction, Sections 3 and 5–7, and Tables 1 and 3; no new experimental findings are introduced. [Manuscript PDF](paper/organizational_visibility_preprint.pdf) · [Full results](docs/results.md) · [Paper evidence](paper_evidence/data)

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
