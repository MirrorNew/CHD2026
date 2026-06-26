# Influence Maximization related work and baseline plan

## Scope

This folder records native Influence Maximization (IM) baselines for the CHD multi-task extension. IM is not network dismantling: the objective is to choose a seed set of size `k` that maximizes expected diffusion spread under a propagation model, most commonly Independent Cascade (IC) or Linear Threshold (LT).

The previous local `IM_native_baseline` centrality/proxy code should not be presented as a true IM baseline. It has been replaced with IC-native implementations in `src/baselines/IM_native_baseline`.

## Native baseline families

| Family | Representative algorithms | Venue/status | Use in CHD paper |
|---|---|---:|---|
| Monte-Carlo greedy | Greedy under IC/LT | Kempe, Kleinberg, Tardos, KDD 2003 | Strong-quality but slow reference on small graphs |
| Lazy greedy | CELF, CELF++ | CELF: Leskovec et al., KDD 2007; CELF++: Goyal et al. | Strong traditional baseline; practical on small/medium graphs |
| Fast IC heuristics | DegreeDiscount-IC, PMIA/MIA | Chen et al., KDD 2009/KDD 2010 | Good root choice: simple, fast, recognizably IM-native |
| LT-specific heuristic | SimPath | Goyal et al., ICDM 2011 | Use only if LT task is included |
| RR/sketch approximation | RIS, TIM/TIM+, IMM, SSA/D-SSA, OPIM/OPIM-C | SODA 2014, SIGMOD 2014/2015/2016/2018, PVLDB 2017 | Main strong native baselines for serious experiments |
| Recent scalable systems | PaC-IM, FuseIM, eIM | PVLDB 2023/2024, ICS 2024, CIKM 2025 | Cite as recent strong systems; use only if environment supports C++/GPU/HPC |
| Recent heuristics | DomIM, ClusterGreedy-LT | Frontiers in Physics 2021, Information 2024 | Recent heuristic supplements; less authoritative than KDD/SIGMOD baselines |

## Strong baseline recommendations

1. **Minimum defensible experiment set**
   - DegreeDiscount-IC: fast root/simple heuristic.
   - CELF: traditional strong greedy baseline.
   - Fixed RR-set greedy: lightweight RIS-style smoke baseline.
   - IMM or OPIM-C: strong published RR-set baseline for final large experiments.

2. **Best root strategy for CHD**
   - Recommended root: **DegreeDiscount-IC**.
   - Reason: it is native to IC influence maximization, deterministic, very fast, and has a clear published origin. It gives CHD an IM-specific starting point without spending the search budget on expensive Monte-Carlo evaluation.
   - Alternative root: **RR-set greedy with a small fixed sample budget**. This is closer to TIM/IMM/OPIM mechanics, but noisier and less simple.
   - Avoid as root: PageRank/two-hop coverage/community-degree unless explicitly labeled as centrality heuristics, not native IM baselines.

3. **Strong final baseline**
   - Use **OPIM-C** if a C++14 compiler is available. The official code supports Windows/*nix and IC/LT with WC/TRI/UNI/load probability settings.
   - Use **IMM/TIM+** when OPIM-C is not convenient but RR-set approximation is required.
   - Use **NetMax** for Python-only prototyping; it implements MC-Greedy, CELF, CELF++, DegreeDiscount, RIS, TIM, TIM+, IC, and LT, but pip/git install timed out in the current run, so it was not used as the local smoke dependency.

## Local implementation status

Implemented in `src/baselines/IM_native_baseline/algorithms.py`:

- `degree_discount_ic_seed_order`
- `greedy_mc_seed_order`
- `celf_seed_order`
- `celfpp_seed_order`
- `mia_seed_order`
- `rr_greedy_seed_order`
- `imm_seed_order`
- `domim_seed_order`
- `cluster_greedy_lt_seed_order`
- `estimate_ic_spread`

Smoke test on `src/dataset/smoke.edgelist`:

```text
nodes=12 edges=12 k=3 p=0.1 eval_sims=512
DegreeDiscountIC: seeds=[2, 9, 7] spread=3.727
MCGreedy: seeds=[1, 4, 6] spread=3.754
CELF: seeds=[1, 10, 7] spread=3.773
CELF++: seeds=[2, 10, 8] spread=3.787
MIA-PMIA-family: seeds=[2, 5, 8] spread=3.787
RRGreedy: seeds=[7, 1, 5] spread=3.781
IMM-style: seeds=[7, 1, 5] spread=3.781
DomIM-2021: seeds=[2, 8, 10] spread=3.781
ClusterGreedy-LT-2024: seeds=[7, 3, 10] lt_spread=7.852
```

Re-run command:

```powershell
$env:PYTHONPATH='src'
C:\Users\ROG\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe src\baselines\IM_native_baseline\run_smoke.py
```

This smoke result only proves that the interfaces run on a tiny graph. It must not be reported as a main experimental average.

## Recent Python3 heuristic reproductions

| Method | Year | Model | Source authority | Reproduction status |
|---|---:|---|---|---|
| DomIM | 2021 | IC-style influence evaluation | Frontiers in Physics; peer-reviewed, but not top IM venue | Implemented as `domim_seed_order`: dominating-set initialization + uncorrelated-degree candidate set + local exchange search |
| ClusterGreedy-LT | 2024 | LT | Information; peer-reviewed, not top IM venue | Implemented as `cluster_greedy_lt_seed_order`: graph partition + subgraph greedy + knapsack/ILP-equivalent budget combination |

Important boundary: recent methods such as HDIM, balanced IM with DRL/GNN, dynamic IM, and homophily-aware IM often require node attributes, dynamic graph snapshots, learned representations, or training code. They should not be treated as precise native baselines on plain `.edgelist` graphs unless their required inputs are reconstructed explicitly.

External GitHub smoke:

```text
Source: geopanag/DiffuGreedy-Influence-Maximization, PMIA.py/runIAC.py
Adaptation: temporary 2to3 conversion under .codex_tmp/pmia_py3; matplotlib import made optional
Graph: smoke.edgelist converted to a bidirectional IC graph
Result: PMIA-open-source-converted: nodes=12 edges=24 seeds=[2, 5, 8] spread=3.785
```

This validates that a real open-source PMIA implementation can be made runnable on the smoke graph, but the code is Python-2-era and should not be merged directly without a clean port and license/header preservation.

## Open-source baseline candidates

| Codebase | Algorithms | Practical status |
|---|---|---|
| `tangj90/OPIM` | OPIM, OPIM-C | Strongest practical candidate; needs C++14 compiler |
| `thang-dinh/Stop-and-Stare-1` | SSA, D-SSA | Strong RR-set baseline; C++/legacy build expected |
| `pnnl/ripples` | scalable IM framework | Good C++ framework, heavier Conan/C++ dependency |
| `ucrparlay/Influence-Maximization` | PaC-IM | Recent PVLDB-scale system; needs Linux-like C++17/parallel environment |
| `lorenzobloise/netmax` | MC-Greedy, CELF, CELF++, DegreeDiscount, RIS, TIM/TIM+ | Best Python candidate; install timed out in this environment |
| `geopanag/DiffuGreedy-Influence-Maximization` | PMIA wrapper and diffusion-greedy scripts | Cloned successfully; PMIA smoke passed after temporary `2to3` conversion |

## Key references and URLs

- Kempe, Kleinberg, Tardos. "Maximizing the Spread of Influence through a Social Network." KDD 2003. https://dl.acm.org/doi/10.1145/956750.956769
- Leskovec et al. "Cost-effective Outbreak Detection in Networks." KDD 2007. https://dl.acm.org/doi/10.1145/1281192.1281239
- Chen, Wang, Yang. "Efficient Influence Maximization in Social Networks." KDD 2009. https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/weic-kdd09_influence.pdf
- Chen, Wang, Wang. "Scalable Influence Maximization for Prevalent Viral Marketing in Large-Scale Social Networks." KDD 2010. https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/msr-tr-2010-2_v2.pdf
- Borgs et al. "Maximizing Social Influence in Nearly Optimal Time." SODA 2014. https://arxiv.org/abs/1212.0884
- Tang, Xiao, Shi. "Influence Maximization: Near-Optimal Time Complexity Meets Practical Efficiency." SIGMOD 2014. https://dl.acm.org/doi/10.1145/2588555.2593670
- Tang, Shi, Xiao. "Influence Maximization in Near-Linear Time: A Martingale Approach." SIGMOD 2015. https://dl.acm.org/doi/10.1145/2723372.2723734
- Huang et al. "Revisiting the Stop-and-Stare Algorithms for Influence Maximization." PVLDB 2017. https://www.vldb.org/pvldb/vol10/p913-Huang.pdf
- Tang et al. "Online Processing Algorithms for Influence Maximization." SIGMOD 2018. https://dl.acm.org/doi/10.1145/3183713.3183749
- Zhu et al. "A Local Search Algorithm for the Influence Maximization Problem." Frontiers in Physics 2021. https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2021.768093/full
- Agra and Samuco. "A New Algorithm Framework for the Influence Maximization Problem Using Graph Clustering." Information 2024. https://doi.org/10.3390/info15020112
- Wang et al. "Fast and Space-Efficient Parallel Algorithms for Influence Maximization." PVLDB 2023/2024. https://www.vldb.org/pvldb/vol17/p400-wang.pdf
- Neff et al. "FuseIM: Fusing Probabilistic Traversals for Influence Maximization on Exascale Systems." ICS 2024. https://dl.acm.org/doi/10.1145/3650200.3656621
- Doney, Huang. "eIM: GPU-Accelerated Efficient Influence Maximization in Large Social Networks." CIKM 2025. https://dl.acm.org/doi/10.1145/3731599.3767442
- NetMax Python library. https://github.com/lorenzobloise/netmax
- OPIM official code. https://github.com/tangj90/OPIM
- Stop-and-Stare code. https://github.com/thang-dinh/Stop-and-Stare-1
- Ripples framework. https://github.com/pnnl/ripples
- PaC-IM code. https://github.com/ucrparlay/Influence-Maximization
