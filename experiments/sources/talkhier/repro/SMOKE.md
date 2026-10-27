# LangChain 直连 API 与本地原生事件轨迹

用户授权后，`src/multiagent/llm.py` 直接创建 LangChain `ChatOpenAI(model, api_key, base_url)`，调用 Qwen 的 OpenAI-compatible API。默认模型 `qwen3.7-flash`，temperature=0；凭据从已有本地 `external_archive/env/glm_api.env` 读取。没有 ROMA/LiteLLM 转发进程、自定义 HTTP transport、消息重写或 JSON 解析回退。角色提示、工具、组织图、路由、字段 schema 与评分保留；结构化模型边界采用下面的原生 JSON Schema 方式。

外部入口只填写原生 LLM 类的配置，不再替换模型工厂。BASE 直接使用原生模型和流程，不经过 ModelView；V2 仍由 `org_v2/adapter.py` 在每次模型输入前增加一份冻结的系统消息，角色/阶段 metadata 仅用于回调。`direct_model.install` 保留给历史离线 fixture 使用，不是当前真实入口。

主管和成员两处结构化入口调用 `src/multiagent/structured_output.py`：从原字段声明生成 JSON Schema 字典，交给 LangChain `with_structured_output(..., method="json_schema", strict=True)`；返回 dict 只经 `SimpleNamespace` 映射以保持下游属性访问。原声明中的字段、描述、枚举、状态、内层中间结果处理、错误重试和路由不改。没有 Pydantic 响应实例化或 validation；JSON 反序列化由 LangChain 自带路径完成，薄层没有文本解析或修复。实际业务工具调用仍使用原来的 bind_tools。当前按用户要求升级 `langchain-openai=0.3.35`、`langchain-core=0.3.86`、`langchain=0.3.30`，固定原 LangGraph 三个包的版本。模型显式设置 `enable_thinking=true`、`thinking_budget=8192`，总输出上限为 `max_completion_tokens=16384`。依赖变更及锁文件独立记录；实际运行状态由各次不可变归档给出。

默认 `enable_thinking=true`、`thinking_budget=8192`、`max_completion_tokens=16384`，不设置 `max_tokens`。思考开关和预算通过 ChatOpenAI 的 `extra_body` 传入提供方请求；总输出上限直接传入模型构造，限制单次思考加最终回复的合计长度。可由 `--thinking-budget` 和 `--max-completion-tokens` 调整；配对及子集入口向 BASE/V2 传递相同值，并写入各自有效配置和 MLflow。思考预算须小于总输出上限，以留出回复空间。

轨迹通过 LangChain `BaseCallbackHandler` 接收框架事件，LangGraph 节点元数据与父子 run ID 沿原生嵌套流程传递。外部 `RunnableLambda` 只为每道题配置继承回调，不替换原生图或其 stream 模式。本地记录器把收到的事件保存为文件，没有开启 LangSmith；入口显式关闭 `LANGCHAIN_TRACING_V2`。

| 文件 | 内容 |
|---|---|
| `trace.jsonl` | 框架 chain/model/tool 开始、结束、错误，父子 run ID、节点元数据、输入输出和耗时 |
| `graph_nodes.jsonl` | 从原生回调提取的 LangGraph 节点事件，包括嵌套主管、成员与内部工具节点 |
| `model_calls.jsonl` | 逐次模型响应、角色、阶段、原始 usage、归一化 token 统计或错误 |
| `token_usage.json` | 全题与可识别角色的模型逻辑调用、错误、缺失用量、输入/输出/总 token、缓存与 reasoning 子集 |
| `native_results.csv` | 作者原生最终答案、金标和修订前答案 |
| `native_console.log` | 作者执行期间的原生控制台输出，原样保存角色、消息、背景和路由 |
| `manifest.json` | 题号、条件、输入与源码散列、模型连接参数、状态和日志散列；无认证信息 |

BASE 不经过 ModelView，因此部分模型回调没有角色标签，汇总中的 unknown 不猜填角色；节点和父子 run ID 仍保留，可用于后续归属分析。usage 首选模型返回的原始 `token_usage`，兼容 `AIMessage.usage_metadata`。缺失值保持未知，未返回响应的请求无法仅靠框架回调得知收费量；缓存 token 与 reasoning token 分别属于输入和输出子集，不重复加入 total。LangChain 的一次模型回调是逻辑调用；SDK 内部 HTTP 重试不一定产生额外回调，因此这里不把它称作真实 HTTP 尝试数或完整账单。默认 SDK 两次重试与原生客户端一致，可显式设置 `--max-retries`；单请求时限和外部总时限默认 900 秒。

## 离线核对与后续入口

```sh
.venv/bin/python repro/validate_direct_trace.py
.venv/bin/python repro/smoke_pair.py --preflight-only
```

离线核对使用原生大学物理第一题、真实 ChatOpenAI SDK 和进程内 HTTP mock，网络被禁用。BASE/V2 分别运行完整原生流程，覆盖六个组织角色、四次工具调用与结构化格式化，检查父子调用、角色 metadata、返回用量及 provider 请求体只有 V2 前缀不同。另检查不合规的 provider 内容不经过自写修复，HTTP 错误与缺失 usage 保留。模拟返回值不是真实题目答案或实际费用。

实际单题与并发配对入口如下。真实运行状态以各次封存记录为准，离线验证不代表真实解题成功：

```sh
.venv/bin/python repro/run_mmlu.py --mode college_physics --problem-id 0 --condition BASE
.venv/bin/python repro/run_mmlu.py --mode college_physics --problem-id 0 --condition V2
.venv/bin/python repro/smoke_pair.py --mode college_physics --problem-id 0
```

单题结果默认保存到 `.local/runs/`。配对入口同时启动两个独立工作进程，在 `.local/smoke_pairs/<timestamp>_direct_<domain>_q<id>/BASE/` 和 `V2/` 保存各自原生结果与轨迹。凭据、题目数据、缓存和实际轨迹均不进入 Git。

每次入口启动都自动建立 MLflow Run 并冻结源码/配置/题目，结束时封存校验并把结果与上述轨迹挂回同一个 Run。预检也有独立 Run，但模型调用为零；配对启动具有父 Run 与 BASE/V2 两个子 Run。MLflow 只作参数、指标、版本和产物的索引，轨迹仍来自框架 callbacks，无 LangSmith/autolog。详见 [自动留底](RECORDS.md)。

此前经 ROMA 转发层的运行代码可由提交 `c9521f4967a461b3341866c797e40bd41199183e` 追溯；停止的原始运行记录保留在 `.local/smoke_pairs/20261005T120041Z_college_physics_q0/`，两组均没有最终 CSV 成绩。当前入口已经改为直连，原有运行记录未重写。
