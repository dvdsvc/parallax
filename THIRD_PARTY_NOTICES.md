# Third-party notices and release checks

This local review candidate includes research additions, third-party source snapshots and benchmark excerpts. No blanket project license is asserted. Preserve each upstream notice and verify redistribution scope before public release.

| Component | Retained evidence | Status |
|---|---|---|
| ROMA / roma-dspy | Native pyproject author metadata and historical source manifests; `third_party/ROMA_LATER_CHECKOUT_LICENSE` | Later local upstream checkout has MIT, copyright Salah Al-Zubi. The pinned native commit `a6e3bb4…` has no root LICENSE; the later license is contextual evidence, not proof of historical license coverage. Verify before release. |
| TalkHier | `experiments/sources/talkhier/LICENSE`, native README and frozen commit | Existing Sony upstream license retained verbatim; follow its terms. |
| MMLU-Pro scoring source | `experiments/sources/mmlu_pro_scoring/LICENSE` | Pinned official scoring implementation and notice retained. Dataset and scoring-code rights should be checked separately. |
| MARBLE / collaboration rubrics | `experiments/analysis/frozen/collaboration_sources/07_LICENSE`; `paper_evidence/scoring_prompts/MARBLE_LICENSE` | Existing rubric/source license files retained. |
| FRAMES and MMLU-Pro sample packs | `experiments/samples/`, manifests and manuscript bibliography | Frozen benchmark excerpts are intentional reproducibility artifacts in this local copy. Confirm dataset redistribution/attribution terms before publication; no new data license is granted. |
| SEAL-0 / SealQA-derived evidence | Frozen panels, grading protocol and manuscript bibliography | Retained as analysis evidence; verify any upstream data/trace redistribution terms. |
| ACM reference style | `paper/source/ACM-Reference-Format.bst` | Original distribution header retained; this is a formatting asset, not a paper acceptance claim. |

Research-specific scripts, explanatory documents, manuscript and figures remain subject to the owner's license choice. Do not infer a permissive license from the presence of a third-party MIT file. This preparation does not upload benchmark data or publish the local author-identified manuscript.
