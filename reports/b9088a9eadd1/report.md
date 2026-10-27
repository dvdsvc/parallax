# ROMA 与 TalkHier：分角色、分层级、分 benchmark 的组织信息可见范围审计

审计日期：2026-10-07。对象是本地实验所用实现和已留档模型输入，不是对两个框架全部版本的概括。本文只审计组织信息披露，不重跑推理，不重新评分，不修改 Agent、V2、提示词、环境或原实验档案。

**结论：ROMA 与 TalkHier 的 BASE 都已有组织相关信息，但信息类型和分布明显不同。ROMA 明确披露任务递归深度、总目标及部分依赖/子任务结果；TalkHier 明确向主管披露直属成员、职责、下一跳及向上汇报接口。两者都没有向所有角色统一提供完整全局组织说明。现有全角色 V2 增加的不只是远端节点清单：它也给原本局部定位较弱的角色补充了更明确的上下游和流程定位。因此，可比较的是“在各自原生上下文之上补充全局静态组织说明”的边际价值，不能把两个 BASE 描述成局部组织信息完全相同或完全充分。**

## 1. 口径与证据

本文的“知道”指内容进入 LLM 的可见输入，不证明模型理解、记住或遵循。区分四种证据：**明示**＝提示词/输入/schema 中出现；**条件披露**＝只有相应历史、依赖结果或产物存在时出现；**可推断**＝由名称、任务语义等推知，但没有完整声明；**未统一披露**＝输入生成代码没有保证给所有角色这项信息，并不意味着模型绝对无法从其他文字猜到。

需要特别分开：①角色职责；②直属邻居与消息收发；③调度/结束/修改权限；④当前位置；⑤全局静态组织模板；⑥当前任务的动态组织状态。代码持有完整 TaskDAG、LangGraph state 或 callback metadata，不代表模型看到了它们。披露角色图也不会自动增加工具、改变路由 schema、放开跨组派发或提供其他角色私有历史。

来源按强度排列：实际模型输入 → 对应冻结源码/原生输入构造 → 固定 upstream 源码 → 论文/README。离线 fixture 用于核验输入与路由协议，不当作真实 LLM 行为。备份包含 40 份来源文件、25 份 ROMA FRAMES 代表输入、历史 SEAL-0 代表输入、20 份 TalkHier Physics 代表输入，以及五个 MMLU 领域的完整原生 team 配置；详见 证据索引 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/source_inventory.json`; archival reference, not bundled) 和 审计 manifest (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/manifest.json`; archival reference, not bundled)。

## 2. 先区分“层”是什么

| 系统 | 本文使用的层级 | 不能混用的概念 |
| --- | --- | --- |
| ROMA | 根 TaskNode 为 depth 0；Planner 建立的子任务 depth +1；子任务再次进入相同执行机制，直到原生深度上限 | Atomizer、Planner、Executor、Aggregator 是功能模块，不是四层上下级。一次 ReAct 工具循环也不是新增任务层 |
| TalkHier | 组织层 L0：Default Supervisor；L1：Answer Generator、Revisor、Evaluator Supervisor；L2：评估员 | 两层主管、三层角色，最长根到专家路径为两条组织边。叶子内部 agent/tools/respond 是计算流程节点，不是三个组织成员 |

ROMA 的差异是**按任务递归产生分支，复用功能模板**；TalkHier 本地 MMLU 的差异是**固定、不对称的嵌套组织，主管逐次选择允许的通信路径**。TalkHier 运行中选择下一跳，不等于运行中创建任意组织节点。ROMA 任务节点与 TalkHier 角色节点不是同一种计数单位，不能直接比较“Agent 数”或平均深度。[R1][R2][T1]

```text
ROMA：Task(depth d)
      ├─ 原子 → Executor → 当前任务结果
      └─ 分解 → Planner → 子任务(depth d+1，各自重复机制) → Aggregator → 当前任务结果
      （一般先 Atomizer；到深度上限时，原生代码可直接强制执行）

TalkHier：Default Supervisor (L0)
          ├─ Answer Generator (L1)
          ├─ Revisor (L1)
          └─ Evaluator Supervisor (L1)
             └─ 本 benchmark 的评估员 (L2)
          每个直属成员完成后返回本组主管；评估分支通过评估主管向上返回。
```

## 3. TalkHier 的 benchmark 差异：不能沿用同一个专家清单

下表统计**配置的 LLM 组织角色**，包含主管，不包含工具、FINISH 或叶子内部的整理节点；实际某题可以未调用全部配置角色。[T1][T2]

| benchmark / 配置 | 评估主管的直属成员 | 配置角色总数 | 已核验的组织层级与可见上下文 |
| --- | --- | ---: | --- |
| MMLU College Physics | Physics、Mathematics | 6 | L0/L1/L2；源码、离线完整输入和真实实验输入均已核验 |
| 本次 MMLU-Pro Physics | Physics、Mathematics | 6 | 外部数据入口明确映射到原生 college_physics；同一角色树，不是新专家团队。题目、选项数和任务内容发生变化 |
| MMLU Moral Scenarios | Intent、Normality、Responsibility、Well-being | 8 | 同样 L0/L1/L2；源码和离线输入已核验，没有把这次 Physics 真实轨迹冒充其轨迹 |
| MMLU Machine Learning | Answer Consistency、Machine Learning、Statistical Soundness | 7 | 同样 L0/L1/L2；同上 |
| MMLU Formal Logic | Truth Table、Counterexample、Predicate Logic、Logical Argument、Formal Logic | 9 | 同样 L0/L1/L2；另有方法选择要求与专用工具，不能只替换专家名字 |
| MMLU US Foreign Policy | Factual Accuracy、Policy Alignment、Conceptual Clarity | 7 | 同样 L0/L1/L2；源码和离线输入已核验 |
| 论文 WikiQA | 示例明确出现 Simplicity、Coverage 两类评估员及 ETeam Supervisor，并包含生成、修订、再评估 | 不由本地证据确定 | 固定 checkout 没有完整 WikiQA team 构造和可执行上下文入口；不能保证各角色收到的路由、职责或层级与 Physics 相同 |
| 论文 Camera 广告任务 | 论文介绍生成、评价、修订；Faithfulness、Fluency、Attractiveness 三个评价维度，并描述评估员向评估主管汇报 | 不由本地证据确定 | 本地只有 ad.py 的部分广告/关键词提示字符串，没有完整 Camera team 配置。评价维度数不能直接当完整角色数，不能据此报“必定 7 个节点” |

**你的提醒成立，但要精确区分：本地五个 MMLU 领域改变的是专家节点、职责、工具和部分流程要求，已核验的管理层数没有变化。跨到 WikiQA/Camera 时，完整上下文披露证据不足，不能默认层数或节点仍然一致。** 论文级信息仅用于标出差异和待核验边界：[WikiQA Appendix C、Camera Appendix D](https://arxiv.org/html/2502.11098v1)。

原生 CLI 虽列出 camera/wiki_qa，所选版本的实际主入口只分派五个 MMLU 领域；“参数列表里有名字”不是已具备完整 benchmark 实现的证据。[T3] 五个 MMLU 领域的 V2 文本分别生成并冻结；当前不存在经过同等核验的 WikiQA/Camera V2。未来换 benchmark，必须重新核验 team 配置与真实输入，不能直接搬运 Physics 说明。

Formal Logic 的差异也属于可见上下文：Truth Table 和 Counterexample 分别有专用工具，Revisor 同时有这两种工具；主管提示按题目所涉方法选择相关评估员，并要求结束前评价为正。Physics 所配置的叶子工具是 output_tool，用于输出/分析记录，不是外部搜索或物理模拟。这里既有职能分工，也有不同的工具可用范围。[T2][T4]

## 4. ROMA：不同角色及深度已经知道什么

所有当前任务层的模块都由原生 XML 获得当前 goal（Aggregator 为 original_goal）、overall_objective、current_depth、max_depth、at_limit。**overall_objective 是总任务目标，不是全局组织图。** root depth 0 可以识别自己在根层；child depth 1/2 等可以识别自身深度，但 XML 没有统一提供当前 task_id、parent_id、完整路径、所有同级节点或剩余组织树。[R1][R3]

| 角色 / 适用深度 | BASE 明示的职责和局部机制 | 运行时条件披露 | BASE 未统一提供；V2 的主要增量 |
| --- | --- | --- | --- |
| Atomizer；通常 d < 上限 | 判断原子性，输出 PLAN/EXECUTE；原生指令提到 Think/Search/Write 类型及何时需要规划。知道分类职责和当前深度 | 本次任务语义可透露需要分解/检索；不自动拿到父/兄弟完成结果 | 缺少从分类到 Planner、递归子任务、Aggregator 的完整连接说明；V2 将这些功能模块和信息流串起来 |
| Planner；通常 d < 上限 | 拆解当前任务，输出 subtasks、任务类型、dependencies_graph；知道依赖结果会提供给依赖方，自己只规划、不执行 | 可获得已经存在的父结果、已完成兄弟结果；是否非空取决于运行状态。产物可见范围还受 artifact 配置影响 | 没有统一的父节点身份、完整祖先链、完整动态树；V2 明示子任务重复 ROMA 机制、向下展开及向上汇总 |
| Executor；可以 d = 上限 | 执行当前目标；ReAct 场景能看到绑定工具与本次轨迹；知道自己的深度和可执行手段 | 获得已完成依赖的 goal/output；有产物时可获其引用和来源任务标识；文件路径含 execution_id | 不保证知道“具体由哪个父 Planner 委派”“自己的输出最终由谁收集”、全局分支；V2 补功能关系与汇总方向 |
| Aggregator；有完成子任务的父层 | 合成当前 original_goal 和已收集的 subtasks_results；原生指令明示这是 child 输出，禁止重规划/重执行 | 能看到直接子任务的目标、类型、结果及可用依赖上下文/产物。因此它对本地已完成子分支了解最充分 | 不保证看到整棵任务树、祖先权限或其他分支；V2 补全功能模板及上下流方向。原生收集结果时 dependencies 字段实际置为空列表，不能把输出 schema 能表示依赖等同于实际传入完整 DAG |
| Verifier；原生类/配置存在 | signature 定义 goal、candidate_output、验证 verdict/feedback；职责本身可明确 | 本次实际观测没有 Verifier 调用；被审计的 solve/runtime 未发现调用它的入口 | V2 将其标为 optional。它在说明中出现，不能证明实际实验多了一层 Verifier，也不能当作已运行节点 |

父层与子层的**职责模板基本相同**，变化的是当前目标、深度、实际子任务/依赖结果，而不是每层更换一套主管权限。达到 max_depth 时程序可以绕过 Atomizer/Planner，直接执行；说明模板中的一般“先分类”不能理解成每个最深节点都必经 Atomizer。[R2]

两个重要限制：第一，ContextManager 支持 parent_results/sibling_results，不意味着子 Planner 每次都有这些内容。FRAMES 已观测记录中，BASE 236 条、V2 142 条带请求内容的 raw 返回记录全部有总目标和深度；非空 dependency_results 分别出现 35、22 次，Aggregator 子任务列表分别出现 7、6 次；没有观测到非空 parent_results、sibling_results 或 artifact 引用。计数用于证明披露存在及条件性，不用于比较行为强弱，因为这批 Pilot 被用户主动停止，存在未结束调用。[R5]

第二，原生 runtime 对 artifact 注入模式的默认值是 full，若具体 Agent 没有覆盖该配置，Planner/Executor/Aggregator 可获得 registry 中全部已登记产物；产物 XML 可包含创建它的 task 标识。这比“只知道依赖”更宽，但仍不是完整 TaskDAG，且该 Pilot 没有实际非空引用。不能根据方法参数默认写 DEPENDENCIES，就漏掉 runtime 实际传入 FULL 的情况。[R1][R4]

以上原生核心源码逐文件与 ROMA 提交 a6e3bb4f9e0694375fa627fa4b8bf8cae50592a6 对照，备份的上下文构造、runtime、solve、signature 与 seed prompts 均字节一致。FRAMES 使用冻结 general profile 与外部入口；SEAL-0 入口也选 general。另对 remaining59 repeat1 的 BASE/V2 留档 q-0022 作了直接交叉检查：同 native commit、同深度上限 3、同 V2 模板 SHA，BASE 4 条现有请求无注入，V2 4 条有注入；该题只出现根 Atomizer/Executor。**这不是对所有历史 SEAL-0/FRAMES 批次的完整上下文复核**。[R6]

## 5. TalkHier：主管与叶子的组织知情不同

以下首先描述当前真实 Physics 实验；五个 MMLU 领域沿用同一个建组/输入机制，但评估主管所看到的成员清单、完整成员 prompt 和工具随领域改变。[T1][T2][T5]

| 角色层级 | BASE 明示/实际传入的组织信息 | BASE 的权限说明与边界 | V2 新增的主要内容 |
| --- | --- | --- | --- |
| L0 Default Supervisor（论文常称 Main Supervisor） | 三个直属成员：Answer Generator、Revisor、Evaluator Supervisor；Joblist 包含它们的原生职责/输入输出契约。选择项含 FINISH；先生成、结束前联系修订者等要求已明示 | 能派发直属成员、接收返回、选择 FINISH。Evaluator Supervisor 在 Joblist 中是团队概述，未直接展开全部内部专家 prompt | 评估组内部专家清单、专家所属关系、完整嵌套返回路径。生成/修订/部分反馈原本已知，不能全算新增 |
| L1 Evaluator Supervisor | 本领域全部直属专家及完整评价 prompt；精确下一跳；向 Default Supervisor 汇报；汇总评价与被要求重新评估的接口 | 可选本组专家或向上返回；不能选择主团队 FINISH，也不能直接派发 Answer Generator/Revisor。这些路由边界由 schema/图约束 | 上层生成/修订分支、谁结束主任务、跨分支反馈循环；自身局部成员清单和评价职能主要是重复信息 |
| L1 Answer Generator | 生成职责、工具、输入输出格式；实际消息 name 和 Background 的文本表示含 Default Supervisor 名称 | 原生叶子通过固定边回主管；没有主管式 next 选项。看到来信名称不等于看到主管完整权限说明 | 明确自己的直属关系和返回定位、其他角色及决策权限、全局生成—评估—修订关系 |
| L1 Revisor | 修订职责；答案与评价结果输入；修改后提出再评估需求。输入评价字典/摘要还可条件性透露专家名称 | 可以修改自己的输出、请求重评；请求需要主管路由，自己没有直接调度评估员或 FINISH 的权限 | 请求如何经主主管进入评估组、全部专家所属关系及返回链；“我负责修订”“需要反馈”原本已明示 |
| L2 各评估员 | 自身名称、判断标准、工具、待评答案；实际来信与 Background 中出现 Evaluator Supervisor 名称 | 通过固定边向评估主管返回；无跨组 next 选择。输入模板未统一列出其他专家或上层生成/修订节点 | 同组成员清单、评估主管的上级、上层分支、完整返回与反馈关系；还强化此前仅由消息名称透露的局部定位 |

真实 Physics 输入中，评估员能看到 Evaluator_Supervisor 来信，背景字符串也含 name='Evaluator Supervisor'；生成者/修订者相应看到 Default Supervisor。这些是**确实进入文本/消息的线索**，不同于仅在 callback metadata 中出现的角色标签。不过，不能因此写成“叶子已经完整知道上游的权限和所有下游”。角色职责、父关系线索和完整权限图是不同的披露粒度。

原生 fullshared_memory 默认 False，主管/成员进入组织调用时选择自己的局部 history 并截取最近 15 条；叶子内部工具循环可继续追加消息。因此不能把 LangGraph state 中保存了多角色历史，理解成所有模型都读到全部历史，也不能声称每次内部工具调用都严格只有 15 条。V2 不提供其他角色的历史内容。[T1]

评估主管原生提示要求给评估员答案时不展示已有评价，以减少相互影响；这是提示词层的传递要求，不是独立的访问控制隔离。V2 提供其他评估员的**存在与职责**，没有添加其评价内容。另一方面，主管/修订者本来就可能收到全组评价字典，从而逐渐获知成员信息；BASE 的组织信息不是从头到尾完全静态不变。

**跨 benchmark 残留必须保留在审计里。** 原生通用 Revisor 提示有“至少三个/四个评价支持”的字面规则，在 Physics 只有两个实际专家、其他领域为三/五个时仍存在。不能用这句话推定四个真实节点。这是原生 BASE/V2 共同保留的提示词事实，本次没有修订；V2 的专家清单按实际 team 配置生成。正确的组织图不等于原生局部提示的所有跨领域语义已经一致。[T2]

## 6. V2 增加哪些知识；哪些权限没有改变

| 比较维度 | ROMA V2 | TalkHier V2 |
| --- | --- | --- |
| 描述对象 | 可复用递归功能架构：分类、规划、直接执行、子任务递归、汇总；optional Verifier | 该领域配置的固定角色树：主主管、生成者、修订者、评估主管、具体专家 |
| 表达形式 | ASCII 图＋角色职责＋信息流＋解释的语言描述 | 同样四部分，具体角色和串行/返回规则按本领域生成 |
| 注入位置与范围 | DSPy LM forward/aforward 前，前置一条 system；LM 边界不按角色重新生成文本。TaskNode bridge/second_order 是另外的开关 | 外部 ModelView 在选中角色的原生调用前放一条 system；当前主条件 all_roles，包含普通工具推理及结构化整理/主管调用 |
| 已有知识的重复 | 原生模块职责、当前深度/总目标、Planner 依赖契约、Aggregator 子结果合成已经存在；V2 将功能连接完整说出 | 主管成员/局部路由和许多流程规则已经存在；V2 向主管补远端分支，向部分叶子同时补明确局部定位 |
| 动态位置/状态 | V2 不添加 task_id、parent_id、当前路径、实际树或完整当前计划；已有深度来自原生 XML | V2 不添加本题选中路径、评估顺序、已访问状态、轮次或别人私有历史；角色标注 metadata 只供审计 |
| 实际权限 | 不新增工具/可执行权限，不修改递归调度或结束状态机 | 不修改 next 枚举、固定返回边、FINISH 权限或工具列表，不允许叶子绕过主管 |

TalkHier 还说明了原生提示层的先生成、结束前修订及重评要求。须与程序门禁区分：START 进入主管、直属成员返回主管、评估组向上返回、允许的 next 枚举由图/schema 约束；访问生成者/修订者/全部评估员的完整性没有统一图门禁。专家没有固定的同级 A→B→C 调用顺序；主管每次选择单一 next，选中的嵌套组返回后主团队才继续。原生 MMLU 没有 ROMA 的独立任务依赖 DAG。[T1][T6]

论文 Algorithm 1 的质量阈值结束/修订分支与原生 MMLU “结束前联系 Revisor”提示并不完全相同。现有 V2 依据所选可执行实现，明确保留提示要求与程序门禁的区别，不把论文概览作为覆盖代码事实的理由；也不声称已经复原所有 benchmark 的精确流程。[T6]

实际注入核验：TalkHier Pro Physics 的 2,308 个 BASE model_start 无组织前缀，3,093 个 V2 model_start 均只有同一完整前缀，首条 system 精确一致；100 对初始请求移除 V2 前缀后没有原生内容差异。ROMA Pilot 的全部 236/142 条现有带请求 raw 返回记录分别无/有同一组织前缀。这些验证的是注入位置、范围与文本身份，不证明运行中所有后续调用内容仍相同——路由、答案和后续历史本来可能因干预而改变。[R5][T5]

模板身份：ROMA SHA256 为 e17ebbbef2e0286a6496a86a42a4f22b23e5d43ba0b171690737fedeea46d7a7；TalkHier Physics SHA256 为 beaf76a7c61a5a98c7c8d50b5cb2e447222d94d64526955388d4becbba97600b。本文未修改两份模板。[R7][T7]

## 7. 对论文 claim 的具体影响

比较可以成立，但前提应描述为**原生角色和任务/路由上下文已经存在**，避免声称“所有 Agent 的局部上下游和权限已完全公开”。ROMA 的深度、总目标、依赖/子结果信息与 TalkHier 的直属成员/返回路由形成清楚的结构对照；它们对“局部组织信息”的覆盖是不同的。全角色条件下的效果应解释为额外全局静态说明的总边际效果，其中包含重复已知信息和补充局部定位两部分，当前实验没有把二者独立识别。

如果严格使用“已拥有局部角色、上下游/路由信息，再增加全局拓扑”的表述，**TalkHier 的 Evaluator Supervisor 最贴合这个前提**：BASE 已明确整个直属评估团队、向上接口和局部路由，V2 主要补生成/修订及全局结束/反馈关系。ROMA 则应按模块分别说明前提：Aggregator 对已完成本地子分支、Planner 对自身规划/依赖规则的知识较充分；Executor/Atomizer 不保证拥有同样充分的上下游角色身份。这个观察不能倒推出仅评估主管注入的实验效果，因为现有正式条件是 all_roles。

本报告不据组织图完整性推断收益，也不据某角色工具或 token 增多证明它“理解了组织”。后续行为解释应结合本报告的披露边界：例如是远端分支补充、局部角色强调、已有 workflow 要求重述，还是其他路径；这些属于机制假设，不能由上下文审计单独认定。当前报告没有启动新条件，也没有用异常调用用量作效果证据。

## 8. 留档与来源定位

本目录为独立只读分析备份，`report.md` 是入口；`evidence/` 保存代表模型输入、披露统计和 benchmark 清单，`sources/` 保留固定来源副本，`source_inventory.json` 记录来源与每份 SHA256，`checksums.sha256` 覆盖最终备份文件。实际输入 JSON 不包含 API transport headers、认证配置或密钥，只保留核验组织可见性所需的消息和定位信息。脚本只写本报告目录，不调用模型或加载推理运行入口。

| 标号 | 核验来源（备份副本，可直接打开） |
| --- | --- |
| R1 | ROMA context manager (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/context/manager.py:85`; archival reference, not bundled)、runtime 的实际模式与上下文构造 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/engine/runtime.py:415`; archival reference, not bundled) |
| R2 | 深度上限强制执行 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/engine/solve.py:944`; archival reference, not bundled)、创建递归子任务 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/engine/runtime.py:917`; archival reference, not bundled) |
| R3 | signature 字段 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/signatures/signatures.py:7`; archival reference, not bundled)、XML 序列化 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/context/models.py:238`; archival reference, not bundled)；原生角色 seed prompts 已备份 |
| R4 | 实际收集子任务结果 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/core/engine/runtime.py:1000`; archival reference, not bundled)、产物 XML 来源任务字段 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/native/src/roma_dspy/types/artifact_models.py:251`; archival reference, not bundled) |
| R5 | FRAMES 实际输入统计 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/roma_observed_visibility_stats.json`; archival reference, not bundled)、按角色/深度保存的代表输入 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/roma_observed_request_examples.json`; archival reference, not bundled)；236/142 为可见请求记录，非完整已发送调用数 |
| R6 | 历史 SEAL-0 的交叉核验 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/roma_historical_seal0_crosscheck.json`; archival reference, not bundled)、其代表输入 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/roma_historical_seal0_examples.json`; archival reference, not bundled)、FRAMES runner (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/runtime/run_official_frames.py:32`; archival reference, not bundled)、SEAL-0 runner (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/runtime/run_official_seal0.py:236`; archival reference, not bundled) |
| R7 | ROMA V2 说明全文 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/runtime/global_organizational_architecture_v2.txt`; archival reference, not bundled)、注入与 metadata 分离的桥接实现 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/roma/runtime/current_node_context.py`; archival reference, not bundled) |
| T1 | TalkHier 主管的 Joblist 与路由提示 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/multiagent/agent_team.py:47`; archival reference, not bundled)、成员上下文和局部历史 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/multiagent/agent_team.py:280`; archival reference, not bundled)、递归建组 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/multiagent/agent_team.py:385`; archival reference, not bundled) |
| T2 | 五个领域的原生配置 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/prompts/mmlu.py:3`; archival reference, not bundled)、机器可读 roster 与完整 team fixture (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/talkhier_benchmark_rosters.json`; archival reference, not bundled) |
| T3 | 原生实际 benchmark 分派 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/experiments.py:184`; archival reference, not bundled)、Pro Physics 的原生配置映射 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/repro/benchmark_data.py:54`; archival reference, not bundled)、upstream 文件清单 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/talkhier_upstream_file_inventory.json`; archival reference, not bundled)、广告提示字符串 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/prompts/ad.py`; archival reference, not bundled) |
| T4 | 原生工具清单 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/src/multiagent/tools.py`; archival reference, not bundled)；完整领域工具索引位于 roster JSON |
| T5 | 真实 Physics 代表输入 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/evidence/talkhier_actual_physics_request_examples.json`; archival reference, not bundled)、全批次注入核验 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/prior_audit/audit.json`; archival reference, not bundled)；其他领域离线输入位于 sources/talkhier/fixtures |
| T6 | 流程、门禁与可选路径审计 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/repro/org_v2/FLOW_AUDIT.md`; archival reference, not bundled)、官方源码与论文差异核验 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/prior_audit/official_comparison.json`; archival reference, not bundled) |
| T7 | Physics V2 说明全文 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/repro/org_v2/global_organizational_architecture_v2_college_physics.txt`; archival reference, not bundled)、按角色注入实现 (`archive://2026-10-02/x/outputs/01a0fbb3-df0e-7863-8526-ce0074debb4f/roma_talkhier_visibility_comparison_20261007/sources/talkhier/frozen/repro/org_v2/adapter.py:54`; archival reference, not bundled) |

版本范围：ROMA native a6e3bb4f9e0694375fa627fa4b8bf8cae50592a6；TalkHier official upstream 842a62160bcd326c5f8bb11c6cd1f3da7ced00f6，真实 Pro Physics 批次 runtime 0cddfdc3581bafb969b9d71e68dbeca1c4e6bdde。TalkHier 原生 MMLU prompt、ad.py 与 experiments.py 对固定 upstream 字节一致；agent_team/react_agent 的既有 provider 边界兼容差异已在独立官方对照审计中归一化核验，不能称整个 runtime 是未经修改的 upstream。ROMA Pilot 的 provider 预算改动和 dirty diff 已留在 source snapshot manifest；不能仅凭 HEAD 把它称为完全干净工作树。
