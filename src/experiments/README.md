# 实验入口

这个文件夹只保留当前论文和复现实验需要的实验入口，不再使用日期后缀或 `e4/e6/e7` 这类内部代号。

| 文件 | 作用 | 生成表格 | 生成图片 |
| --- | --- | --- | --- |
| `chd_main_search.py` | 准备或执行 CHD 阶段1/2/3搜索，并可选调用完整验证。 | 是 | 否 |
| `full_validation.py` | 对阶段3固定的 `HAST-Final-Q/S` 做完整 12 图验证，输出可接入论文表格的结果。 | 是 | 否 |
| `stage_search_ablation.py` | 第 5.3 节阶段搜索消融：独立采样、无时间感知、无阶段2边界等对照。 | 是 | 是 |
| `motivation_observation_experiments.py` | 运行动机实验，包括 cNBI 同 GCC 柱状图，以及观察2/3的确定性代理实验。 | 是 | 是 |
| `obs1_basic_baseline_horizontal.py` | 基于固定 Collaboration 案例表重画观察1横向对比图。 | 是 | 是 |
| `paper_source_tables.py` | 同步并规范化已有实验 CSV 到 `artifacts/source_tables/`。 | 是 | 否 |
| `convert_network_data_for_baselines.py` | 将 `network/Data/Data` 转为 baseline 可读边列表，并写 manifest。 | 是 | 否 |
| `recompute_classic_r_from_sequences.py` | 从可信删除序列或 fallback baseline 重算经典完整序列 R 表。 | 是 | 否 |
| `current_hast_scaling.py` | 刷新当前 CHD/HAST-Final-Q/S 的规模扩展证据。 | 是 | 是 |
| `case_study_hast_q.py`, `case_study_hast_s.py` | 生成 HAST-Final-Q/S 的机制案例分析表和图。 | 是 | 是 |
| `audit_main_layout.py` | 检查当前主目录是否包含预期代码、数据镜像和入口。 | 否 | 否 |
| `audit_paper_data_alignment.py` | 检查论文图表与源表是否对齐。 | 是 | 是 |
| `motivation_observation_contract.py`, `scaling_contract.py` | 记录当前实验协议、预算和数据范围。 | 否 | 否 |

主搜索逻辑位于 `experiments/chd_main_search.py` 和 `model/stage1_stage3_search.py`。完整验证逻辑位于 `experiments/full_validation.py`，`src/scripts/run_full_validation.py` 只是薄命令入口。

已经删除的旧探针、旧本地路径绑定脚本不再作为复现入口。若需要重画论文图，优先使用 `src/plotting/README.md` 中列出的正式绘图脚本。
