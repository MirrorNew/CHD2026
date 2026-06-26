# HAST 第 15 版论文数据来源记录

本文档记录 `15_chinese_paper_full_cn.md` 中各章图、表和关键数值的来源。路径均相对 `HAST2026/main/`。

## 总体说明

- 正文文件：`docs/15_chinese_paper_full_cn.md`
- 主 benchmark：12 个图，分别为 `CEnew`、`Collaboration`、`condmat`、`crime`、`email`、`Grid`、`GrQC`、`hamster`、`HepPh`、`PH`、`Powerlaw_500`、`Yeast`。
- 旧版 12 图汇总来源：`artifacts/source_tables/benchmark_12graph/`
- 当前 root-relative HAST run：`src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/`
- 当前 5.2 与 5.5.2 图像目录：`src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/`

## 按章节对应关系

| 章/节 | 正文内容 | 主要数据或图表来源 | 备注 |
|---|---|---|---|
| 摘要、引言 | HAST-Final-Q/S 的主结果、ERA-like 对比、CHD 动机 | 主要来自第 5.2、5.3、5.4、5.5 的最终表述 | 若 5.2 Q/S 表格刷新，摘要和第 6 章结论中的 Q/S 数字也必须同步刷新。 |
| 第 2 章 相关工作 | AHD、Harness Evo、LLM 程序搜索、网络瓦解对比 | 正文参考文献、`docs/HAST_定位以及引言.md`、`docs/14_chinese_paper_full_cn.md` | 该章主要是文献归纳，不依赖实验 CSV。 |
| 3.1 开放自由程序探索会导致复杂度漂移 | Relative-Free、CostAware-Free、Bounded-Guided 的候选复杂度和搜索成本观察 | `artifacts/source_tables/motivation_observation/e1_e3/e3_observation3_candidate_records.csv`；`artifacts/source_tables/motivation_observation/e1_e3/e3_observation3_group_summary.csv`；图 `artifacts/figures/fig23_bounded_generation_controls_scan_cost.png` | 用于支撑“开放自由程序探索会带来复杂度漂移，有界生成能抑制慢扫描”。 |
| 3.2 强 root 使高分不等于新机制 | R/GCC-only、Absolute-cNBI、Relative-Delta-cNBI 的 credit 分配观察 | `artifacts/source_tables/motivation_observation/e1_e3/e2_observation2_candidate_records.csv`；`artifacts/source_tables/motivation_observation/e1_e3/e2_observation2_group_summary.csv`；图 `artifacts/figures/fig22_relative_credit_allocation_effect.png` | 用于说明 root-relative credit 的必要性。 |
| 3.3 GCC/R 是最终目标但不能成为搜索的唯一来源 | 相同 GCC/R 下的残余碎裂差异、cNBI 区分能力 | `artifacts/source_tables/motivation_observation/e1_e3/e1_obs1_same_gcc_cnbi_cases.csv`；`artifacts/source_tables/motivation_observation/e1_e3/e1_obs1_same_gcc_cnbi_summary.csv`；`artifacts/source_tables/motivation_observation/obs1_basic_baseline/`；图 `artifacts/figures/fig21_obs1_basic_baseline_same_r_horizontal.png`、`artifacts/figures/fig_obs1_same_gcc_cnbi_bar.png` | 用于说明 GCC/R 可以作为最终目标，但搜索期需要 cNBI 作为残余碎裂传感器。 |
| 3.4 CHD 定义 | 收缩式启发式发现的定义和三类收缩(contractive) | 由 3.1-3.3 的动机实验归纳 | 该节不引入新实验数据。 |
| 第 4 章 方法 | HAST 三阶段机制、root-relative credit、Stage II 策略归纳、Stage III Pareto 输出 | 框架图 `artifacts/figures/Gemini-Framework.png`；当前 run 的 `input_parameters.json`、`root_proxy_metrics.json`、`stage1_candidate_log.csv`、`stage1_tree_nodes.csv`、`stage2/`、`stage3_candidate_log.csv`、`stage3_tree_nodes.csv`、`stage3_final_selection.json`、`stage3_pareto_frontier.json` | 第 4 章主要描述机制，运行文件用于确认阶段预算、日志字段和策略归纳结果。 |
| 5.1 实验设计 | 12 图 benchmark、baseline 组、指标定义、统计边界 | `artifacts/source_tables/benchmark_12graph/`；当前 run 的 `final/final_code_manifest.json`、`full_validation/e7_evaluation_manifest.json`、`full_validation/point_evaluation_manifest.csv` | baseline 名称与别名参考 `baseline_alias_policy.csv` 和 `baseline_reproduction_status.csv`。 |
| 5.2.1 质量-时间主结果 | 所有方法质量-时间散点图、主结果表、Top-10 表 | 新图：`src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/fig13_12graph_quality_runtime_all_methods.png`；旧 baseline 汇总：`artifacts/source_tables/benchmark_12graph/method_mean_metrics.csv`；当前 Q/S 汇总：`src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/full_validation/method_mean_metrics.csv` 与 `figures_5_2/figures_5_2_summary.json` | 当前正文 5.2 表格仍保留旧 Q/S 数值；若采用新 5.2 图，表格与摘要/结论应同步改为新 run 数值，并重新计算 all-method rank/top-k。 |
| 5.2.2 归一化质量-速度图 | 以 AlphaEvolve-like 为基准的 Q/S 质量与运行时间对比 | `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/fig17_hast_quality_speed_panel.png`；对应汇总同 5.2.1 | 与 5.2.1 同源，不能与旧 Q/S 表格混用。 |
| 5.2.3 GCC 与 cNBI 曲线 | 12 图 GCC/R 曲线和 cNBI 曲线 | `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/fig10_gcc_curves_12graphs.png`；`src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/fig11_cnbi_curves_12graphs.png`；逐图曲线来自当前 run `full_validation/point_evaluations/` 与旧 baseline `artifacts/source_tables/benchmark_12graph/<dataset>/point_evaluations/` | 用于检查 HAST 是否仍服务 GCC/R 网络瓦解目标，并补充 cNBI 过程碎裂解释。 |
| 5.2.4 搜索成本 | Stage I/II/III 预算、有效率、prompt 时间、validation 时间 | 图 `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/fig20_framework_search_time.png`；`artifacts/source_tables/search_runtime/framework_search_time_summary.csv`；当前 run 的 `stage1_tree_nodes.csv`、`stage3_tree_nodes.csv`、`stage2/policy_replay_report.md` | 最终候选 runtime 与离线 LLM 搜索成本分开报告。 |
| 5.3 消融实验 | 独立采样、无时间压力、无 Stage II bounds、不同 selection credit 的对照 | `artifacts/source_tables/hast_53_ablation/table_5_3_ablation_summary.csv`；`artifacts/source_tables/hast_53_ablation/pool_summary_proxy.csv`；图 `artifacts/figures/fig_5_3_hast_ablation_search_curves.png` | 该节验证搜索机制，不是单个最终算法的组件消融。 |
| 5.4.1 自由探索日志的可解释性 | 日志观察到的有效局部机制和失败模式 | 当前 run 的 `stage1_candidate_log.csv`、`stage3_candidate_log.csv`、`stage2/code_feature_table.csv`、`stage2/failure_patterns.json`、`stage2/family_summary.csv`、`stage2/family_policy.json` | 用于说明 Stage II 策略归纳并非凭空生成，而是来自执行日志。 |
| 5.4.2 HAST-Final-Q 机制解释 | Q（`cd9e3818033d`）的组件 knockout、早期节点特征、打分项分解、lineage | `artifacts/source_tables/case_study_hast_s/`；图 `artifacts/figures/fig24_hast_s_component_knockout.png`、`fig25_hast_s_early_node_features.png`、`fig26_hast_s_score_decomposition.png`；脚本 `src/experiments/case_study_hast_s.py` | 脚本名保留早期 source-label；正文最终映射以 Q=`cd9e3818033d`、S=`0ade8d3405c2` 为准。case-study runtime 用同一脚本内比较；正文主表 runtime 以 full validation 为准。 |
| 5.4.3 HAST-Final-S 机制解释 | S（`0ade8d3405c2`）的组件 knockout、早期节点特征、打分项分解、lineage | `artifacts/source_tables/case_study_hast_q/`；图 `artifacts/figures/fig27_hast_q_component_knockout.png`、`fig28_hast_q_early_node_features.png`、`fig29_hast_q_score_decomposition.png`；脚本 `src/experiments/case_study_hast_q.py` | 脚本名保留早期 source-label；用于说明 S 的局部项对排序和过程碎裂质量有实质贡献。 |
| 5.5.1 扩展性实验 | 500 到 10k full-evaluation scaling，500 到 1M runtime-only scaling | `artifacts/source_tables/scaling/current_hast_full_eval_500_to_10k.csv`；`artifacts/source_tables/scaling/full_eval_500_to_10k_unified.csv`；`artifacts/source_tables/scaling/current_hast_runtime_only_500_to_1000k.csv`；`artifacts/source_tables/scaling/runtime_only_500_to_1000k_unified.csv`；图 `artifacts/figures/scaling_full_eval_500_to_10k_unified.png`、`artifacts/figures/runtime_only_scaling_500_to_1000k_unified.png` | 该节只声明可执行的大图上界证据，不声明最快实现。 |
| 5.5.2 崩溃点分析 | CT@0.10、CT@0.05、CT-1% nodes | 脚本 `src/plotting/plot_critical_threshold.py`；图和表均来自 `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/` 下的 `critical_threshold_ratio_summary.csv`、`critical_threshold_ratio_values.csv`、`critical_threshold_1pct_nodes_summary.csv`、`critical_threshold_1pct_nodes_values.csv`、`fig21_gcc_critical_threshold_mean.png`、`fig22_gcc_critical_threshold_ct10_heatmap.png`、`fig21_gcc_critical_threshold_1pct_nodes_mean.png`、`fig22_gcc_critical_threshold_1pct_nodes_12graphs.png` | 原 `docs/15_section_5_5_2_critical_threshold_data_sources.md` 的内容已并入本总来源文件。 |
| 第 6 章 结论 | HAST 的总结果、边界和贡献 | 汇总自 5.2、5.3、5.4、5.5 | 若 5.2 表格换为新 run，结论中的 Q/S 数字和相对 ERA-like 比例也必须同步改。 |
| 附录 A 符号表 | 符号定义 | 第 3、4、5 章公式和指标定义 | 无独立实验数据。 |

## 5.2 当前同步状态

第 5.2 节已使用 `figures_5_2` 下的新图，并将正文、当前 full validation CSV、`artifacts/source_tables/benchmark_12graph/` 中的 HAST-Final-Q/S 标签统一为 Q=`cd9e3818033d`、S=`0ade8d3405c2`。当前 run 的 Q/S 均值为：

| method | candidate_id | datasets | mean R ↓ | mean auc-cNBI ↑ | mean time ↓ |
|---|---|---:|---:|---:|---:|
| HAST-Final-S | `0ade8d3405c2` | 12 | 0.3656505747 | 362.8152162 | 0.605584s |
| HAST-Final-Q | `cd9e3818033d` | 12 | 0.3563732544 | 347.0674339 | 1.181991s |

这些数值来自：

- `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/full_validation/method_mean_metrics.csv`
- `src/runs/runs_HAST_root_pE4_smoke_elite_guard_online_20260528/figures_5_2/figures_5_2_summary.json`

已同步项：

- 5.2.1 主结果表中 HAST-Final-Q/S 两行。
- 5.2.1 Top-10 表中的 Q/S 排名、mean R、mean auc-cNBI、mean time、top-k/rank 字段。
- 5.2.1、5.2.2、5.2.3、5.2.4 中引用 Q/S mean auc-cNBI、mean R、mean time 的正文。
- 摘要和第 6 章结论中的 Q/S 数值、相对 ERA-like 比例和加速比。
- 当前 paper evidence run 的 `full_validation/method_mean_metrics.csv`、`full_validation/per_graph_metrics.csv`、逐图 `method_summary.csv`、`stage3_final_selection.json`、`final/final_code_manifest.json` 和 `final/HAST-Final-Q.py` / `final/HAST-Final-S.py`。

注意：`full_validation/method_mean_metrics.csv` 只包含当前 Q/S 两个候选；all-method 的 `top1 auc`、`top3 auc`、`mean rank auc` 已按当前 full-validation 结果写入正文和当前 source table。若后续重新加入更多候选，应与 `artifacts/source_tables/benchmark_12graph/per_graph_metrics.csv` 或逐图结果合并后重新计算。

## 5.5.2 崩溃点指标定义

- `CT@0.10`：逐点 GCC 曲线中第一次满足 `GCC <= 0.10` 的 removal ratio；使用相邻采样点线性插值；越低越好。
- `CT@0.05`：逐点 GCC 曲线中第一次满足 `GCC <= 0.05` 的 removal ratio；使用相邻采样点线性插值；越低越好。
- `CT-1% nodes`：逐点 GCC 曲线中第一次满足 `GCC <= 0.01` 的整数删除步数 `step`；不插值；越低越好。
- 如果某方法在记录曲线内没有达到对应阈值，ratio 指标记录最后一个 removal ratio 并标记 `reached=false`，node 指标记录最后一个 step 并标记 `reached=false`；正文表格用 reached graphs 标记实际达标图数。

## 复现和刷新建议

- 第 3 章动机实验若重跑，优先使用 `src/scripts/run_motivation_experiments.py` 并刷新 `artifacts/source_tables/motivation_observation/` 与对应 `artifacts/figures/`。
- 第 5.2 节若重画，优先使用 `src/plotting/plot_hast_521_523.py` 或当前生成流程对应脚本，并保证图、表、摘要、结论来自同一批 Q/S full validation。
- 第 5.5.2 节若重画，使用：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
& 'C:\Users\ROG\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'CHD2026\src\plotting\plot_critical_threshold.py' `
  'CHD2026\src\runs\runs_HAST_root_pE4_smoke_elite_guard_online_20260528'
```

