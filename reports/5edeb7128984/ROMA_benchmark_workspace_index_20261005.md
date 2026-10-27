# ROMA、SEAL-0、FRAMES 与实验留档位置索引

检查日期：2026-10-05（北京时间）。本次定位并阅读现有材料，查询只读 MLflow SQLite 数据库，抽查校验和；没有启动 Agent、评分器或 MLflow 服务，没有修改源实验。

## 目录与入口

| 内容 | 位置与用途 |
|---|---|
| 近期实验使用的 ROMA | `archive://2026-09-12/hira/forammas`；HEAD `a6e3bb4f9e0694375fa627fa4b8bf8cae50592a6` |
| 其他 ROMA checkout | 同根目录下 `official-roma`、`official-roma-v2`、`official-roma_modified_20260914`；不要仅按目录名选择实验版本 |
| 实验控制层 | `archive://2026-09-12/hira/work/forammas_study/README.md`；配置、条件定义、V2 提示词、trace guard 和 MLflow |
| SEAL-0 正式 Paper Run 入口 | `archive://2026-09-12/hira/work/roma_v1_adapters/run_isolated_seal0.py`，以 `--paper-run-config <json>` 启动 |
| FRAMES 运行与归档接口 | `archive://2026-09-12/hira/work/roma_v1_adapters/run_isolated_frames.py`；当前 CLI 与 SEAL-0 不同，不能直接照搬 `--paper-run-config` |
| 最新 FRAMES 配置启动入口 | `archive://2026-10-02/frames/work/frames80-paper-launch/run_selected_arm.py`；接收配置路径，调用 FRAMES 接口并注册 MLflow |
| 归档实现 | `archive://2026-09-12/hira/work/roma_v1_adapters/paper_run_archive.py`、`paper_run_archive_frames.py` |
| 原生评分入口 | 上述 adapters 目录下 `score_seal0_native.py`、`score_frames_native.py` 与 `paper_grade_run.py` |
| SEAL-0 Paper Run 归档 | `archive://2026-09-12/hira/work/paper_runs` |
| 历史 FRAMES Paper Run 归档 | `archive://2026-09-12/hira/work/paper_runs_frames`；最新 FRAMES50 另有 study 自有的 `paper_runs/` |
| SEAL-0 批次配置及状态 | `archive://2026-09-12/hira/work/paper_studies` 和 `paper_run_configs` |
| 原始 worker 目录 | `archive://2026-09-12/hira/work/isolated_seal0_runs` |
| 较早多条件分析 | `archive://2026-09-16/wo/outputs`；包括旧 BASE/111/011/001、交互分析和早期条件审计 |
| 后续配对与递归分析 | `archive://2026-09-30/soi/outputs` |
| 最近的完整分析工作区 | `archive://2026-10-02/frames/outputs`；同时包含全94题 SEAL-0 后续分析和最新 FRAMES50 |

近期 SEAL-0 正式启动形式（仅说明接口，本次未执行）：

```bash
archive://2026-09-12/hira/forammas/.venv/bin/python \
  archive://2026-09-12/hira/work/roma_v1_adapters/run_isolated_seal0.py \
  --paper-run-config /absolute/path/to/config.json
```

当前 `forammas` 的工作树有 `.gitignore` 改动及若干未跟踪脚本、子集文件；adapter/control 层也有未提交改动。历史实验版本应依照各归档中的 commit、diff、未跟踪快照和文件哈希恢复，不能只凭当前 HEAD。

## MLflow

- 数据库：`archive://2026-09-12/hira/work/forammas_study/mlflow.db`。
- Tracking URI：`sqlite:///archive://2026-09-12/hira/work/forammas_study/mlflow.db`。
- 可执行入口：`archive://2026-09-12/hira/work/forammas_study/.venv/bin/mlflow`（已确认存在）。
- 生命周期与归档索引代码：`archive://2026-09-12/hira/work/forammas_study/mlflow_archive.py`；创建 tracking run 后运行，结束后把本地归档挂到同一个 run。
- 相关 experiments：`ROMA-Formal-Runs`、`ROMA-SEAL0-Clean-Paired-Seed42`、`ROMA-FRAMES80-BASE-V2`、`ROMA-FRAMES50-Budget-BASE-V2`。
- Artifact 目录由数据库每个 run 的 `artifact_uri` 决定。抽查的 SEAL-0 artifacts 位于 `archive://2026-09-16/wo/mlruns/1/...`；最新 FRAMES50 位于 `archive://2026-10-02/wo-2/mlruns/9/...`。不能根据数据库位置猜 artifacts 位置。

如需手动显示该数据库，可用以下启动形式；本次未启动，也未确认已有服务端口：

```bash
archive://2026-09-12/hira/work/forammas_study/.venv/bin/mlflow ui \
  --backend-store-uri sqlite:///archive://2026-09-12/hira/work/forammas_study/mlflow.db \
  --host 127.0.0.1 --port 5000
```

## SEAL-0：先读这些结果

1. [全94题三轮行为、性能与资源分析](../75cba6bcf0e9/seal0_all94_three_round_behavior_20261002.md)。H/R1/R2 共272个有效配对题目轮次、544次正常执行；86题三轮完整、6题两轮、2题一轮。每题先平均有效轮次，再让94题等权。BASE 35.64%，V2 35.46%，差−0.18个百分点；资源平均值接近，同题波动仍大。
2. 历史与剩余59题的合并准确率 (`archive://2026-10-02/frames/outputs/seal0_history_plus_remaining59_20261002.md`; archival reference, not bundled)。同33题三轮差 +5.05个百分点，而剩余完整53题三轮差−6.29个百分点；不能把子集正结果作为全体收益。不同日期、工具声明排序和模型可见路径控制影响合并解释，历史合并属于描述性结果。
3. [全94题按题等权递归分析](../6cc36b625298/comparison.md)。节点数5.087→4.759，展开节点1.493→1.257，平均最大深度0.807→0.738，到达深度3比例23.9%→18.4%。这些是结构观测，不能直接替代准确率或资源效率结论。
4. [剩余59题追加实验最终留档核查](../4323b35b7346/seal0_remaining59_final_report_20261002.md)。236次计划执行，226完成、9供应商阻断、1运行错误；226个完成答案均已原生评分。对应 study：`archive://2026-09-12/hira/work/paper_studies/seal0_remaining59_repeats2_parallel4x4_20261002T080159Z`。

历史首轮94题是 BASE 34/94、V2 35/94，8题改善、7题退步；该历史结果位于 `archive://2026-09-12/hira/work/analysis_outputs/roma-v2-vs-base-native-e2b-20260929T062249Z/summary.json`。不要把它与三轮合并结果混为一批。

## FRAMES：新旧两组结果

最新 study：`archive://2026-10-02/frames/outputs/frames50_budget_BASE_V2_20261004T132044Z`。

- [完整分析报告](../eab63228a788/report.md)：计划50题，BASE完成49、阻断1；V2完成47、阻断3；96个完成答案原生评分成功，无评分错误。双方有效配对47题：BASE 34/47=72.34%，V2 38/47=80.85%，差+8.51个百分点，8题改善、4题退步；条件bootstrap区间[-6.38,+23.40]个百分点。
- 行为观测：逻辑节点17.553→14.574，展开节点5.447→4.426，工具调用22.298→19.787；平均token244.1万→253.1万，不能把节点更少直接解释成更省token。全部极端题均保留。
- 有效配对结果 (`archive://2026-10-02/frames/outputs/frames50_budget_BASE_V2_20261004T132044Z/paired_results.md`; archival reference, not bundled) 与 全部50题状态 (`archive://2026-10-02/frames/outputs/frames50_budget_BASE_V2_20261004T132044Z/aligned_results.md`; archival reference, not bundled)。
- 这组来自80题 study 启动后的预算收缩：保留所有已启动题，未启动部分在层内按固定hash选取。是预算适应后的子集，不能视为原783题总体的无偏估计；原80题档案不能作为80题完整结果。
- 汇总 MLflow ID：`1e8196a7f4794dd7ab5aa66a455e785c`；BASE续跑 `bca6db30d5b641d38e31c0b518dd43b0`，V2续跑 `20d44bb5547a49d6ab9f5d1b8b441854`。均在数据库中记录为 FINISHED。续跑run指标仅覆盖续跑部分，全50题必须读取aggregate和完整分析。
- 留档还包括 `source_snapshot/`、脚本bundle/快照、`benchmark_snapshot/`、`config/`、`selection/`、`accounting_inputs/`、`paper_runs/`、`grading_view/`、`SHA256SUMS` 和 `analysis_report/source_sha256.json`。

旧结果：BASE 与旧111共同35题 (`archive://2026-09-30/soi/outputs/frames_BASE_111_paired35_20261001T160113Z/comparison.md`; archival reference, not bundled)。冻结100题子集前40个位置，只有35题双方完成且条件有效、记录完整、成功原生评分；BASE与111均28/35=80%，q26改善、q36退步，另外5题异常不记零。旧111不是当前V2。

## 如何沿证据追溯

标准Paper Run目录通常含 `manifest.json`、`checksums.sha256`、`runner_results.csv`、`metrics.csv`、`outputs.jsonl`、`config/`、`prompts/`、`code_state/`、`traces/` 和后续的 `grader/`。`code_state/git_state.json` 分别记录Agent、控制层、adapter、proxy版本，并配套源码/差异/环境快照。manifest关联benchmark文件hash、题目goal hash、runner/proxy hash、模型参数、开关与MLflow ID。

逐题目录为 `traces/q-####/`，包括 `result.csv`、`result.metrics.json`、`recording_manifest.json`、runner/proxy日志；其 `trace/` 内有 `llm_events.jsonl`、`tool_events.jsonl`、`tree_events.jsonl`、`run_events.jsonl`、`pre_call.jsonl`，有的批次还含raw事件和raw请求。行为分析优先读取事件流；零工具调用可能没有tool事件文件。阻断、错误和缺失必须独立保留。

当前BASE/V2两臂可能均写 `condition=BASE`，真正的组织感知开关是 `interventions.organization_awareness_v2`。V2是外部worker在LiteLLM前追加静态架构提示词，proxy只审计接收。`official-roma-v2`目录名、旧111条件名、当前V2干预均不能相互替代。

## 本次实际验证范围

读现有配置、入口代码、分析报告、批次状态与数据库，未重新验证每题评分语义。三个分析目录共11个checksum条目通过；最新FRAMES报告/结果的5个checksum条目通过；SEAL-0一个逐题目录的10个结果/记录/原生事件条目通过。抽查SEAL-0剩余59题BASE第1遍和FRAMES50 BASE续跑：本地manifest哈希与MLflow数据库记录一致，MLflow的paper_archive manifest副本与本地逐字节一致。现有报告中的全量历史校验结论属于原报告记录，本次没有重新遍历全部历史归档。
