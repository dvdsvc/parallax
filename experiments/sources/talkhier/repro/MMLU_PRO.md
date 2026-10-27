# MMLU-Pro Physics: fixed 100-question sample

Official dataset: https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro

Pinned dataset revision: `b189ec765aa7ed75c8acfea42df31fdae71f97be`. The original parquet files and dataset card are preserved under `data/mmlu_pro/<revision>/official/`. All Physics records are exported without rewriting their question, options, answer, explanation or source fields. The test population contains 1,299 Physics questions; validation contains 5 and is excluded from sampling.

The fixed sample is `repro/subsets/mmlu_pro_physics_test_n100_seed42/`. Selection is `random.Random(42).sample(range(1299), 100)`, without replacement, exclusions, difficulty filtering or outcome-based selection. Records are saved in original test-split order. The 100 sampled questions have 97 sets of 10 options, 2 sets of 9, and 1 set of 7. No test Physics record contains the literal `N/A` padding option at this revision. No options are removed or reordered.

Three IDs are preserved separately:

* `indices.json`: original full test-split row indices, zero based.
* `physics_indices.json`: ordinals within the filtered Physics population, zero based.
* `question_ids.json`: official `question_id`, preserved independently of row numbers.

`indices.csv` maps these IDs to sample position and archival gold labels. `draw_order.json` preserves Physics population ordinals in RNG draw order. `questions.jsonl` preserves complete selected official records, including gold/explanation fields for archival and scoring only; these are not model-input packets. `sampling_script.py` is the exact sampler snapshot, `command.txt` the invocation, and `manifest.json`/`checksums.sha256` preserve sampling policy and file hashes.

Preparation and replay:

```sh
.venv/bin/python repro/prepare_mmlu_pro.py --revision b189ec765aa7ed75c8acfea42df31fdae71f97be --parquet-python sources/roma/controls/.venv/bin/python
.venv/bin/python repro/sample_mmlu_pro.py --count 100 --seed 42 --output-dir repro/subsets/mmlu_pro_physics_test_n100_seed42
.venv/bin/python repro/prepare_mmlu_pro.py --verify
.venv/bin/python repro/sample_mmlu_pro.py --output-dir repro/subsets/mmlu_pro_physics_test_n100_seed42 --verify
```

Once the sample exists, the sampling command refuses to overwrite it. The saved sampler can replay into a new output directory within the workspace. Sample manifest timestamps and output command paths differ between replays; the question bytes, all three ID lists, draw order and index CSV must be identical.

The agent environment's PyArrow 19.0.0 encounters a parquet-reading compatibility error on this snapshot. Preparation reuses an existing separate interpreter with PyArrow 25.0.1 solely to read/verify parquet; it does not install packages or alter the TalkHier environment. On another machine, supply a compatible data-reader interpreter with `--parquet-python`. Once exported, sampling needs only Python's standard library.

This preparation does not run an agent or grader, change TalkHier prompts/graph, add validation examples to model context, or modify prior run archives. The existing runner targets `cais/mmlu`; execution of this new dataset requires a separate external dataset mapping. The sampling seed is not a model-generation seed. Report future results as the fixed 100-question Physics sample, rather than the full MMLU-Pro benchmark.
