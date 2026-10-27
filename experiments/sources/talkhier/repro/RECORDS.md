# 自动留底与 MLflow Run

`run_mmlu.py` 和 `smoke_pair.py` 的每次有效启动都会建立新目录并自动留底；已有非空目录不会覆盖。MLflow 用作实验运行索引，保存参数、指标、版本标识和产物，轨迹来源仍是 TalkHier 的原生 LangChain/LangGraph 事件。原生角色提示、组织图、流程、工具、字段声明和结果记录代码没有修改。结构化模型边界的兼容改动单独记录。没有开启 LangSmith 或 MLflow 的 LangChain autolog。

用户随后授权把模型创建直接改到 `src/multiagent/llm.py`：AzureChatOpenAI → ChatOpenAI。这个文件的改变会真实计入 agent 哈希；其上游/当前哈希和修改范围记入组织 manifest，不把它伪装为未修改源码。外部入口只填写配置，BASE 不再经过模型工厂替换或 ModelView。此前冻结的离线验证报告及运行归档仍对应各自记录的版本。

用户随后授权把两处结构化调用改为严格 provider-native JSON Schema 字典；LangChain 返回 dict 后，仅通过 `src/multiagent/structured_output.py` 映射成属性对象，不实例化 Pydantic 响应，不增加文本解析/修复。原字段 schema、工具、提示、图、路由和内层中间结果处理保留。四个相关源码文件的上游/当前散列真实计入每次快照；新增边界文件注明无上游文件。接口包版本已兼容升级，LangGraph 版本固定。有效配置记录 `json_schema`、`strict=True`、`pydantic_response_validation=False` 和默认思考设置。

默认 `enable_thinking=true`、`thinking_budget=8192`、`max_completion_tokens=16384`，不设置 `max_tokens`。思考开关和预算通过 ChatOpenAI 的 `extra_body` 传入提供方请求；总输出上限直接传入模型构造，限制单次思考加最终回复的合计长度。可由 `--thinking-budget` 和 `--max-completion-tokens` 调整；配对及子集入口向 BASE/V2 传递相同值，并写入各自有效配置和 MLflow。思考预算须小于总输出上限，以留出回复空间。

## 启动、执行、封存

入口在模型工作前先复制源码，记录 Git commit、分支、dirty 状态、diff 和相关未跟踪源码，计算 agent 与外部入口的独立 SHA-256，再创建状态为 RUNNING 的 MLflow Run。随后冻结所选题目的完整题目/选项/金标、原生题号、数据 manifest、去认证信息的配置、有效模型/重试/时限/条件与组织提示词版本。相关来源均有逐文件哈希；输入冻结完成且 MLflow 索引成功后才可调用模型。启动索引失败会停止实验，保存本地失败归档。

执行中继续使用 LangChain callbacks、LangGraph 节点元数据和原生返回值。`native_console.log` 原样保存作者在执行期间输出的角色、消息、背景、路由及答案，`native_results.csv` 保存作者的 CSV 字节；结构化轨迹及 token usage 由已有的本地框架回调记录器落盘。每次模型事件带对应的 MLflow Run ID，便于相互定位；这个 metadata 不进入 API 消息。

结束或可捕获的中断/错误会汇总指标、写入完成状态，并生成 `archive_manifest.json` 和 `checksums.sha256`。封存后把完整归档挂回同一个 MLflow Run：正常结束为 FINISHED，人工中断为 KILLED，超时/错误/启动失败为 FAILED。`run_kind` 区分 benchmark、preflight 与 paired controller；预检成功不代表题目已经解完。强制杀进程或断电可能留下 RUNNING 与未封存目录，这种情况不会伪装成已完成记录。

| 记录 | 内容 |
|---|---|
| `launch.json`、`startup/git_state.json` | Launch ID、MLflow Run ID、上游和工作区 commit、分支、dirty 状态、父 Run |
| `startup/source/`、`source_hashes.json`、`git.diff` | 运行前相关源码的完整副本、逐文件哈希和当前差异，包括外部入口及冻结组织说明 |
| `startup/command.json`、`environment.json` | 启动命令、Python、平台、agent 环境的全部安装版本；MLflow 版本和独立解释器见 launch receipt |
| `startup/config/`、`effective_configuration.json` | 去认证信息的配置和实际参数；预检注明连接未解析，原生 Azure 默认值不冒充已应用的直连参数 |
| `startup/questions.jsonl`、`dataset_manifest.json`、`input_hashes.json` | 所选题目、原始行号、选项、金标及题目/配置/数据版本哈希 |
| `native_console.log`、`native_results.csv` | 作者原生过程输出与结果，不重新生成答案、不改变评分 |
| `trace.jsonl`、`graph_nodes.jsonl`、`model_calls.jsonl`、`token_usage.json` | 框架原始事件、节点、逐次模型响应及观察到的返回用量 |
| `manifest.json`、`completion.json` | 运行状态、结果/用量汇总、错误、结束时源码是否变化 |
| `archive_manifest.json`、`checksums.sha256` | 全归档逐文件校验与封存状态 |

agent 哈希是 `src/` 全部纳入快照文件的路径→SHA-256 映射经 canonical JSON 再计算 SHA-256；外部入口哈希同理，覆盖 `repro/` 的 Python/shell 文件。各组织说明单独有文件哈希，完整题目包和有效配置另有哈希，避免只保存一个 Git commit 无法解释 dirty 改动。源码快照保存当前相关未跟踪文件，而不是只依赖 commit。

原生程序在退出时会删除 CSV 中的未完成占位行，因此它的可写工作文件保存在 `.local/native_work/<launch_id>/`，封存目录保存结束时观察到的原始字节。中断时 `-` 占位行保留为未完成，不按错误答案计分。MLflow 的 `native_accuracy` 只汇总已返回整数答案的原生 CSV 行，观察不到答案时不记录准确率；token 用量缺失时同样保持未知。缓存与 reasoning token 是输入/输出的子集，逻辑调用数不等于 SDK 隐藏的 HTTP 重试数，也不代表完整账单。

配对入口建立一个父 Run，BASE/V2 并发工作进程各有独立子 Run、完整启动快照和封存归档。父记录的 `child_run_index.json` 引用子 Run ID、封存哈希与校验状态；子目录不再重复上传到父 Run。每个子归档单独校验，父校验覆盖引用及控制器日志。

## 本地存储与检查

本机直接复用 ROMA 已安装的 MLflow **3.16.1** 独立环境，不往 TalkHier 的 agent 环境新增依赖。TalkHier 的记录独立存放于 `.local/mlflow/tracking.db`（SQLite）和 `.local/mlflow/artifacts/`，实验名 `TalkHier-MMLU`，显式关闭 MLflow telemetry。使用不需要运行 MLflow 服务或开启网页；可通过 `--mlflow-python`、`--mlflow-tracking-uri`、`--mlflow-experiment` 指定其他本地配置。索引解释器默认 `sources/roma/controls/.venv/bin/python`；换机器时须指定可用的 MLflow 解释器。

本地归档及框架原始轨迹是证据来源；MLflow 提供按 Run 的检索、参数/指标比较和产物副本。`.local/run_index/<launch_id>.json` 是归档之外的索引收据，记录归档封存后上传成功或失败，重试不会改写封存文件。

```sh
# 预检也自动留底并索引，但模型调用为零。
.venv/bin/python repro/smoke_pair.py --mode college_physics --problem-id 0 --preflight-only

# 校验单个子 Run 或单题归档。
.venv/bin/python repro/run_archive.py /absolute/path/to/archive

# 只重试向已有 Run 挂载封存产物，不重新运行 agent。
.venv/bin/python repro/run_archive.py /absolute/path/to/archive --reindex

# 本地模拟完整原生流程及中断/失败，检查索引状态、哈希、脱敏和产物一致性。
.venv/bin/python repro/validate_run_archive.py
```

普通检查写入忽略的 `.local/validation/run_archive/`；`repro/run_archive_validation.json` 保存本次准备的验证结果。所有真实 API 调用继续暂停。凭据不复制到快照，配置中的 KEYS 和认证字段脱敏；题目、轨迹、数据库及运行产物都留在本地忽略目录。

模拟验证入口使用独立的 `TalkHier-RecordValidation` experiment，并标记 `validation_fixture=true`；最初接线时已生成的模拟 Run 也保留并补上该标签，便于排除它们。真实实验不使用模拟响应；preflight Run 则以 `run_kind` 和零模型调用明确区分。
