# Results, populations and evidence

[Home](../README.md) · [Methods](methods.md) · [Reproduce](reproduction.md)

## Primary utility

| Panel | BASE | ORG-DESC | Difference (percentage points) | Evidence |
|---|---:|---:|---:|---|
| SEAL-0, 94 question-equal means over 272 matched rounds | 35.6383% | 35.4610% | −0.1773 | `seal0_results.json` |
| FRAMES, 47 common valid pairs | 34/47 | 38/47 | +8.5106 | `frames_aligned.json` |
| TalkHier Physics, 94 common valid pairs | 88/94 | 90/94 | +2.1277 | `talkhier_summary.json`, `whole_experiment_reconciliation.json` |

Evidence paths above are under [current manuscript evidence](../paper_evidence/data); the historical bundle carries eight quantitatively equivalent core artifacts, checked with an explicit mapping for anonymized archive locators. The frozen FRAMES paired interval is approximately [−6.38, +23.40] percentage points. Use the retained intervals and paired populations rather than interpreting nominal changes as reliable general gains.

TalkHier's marginal completed-answer rates are 91/97 and 93/97. They have different inclusion rules from the 94-pair comparison and must not be substituted into that table. SEAL-0 question-equal averages are not a count divided by 272 or 544 independent executions.

## Execution and model work

| Quantity | BASE | ORG-DESC | Relative change |
|---|---:|---:|---:|
| ROMA SEAL-0 expanded tasks | 1.4929 | 1.2571 | −15.80% |
| ROMA FRAMES expanded tasks | 5.4468 | 4.4255 | −18.75% |
| ROMA SEAL-0 recorded total tokens | 894,741.13 | 882,762.24 | −1.34% |
| ROMA FRAMES recorded total tokens | 2,441,301.64 | 2,530,584.19 | +3.66% |
| TalkHier normal-return model calls | 22.0957 | 29.7340 | +34.57% |
| TalkHier normal-return tokens | 171,688.68 | 283,211.86 | +64.96% |
| TalkHier output-tool calls | 3.1170 | 9.3723 | +200.68% |

Values are means over their stated paired panels. Native recursion changes and role/tool work changes demonstrate behavioral response to the informational intervention. More work does not establish better collaboration or task performance. Token accounting is system-specific; these quantities are not monetary costs or a cross-framework efficiency ranking.

## Reliability and collaboration

On the 86 SEAL-0 questions with three complete matched rounds, at-least-one-pass counts are 48 → 46 and all-three-pass counts are 18 → 18. The three observed trials are the denominator; no missing trial is imputed.

The collaboration common panel contains 86 questions / 227 matched rounds. Question-equal planning means are 4.8469 → 4.8779, communication 4.8992 → 4.8895, and their composite 4.8731 → 4.8837. Retained paired intervals cross zero. These model-based external ratings provide a secondary view of recorded collaboration.

## How to read the broader archive

The [19-report reading list](../index/reports.md) includes primary reports, source audits, supporting analyses and historical context. The later FRAMES150 record and the interrupted pilot are explicitly excluded from the principal paper panels. Older 111/011 controls, College Physics50, fixed-15 explorations and extra N rounds have their own scopes. A tool-count correction is retained through the [version relations](../index/version_relations.md); observer event rows must not be treated as unique logical tool calls.

Original titles, values and archived analysis scripts remain intact. This showcase adds documentation and semantic entry points; it does not produce new inference, model ratings, bootstrap intervals or significance tests.
