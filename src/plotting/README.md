# 绘图入口

这个文件夹只放论文图和诊断图的绘制代码。绘图层不负责搜索新算法；如果图需要新数据，应先运行 `src/experiments/` 下的实验入口，再由这里读取 CSV。

| 文件 | 作用 | 主要数据来源 | 输出位置 |
| --- | --- | --- | --- |
| `paper_figures.py` | 从已记录 CSV 重画主论文核心图。 | `artifacts/source_tables/benchmark_12graph/`、`motivation_observation/`、`search_runtime/`、`scaling/` | `artifacts/figures/` |
| `rebuild_paper_figures.py` | 按 `docs/15_chinese_paper_full_cn.md` 的引用收集图片到章节目录，并写 `figure_manifest.csv`。 | 现有引用图片与 `src/runs/runs_paper_evidence_20260616/` 备用图 | `artifacts/figures/<section>/` |
| `update_521_complexity_figure.py` | 绘制当前论文第 5.2.1 节复杂度-质量图。 | `src/runs/classic_r_recomputed_20260624/method_mean_classic_r.csv` | `artifacts/figures/05_2_benchmark/fig13_12graph_quality_complexity_all_methods.*` |
| `gen_fig30_hast_three_stage_search_tree.py` | 绘制附录阶段1/3搜索树可视化。 | 论文证据包中的 stage tree CSV/JSON | `artifacts/figures/appendix/fig30_*` |
| `plot_critical_threshold.py` | 绘制最低崩溃点/阈值相关图。 | 对应 source table 或运行记录 | `artifacts/figures/05_5_collapse/` |
| `plot_qs_internal_ablation.py` | 绘制 Q/S 内部消融图。 | 完整验证协议下的 Q/S 对照记录 | `artifacts/figures/` |
| `plot_hast_521_523.py` | 旧完整运行的第 5.2/5.3 图重画入口，仅在需要复核历史运行时使用。 | 已完成 run 目录 | `artifacts/figures/` |
| `gen_hast_framework_big.py`, `gen_hast_framework_gpt_image2.py` | 框架图辅助脚本，可生成或整理替代版框架图。 | 本地绘图代码或 `Gemini-Framework.png` 参考图 | `artifacts/figures/HAST-Framework-*` |

## 图像溯源

| `artifacts/figures` 中的图组 | 主要生成或收集路径 |
| --- | --- |
| `03_motivation/fig21_*`, `fig22_*`, `fig23_*`, `fig_obs1_*` | 由 `src/experiments/obs1_basic_baseline_horizontal.py` 和 `src/experiments/motivation_observation_experiments.py` 生成，再由 `src/plotting/rebuild_paper_figures.py` 收集。 |
| `04_method/Gemini-Framework.*` | 由 `src/plotting/rebuild_paper_figures.py` 从 `src/runs/runs_paper_evidence_20260616/00_framework_overview/figures/` 收集；本地框架图辅助脚本可生成替代图。 |
| `05_2_benchmark/fig10_*`, `fig11_*`, `fig17_*`, `fig20_*` | 由 `src/plotting/paper_figures.py` 从源表生成，或由 `src/plotting/plot_hast_521_523.py` 基于完整 run 重画；最终由 `rebuild_paper_figures.py` 收集。 |
| `05_2_benchmark/fig13_12graph_quality_complexity_all_methods.*` | 由 `src/plotting/update_521_complexity_figure.py` 生成，是当前草稿引用的 Fig. 13。 |
| `05_3_ablation/fig_5_3_hast_ablation_search_curves.*` | 由 `src/experiments/stage_search_ablation.py` 或 `src/scripts/run_stage_search_ablation.py` 生成，再由 `rebuild_paper_figures.py` 收集。 |
| `05_4_interpretability/fig24_*` 到 `fig29_*` | 由 `src/experiments/case_study_hast_s.py` 和 `src/experiments/case_study_hast_q.py` 生成，再由 `rebuild_paper_figures.py` 收集。 |
| `05_5_scaling/*scaling*` | 由 `src/experiments/current_hast_scaling.py` 或 `src/scripts/run_scaling.py` 生成，再由 `rebuild_paper_figures.py` 收集。 |
| `05_5_collapse/fig21_*`, `fig22_*` | 由 `src/plotting/plot_critical_threshold.py` 生成，再由 `rebuild_paper_figures.py` 收集。 |
| `appendix/fig30_*` | 由 `src/plotting/gen_fig30_hast_three_stage_search_tree.py` 生成。 |
