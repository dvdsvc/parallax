# TalkHier BASE/V2

此目录冻结与 ROMA V2 表达形式一致的五份全局说明，并提供原生代码之外的请求适配器。主条件由用户指定为 `all_roles`；BASE 不注入，V2 在每个角色的模型调用前加入相同领域的固定系统消息。原生角色提示、工具、路由、响应 schema 与评分保持原样；后续经用户授权的 API 兼容改动单独记录。

后续用户明确授权的兼容修改涉及模型创建及结构化方法选择：`src/multiagent/llm.py` 直接使用 ChatOpenAI，显式开启思考并设置8192 token预算、16384 token总输出上限；主管和成员调用严格 provider-native `json_schema`，直接传 JSON Schema 字典；原 schema 声明只生成字段规范，不实例化或验证响应。返回 dict 后只映射为属性对象，原业务工具调用和内层结果处理不变。BASE 使用原生流程且不经过 ModelView；V2 继续使用本目录的外部注入。组织说明文本没有重建或改写；manifest 的 `provider_compatibility_changes` 同时保留这四个文件的上游与当前哈希。

先阅读 [流程与来源审计](FLOW_AUDIT.md)：它区分程序强制路径、原生提示词要求和结构上允许的可选路径，并核对下游、串行调用、输入依赖、返回和修订反馈关系。五个描述保留 ROMA V2 的四个栏目，使用 ASCII 图加自然语言；与任务无关，不提供当前题目执行路径。每个领域包含原生配置中的全部角色，Formal Logic 还记录其声明的领域流程条件。

## 离线核对

从仓库根目录运行，无须凭据且不调用服务：

```sh
.venv/bin/python repro/validate_organization_v2.py
.venv/bin/python repro/org_v2/check_provider_payload.py
.venv/bin/python repro/run_mmlu.py --mode college_physics --condition V2 --preflight-only
```

`validation.json` 冻结初次 180 个离线流程用例的结果，普通重跑结果写入忽略的 `.local/organization_v2/`。这里的 fixture 由本地替身指定返回值和路由，不是真实解题准确率或成本数据。`provider_payload_validation.json` 是原生 SDK 的六条本地 HTTP mock 请求构造检查，不是服务认证验证。

默认 `enable_thinking=true`、`thinking_budget=8192`、`max_completion_tokens=16384`，不设置 `max_tokens`。思考开关和预算通过 ChatOpenAI 的 `extra_body` 传入提供方请求；总输出上限直接传入模型构造，限制单次思考加最终回复的合计长度。可由 `--thinking-budget` 和 `--max-completion-tokens` 调整；配对及子集入口向 BASE/V2 传递相同值，并写入各自有效配置和 MLflow。思考预算须小于总输出上限，以留出回复空间。

## 真实原生单题入口

外部入口默认通过 LangChain `ChatOpenAI` 直接调用 Qwen 的兼容 API，读取已有本地凭据，不经过 ROMA/LiteLLM 转发层。下列直连命令已离线验证，但按用户要求尚未恢复真实调用：

```sh
.venv/bin/python repro/run_mmlu.py --mode college_physics --problem-id 0 --condition BASE --scope all_roles
.venv/bin/python repro/run_mmlu.py --mode college_physics --problem-id 0 --condition V2 --scope all_roles
```

默认条件为 BASE，默认 scope 为用户选择的 all_roles。两种条件的环境、题号和运行参数须固定配对；`--all` 显式运行整科。`evaluation_supervisor` 是保留的可选作用范围。每次运行新建目录，保存原生 CSV、题号、条件、scope、源码/组织说明/数据标识以及 LangChain/LangGraph 回调轨迹。模型事件记录角色、输入、输出、注入 metadata 与响应 token usage。V2 每次只前置一份说明，不把它写进历史或再传播到其他节点。metadata 只用于本地回调，不进入 API 请求体。

真实凭据不提交；模型设置仅记录 LLM 部分及去除认证信息的连接参数，不记录 KEYS。运行输入可能包含题目与模型输出，留在本地忽略目录。外部总时限防止原生无限失败循环；`--all` 的时限作用于整批。原始 Azure 构造保留在上游 Git 基线中，当前入口只使用原生 ChatOpenAI 构造。详见 [直连与本地轨迹](../SMOKE.md)。

每次 BASE/V2 启动现在自动冻结源码、配置、完整题目包与组织说明版本，建立独立 MLflow Run，结束时挂载原生轨迹及封存校验。索引不接管 agent 执行或轨迹采集；预检 Run 的模型调用为零。详见 [自动留底](../RECORDS.md)。

## 冻结与重建

`build_prompts.py` 从固定原生配置直接提取成员清单、结合已审计职责摘要生成五个领域说明。源文件和提示文件的散列记录在 `manifest.json`，当前 ROMA V2 的参考文本单独冻结为 `roma_v2_reference.txt`。适配器在每次启动前检查来源和说明散列；修改说明必须重新生成 manifest，属于明确的新处理文本版本。

```sh
.venv/bin/python repro/org_v2/build_prompts.py
```

重建只生成文本，不调用 agent。当前 ROMA V2 原文和实验归档没有修改。
