# Claim and artifact map

All differences are ORG-DESC minus BASE. Historical V2 denotes ORG-DESC. Primary populations retain failed/missing states and only use common valid observations.

| Paper content | Packaged supporting evidence | Verification |
| --- | --- | --- |
| Section 3, native organization and visible input | `sources/roma/native/src/roma_dspy/core/`, `sources/talkhier/src/multiagent/`, `sources/talkhier/src/prompts/mmlu.py`, `context_examples/` | Frozen code hashes, native-vs-runtime identity and illustrative actual inputs |
| Section 3, descriptive intervention | `prompts/roma_global_description.txt`, `prompts/talkhier_physics_global_description.txt`, archived injection adapters | Exact intervention bytes; unchanged runtime permissions |
| Table 2, SEAL-0 | `data/seal0_results.json`, `data/seal0_grading_protocols.json` | 94 questions / 272 matched rounds; means recomputed from retained outcomes |
| Three-attempt reliability | `data/seal0_results.json`, `data/reliability_derivation.json` | 86 complete-repeat questions; stored-attempt pass@3 and pass^3 recomputed |
| Table 2, FRAMES | `data/frames_aligned.json`, `data/frames_question_metrics.json`, `samples/frames_selection50_manifest.json` | 50 planned, 47 paired, 34 to 38 correct; errors not zeros |
| Table 2, Physics | `data/talkhier_primary_pairs.csv`, official score records, `samples/talkhier_physics100_questions.jsonl` | 100 planned, 94 paired, 88 to 90 correct; 91/97 and 93/97 are different marginal denominators |
| Table 3, recursion and tokens | `data/roma_recursion.json`, `data/seal0_results.json`, `data/frames_question_metrics.json` | Within-question repeat averages and then equal question weighting |
| Table 3 and expert participation | `data/talkhier_primary_pairs.csv`, `data/talkhier_primary_role_summary.csv`, `data/talkhier_role_question_metrics.csv` | Normal model returns and actual internal OutputTool executions |
| Complete-tree geometry | `data/morphology_results.json`, `analysis/frozen/tree_morphology/` | 544 SEAL-0 / 94 FRAMES trees; canonical ordered APTED, blocked PERMANOVA |
| Table 4, collaboration | `data/collaboration_derivation.json`, `prompts/`, `analysis/frozen/collaboration_sources/` | Common 86-question / 227-round panel; planning and communication plus derived composite |
| Section 7, depth/shape/prediction | `data/roma_recursion.json`, `data/seal0_tree_associations.json`, `data/frames_tree_associations.json`, `data/pls_full_results.json`, `analysis/frozen/method_sources/` | Existing descriptive and held-out results; not new causal mediation evidence |
| Runtime/source provenance | `configs/`, `provenance/source_record_verification.json`, `provenance/frozen_code_verification.json`, `provenance/source_manifest.json` | Fresh raw-record hashes; original and transformed submitted hashes recorded separately |
| AI preparation | `provenance/retained_ai_prompts.json`, supplement S7 | Retained exact prompt excerpts and logged tool/model; broader earlier design dialogue remains outside this retained excerpt set |

Full original raw ledgers are not all contained in the ZIP. Anonymous external-archive locators in frozen code/configuration identify provenance, not extra included files. This distinction is explicit in the supplement and README.
