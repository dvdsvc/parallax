# Parallax

**研究组织信息可见性如何影响层级多智能体系统。**

**论文状态：AAMAS 2027 — Under Review（审稿中）。**

[English](README.md) · **简体中文**

[论文 PDF](paper/organizational_visibility_preprint.pdf) · [研究方法](docs/methods.md) · [结果与口径](docs/results.md) · [离线复核](docs/reproduction.md) · [报告索引](index/reports.md) · [运行归档](index/runs.md)

## 研究问题

系统代码实现了层级组织，不等于每次模型调用都能看到完整组织。给模型补充现有组织的角色、关系和信息流，是否有助于它更有效地使用这个组织？实验比较原生输入 BASE 与增加静态说明的 ORG-DESC（归档标签为 V2），同一对照内保留原生工具、角色契约、路由和执行接口。

ROMA 在递归任务的不同深度复用 Atomizer、Planner、Executor、Aggregator；TalkHier Physics 则采用固定的六角色组织。研究分别审计两者实际输入中的信息边界，再考察执行行为、任务收益、计算投入、重复可靠性和外部协作评分。干预也会澄清或重复已有局部信息，因此结论对应整段组织说明的边际作用。

## 论文主要结果

以下内容摘编自论文正文，集中展示组织信息可见性对执行行为、任务表现和计算投入的影响。实验在各自原生框架内比较 BASE 与 ORG-DESC，模型配置在同一配对实验内保持一致。

### 执行行为：减少递归展开，或增加角色内部工作

ROMA 在两个任务中都减少了递归展开：SEAL-0 的平均展开任务数下降 **15.80%**，FRAMES 下降 **18.75%**。在 FRAMES 中，平均搜索调用也从 21.06 降至 18.32，47 个配对问题在两种条件下仍全部使用搜索。组织说明改变了系统使用既有递归机制的方式。

TalkHier 的角色层级保持固定，变化主要发生在专家参与和角色内部计算。数学专家参与的问题从 **74/94 增至 94/94**；物理专家的总访问次数从 135 降至 120，正常返回模型调用却从 390 增至 653，平均每次访问调用数从 2.89 增至 5.44。角色被调用的次数与角色内部完成的工作量需要分别观察。

| 系统与任务 | 指标（每题均值） | BASE | ORG-DESC | 相对变化 |
|---|---|---:|---:|---:|
| ROMA / SEAL-0 | 展开任务数 | 1.49 | 1.26 | −15.80% |
| ROMA / FRAMES | 展开任务数 | 5.45 | 4.43 | −18.75% |
| ROMA / SEAL-0 | 记录总 token | 894,741 | 882,762 | −1.34% |
| ROMA / FRAMES | 记录总 token | 2,441,302 | 2,530,584 | +3.66% |
| TalkHier / Physics | 正常返回模型调用 | 22.10 | 29.73 | +34.57% |
| TalkHier / Physics | 正常返回 token | 171,689 | 283,212 | +64.96% |

相对变化按未四舍五入的均值计算。ROMA 使用归档中的记录总量，TalkHier 使用正常返回调用的统计量；比较在各自系统内进行。

### 任务表现：行为变化与任务收益并不同步

| 论文主面板 | BASE | ORG-DESC | 差值（百分点） | 配对 95% 区间（百分点） |
|---|---:|---:|---:|---:|
| ROMA / SEAL-0：94 题、272 个配对题目轮次 | 35.64% | 35.46% | −0.18 | [−6.38, +5.67] |
| ROMA / FRAMES：计划 50 题、有效配对 47 题 | 34/47（72.34%） | 38/47（80.85%） | +8.51 | [−6.38, +23.40] |
| TalkHier / MMLU-Pro Physics：计划 100 题、有效配对 94 题 | 88/94（93.62%） | 90/94（95.74%） | +2.13 | [0.00, +5.32] |

SEAL-0 的平均任务表现基本持平；FRAMES 中有 8 题由错转对、4 题由对转错，对应 +8.51 个百分点的估计增量，其区间跨零。TalkHier 多答对 2 题，同时正常返回 token 增加约 65%。递归展开减少也没有直接转化为更低的 token 使用：FRAMES 的展开任务更少，总 token 仍略有增加。

SEAL-0 在每题内部平均有效配对轮次，再使题目等权；区间使用题目层面的配对 bootstrap。失败、阻断与缺失保留原状态，主表采用共同有效配对记录。

### 重复成功与研究结论

在具有完整三轮配对记录的 86 道 SEAL-0 题目中，至少成功一次的题目数为 **48 → 46**，三轮全部成功均为 **18**。外部规划与通信评分的均值也变化较小。

论文的主要发现是：**更完整的组织信息能够改变智能体如何参与协作，其任务收益与计算代价取决于具体系统和任务。** ROMA 更少使用递归委派，TalkHier 则扩大专家参与、增加角色内部工作。组织的实现方式与智能体实际看到的组织信息，是两个需要共同考虑的设计维度。

数据对应论文正文的执行行为表、任务表现表及相关分析段落。[论文 PDF](paper/organizational_visibility_preprint.pdf) · [完整结果与统计口径](docs/results.md) · [论文证据](paper_evidence/data)

## 研究工作与代码归属

本研究完成组织可见范围审计、外部干预与输入校验、配对实验留档，以及任务树、角色调用和题目层面的结果分析。ROMA、TalkHier 的原生框架及第三方评分方法保留上游归属。

| 研究环节 | 核心入口 |
|---|---|
| 原生模型输入与组织边界 | [架构审计](paper_evidence/architecture_audit/README.md)、[论断与代码映射](paper_evidence/architecture_audit/claim_code_map.json) |
| 全局组织说明设计 | [ROMA 说明](experiments/prompts/roma_global_description.txt)、[TalkHier Physics 说明](experiments/prompts/talkhier_physics_global_description.txt) |
| ROMA 注入与请求校验 | [上下文桥接](experiments/sources/roma/adapters/current_node_context.py)、[代理审计](experiments/sources/roma/proxy/custom_hook.py)、[控制层](experiments/sources/roma/controls/README.md) |
| TalkHier 外部适配和原生流程保留 | [适配器](experiments/sources/talkhier/repro/org_v2/adapter.py)、[运行入口](experiments/sources/talkhier/repro/run_mmlu.py) |
| 配置、抽样、评估与复核 | [配置](experiments/configs)、[样本](experiments/samples)、[已有主表复算](experiments/analysis/reproduce_tables.py) |
| 树结构与结构—结果分析 | [方法快照](paper_evidence/method_sources)、[证据索引](paper_evidence/evidence_ledger.md) |

个人研究贡献与上游实现的边界、归档 commit 及权属待核项见[来源说明](docs/provenance.md)。

## 离线复核

Python 3.12+ 与标准库即可，不需要模型密钥，不执行新推理或评分：

```sh
uv run --offline --no-project --python python3.12 scripts/reproduce_paper.py
uv run --offline --no-project --python python3.12 scripts/check_repository.py
```

若系统找不到 `python3.12`，可替换为已安装的 Python 3.12 解释器路径；没有 uv 时可直接执行 `python3.12 scripts/reproduce_paper.py`。前者校验历史附件并复算主要汇总，后者检查来源哈希、索引、精选链接和公开敏感文件模式。[复核步骤](docs/reproduction.md) · [本地检查记录](docs/validation.md)。

## 仓库结构

| 目录 | 内容 |
|---|---|
| `paper/` | 已有作者署名 PDF 与最小 TeX 源码 |
| `paper_evidence/` | 与当前论文对齐的证据、输入审计、干预文本和 AI 使用披露 |
| `experiments/` | 完整保留的历史大附件：原生代码、外部适配、配置、样本及离线校验 |
| `reports/` | 精选的 19 份报告正文及小型配图，已转换本地路径引用 |
| `index/` | 260 条报告元数据、69 条运行元数据、版本更正关系 |
| `scripts/` | 为展示新增的轻量离线入口 |
| `provenance/` | 原文件与副本哈希、索引来源 |

历史附件保留旧题名和表号：原 Table 3 / 2 / 4 分别对应当前论文的行为、任务表现、协作评分（Table 1 / 2 / 3）。新版入口按语义命名，不改写旧结果。FRAMES150、历史 111/011 和试点只保留为背景材料，不并入论文主面板。

## 新实验与公开准备

重新运行模型需要分别恢复 ROMA 与 TalkHier 环境、冻结样本和外部服务，迁移归档路径；[运行说明](docs/runtime.md)列出入口与条件。本次验证覆盖已有证据的离线复核，未重新执行完整 Agent 实验，也未附带完整的多 GB 原始轨迹。

上游许可保留。研究新增部分与论文尚未指定统一开源许可；历史 ROMA 许可缺口和基准数据再分发核对项见[第三方说明](THIRD_PARTY_NOTICES.md)。此目录供本地审阅，公开发布另由作者确认。

运行配置：[环境变量](docs/security.md)。
