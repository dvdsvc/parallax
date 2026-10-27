# Frozen FRAMES80 BASE/V2 paper run

External orchestration only. `run_arm.py` invokes the existing
`run_isolated_frames.main_async` and adds logging-only PaperRunArchive lifecycle
hooks for pre-run MLflow creation and post-run indexing. Native ROMA source,
solver, prompts and retry behavior are unchanged. The two arms share all controls
except `ROMA_ORG_AWARENESS_V2`; the existing static V2 prompt is used verbatim.

`supervise.py` launches BASE and V2 concurrently at 8 question workers per arm.
It refuses duplicate study launches. Each question uses the existing isolated
worker/proxy/trace guard, storage and opaque UUID worker directory. Inputs are the
frozen eighty-task TSV and matching JSONL; loader seed is 0, independent of
sampling seed 20261003. Official IDs and loader positions are both retained.

After both arms finish, `grade_native.py` calls the official
`SearchMetric.forward` directly, preserving its predictor, prompt and label
mapping. Each stable completed, guard-validated output is graded once. Native LM
transport retries remain native; terminal errors remain null. No MAB scoring.
The grader stores source hashes, inputs, native LM histories and scores, with
credential fields redacted. Grading does not alter execution archives.

The study records configs, task/source hashes, full Git bundles and byte-exact
tracked Agent/control snapshots, including dirty diffs and effective profiles.
Existing snapshots, raw traces and sampling artifacts are never overwritten.
