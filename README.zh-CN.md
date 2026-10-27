<img src="assets/mark.svg" width="68" alt="组织信息可见性标志">

# 层级多智能体系统中的组织信息可见性

**在保留原有执行接口的条件下，研究全局静态组织说明如何影响 ROMA 与 TalkHier 的行为、任务结果和计算投入。**

**论文状态：AAMAS 2027 — Under Review（审稿中）。** 本仓库保存本地作者署名稿，不代表录用或已公开发表。

[English](README.md) · **简体中文**

论文：*How Much of the Organization Should Agents Know? The Marginal Value of Global Topology Awareness in Hierarchical Multi-Agent Systems*。作者：Haoyan Xu，中国地质大学（北京）。

[论文 PDF](paper/organizational_visibility_preprint.pdf) · [研究方法](docs/methods.md) · [结果与口径](docs/results.md) · [离线复核](docs/reproduction.md) · [报告索引](index/reports.md) · [运行归档](index/runs.md)

## 研究问题

系统代码实现了层级组织，不等于每次模型调用都能看到完整组织。给模型补充现有组织的角色、关系和信息流，是否有助于它更有效地使用这个组织？实验比较原生输入 BASE 与增加静态说明的 ORG-DESC（归档标签为 V2），同一对照内保留原生工具、角色契约、路由和执行接口。

ROMA 在递归任务的不同深度复用 Atomizer、Planner、Executor、Aggregator；TalkHier Physics 则采用固定的六角色组织。研究分别审计两者实际输入中的信息边界，再考察执行行为、任务收益、计算投入、重复可靠性和外部协作评分。干预也会澄清或重复已有局部信息，因此结论对应整段组织说明的边际作用。

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

## 主要观察

| 论文主面板 | BASE → ORG-DESC 任务表现 | 行为变化 |
|---|---|---|
| ROMA / SEAL-0：94 题、272 个配对题目轮次 | 35.64% → 35.46% | 展开任务数 −15.80%；记录总 token −1.34% |
| ROMA / FRAMES：计划 50 题、有效配对 47 题 | 34/47 → 38/47（72.34% → 80.85%） | 展开任务数 −18.75%；记录总 token +3.66% |
| TalkHier / MMLU-Pro Physics：计划 100 题、有效配对 94 题 | 88/94 → 90/94（93.62% → 95.74%） | 正常返回调用 +34.57%；正常返回 token +64.96% |

组织说明会改变执行行为，但这些变化没有给出可靠的普遍准确率收益。FRAMES 的配对增量为 +8.51 个百分点，冻结区间跨零。SEAL-0 先在每题内部平均有效配对轮次，再使题目等权；失败、阻断、缺失保留原状态。ROMA 与 TalkHier 的 token 口径不同，不能直接作跨系统费用排名。[完整结果说明](docs/results.md)。

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

凭据配置与发布前检查：[安全说明](docs/security.md)。
