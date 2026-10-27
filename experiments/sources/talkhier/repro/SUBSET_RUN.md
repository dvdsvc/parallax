# Frozen 50-question college-physics run

The main sample is `repro/subsets/college_physics_test_n50_seed42`. It selects 50 of the 102 native `cais/mmlu` college-physics **test** rows without replacement using `random.Random(42).sample`. No rows are excluded, including earlier smoke-test rows. `indices.json` contains the original zero-based row indices in sorted execution order; `draw_order.json` preserves the random draw order. Each condition runs these same 50 questions once (100 question-condition executions total).

```sh
.venv/bin/python repro/sample_mmlu.py --mode college_physics --count 50 --seed 42 --output-dir repro/subsets/college_physics_test_n50_seed42
.venv/bin/python repro/sample_mmlu.py --verify --output-dir repro/subsets/college_physics_test_n50_seed42
.venv/bin/python repro/run_subset.py --subset repro/subsets/college_physics_test_n50_seed42 --workers-per-condition 8 --thinking-budget 8192 --max-completion-tokens 16384 --timeout-seconds 3600
```

The saved sample includes the exact sampler snapshot, command, seed, population/exclusion rule, original indices, full question text/choices/gold answers, source dataset revision and per-question/file checksums. The seed controls question sampling, not model generation. Existing samples and run directories cannot be overwritten.

The two queues each allow at most eight independent native single-question processes. The original agent implementation, role prompts, tools and routes are preserved. BASE has no organization wrapper; V2 injects the previously frozen static organization text for all roles. Both use `qwen3.7-flash`, temperature 0, explicitly enabled thinking, strict provider JSON Schema dictionaries, the same 8,192 thinking-token budget and 16,384 combined reasoning/final-response token ceiling. `max_tokens` is omitted. Both caps apply per model call and are passed identically to all roles in both conditions. The documented values are candidate defaults for future runs; changing them does not resume or rewrite any stopped batch. Each question has a 3,600-second external wall-time limit; each API call has a 900-second timeout and two SDK retries. Failed or timed-out questions remain incomplete and are not automatically rerun or converted into incorrect answers.

A controller MLflow Run is created before any workers. Every question-condition process has its own child Run, source/environment/config/question snapshots, native console/CSV, LangChain/LangGraph callback trace, returned usage and sealed checksums. The full sample is copied into every startup archive. The controller continuously writes `manifest.json` and `paired_results.csv`, then seals its own archive after the workers finish. Native working CSVs stay outside sealed archives so the author's exit cleanup cannot rewrite them. Provider usage for failed/cancelled or unreturned calls can be missing; recorded usage totals are observed usage, not a complete billing statement.

No LangSmith service is enabled. The MLflow store and artifacts are local. The live batch's recorded source files must stay unchanged until it finishes.
