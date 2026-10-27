# Methods and implementation boundaries

[Home](../README.md) · [Results](results.md) · [Evidence ledger](../paper_evidence/evidence_ledger.md)

## Study design

The independent variable is the addition of a fixed architecture-specific organizational description to native model inputs. BASE retains its native local context; ORG-DESC adds roles, relationships, workflow position and information flow. In archived artifacts ORG-DESC is called `V2`. Within a contrast, native task tools, role contracts, routing interfaces and execution rules remain the same; subsequent decisions and histories may diverge.

This is an intervention on the model-visible organizational account. It is a bundled informational treatment: remote relations, clarification and repetition of native information can all contribute. It does not isolate topology alone, expose the full live recursive tree, or grant access to every member's private history.

## Native organizations

ROMA uses recursive TaskNodes. Atomizer, Planner, Executor and Aggregator are functional modules reused at multiple task depths. Native context construction supplies goal, overall objective, depth/limit and module-specific dependency or child results when available. A depth cap forces execution. See [native context manager](../experiments/sources/roma/native/src/roma_dspy/core/context/manager.py) and [the current audit](../paper_evidence/architecture_audit/README.md).

TalkHier Physics has DefaultSupervisor, AnswerGenerator, Revisor, EvaluatorSupervisor, Physics and Mathematics. Supervisors know direct rosters and dispatch choices; leaves see task background and selected local history. This six-role map applies to Physics. See [frozen team implementation](../paper_evidence/architecture_audit/sources/talkhier/frozen/src/multiagent/agent_team.py) and [Physics prompts](../paper_evidence/architecture_audit/sources/talkhier/frozen/src/prompts/mmlu.py).

## External intervention and control

ROMA's [current-node bridge](../experiments/sources/roma/adapters/current_node_context.py) separates request-local metadata from the static organization prefix. The [proxy observer](../experiments/sources/roma/proxy/custom_hook.py), particularly `_observe_org_awareness_v2`, checks exact template bytes, presence and duplicate/conflicting markers at the pre-LiteLLM boundary. It observes an already-inserted block rather than adding a second one. Keep `condition=BASE` in both primary arms and vary `organization_awareness_v2`; older `111`/`011` visibility controls are different interventions.

TalkHier's [adapter](../experiments/sources/talkhier/repro/org_v2/adapter.py) verifies frozen sources, deep-copies messages, rejects duplicate organization markers and wraps selected model objects. `invoke`/`ainvoke`, tool binding and structured-output delegation preserve native interfaces. The installation context manager restores patched constructors afterward. In the actual [runner](../experiments/sources/talkhier/repro/run_mmlu.py), BASE bypasses installation; V2 installs the wrapper with `all_roles` for the primary comparison. Provider compatibility changes were shared by both arms and are recorded separately from the organizational treatment.

## Sampling and unit of analysis

| Panel | Sampling and analysis unit |
|---|---|
| ROMA SEAL-0 | H/R1/R2, 94 questions and 272 matched question-round pairs; 86 questions have 3, six have 2 and two have 1 matched round. Average within question before equal question weighting. |
| ROMA FRAMES | Budget-reduced selection of 50 from the archived candidate set; 47 valid paired questions. Preserve candidate loader index, official ID and selection manifest together. |
| TalkHier Physics | Fixed seed-42 sample of 100 from 1,299 official MMLU-Pro test Physics questions; 94 valid paired questions. Official answer order is preserved for exact-match scoring. |

Blocks, errors, timeouts and missing records retain their statuses. Common valid records define paired comparisons. Historical rounds have distinct budgets/protocols; do not reconstruct them using one default configuration.

## Evaluation and supporting analysis

Task utility, execution behavior and resource work are separate outcomes. ROMA trees count logical native tasks; callbacks and tool loops are not additional task nodes. Whole-tree edit distance uses structural representations without attaching correctness or token labels. Typed dependency graphs and whole-tree comparisons are supporting analyses with their own definitions.

TalkHier role visits, model calls and tool executions are separate. Primary work totals include successful callback returns without length truncation and with nonempty text or valid tool calls. Empty prose with valid tool calls remains valid. Normal work before a graph failure remains recorded work. Graph retries, model API errors and HTTP attempts are distinct events. Reasoning/cache usage is a subset of output/input usage and is not added twice.

The shared collaboration panel has 86 questions and 227 matched rounds. Planning and communication use retained external rubrics; the composite is their derived average. Frozen intervals are retained. Structural-outcome associations, PCA and PLS are descriptive supporting evidence; the study does not establish a causal mediation mechanism.
