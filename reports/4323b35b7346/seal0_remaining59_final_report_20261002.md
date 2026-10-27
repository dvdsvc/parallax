# SEAL-0 剩余59题重复实验最终留档核查

核查时间：北京时间 2026-10-02 19:29:56。

共236次计划执行，全部已终止：226次正常完成、9次provider阻断、1次运行错误；未完成0。226次正常完成均有完整记录并通过条件验证，原生评分226/226，待评分0，评分错误0。阻断和运行错误未按零分计入。

| 条件 | 重复 | 正常完成 | 阻断 | 运行错误 | 原生评分覆盖 |
|---|---:|---:|---:|---:|---:|
| BASE | 1 | 59/59 | 0 | 0 | 59/59 |
| V2 | 1 | 56/59 | 3 | 0 | 56/56 |
| BASE | 2 | 56/59 | 3 | 0 | 56/56 |
| V2 | 2 | 55/59 | 3 | 1 | 55/55 |

异常记录：V2 repeat1阻断q6、q92、q96；BASE repeat2阻断q6、q55、q96；V2 repeat2阻断q6、q38、q96，q62出现原生JSONAdapter响应解析错误。阻断记录的provider错误类型为DataInspectionFailed。

归档校验：13963条文件校验记录，覆盖四个源Paper Run、四个评分工作目录及四个评分归档副本；异常0项。另核对226题原始结果、指标、记录清单与评分输入的哈希及逐题评分链接。原始checksum清单和归档均保留，评分归档各有独立checksum清单。

17项运行与原生评分源码、数据、配置哈希保持一致；原生agent的src与config未改动。8条独立MLflow记录（4条执行、4条评分）均为FINISHED，并存在结束时间。源归档的partial_or_error状态保留已发生的阻断或执行错误，不代表归档仍在运行。

## 留档位置

批次目录：archive://2026-09-12/hira/work/paper_studies/seal0_remaining59_repeats2_parallel4x4_20261002T080159Z

| 条件 | 重复 | 源Paper Run目录 | 执行MLflow ID | 评分MLflow ID |
|---|---:|---|---|---|
| BASE | 1 | archive://2026-09-12/hira/work/paper_runs/20261002T080800Z_BASE_seal0-remaining59-base-repeat1-20261002T080159Z | 4062ba97b1934353bdb5c3e0b61ddc0f | 50d082a0f6504ed6af58286c6f35884e |
| V2 | 1 | archive://2026-09-12/hira/work/paper_runs/20261002T080800Z_BASE_seal0-remaining59-v2-repeat1-20261002T080159Z | 44b911513d6845dcb1c8d3884c2cc301 | 3b9dde1dfef64304987b7c5031410da0 |
| BASE | 2 | archive://2026-09-12/hira/work/paper_runs/20261002T080800Z_BASE_seal0-remaining59-base-repeat2-20261002T080159Z | cea2970821904f7eb0e605064bb943d7 | 47d817952596420f919ed05ceb45f63c |
| V2 | 2 | archive://2026-09-12/hira/work/paper_runs/20261002T080800Z_BASE_seal0-remaining59-v2-repeat2-20261002T080159Z | c082928dcd8146d3974aac865e4b8080 | 1b7043b4e6674535a0df222fbe159386 |

评分产物位于各源Paper Run目录的grader子目录；逐题执行原始记录路径、阻断与错误证据、评分批次及完整哈希核查见同名JSON报告。

监控状态：最终留档核查通过，seal-0-59-10已通过应用自动化工具暂停。
