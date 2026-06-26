# IM 原生基线

这个包对应 Influence Maximization 的原生 baseline 边界。当前实现只保留 IC 模型下的真实 IM 算法，不再使用 PageRank/two-hop coverage 这类伪 IM 代理作为主 baseline。

- `degree_discount_ic_seed_order`：Chen et al. KDD 2009 的 DegreeDiscount-IC 思路，适合作为复杂度很低的 root。
- `greedy_mc_seed_order`：Kempe et al. KDD 2003 的 Monte-Carlo greedy 框架，质量强但慢。
- `celf_seed_order`：Leskovec et al. KDD 2007 的 lazy-forward greedy/CELF，保持 greedy 目标但减少重复边际评估。
- `celfpp_seed_order`：CELF++ 风格复现，缓存候选的二阶 lazy 信息。
- `mia_seed_order`：MIA/PMIA-family Python3 复现，用最大概率路径近似 IC 影响力。
- `rr_greedy_seed_order`：固定样本 RR-set/RIS greedy，用于 smoke 和接口验证。
- `imm_seed_order`：IMM-style RR-set 双阶段采样复现，带样本上限；完整强 baseline 仍建议用官方 C++ IMM/OPIM-C 做最终大实验。
- `domim_seed_order`：DomIM 风格复现，2021 年提出的 dominating-set local search 强启发式，IC 评估。
- `cluster_greedy_lt_seed_order`：ClusterGreedy 风格复现，2024 年提出的聚类 + 子图 greedy + 预算组合框架，LT 评估。

默认接口返回完整 seed order；论文实验应截取前 `k` 个种子，并用统一 IC/LT 扩散评估器报告平均 spread。
