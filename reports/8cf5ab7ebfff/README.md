# FRAMES 150题与前5题预算子集

2026-10-06。从官方固定版本58d9fb6330f3ab1316d1eca12e5e8ef23dcc22ef的全部824题抽150题。按用户要求，历史接触过的题目仍可入样，不做排除。当前只冻结数据，agent和grader均未启动。

## 入口

- `frames150_index.xlsx`：150题固定顺序、预算5题、全824题三个可筛选工作表；参考答案只保存在原生数据文件中。
- `sample150_index.jsonl` / `sample150_index.csv`：按冻结顺序排列的150题索引，含题干、官方ID、层、权重及各数据文件加载位置。
- `pilot5_index.jsonl` / `pilot5_index.csv`：严格等于上述索引的前5条。
- `sample150_native_test.tsv` / `sample150_tasks_native.jsonl`：原始题干、参考答案和字段，保留源数据顺序。
- `pilot5_native_test.tsv` / `pilot5_tasks_native.jsonl`：预算测试原生数据，原始字段同样保留。
- `frozen_execution_plan.json`：150题和5题各自的运行顺序及对应原生加载位置。
- `sampling_script_snapshot.py`、`command.txt`、`protocol_before_draw.json`、`selection_manifest.json`、`verification.json`、`checksums.sha256`：抽样留档及核验证据。

## 固定抽样与顺序

8个互斥穷尽层为Wikipedia证据篇数2/3/4/5+与推理标签数量1/2+的交叉。按总体比例用最大余数法分配150题，余数相同按层名称排序；层内按官方数字ID排序后使用独立的抽样随机数生成器无放回抽取。

抽样seed=20261006。先冻结150题成员，再将其官方数字ID排序，用独立order seed=20261007打乱并冻结运行顺序。前5题直接截取该顺序，不再抽样、不按费用或结果挑选，也不搜索seed。

| 分层 | 全集题数 | 抽取题数 | 比例差(百分点) |
|---|---:|---:|---:|
| E2_L1 | 195 | 35 | -0.332 |
| E2_L2+ | 115 | 21 | +0.044 |
| E3_L1 | 135 | 25 | +0.283 |
| E3_L2+ | 153 | 28 | +0.099 |
| E4_L1 | 52 | 9 | -0.311 |
| E4_L2+ | 82 | 15 | +0.049 |
| E5+_L1 | 39 | 7 | -0.066 |
| E5+_L2+ | 53 | 10 | +0.235 |

最大层比例差为0.332个百分点，总变差为0.709%。这是抽样元数据平衡，不是性能或费用结果。

| 推理标签 | 全集占比 | 150题占比 |
|---|---:|---:|
| Numerical reasoning | 35.6% | 34.7% |
| Tabular reasoning | 28.6% | 28.0% |
| Multiple constraints | 66.6% | 63.3% |
| Temporal reasoning | 33.7% | 31.3% |
| Post processing | 13.0% | 12.7% |

同一题可有多个推理标签。覆盖全部5类标签，完整组合覆盖26/30；粗分层不保证每个细组合比例完全相等。

## 预算测试前5题

| 固定序号 | 官方题号 | 证据篇数 | 分层 | 150题加载位置 | 5题加载位置 |
|---|---:|---:|---|---:|---:|
| 1 | 42 | 3 | E3_L1 | 147 | 2 |
| 2 | 555 | 3 | E3_L1 | 49 | 4 |
| 3 | 295 | 3 | E3_L2+ | 116 | 0 |
| 4 | 729 | 2 | E2_L1 | 91 | 3 |
| 5 | 84 | 2 | E2_L2+ | 32 | 1 |

官方题号顺序：42, 555, 295, 729, 84。这5题用于测试预算设置与调用路径；证据篇数只有2或3，不能据此声称150题的成本长尾已受控，也不是单独的分层5题性能样本。

## 运行时保持顺序

原生`load_frames_dataset`即使`no_split=True`也会按seed打乱数据。这里各TSV保留源顺序，原生loader seed固定为0。运行时应从`frozen_execution_plan.json`读取对应数据文件及`ordered_selected_indices`，不要把官方题号当加载位置，也不要直接使用`range(5)`或`range(150)`。

使用独立5题TSV时，选题位置按冻结顺序为[2, 4, 0, 3, 1]；使用150题TSV只跑前5题时，位置为[147, 49, 116, 91, 32]。两者对应同一组官方题号。JSON中的文件名相对于本归档目录解析。

这里固定的是提交顺序；并发执行的实际完成顺序可能不同。比较预算设置时使用同一5题、相同模型、工具及执行限制，单独标记每个预算条件。正式150题运行应冻结预算后执行；不同预算的pilot输出不得直接混入正式成绩。如使用pilot正确率调参，应披露这一开发接触。

## 复现与分析

原始824题TSV、JSONL及原生加载器源文件均已保存快照。原始字段、题干和答案没有修改；原生加载器函数核对了824+150+5=979条题干及答案映射。独立进程重放15份核心文件逐字节一致，27项核验通过。旧80题档案保留。

在新的输出目录运行以下命令可复现相同150题和前5题；脚本会拒绝覆盖已有目录：

```sh
external_home/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 archive://2026-10-02/frames/outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames150_full824_20261006/sampling_script_snapshot.py --output /private/tmp/frames150_reproduction_new_directory --sample-size 150 --pilot-size 5 --sampling-seed 20261006 --order-seed 20261007 --loader-seed 0 --source-tsv archive://2026-10-02/frames/outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames150_full824_20261006/full824_native_test.tsv --source-tasks archive://2026-10-02/frames/outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames150_full824_20261006/full824_tasks_native.jsonl --loader-source archive://2026-10-02/frames/outputs/01a0fab2-cbaa-76a2-85e2-9f7af4712cf1/frames150_full824_20261006/native_loader_source_snapshot.py
```

正式BASE/V2比较使用同一150题。每题先合并有效成对重复，再按各层总体权重N_h/824汇总，并附题目等权结果；阻断、错误和缺失单列。预算pilot不产生论文性能结论。当前没有付费运行、评分或新建MLflow执行记录。
