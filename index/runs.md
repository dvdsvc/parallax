# Run archive index / 运行归档索引

[Reports](reports.md) · [Methods](../docs/methods.md)

69 historical manifest records. These are archive metadata, not 69 live processes or a claim that all raw traces are bundled. The recorded condition label and effective organization switch are separate columns. A recorded `running` status is not current process status. Exact hashes, model configuration and source commits are in [JSON](run_archive_index.json).

| Archive ID | Agent / benchmark | Label | Organization switch | Historical status |
|---|---|---|---|---|
| `20260918T055838Z_111_seal0-111-6ee07c85336c` | ROMA / SEAL-0 | 111 | None | completed |
| `20260918T060407Z_111_seal0-111-61a242e32a3e` | ROMA / SEAL-0 | 111 | None | partial_or_error |
| `20260918T065250Z_111_seal0-111-62a6b8137a71` | ROMA / SEAL-0 | 111 | None | partial_or_error |
| `20260920T174008Z_111_seal0-layered-intent-smoke-20260921` | ROMA / SEAL-0 | 111 | None | partial_or_error |
| `20260920T183712Z_101_seal0-executor-intent-off-org-unaware-20260921` | ROMA / SEAL-0 | 101 | None | partial_or_error |
| `20260920T183956Z_101_seal0-executor-intent-off-org-unaware-v2-20260921` | ROMA / SEAL-0 | 101 | None | partial_or_error |
| `20260920T184252Z_101_seal0-executor-intent-off-org-unaware-second-order-20260921` | ROMA / SEAL-0 | 101 | None | partial_or_error |
| `20260920T184457Z_101_seal0-executor-intent-off-org-unaware-second-order-v2-20260921` | ROMA / SEAL-0 | 101 | None | completed |
| `20260921T070525Z_101_seal0-111-intent-plan-on-org-off-20260921T070521Z` | ROMA / SEAL-0 | 101 | None | running |
| `20260921T070525Z_101_seal0-eoff-org-off-20260921T070521Z` | ROMA / SEAL-0 | 101 | None | running |
| `20260921T070525Z_101_seal0-peoff-org-off-20260921T070521Z` | ROMA / SEAL-0 | 101 | None | running |
| `20260921T070638Z_101_seal0-111-intent-plan-on-org-off-20260921T070635Z` | ROMA / SEAL-0 | 101 | None | partial_or_error |
| `20260921T070640Z_101_seal0-peoff-org-off-20260921T070635Z` | ROMA / SEAL-0 | 101 | None | partial_or_error |
| `20260921T070641Z_101_seal0-eoff-org-off-20260921T070635Z` | ROMA / SEAL-0 | 101 | None | completed |
| `20260921T095301Z_111_seal0-peoff-org-aware-20260921T095257Z` | ROMA / SEAL-0 | 111 | None | partial_or_error |
| `20260928T110427Z_11_seal0-11-c19f1ca61bdf` | ROMA / SEAL-0 | 11 | True | partial_or_error |
| `20260928T111230Z_11_seal0-v2-tail-flip-rerun-20260928T1912` | ROMA / SEAL-0 | 11 | True | partial_or_error |
| `20260928T113846Z_11_seal0-v2-tail-flip-valid-20260928T113841Z` | ROMA / SEAL-0 | 11 | True | partial_or_error |
| `20260928T121938Z_BASE_seal0-v2-org-aware-smoke-20260928T121923Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20260928T122531Z_BASE_seal0-v2-org-aware-smoke-isolated-20260928T122507Z` | ROMA / SEAL-0 | BASE | True | completed |
| `20260928T122826Z_BASE_seal0-v2-org-aware-tail-flip-20260928T1228Z` | ROMA / SEAL-0 | BASE | True | completed |
| `20260928T145834Z_BASE_seal0-base-86c3dee8a589` | ROMA / SEAL-0 | BASE | True | completed |
| `20260928T150512Z_BASE_seal0-base-0381d83a2b6a` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20260929T025106Z_BASE_seal0-base-native-e2b-smoke-20260929` | ROMA / SEAL-0 | BASE | False | completed |
| `20260929T025511Z_BASE_seal0-base-native-e2b-1-110-20260929` | ROMA / SEAL-0 | BASE | False | partial_or_error |
| `20260929T041539Z_BASE_seal0-v2-e2b-rerun-q1-11-29-32-39-40-48-50-87-109-20260929T0415Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20260930T113142Z_BASE_seal0-base-9fd6a0a9e2cd` | ROMA / SEAL-0 | BASE | False | completed |
| `20260930T113142Z_BASE_seal0-base-a0c25fee45dc` | ROMA / SEAL-0 | BASE | True | completed |
| `20260930T141921Z_BASE_seal0-paired15-base-repeat1-20260930T141651Z` | ROMA / SEAL-0 | BASE | False | completed |
| `20260930T141921Z_BASE_seal0-paired15-base-repeat2-20260930T141651Z` | ROMA / SEAL-0 | BASE | False | partial_or_error |
| `20260930T141921Z_BASE_seal0-paired15-v2-repeat2-20260930T141651Z` | ROMA / SEAL-0 | BASE | True | completed |
| `20260930T141922Z_BASE_seal0-paired15-v2-repeat1-20260930T141651Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20261001T115919Z_BASE_seal0-seed43-base-repeat1-20261001T115351Z` | ROMA / SEAL-0 | BASE | False | partial_or_error |
| `20261001T115919Z_BASE_seal0-seed43-base-repeat2-20261001T115351Z` | ROMA / SEAL-0 | BASE | False | partial_or_error |
| `20261001T115919Z_BASE_seal0-seed43-v2-repeat1-20261001T115351Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20261001T115919Z_BASE_seal0-seed43-v2-repeat2-20261001T115351Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20261001T135821Z_BASE_seal0-seed44-base-repeat1-20261001T135508Z` | ROMA / SEAL-0 | BASE | False | completed |
| `20261001T135821Z_BASE_seal0-seed44-base-repeat2-20261001T135508Z` | ROMA / SEAL-0 | BASE | False | completed |
| `20261001T135821Z_BASE_seal0-seed44-v2-repeat1-20261001T135508Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20261001T135821Z_BASE_seal0-seed44-v2-repeat2-20261001T135508Z` | ROMA / SEAL-0 | BASE | True | completed |
| `20261001T142320Z_BASE_seal0-seed44-v2-repeat1-q2-retry1-20261001T142211Z` | ROMA / SEAL-0 | BASE | True | completed |
| `20261002T080800Z_BASE_seal0-remaining59-base-repeat1-20261002T080159Z` | ROMA / SEAL-0 | BASE | False | completed |
| `20261002T080800Z_BASE_seal0-remaining59-base-repeat2-20261002T080159Z` | ROMA / SEAL-0 | BASE | False | partial_or_error |
| `20261002T080800Z_BASE_seal0-remaining59-v2-repeat1-20261002T080159Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20261002T080800Z_BASE_seal0-remaining59-v2-repeat2-20261002T080159Z` | ROMA / SEAL-0 | BASE | True | partial_or_error |
| `20260919T064245Z_BASE_seal0-base-534a5fb387bb` | ROMA / FRAMES | BASE | None | completed |
| `20260919T071958Z_BASE_frames-base-a37104188239` | ROMA / FRAMES | BASE | None | partial_or_error |
| `20260919T074200Z_BASE_frames-base-dc0ff762bb83` | ROMA / FRAMES | BASE | None | partial_or_error |
| `20260919T075412Z_BASE_frames-base-431a74236ce4` | ROMA / FRAMES | BASE | None | partial_or_error |
| `20260920T035225Z_111_frames-111-0ff55c615e98` | ROMA / FRAMES | 111 | None | partial_or_error |
| `20260920T035225Z_BASE_frames-base-20c2ca26c613` | ROMA / FRAMES | BASE | None | partial_or_error |
| `20260920T071543Z_001_frames-001-a97dba127bc0` | ROMA / FRAMES | 001 | None | partial_or_error |
| `20260920T071543Z_011_frames-011-fb5e6830f5b6` | ROMA / FRAMES | 011 | None | partial_or_error |
| `20260920T073129Z_001_frames-001-d2641b6d4c8e` | ROMA / FRAMES | 001 | None | partial_or_error |
| `20260920T073129Z_011_frames-011-c32bdc137483` | ROMA / FRAMES | 011 | None | partial_or_error |
| `20260929T153429Z_BASE_frames-clean-v2-smoke-20260929T153426Z` | ROMA / FRAMES | BASE | True | partial_or_error |
| `20260929T153548Z_BASE_frames-clean-v2-smoke-20260929T153543Z` | ROMA / FRAMES | BASE | True | partial_or_error |
| `20260929T153730Z_BASE_frames-clean-v2-smoke-20260929T153727Z` | ROMA / FRAMES | BASE | True | running |
| `20261006T133220Z_BASE_roma_pilot5_tb4096_mc8192_20261006T132647Z-BASE` | ROMA / FRAMES | BASE | False | interrupted |
| `20261006T133220Z_BASE_roma_pilot5_tb4096_mc8192_20261006T132647Z-V2` | ROMA / FRAMES | BASE | True | interrupted |
| `20261004T135630Z_BASE_frames50-v2-20261004T132044Z` | ROMA / FRAMES | BASE | True | partial_or_error |
| `20261004T135751Z_BASE_frames50-base-20261004T132044Z` | ROMA / FRAMES | BASE | False | completed |
| `20261004T120910Z_BASE_frames80-base-20261004T120825Z` | ROMA / FRAMES | BASE | False | partial_or_error |
| `20261004T120910Z_BASE_frames80-v2-20261004T120825Z` | ROMA / FRAMES | BASE | True | partial_or_error |
| `20261005T153505526128Z_college_physics_n50_seed42` | TalkHier / {} | None | None | interrupted |
| `20261006T045520595135Z_college_physics_n50_seed42_tb8192_mc16384` | TalkHier / {} | None | None | completed_with_errors |
| `20261006T090617775637Z_mmlu_pro_physics_n100_seed42_tb8192_mc16384_gw16x16` | TalkHier / TIGER-Lab/MMLU-Pro | None | None | completed_with_errors |
| `20261006T090617775637Z_mmlu_pro_exact_match` | TalkHier / {} | None | None | completed |
| `20261006T090617775637Z_mmlu_pro_exact_match_interim_20261006T113715670482Z` | TalkHier / {} | None | None | completed |
