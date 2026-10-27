# Report catalogue / 报告目录

[Repository guide](../README.md) · [Run archives](runs.md) · [Version relations](version_relations.md)

Historical index: 260 reports; 19 selected report bodies are packaged here. The other 241 entries retain metadata and original archive references only. The original index was curated on 2026-10-07; this packaging does not re-audit every historical conclusion. Use the current paper and its evidence for principal results.

## Selected reading / 推荐阅读

| Report | Role in this repository | Purpose |
|---|---|---|
| [ROMA 与 TalkHier：分角色、分层级、分 benchmark 的组织信息可见范围审计](../reports/b9088a9eadd1/report.md) | primary evidence or implementation audit | 组织知情权：ROMA vs TalkHier，分角色与 benchmark |
| [TalkHier：评分、组织行为与 token 的配对审计](../reports/393455e5fe5e/report.md) | primary evidence or implementation audit | TalkHier：完整评分、工具行为、token、异常口径 |
| [TalkHier MMLU-Pro Physics 最终官方精确匹配评分](../reports/7070efeaf6bc/score_summary.json) | primary evidence or implementation audit | 最终分数的原始汇总入口 |
| [TalkHier College Physics 50题最终原生整数匹配评分](../reports/fc86bcd81eab/score_summary.json) | historical context | 大学物理50题的最终评分入口 |
| [SEAL-0 全94题：三轮合并后的性能、成本分布与重复波动](../reports/75cba6bcf0e9/seal0_all94_three_round_behavior_20261002.md) | primary evidence or implementation audit | ROMA SEAL-0 全94题三轮：性能、token与重复波动 |
| [ROMA SEAL-0 历史首轮94题原生评分汇总](../reports/9d89994a2e20/summary.json) | historical context | 历史首轮的原始汇总入口 |
| [SEAL-0递归展开：按题目等权的主口径](../reports/6cc36b625298/comparison.md) | primary evidence or implementation audit | ROMA 全94题按题等权的递归与深度 |
| [FRAMES50 BASE / V2 完整报告](../reports/eab63228a788/report.md) | primary evidence or implementation audit | ROMA FRAMES50：完整配对评分、行为、资源 |
| [SEAL-0 剩余59题重复实验最终留档核查](../reports/4323b35b7346/seal0_remaining59_final_report_20261002.md) | historical context | ROMA 剩余59题追加实验：最终留档与评分核查 |
| [组织架构知情：重复实验的稳定性与论文方向](../reports/1827bc7ee270/research_direction.md) | historical context | 固定15题重复实验：稳定性与论文方向 |
| [ROMA分解树、完整组织DAG与outcome分析](../reports/1e49bd875fe7/report.md) | supporting analysis or correction | ROMA 分解树、组织DAG与 outcome |
| [Outcome-blind 执行树状态分析](../reports/02ddd862a401/report_reviewed.md) | supporting analysis or correction | 树形状态分组：审阅版入口 |
| [原生 MAB 评分事后分析](../reports/2670fba6ff59/report.md) | supporting analysis or correction | MultiAgentBench 原生协作评分事后分析 |
| [根Atomizer输出与协作过程：完成审计](../reports/9da5454aa702/findings.md) | supporting analysis or correction | ROMA 工具去重与根Atomizer过程审计 |
| [旧111组织知情开关与当前V2：实现审计及同轮BASE配对分析](../reports/a89d260dda7e/report.md) | historical context | 辨别早期111和当前V2的开关与注入 |
| [TalkHier 全局组织、必经关系与调度审计](../reports/8efe7e9c686b/FLOW_AUDIT.md) | primary evidence or implementation audit | TalkHier：必经/可选路径、串行与反馈关系 |
| [FRAMES 150题与前5题预算子集](../reports/8cf5ab7ebfff/README.md) | excluded later experiment | FRAMES150固定抽样与前5题索引 |
| [用户主动中断留档](../reports/5a1c2c3aee68/final_report.md) | excluded later experiment | ROMA五题预算Pilot：主动中断收尾 |
| [ROMA、SEAL-0、FRAMES 与实验留档位置索引](../reports/5edeb7128984/ROMA_benchmark_workspace_index_20261005.md) | historical context | ROMA原有目录、Paper Run和MLflow说明 |

## All indexed reports / 全部条目

Metadata-only entries below are intentionally plain text. Search by ID, benchmark or title in this document or in `catalog.json`.

| ID | Report | Benchmark | Original status |
|---|---|---|---|
| `b9088a9eadd1` | [ROMA 与 TalkHier：分角色、分层级、分 benchmark 的组织信息可见范围审计](../reports/b9088a9eadd1/report.md) | 跨 benchmark | 已完成的上下文审计 |
| `393455e5fe5e` | [TalkHier：评分、组织行为与 token 的配对审计](../reports/393455e5fe5e/report.md) | MMLU-Pro Physics, MMLU College Physics | 已完成的综合分析 |
| `7070efeaf6bc` | [TalkHier MMLU-Pro Physics 最终官方精确匹配评分](../reports/7070efeaf6bc/score_summary.json) | MMLU-Pro Physics | 最终评分已封存 |
| `fc86bcd81eab` | [TalkHier College Physics 50题最终原生整数匹配评分](../reports/fc86bcd81eab/score_summary.json) | MMLU College Physics | 最终时点评分；provisional=false |
| `75cba6bcf0e9` | [SEAL-0 全94题：三轮合并后的性能、成本分布与重复波动](../reports/75cba6bcf0e9/seal0_all94_three_round_behavior_20261002.md) | SEAL-0 | 指定 H/R1/R2 的综合分析 |
| `9d89994a2e20` | [ROMA SEAL-0 历史首轮94题原生评分汇总](../reports/9d89994a2e20/summary.json) | SEAL-0 | 历史单轮结果，不是三轮合并 |
| `6cc36b625298` | [SEAL-0递归展开：按题目等权的主口径](../reports/6cc36b625298/comparison.md) | SEAL-0 | 主递归统计入口 |
| `eab63228a788` | [FRAMES50 BASE / V2 完整报告](../reports/eab63228a788/report.md) | FRAMES | 已完成的综合分析 |
| `4323b35b7346` | [SEAL-0 剩余59题重复实验最终留档核查](../reports/4323b35b7346/seal0_remaining59_final_report_20261002.md) | SEAL-0 | 最终收尾报告 |
| `1827bc7ee270` | [组织架构知情：重复实验的稳定性与论文方向](../reports/1827bc7ee270/research_direction.md) | SEAL-0 | 机制与稳定性分析 |
| `1e49bd875fe7` | [ROMA分解树、完整组织DAG与outcome分析](../reports/1e49bd875fe7/report.md) | SEAL-0, FRAMES | 探索性结构分析 |
| `02ddd862a401` | [Outcome-blind 执行树状态分析](../reports/02ddd862a401/report_reviewed.md) | SEAL-0, FRAMES | 审阅版，探索性分析 |
| `2670fba6ff59` | [原生 MAB 评分事后分析](../reports/2670fba6ff59/report.md) | SEAL-0, FRAMES | 探索性协作评分分析 |
| `9da5454aa702` | [根Atomizer输出与协作过程：完成审计](../reports/9da5454aa702/findings.md) | SEAL-0 | 工具统计更正后的推荐入口 |
| `a89d260dda7e` | [旧111组织知情开关与当前V2：实现审计及同轮BASE配对分析](../reports/a89d260dda7e/report.md) | SEAL-0, FRAMES | 条件实现审计 |
| `8efe7e9c686b` | [TalkHier 全局组织、必经关系与调度审计](../reports/8efe7e9c686b/FLOW_AUDIT.md) | MMLU 多领域 | 已准备并验证的协议审计 |
| `8cf5ab7ebfff` | [FRAMES 150题与前5题预算子集](../reports/8cf5ab7ebfff/README.md) | FRAMES | 数据与顺序已冻结；不是150题实验结果 |
| `5a1c2c3aee68` | [用户主动中断留档](../reports/5a1c2c3aee68/final_report.md) | FRAMES | 用户主动中断，非完整五题结果 |
| `5edeb7128984` | [ROMA、SEAL-0、FRAMES 与实验留档位置索引](../reports/5edeb7128984/ROMA_benchmark_workspace_index_20261005.md) | SEAL-0, FRAMES | 2026-10-05历史位置索引 |
| `7159e0ffbdfb` | FRAMES评分历史索引 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `6ba4f0dde1db` | ROMA FRAMES 五题预算与吞吐 Pilot (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `0971a24a6a6b` | FRAMES 150题与前5题预算子集 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `7b25b8be2d83` | AAMAS 投稿定位与有限预算下的证据优先级 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `284ea5c47233` | FRAMES50 budget-constrained continuation (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `c59451d3dedc` | FRAMES50 全部计划题状态 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `35f5e5c47bfc` | 按官方题号的完整逐题结果 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `7186db02ba28` | Token记录补充说明 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `7a3395dfeadb` | FRAMES50 有效配对主结果 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `4ad2eb54207c` | 固定50题预算子集 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `61972dfd6ad3` | FRAMES80 BASE/V2 paper run (metadata only) | FRAMES | 原80题计划与启动阶段 |
| `5ca43d3b8e14` | ROMA 后续运行的中性目录修正 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `dc8129eaf866` | 第二个 Agent：价值、候选与预算决策 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `6e0fd4efb1fd` | SEAL-0 paired V2 vs BASE trace analysis (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `2989dd6dc609` | SEAL-0 paired V2 vs BASE trace analysis (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `18f7a9ef70e6` | SEAL-0 paired V2 vs BASE trace analysis (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `47e0c8ff8e43` | Forammas study control and provenance layer (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `acf931140d74` | 历史94题与随机15题重复的正确率差异 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e43c13b16a50` | 固定15题原生正确率复核（2026-10-01） (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `540b71201fd7` | 正确率与对错翻转复核 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2ef773b688ab` | 原生正确概率与持续成功：数学模型及现有数据拟合 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a9a52bc65f5e` | 94题执行指标重新分析：方向性与同条件重跑参照 (metadata only) | 跨 benchmark / 待细分 | 历史分析：工具计数须结合更正 |
| `89bc4be9d267` | chat_q004 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `50bf58ee0d11` | chat_q005 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2ac44927acf5` | chat_q013 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `5449d325721c` | chat_q015 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2b559f383611` | chat_q016 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `bd56fb1a862f` | chat_q019 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `fe7294188a28` | chat_q030 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `6a44336464e7` | chat_q031 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8c22eb7e586f` | chat_q034 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8e9f7ee8a5af` | chat_q039 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e98f0c4ba633` | chat_q063 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `4c9a2873f097` | chat_q081 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2785c6796897` | chat_q087 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `28cd8c47df5a` | chat_q093 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `5eb41ea09512` | chat_q100 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `b7a0f52807a0` | chat_tables (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `156203ec58fb` | 同条件重跑参照：描述性核对 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `fc9fe08cfe8b` | raw_per_question (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `5df8e8db84c7` | raw_q004 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `59afdd20bea8` | raw_q005 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `1ca646bb18b0` | raw_q013 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d90a1b2fa0e1` | raw_q015 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a9f05f8511c1` | raw_q016 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `123f6ac7512a` | raw_q019 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `c85e1b8d3ab5` | raw_q030 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `9db50c769365` | raw_q031 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a316b7b20e6e` | raw_q034 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `42b89cb6cc3a` | raw_q039 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `9bc9231a0b9d` | raw_q063 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8f1c9f6619d5` | raw_q081 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `c9812c04cd16` | raw_q087 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a3f17d0a40e2` | raw_q093 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `bd889f8837dd` | raw_q100 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `819460a7ab56` | 固定15题、BASE/V2各四遍：重复波动与任务依赖效应 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e839a3249e71` | 组织知情与协作过程审计：操作定义 v1 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f04156c95b01` | SEAL-0 固定15题：两次追加重复实验与原生评分最终结果 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `4a554dfb2075` | SEAL-0：94题 × 三轮的 BASE / V2 实际深度 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `d8c3eb067472` | BASE / V2 整体递归展开：节点与叶节点加权比较 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `930b0d4a5062` | 新15题与历史94题逐题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `55d6db4747b6` | 新15题与历史94题逐题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `dde1df5a9dff` | seed43 与 seed44 正确率合并及逐题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `62b606709db8` | seed43 与 seed44 正确率合并及逐题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `6b59e3c53b84` | 五批 SEAL-0 trace 检查 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `80b27a6165bf` | 全94题：把观测差额放回重复噪声背景 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `ca469686755f` | 全94题：用百分比、比率和百分点解释条件差异 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `ef46e1988a17` | 全94题：极端值影响与稳健性检查 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `57a642962968` | 全94题：工具调用均值、覆盖、强度与噪声背景 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `4db399485b1c` | SEAL-0：预算限制下的论文结论与停止点 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `dc1845263b43` | SEAL-0：历史第一轮与剩余59题两次新重复合并 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `c88529075846` | 平均边际价值、题目效应差异与运行随机性 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `2366698e4fdf` | SEAL-0 的得分波动：现有证据与下一轮设计 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `a9cdd354db74` | SEAL-0 逐题得分变化：同条件波动与跨条件差值 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `88d3740e8eb0` | SEAL-0 剩余题目的两条件、两次新增重复 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `7c292a777ad4` | SEAL-0：V2 的翻转与 token 变化是否超出重复波动？ (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `7d580fa0417d` | SEAL-0：历史＋重复实验的 token、工具行为与翻转题 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `29b286c5bddf` | ROMA → MultiAgentBench：仅离线格式化 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `71ed453f25a0` | ROMA → 当前官方 MultiAgentBench：仅离线格式化 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f16e16cfd8ac` | MultiAgentBench 官方原版核验 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `b2e27dc3eda6` | BASE深度分层与V2收益：探索分析 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f759ee0642ef` | 统一为V2−BASE的逐题PLS留出预测 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e50b1c125a85` | DAG增强PCA／PLS与统一差值符号 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `ebe9ec8a8026` | 逐题主成分与原生performance (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `0b494a5da934` | 行为变化量PCA：先行为、后performance (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8c64c74a9e05` | PLS 题级观测与留出预测 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2c39eabe9a5b` | 以 performance 差值为目标的 PLS 监督分析 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8ce865183571` | Cross-fitted深度收益：题目影响检查 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `304f3d57238f` | 每题三轮交叉分组与原生结果 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `6536212a7fa2` | Cross-fitted BASE depth propensity 与V2答题收益 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e6edeee17790` | 每题三轮交叉分组与原生结果 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `ed0c2c365a29` | Cross-fitted BASE depth propensity 与V2答题收益 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3136b15a9a06` | 逐题BASE／V2依赖结构核对 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e1172caec8b5` | ROMA DAG依赖审计：四项计数 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `56d0ed600f2d` | 同题分解树与完整DAG逐题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `81f79b6eceeb` | 全节点与仅E节点：深度变化对应BASE−V2正确率差 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `df4bc8b22d2f` | BASE/V2两侧实际深度3分组的正确率 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f96f36b77025` | Agent 轨迹无损引用与增量表示：小样本可行性测量 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `1d32694044ea` | 调用重复留档核查：只读、未评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `1a376ca209f0` | 全量 BASE/V2 原生评分对照 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `b235e59d3650` | 全量 BASE/V2 原生评分对照 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `7a4d4f428e04` | 按题号、批次和轮次对齐的 BASE/V2 原生评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `06f759a0b959` | 按题号、批次和轮次对齐的 BASE/V2 原生评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `0d541604a619` | 按题号、批次和轮次对齐的 BASE/V2 原生评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `1f91cb889d46` | 按题号、批次和轮次对齐的 BASE/V2 原生评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `35cd2b0ece1e` | MultiAgentBench 完整输入覆盖率审计 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `fda5e4bfc9d2` | MultiAgentBench 完整输入覆盖率审计 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `c3e7c6457487` | MARBLE 原生评分：递归深度 2/3 配对试跑 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d3a4ce3afa2e` | 仅供评分器使用：实际深度 2–3 剩余评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f7262d6521d7` | 实际深度 2–3 剩余原生评分记录 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d4139beed892` | 仅供评分器使用：扁平块分层试跑 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d2930b7ff631` | 原生 MAB 扁平输入：深度 0–3 各四组试跑 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `9888a22dc102` | 仅供评分器使用：冻结清单评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3f601d60462e` | 深层评分的缺失对侧补评 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `7271a4f401cb` | 仅供评分器使用：冻结清单评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `dc241e2bb348` | 全量剩余可评轨迹的原生评分 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `4d815a890f5e` | ROMA → MultiAgentBench：仅离线格式化 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `32fa88a5d791` | 一个完整 ROMA 根任务的 BASE/V2 输入样例 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a891ae237df0` | 所有至少一个维度变化的配对 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e565c926abfb` | 主要发现与解释边界 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e1b1346c5b78` | MARBLE 原生评分：五题 BASE/V2 试跑 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `4890aa350022` | 剩余可评轨迹与评分 token 清单 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `a45512fbc139` | 原生评分运行与留档入口 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `9e679ae1e034` | 仅供评分器使用：扁平原文块副本 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `223b9c8b054f` | 扁平评分输入：全量离线覆盖率 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `100de5db6152` | 静态文本哈希引用副本：离线 token 与覆盖率比较 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f7d5240cc8f5` | 按题对齐 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `298b69061fcf` | 节点加权平均深度与原生正确率 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `5d58a046931e` | PCA低方差轴的事后核查 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3e8e592971be` | 86题的三轮平均深度与平均配对收益 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `413baddbe4b0` | 每题三轮平均BASE深度与平均V2收益 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3150ea977f05` | SEAL-0 / FRAMES：协作评分、正确率与树变化的关联 (metadata only) | SEAL-0, FRAMES | 同题目标题的较早分析版本；版本关系待核验 |
| `7a2395cb89ec` | SEAL-0 / FRAMES：协作评分、正确率与树变化的关联 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `c27262491bf7` | SEAL-0逐题变化（共同有效重复先合并） (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `b80aa9207c06` | SEAL-0 / FRAMES：协作评分、正确率与树变化的关联 (metadata only) | SEAL-0, FRAMES | 同题目标题的较晚分析版本；版本关系待核验 |
| `6bcd0519738f` | 按官方题号对齐：树距离与外部信号 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `fd550472d63c` | 执行树形态：结构优先，外部结果随后关联 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f866767e12c8` | 执行树分析：结果概览 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e28e8305fca0` | 按题对齐的样本外预测 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `8f5d6e7a7d4b` | 执行树形态能否预测改善／不变／恶化 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `4b147883a3d0` | 题号对齐：树形状态与原生结果 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `859f5e57fc02` | Outcome-blind 执行树状态分析 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `67503194b127` | 树形状态：主要发现 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `09fbeff74c98` | SEAL-0 0–110 BASE / OFF011 distributional analysis (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `4c97d3119aab` | SEAL-0 0–110 BASE / OFF011 trace comparison (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `a01db52f6b97` | 四条件 common94：111 的计算增量是否由冗余行为解释？ (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `64b246aab93f` | 四条件 common94：111 的计算增量是否由冗余行为解释？ (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d3f4e82efca9` | FRAMES BASE vs 111 trace statistics (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `69f7e9afcffc` | FRAMES BASE vs 111：完整分布与长尾报告 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `c54baf5655d4` | ROMA decomposition/delegation loss audit on FRAMES (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `60f9ef7d6f60` | ROMA decomposition/delegation loss audit on FRAMES (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `f122602fae3c` | ROMA decomposition/delegation loss audit on FRAMES (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `db58ccbc1813` | ROMA decomposition/delegation loss audit on FRAMES (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `c6b700cc23b3` | FRAMES four-condition factorial and paired bootstrap (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `0d20a8e533f8` | FRAMES four-condition factorial and paired bootstrap (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `3eef970d6978` | FRAMES four-condition factorial and paired bootstrap (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `74c2a0244259` | FRAMES grader snapshot (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `2c42c78528fe` | Four-condition paired interaction: 111 vs 011 against BASE vs OFF011 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `ef0f13b1886e` | Four-condition paired interaction: 111 vs 011 against BASE vs OFF011 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `6fe0677a1eff` | 2x2 四条件论文摘要：意图可见性 × 组织架构知情 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `5ce6d79a3ed6` | 2x2 四条件论文摘要：意图可见性 × 组织架构知情 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `2c7df65e4009` | ROMA context-visibility experiments: paper ledger (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `426779278e7a` | Performance difference-in-differences bootstrap (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f7fa0a634c32` | ROMA SEAL-0 测评与 Agent 内部调用报告整理 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `281e7457ace6` | SEAL-0 65–110 intent-off/max3 轨迹暴涨审计 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `303de7403429` | All-eight-condition common-question alignment (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `53165959486e` | All-eight-condition common-question alignment (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `6e312dc61a2b` | SEAL-0 all context-visibility conditions: aligned inventory (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `c1cd744e9990` | SEAL-0 all context-visibility conditions: aligned inventory (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `cee7ced7941c` | SEAL-0 clean trace comparison (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `de2c265235a5` | SEAL-0 ROMA decomposition/delegation audit (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `90fa4b11b83c` | SEAL-0 ROMA decomposition/delegation audit (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `383de373ccf3` | SEAL-0 ROMA decomposition/delegation audit (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `b3f3ccba116d` | SEAL-0 Executor second-order 2x2 analysis (10 completed questions) (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `c07ce5b47da3` | SEAL-0 Executor second-order smoke: paired 2x2 analysis (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `cd2ecb0aae69` | SEAL-0 and FRAMES metadata-stratified interaction analysis (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `6c48402c8f50` | SEAL-0 and FRAMES metadata-stratified interaction analysis (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `e811db1a0125` | SEAL-0 global four-cell strict common-question alignment (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `d383831a5a67` | SEAL-0 layered-intent smoke: full statistics (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `c874d4c94c5c` | SEAL-0 layered intent vs original 111 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `7c30ce6e056e` | SEAL-0 layered intent vs original 111: paired 10-question percentage comparison (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `2f14823a8bec` | SEAL-0 per-question alignment across all eight available conditions (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `a5d22d8574d1` | SEAL-0 second-order common-six per-question trace metrics (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `8a001f55d34f` | SEAL-0 second-order common-seven per-question trace metrics (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `037a9e046109` | ROMA context-visibility experiments：FRAME / SEAL-0 结果与快照审计 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `54ace7890c7e` | ROMA 组织结构可见性：BASE–111 证据、撞题审查与论文方向 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `e1312bb70ca2` | FRAMES：BASE与旧111共同35题的原生评分对齐 (metadata only) | FRAMES | 早期BASE/111历史结果 |
| `c084f5e0e3e4` | FRAMES共同35题：BASE／旧111实际递归深度 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `0f8028647129` | 三批题合并：seed42＋seed43＋seed44 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `dcbdaa1c86b5` | TalkHier 批次留档：20261005T153505526128Z_college_physics_n50_seed42 (metadata only) | MMLU College Physics | manifest 留档状态：interrupted |
| `7dabfa68fc1a` | TalkHier 批次留档：20261006T045520595135Z_college_physics_n50_seed42_tb8192_mc16384 (metadata only) | MMLU College Physics | manifest 留档状态：completed_with_errors |
| `1343b39bb6af` | TalkHier 批次留档：20261006T090617775637Z_mmlu_pro_physics_n100_seed42_tb8192_mc16384_gw16x16 (metadata only) | MMLU-Pro Physics | manifest 留档状态：completed_with_errors |
| `0fe9ad73dee7` | MMLU-Pro Physics 最终离线评分协议 (metadata only) | MMLU-Pro Physics | 已存在；版本与最终性以原文为准 |
| `0b9fb3844075` | TalkHier MMLU-Pro Physics 暂定评分 20261006T090617775637Z_mmlu_pro_exact_match_interim_20261006T113715670482Z (metadata only) | MMLU-Pro Physics | 暂定时点快照 |
| `21fbda6c4bb6` | MMLU-Pro Physics 暂定评分 (metadata only) | MMLU-Pro Physics | 暂定评分：保留作过程快照 |
| `745cae5d8893` | TalkHier College Physics 暂定评分 20261006T065124071262Z (metadata only) | 跨 benchmark / 待细分 | 暂定时点快照 |
| `9f66330a3bf3` | TalkHier College Physics 暂定评分 20261006T065150787806Z (metadata only) | 跨 benchmark / 待细分 | 暂定时点快照 |
| `5b19d5a333a0` | TalkHier native college-physics scoring (metadata only) | MMLU College Physics | 已存在；版本与最终性以原文为准 |
| `3d0d4e18a772` | MMLU-Pro Physics: fixed 100-question sample (metadata only) | MMLU-Pro Physics | 已存在；版本与最终性以原文为准 |
| `0fad1bc92cac` | 自动留底与 MLflow Run (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `fee642ae3850` | LangChain 直连 API 与本地原生事件轨迹 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f7e19f42185f` | Frozen 50-question college-physics run (metadata only) | MMLU College Physics | 已存在；版本与最终性以原文为准 |
| `985c50dee4df` | TalkHier shared inference gateway (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `1f5a806727c1` | seed44 固定10题补充抽样 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `4b4f9c6c7345` | 第二组固定15题抽样留底 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `221ad4924ee5` | Seed43 新15题原生正确率临时快照 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `21432202aac6` | seed43 实验与评分最终核验 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `a1c666a5744a` | seed44原四批与唯一q2补跑最终核验 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `3b745f7a9306` | ROMA 模型预算与共享网关准备 (metadata only) | 跨 benchmark / 待细分 | 模型边界准备与离线验证，非答题结果 |
| `8aad0cf22244` | ROMA 并发与限流等待核验 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `34faf9739de8` | sampling_clarification_20261001 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `764d638fd390` | FRAMES 分层抽样脚本核查 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `ec8848adbc2a` | sampling_clarification_20261001 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3646b85a829c` | SEAL-0 固定 15 题：BASE、V2 各追加两遍 (metadata only) | SEAL-0 | 已存在；版本与最终性以原文为准 |
| `c222623938e2` | FRAMES 80题索引入口 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `8d6575d571a2` | FRAMES 80题：索引与论文抽样核验 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `a74cfe7c2636` | FRAMES 80题：索引与论文抽样核验 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `6dbe27315253` | frames80_paper_design_20261002 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `dce7a0e14f0b` | FRAMES 80／100题抽样与重复方案 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `27522a3da951` | SEAL-0 59 题 BASE/V2 新增两遍：启动记录 (metadata only) | SEAL-0, FRAMES | 已存在；版本与最终性以原文为准 |
| `574fee98b369` | AAMAS 2027 abstract draft (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `f07c4cef53fa` | AAMAS 2027: immediate submission preparation (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `01136287fd91` | ROMA 的 BASE 与 111：上游源码、归档哈希和实际请求核查 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `22fae12c1b33` | 2026-10-01工具调用统计更正 (metadata only) | 跨 benchmark / 待细分 | 明确更正说明 |
| `709316e9d648` | ROMA BASE / V2 信息暴露审计 (metadata only) | FRAMES | 已存在；版本与最终性以原文为准 |
| `2e60afabed39` | TalkHier 实际V2注入核验 (metadata only) | 跨 benchmark / 待细分 | 结构/请求审计，不是新推理实验 |
| `9b108660be1a` | TalkHier 官方实现对照核验 (metadata only) | 跨 benchmark / 待细分 | 结构/请求审计，不是新推理实验 |
| `967f3e6f2d8a` | 第二系统备用候选核验：局部组织已知后，全局静态组织信息的边际价值 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `24da1f24a3f8` | 局部组织信息 → 全局静态组织拓扑：候选可见上下文审计 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `55b04010f9b8` | ROMA 静态组织说明干预：第二系统筛选与复现审计 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `6a43536c9d0e` | TalkHier 原生组织说明复原与 BASE 可见性审计 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `261a8f411d2e` | 已有 ROMA V2 的来源与内容核对 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `3ce97390b5d8` | 与当前 ROMA V2 对齐的 TalkHier 候选说明 (metadata only) | 跨 benchmark / 待细分 | 候选说明阶段 |
| `5516fe272007` | TalkHier BASE/V2 (metadata only) | 跨 benchmark / 待细分 | 已存在；版本与最终性以原文为准 |
| `d09ce028dad9` | TalkHier 20261005T153505526128Z_10m / latest (metadata only) | 跨 benchmark / 待细分 | 时点观测，非独立实验结果 |
| `69a7b0aecac4` | TalkHier 20261006T045520595135Z_5m / final_archive_verification (metadata only) | 跨 benchmark / 待细分 | 时点观测，非独立实验结果 |
| `44dd3a165249` | TalkHier 20261006T045520595135Z_5m / latest (metadata only) | 跨 benchmark / 待细分 | 时点观测，非独立实验结果 |
| `c1230878e6c8` | TalkHier 20261006T090617775637Z_mmlu_pro_5m / final_archive_mlflow_verification (metadata only) | MMLU-Pro Physics | 时点观测，非独立实验结果 |
| `53ed57343914` | TalkHier 20261006T090617775637Z_mmlu_pro_5m / final_observation (metadata only) | MMLU-Pro Physics | 时点观测，非独立实验结果 |
| `24cacf43408c` | TalkHier 20261006T090617775637Z_mmlu_pro_5m / final_versus_interim (metadata only) | MMLU-Pro Physics | 时点观测，非独立实验结果 |
| `f77b913d247b` | TalkHier 20261006T090617775637Z_mmlu_pro_5m / latest (metadata only) | MMLU-Pro Physics | 时点观测，非独立实验结果 |
