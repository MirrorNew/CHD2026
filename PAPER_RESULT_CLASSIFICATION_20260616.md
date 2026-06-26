# CHD2026 analyze_past_results 清理说明

日期：2026-06-16

## 结论

`CHD2026/analyze_past_results` 原先复制过来的内容主要是历史诊断、失败分析、
调参探索和早期机制验证，不是当前
`HAST2026/main/docs/15_chinese_paper_full_cn.md` 的直接图表来源。

当前论文直接使用或讨论的结果已经整理到：

`CHD2026/runs/paper_evidence_20260616`

其中包含 motivation、12 图 benchmark、搜索来源与 5.3 消融、Q/S 内部可解释性、
scaling、critical threshold / collapse point 以及 selected candidate lineage。

## 原 analyze_past_results 中各目录状态

| 原目录 | 是否写入当前论文主结果 | 处理 |
|---|---|---|
| `stage1_powerlaw500_exploration` | 否。早期 Powerlaw500 探索材料，已被当前 motivation/source-table 口径替代。 | 已归档 |
| `stage2_stage3_compression_analysis` | 否。早期压缩分析，不是当前正文图表路径。 | 已归档 |
| `target_family_budget_policy_experiments` | 否。早期 budget/policy 分析，不是当前正文图表路径。 | 已归档 |
| `target_family_stage123_mechanism_experiments` | 否。早期 Stage1/2/3 机制分析，当前论文采用 `artifacts/source_tables` 和 selected lineage。 | 已归档 |
| `real_graph_validation` | 否。旧 real graph validation，不是当前 12 图 benchmark 主表。 | 已归档 |
| `root_run_revision_diagnosis` | 否。诊断材料，不进入论文主结果。 | 已归档 |
| `simple_rank_multi_synth_proxy_20260527` | 否。pE 前置调参探索，不进入当前论文主结果。 | 已归档 |
| `pE1_pE2_gcc_failure_analysis_20260527` | 否。历史失败分析，可作为开发记录，不作为正文实验。 | 已归档 |
| `pE3_gcc_failure_analysis_20260528` | 否。历史失败分析，可作为开发记录，不作为正文实验。 | 已归档 |
| `pE4_qf1_common_network_time_20260529` | 否。qf1/finder 定位辅助材料，不是当前 HAST Q/S 主结果。 | 已归档 |
| `HAST_target_family_consolidated_conclusions_cn.md` | 否。早期汇总文档，不作为当前正文图表来源。 | 已归档 |
| `scripts` | 否。历史分析脚本。 | 已归档 |

## 归档位置

为避免误删证据，旧内容没有硬删除，而是移到：

`CHD2026/_archived_redundant_analyze_past_results_20260616`

若后续需要追溯 pE1/pE2/pE3 失败原因或旧 target-family 分析，可从该目录恢复。

## 当前干净规则

以后在 `CHD2026/analyze_past_results` 中只保留两类内容：

1. 当前论文主结果的轻量索引或解释文件；
2. 明确从 `CHD2026/runs/paper_evidence_20260616` 派生、且会进入论文正文/附录的分析。

其他调参探索、失败分析和旧候选比较应放到归档目录或新建带日期的临时分析目录，避免再次污染 CHD2026 的主结果边界。
