# MMLU-Pro Physics 最终离线评分协议

适用批次：20261006T090617775637Z_mmlu_pro_physics_n100_seed42_tb8192_mc16384_gw16x16。相同 seed=42 的固定 100 题 Physics test 子集；不是完整 MMLU-Pro，也不是官方 few-shot 单模型推理复现。

评分读取封存子运行的 native_results.csv 中最终 Answer（0 基整数），按未经重排的官方 options 映射到 A–J；以官方 gold letter 精确相等判对。不从评估中间节点的文字或推理过程重新提取最终答案，不调用 LLM grader。官方 evaluate_from_api.py 固定到 f418b116db00b065c2aea046518d8fcf74d39872，保留完整源码、许可证、下载 URL 和 SHA256。通过 AST 仅加载原样的 update_result 和 save_summary 两个计分函数，避免执行官方模型推理入口或加载额外模型 SDK。

官方兼容 physics_result.json 的 pred 来源明确为原生结构化整数答案映射；不伪造 model_outputs 文字。只把有效完成答案送入官方函数，故不触发其缺失 pred 的随机猜测兜底。失败、超时、主动中断、未运行、缺失答案保留状态和空分数，不能充当实际错误答案。每组报告正确数/有效评分数、有效覆盖/100、正确数/固定100题（correct-answer yield）；并报告双方有效的配对结果和 BASE→V2 转移。后者是配对可见结果，不覆盖单侧缺失题。

启动前验证同一采样 manifest、100 个题号集合、选项数、官方 gold letter/index、子目录身份、原生 CSV 的 Problem ID/gold、父结果和子结果一致。只有所有题进入终态、200 个子运行和父批次封存校验通过、源变更为空、父 MLflow 索引完成才允许最终评分。评分为独立离线 Run，以原推理父 run 为 parent，保存脚本快照、官方源码、完整样本快照、父输入快照、原生 CSV 快照、201 个归档校验引用、逐题评分、官方格式结果和汇总，并封存校验值与 MLflow 索引副本。评分不改原批次、Agent、提示词、样本、环境，不发模型 API，不自动重跑失败题。

原运行于 2026-10-06 18:53 北京时间将 V2 任务上限从16调整到32，实际峰值29；并发阶段变更保留在原批次 runtime_scheduler/amendment.json，时延分析须说明此事。

最终命令（等待终态后调用，未封存返回75，不生成评分结果）：

```sh
.venv/bin/python .local/evaluation_preparations/20261006T090617775637Z_mmlu_pro_exact_match/score.py --final
```

最终输出：.local/evaluations/20261006T090617775637Z_mmlu_pro_exact_match/。拒绝覆盖已有结果；成功封存后重复调用只核验已有记录。
