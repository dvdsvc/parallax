# TalkHier 本地 agent / MMLU 工作区

本工作区于 2026-10-05 从官方 `https://github.com/sony/talkhier.git` 完整克隆。上游基线为 `842a62160bcd326c5f8bb11c6cd1f3da7ced00f6`，保留完整上游提交历史，并标记为 `baseline/upstream-842a621`。环境准备基线保存在 `setup/native-mmlu` 和 `baseline/ready-mmlu-20261005`。用户随后授权直接修改原生模型创建位置：`src/multiagent/llm.py` 的 AzureChatOpenAI 换为 ChatOpenAI，连接 Qwen 兼容 API。角色提示、工具、评分、图、路由、模板与 `requirements.txt` 保持原样；兼容修改及其原始/当前哈希单独记入 `repro/org_v2/manifest.json`。

## 环境与原生 bench

独立环境在 `.venv/`，Python **3.12.13**；本次安装及验证主机为 macOS / Apple Silicon。覆盖 agent 的 LangChain/LangGraph 运行时、结构化输出、原生 OutputTool / SymPy 逻辑工具、MMLU 下载读取与原生 CSV 答案记录。`repro/requirements.mmlu.in` 描述依赖范围，初始环境按上游 `requirements.txt` 约束准备；当前按用户要求升级模型接口层，完整安装版本锁定于 `repro/requirements.mmlu.lock.txt`。Intel Mac 尚未实测。

| 原生 MMLU 领域 | test | validation | dev |
|---|---:|---:|---:|
| moral_scenarios | 895 | 100 | 5 |
| college_physics | 102 | 11 | 5 |
| machine_learning | 112 | 11 | 5 |
| formal_logic | 126 | 14 | 5 |
| us_foreign_policy | 100 | 11 | 5 |
| 合计 | **1335** | **147** | **25** |

数据来自官方 `cais/mmlu`，固定 revision 为 `c30699e8356da336a370243923dbaf21066bb9fe`。五个领域全部 splits 已下载到 `data/mmlu/`；未抽样、未过滤题目，保留原始顺序、问题、选项和金标。每个领域同时提供可读 JSONL 和 Hugging Face Arrow 格式，文件散列与数量见 `repro/mmlu_manifest.json`。数据与缓存留在本地，不进入 Git；提交保留可重建的 revision 和散列。

这里准备的是 **原生代码实际实现的全部五个 MMLU 领域**。README 还展示 WikiQA 和 Camera 的论文结果，但当前 `experiments.py` 没有这两项的完整执行分支，不能把其参数名或结果表当成可直接运行的 bench。上游全量清单同时包含 Linux CUDA / Triton、本地模型及 notebook 依赖，本环境不安装这些与原生 API + MMLU 路径无关的包；原清单完整保留。

## 模型接口兼容升级

当前 `langchain-openai=0.3.35`、`langchain-core=0.3.86`、`langchain=0.3.30`。`langgraph=0.2.71`、`langgraph-checkpoint=2.0.12`、`langgraph-sdk=0.1.51` 保持原版本；原 LangGraph 要求 core `<0.4`，因此使用兼容的 0.3 分支。`langsmith=0.3.45` 同时满足新版 core 和原有 community 包约束，但服务追踪仍关闭。`pip check` 已通过。版本变更清单见 `repro/interface_upgrade.json`，直接接口约束见 `repro/requirements.interface-upgrade.in`；原版 `requirements.txt` 不修改。

## 使用与重建

在仓库根目录运行。当前环境与数据已准备完成；离线检查不调用任何付费服务：

```sh
.venv/bin/python repro/validate_setup.py
```

新克隆或重建本工作区时，先提供 Python 3.12，再执行：

```sh
./repro/bootstrap.sh
```

如 Python 名称不同，可设置 `TALKHIER_PYTHON=/absolute/path/to/python3.12`。脚本按锁定版本安装独立环境，复制本地配置模板，下载固定数据 revision，并运行离线检查。已有完整数据时仅核对散列，不联网更新数据或改写已提交的 manifest。普通检查结果写入忽略的 `.local/validation/`；`repro/setup_validation.json` 是本次初始准备的提交记录。

本地配置模板在 `config/config.ini` 和 `config/config_llm.ini`，保留占位符。原生 LLM 类现在直接创建 LangChain `ChatOpenAI`，外部入口只在内存中填写其模型、API key、base_url、超时及重试配置，不再替换 `experiments.LLM`。凭据从已有本地 `external_archive/env/glm_api.env` 读取，不复制或提交。BASE 不经过组织模型包装；V2 保留外部系统消息注入。默认 `enable_thinking=true`、`thinking_budget=8192`、`max_completion_tokens=16384`，不设置 `max_tokens`；单次思考预算与思考加最终回复总上限可由 `--thinking-budget`、`--max-completion-tokens` 调整，两组须保持一致。没有 ROMA/LiteLLM 转发、自定义 HTTP transport 或结构化输出回退；原始 Azure 构造可由上游基线或 `fd1bcec` 追溯。

配置完成后，可通过以下入口运行原生单题：

```sh
.venv/bin/python repro/run_mmlu.py --mode college_physics --problem-id 0
```

完整单科须显式使用 `--all`。入口先校验冻结数据，调用上游原生函数，保留原生题号与评分，结果写入 `.local/runs/`。原生角色提示、工具和路由保持原样；`--condition V2` 通过外部适配器前置固定全局组织说明，默认 `--scope all_roles` 为用户指定主条件。默认条件为 BASE，模型为 `qwen3.7-flash`、temperature=0。总时限和单请求时限默认均为 900 秒；总时限也作用于 `--all` 的整批运行。此前经转发层的第一题 BASE/V2 真实尝试已停止并保留在 `.local/smoke_pairs/20261005T120041Z_college_physics_q0/`，两组均无最终 CSV 成绩。后续真实单题已用于定位接口兼容问题，运行状态与成本见各次封存记录。模型显式设置 `enable_thinking=true`、`thinking_budget=8192`，总输出上限为 `max_completion_tokens=16384`；两处结构化入口使用严格 provider-native `json_schema`，直接传 JSON Schema 字典，LangChain 返回 dict 后只映射为属性对象。原字段 schema、角色、提示、工具、内层中间结果处理及流程保持原样；不实例化 Pydantic 响应，不增加文本修复。

轨迹使用 LangChain 原生 callbacks 和 LangGraph 节点元数据写入本地：`trace.jsonl` 保存父子调用、输入、输出、工具和错误；`graph_nodes.jsonl` 提取节点开始/结束/失败；`model_calls.jsonl` 保存逐次模型响应与 usage；`token_usage.json` 汇总模型调用和各角色用量。没有开启 LangSmith。模型逻辑调用数不等于 SDK 内部 HTTP 尝试数，缺失的 usage 保持未知；缓存与 reasoning token 是输入/输出的子集，不重复计入总量。详情见 [直连与本地轨迹](repro/SMOKE.md)。

运行入口现在自动建立 MLflow Run，模型工作前冻结源码、Git 状态、配置和题目，结束时封存哈希并关联原生轨迹/CSV/控制台输出。复用 ROMA 的独立 MLflow 环境，TalkHier 数据库和产物位于自己的 `.local/mlflow/`，不新增 agent 依赖。配对运行建立父 Run 与两个独立子 Run；预检同样留底但不调用模型。MLflow 负责参数、指标、产物和版本索引，本地原始轨迹是证据来源。详见 [自动留底与校验](repro/RECORDS.md)。

若要使用完全原生 CLI，应从 `src/` 运行 `../.venv/bin/python experiments.py --help`；README 根目录命令不对应文件实际位置。正式配对实验的组织说明与注入已准备，模型、任务子集、重试策略和运行预算仍需固定。详见 [BASE/V2 使用说明](repro/org_v2/README.md) 和 [完整流程审计](repro/org_v2/FLOW_AUDIT.md)。`--preflight-only` 可在零服务调用下核对指定条件。

## 验证与追溯

`repro/setup_validation.json` 记录五个领域的离线原生单题流程、全部导出记录与 Arrow 数据的一致性、金标与修订前答案的 CSV 记录、局部主管接口、三个原生逻辑/输出工具，以及本次平台和 Python 版本。每个领域使用独立进程，要求所有成员都经过路由且没有失败重试。模型部分使用确定性本地替身，不能将结果解释为真实准确率或 token 消耗。`repro/workspace_manifest.json` 记录上游源码散列、环境锁和数据 manifest 散列。

上游已知的跨领域提示残留和外层失败重试计数问题保持原样。另发现日志颜色分配器使用有限的进程级列表，在同一个进程连续构建多个不同领域时会耗尽；按原生 CLI 每次只运行一个领域可避免该情况，核验也采用同样的进程边界。外部运行入口用总时限防止原生失败循环无限持续。直连与本地轨迹属于后续外部入口提交；原生提示、工具、组织图、路由和字段 schema 均未修改；结构化模型边界使用原生 JSON Schema 和薄属性映射。

虚拟环境、数据、缓存、含密钥的配置与运行结果都已忽略；源代码和环境/数据记录已提交。查看基线及后续改动可使用 `git log --oneline -5`、`git status --short` 和 `git diff baseline/upstream-842a621 -- src template requirements.txt`。
