

# 摘要

网络瓦解启发式通常以最大连通分量随删除比例的变化作为核心评价，但当大语言模型在程序空间中自动发现新启发式时，这类最终指标并不足以治理搜索过程：候选程序可能因为继承强 root heuristic 而取得高分，却没有贡献新的瓦解机制；也可能通过无界二跳扫描、频繁全图重算或复杂中心性重算追逐短期碎裂收益，最终变得缓慢且不可解释。本文提出 Contractive Heuristic Discovery (CHD)，即收缩式启发式发现，一种面向强先验组合优化任务的发现范式：先允许 LLM 开放探索候选结构假设，再用任务证据将候选语言收缩(contractive)为可归因、可解释、可部署的机制空间。基于 CHD，本文提出 HAST，一个面向网络瓦解的收缩式启发式发现实例。HAST 用 cNBI 感知 GCC/R 之外的残余碎裂形态，用 root-relative credit 剥离强 root 的继承贡献，并将自由搜索日志压缩为有界图操作策略，从而限制无界慢扫描、保留局部边界/弱连接/冗余抑制等有效机制。在 12 图 benchmark 的 classic full-sequence R 口径下，HAST-Final-S 对应候选 `0ade8d3405c2`，达到 mean R 11.52%、mean auc-cNBI 362.815、mean time 0.606s；HAST-Final-Q 对应候选 `cd9e3818033d`，达到 mean R 11.48%、mean auc-cNBI 347.067、mean time 1.182s。结果表明，HAST 的核心贡献不是把通用 LLM 搜索器直接套到网络瓦解上，而是把网络瓦解中的强 root、粗反馈和复杂度漂移显式转化为信用、传感和候选语言收缩问题。

**关键词**：网络瓦解；收缩式启发式发现；LLM 程序搜索；信用分配；有界候选语言；复杂网络

# 1 引言

网络瓦解问题研究如何通过删除少量关键节点快速破坏网络连通性。给定图 $G=(V,E)$ ，典型目标是构造节点删除序列 $\pi=(v_1,\ldots,v_n)$，使删除前缀后最大连通分量尽快缩小。该问题在复杂系统鲁棒性、基础设施风险分析和信息传播控制中都有重要意义。已有工作已经提出了从中心性、2-core、消息传递、优化近似到学习式策略的一系列方法，它们回答了一个核心问题：给定网络，如何设计高质量删除序列。 

LLM 程序搜索提供了另一条路径。与人工设计单个启发式不同，LLM 可以在可执行程序空间中生成、评估和迭代候选算法。FunSearch、ReEvo、HSEvo、AlphaEvolve 等工作表明，LLM 与自动评估器、进化或树搜索机制结合后，可以发现具有竞争力的程序或启发式。近年的 Harness Evolution 工作进一步把接口、历史轨迹、执行日志、记忆、上下文和可回滚修改纳入自动优化循环，使“生成候选程序”逐渐变成“生成并治理候选行为”。对于网络瓦解而言，这条路线看似自然：把一个启发式写成函数，让 LLM 修改代码，用评价器检查删除序列质量，再保留高分候选。

然而，网络瓦解并不是通用 AHD 或 Harness Evo 中常见的“给定 evaluator 后扩大候选搜索”的简单实例。第一，网络瓦解存在强 root heuristic。HDA、degree、CoreHD 等简单规则已经提供很强的一阶结构骨架，候选程序的绝对高分可能主要来自继承，而不是来自 LLM 新增机制。第二，GCC/R 是最终瓦解目标所必需的指标，却不是充分的搜索传感器；两个候选可以具有相同最大连通分量，却留下完全不同的残余碎裂形态。第三，网络图操作天然存在高成本捷径：无界二跳、每步 connected components、全图中心性重算和重复邻域枚举都可能在小图 proxy 上制造短期收益，却损害可解释性和可部署性。

这些现象说明，网络瓦解中的 LLM 启发式发现首先是一个搜索范式问题：开放探索当然有价值，但搜索不能长期停留在无限制程序空间中。它必须从“发现可能有效的结构假设”进一步走向“用任务证据收缩候选语言”。本文将这一范式称为 **Contractive Heuristic Discovery (CHD)**，即收缩式启发式发现。CHD 先允许 LLM 在较开放的候选空间中暴露潜在机制、失败模式和复杂度风险，再把日志证据压缩为可检查的候选策略，使后续搜索集中在有归因、有边界、能部署的机制空间。

本文提出 HAST，作为 CHD 在网络瓦解上的实例。HAST 将候选程序统一为 `degree_order(G) -> removal_order` 接口，并在统一评价器下记录 $R$、auc-cNBI 和运行时间。cNBI 用于补充 GCC/R 对残余碎裂形态的刻画；root-relative credit 用于把 root 已有能力从候选信用中扣除；time-aware credit 用于把计算代价提前纳入搜索；log-induced bounded candidate language 则把自由搜索日志中反复出现的有效局部机制压缩为有上界的图操作策略。

本文的贡献可以概括为四点。

1. 我们提出 CHD，将 LLM 启发式发现从开放式候选生成扩展为“开放探索到证据收缩”的范式，适用于存在强 root、粗反馈和复杂度捷径的启发式任务。
2. 我们指出网络瓦解是 CHD 的典型场景：高分不等于新机制，GCC/R 是最终目标但不是充分搜索传感器，自由程序探索会系统性放大复杂度漂移。
3. 我们提出 HAST，通过 root-relative credit、cNBI fragmentation sensing 和 log-induced bounded graph-operation policies，将自由 LLM 代码搜索收缩(contractive)为可归因、碎裂感知、复杂度有界的瓦解机制空间。
4. 我们通过动机实验、12 图验证、搜索过程消融、机制 case study 和 scaling 实验表明，HAST 不依赖无界慢扫描追逐单点高分，而是在网络瓦解中发现更稳定、更可解释的质量-时间折中候选。
# 2 相关工作

## 2.1 网络瓦解启发式

网络瓦解的经典研究首先关注如何构造有效删除序列。Morone 与 Makse 的最优渗流和 Collective Influence 方法从渗流角度识别对全局连通性有重要影响的节点，强调弱连接位置在系统断裂中的作用 [1]。Braunstein 等将 network dismantling 表述为具有集体性的优化问题，并提出消息传递和 Min-Sum 相关框架 [2]。Zdeborová 等提出 CoreHD，将 decycling 和 dismantling 限制在 2-core 上，通过高阶度贪心以较低计算代价取得较强表现 [3]。Ren 等进一步研究 generalized network dismantling，将异质节点成本纳入目标，使低代价瓦解成为正式优化问题 [4]。

这些方法建立了网络瓦解启发式的主要谱系：中心性和渗流方法提供可解释的结构信号，消息传递和优化方法提供更强理论动机，CoreHD/HDA 类方法在质量和效率之间取得实用折中。它们的共同目标是直接生成节点删除序列，而不是分析“当一个程序搜索器修改启发式代码时，哪一段修改真正带来了增量碎裂”。因此，经典网络瓦解工作为 HAST 提供了目标、指标和基线，但并不直接解决 LLM 程序搜索中的信用归因。

## 2.2 学习式网络瓦解

学习式方法将网络瓦解进一步转化为可从数据中学习的策略。FINDER 将关键节点识别表述为深度强化学习序列决策问题，学习攻击策略以寻找关键节点 [5]。Grassia 等的 GDM 展示了机器学习模型可以从小系统迁移到更大网络，并输出系统解体的早期预警信号 [6]。Zhang 与 Wang 的 NIRM 尝试从 tiny networks 学习可泛化的节点排序模式 [7]。

这些工作说明瓦解策略不必完全由人工规则设计，数据驱动策略可以学习到跨图的拆解模式。HAST 与其问题对象不同：HAST 不直接训练一个节点排序模型，而是让 LLM 在启发式程序空间中搜索候选算法。学习式瓦解方法通常把信用给到节点选择、策略轨迹或最终瓦解效果；HAST 的信用对象则是相对 root heuristic 的代码结构增量。这个区别决定了 HAST 需要显式处理 root 继承带来的信用混淆。

## 2.3 LLM 程序搜索与自动启发式设计

LLM 程序搜索和自动启发式设计近年迅速发展。FunSearch 证明了“LLM 生成 + 自动评估器 + 演化筛选”能够发现新的数学与算法程序 [8]。ReEvo 将反思文本与进化搜索结合，把 LLM 用作 language hyper-heuristics [9]。EoH 进一步把自然语言 thought 与可执行 code 放入共同演化过程，说明 LLM-AHD 不只是代码采样，也包含启发式概念的演化 [22]。MCTS-AHD 则把 LLM 生成的启发式组织成搜索树，通过 Monte Carlo Tree Search 更充分地开发暂时低分但具有后续潜力的候选 [23]。这些工作共同建立了扩张式 AHD 的主流路线：扩大候选覆盖、保留多样化分支、用反思或树搜索避免早熟收敛。

HAST 与这一路线的关系是互补而非替代。扩张式 AHD 默认主要瓶颈是“探索不够”，因此优化目标是更全面地访问候选空间；网络瓦解暴露出的瓶颈则是“探索之后没有及时收缩”，导致强 root 信用混淆、GCC/R 粗反馈和复杂度漂移同时出现。因此，HAST 不试图证明收缩总是优于扩张，而是指出在强 baseline、慢操作捷径和可执行图程序共存的任务中，搜索必须在发现潜在机制后改变可行候选语言本身。

另一条相关路线是把结构先验或奖励层级注入 LLM 生成过程。STRCMP 通过 GNN 提取组合优化实例的结构嵌入，并将其条件化到 LLM 代码生成中，用于 MILP 和 SAT 等任务 [24]。RFTHGS 在 CVRP 中对小模型进行强化学习微调，使其生成 HGS 求解器中的 crossover operator，并通过从可编译、可运行到优于专家算子的多层奖励塑造生成行为 [25]。这些方法说明，组合优化中的 LLM 生成不能只依赖纯文本提示，必须将任务结构、求解器接口和相对改进信号显式纳入搜索。HAST 接受这一判断，但选择了不同入口：它不训练结构编码器，也不更新模型权重，而是从执行日志中归纳图操作策略，用 root-relative credit 和 bounded operation policy 约束后续候选程序。

还有一些工作从图分析、程序组合和智能体拓扑角度提供了相邻背景。GraphChain 将大图分析表述为工具链决策问题，通过 progressive graph distillation 和 structure-aware test-time adaptation 缓解 LLM 处理大规模图时的上下文限制 [26]。Parsel 将复杂程序生成拆成 decomposition、implementation 和 composition，并用测试约束组合空间 [27]。GPTSwarm 把多智能体系统表示为可优化计算图，对节点提示和边连接进行搜索 [28]。这些工作都强调“结构化边界”对 LLM 系统的重要性，但它们的边界分别作用于工具调用序列、函数分解或智能体通信拓扑；HAST 的边界作用于网络瓦解启发式本身的图操作语言。

近期 Harness Evolution 相关工作进一步把问题推进到“可执行环境如何参与智能体自我改进”。Agentic Harness Engineering 强调把测试框架拆成可修改组件、把长执行轨迹转化为可追溯修改，并要求变更绑定可证伪预测 [15]；Meta-Harness 主张保留框架源码、打分数据和运行轨迹，使智能体可直接访问全量历史细节 [16]；Hyperagents、Meta Context Engineering 和 MetaClaw 分别从自指程序、上下文优化和在线技能生成角度扩展了自进化系统 [17,18,19]；AutoHarness 和 VeRO 则强调环境适配、版本快照、资源管控和结构化日志对于公平评测的重要性 [20,21]。这些工作说明，harness 不应被理解为外层工程壳，而是一种使候选行为可观察、可归因、可审计、可约束的机制层。

表 1 总结了 HAST 与最接近文献的差异。已有工作大多回答“如何更好地产生、保留或组合候选”，而 HAST 回答的是“何时以及如何把候选语言从开放程序收缩到任务可解释机制”。这个差异尤其出现在网络瓦解中：候选不是普通求解器组件，而是破坏图连通性的删除规则；评价不是单一最终分数，而包含 residual fragmentation；高分不是天然信用，而必须相对 root heuristic 重新归因。

| Work | 主要任务 | 搜索方向 | 结构信息来源 | 是否处理 root-relative credit | 是否形成候选语言策略 | 是否面向破坏式图操作 |
|---|---|---|---|---|---|---|
| FunSearch / ReEvo | 数学程序、TSP/ACO/EDA/NCO 等启发式 | 开放生成与反思演化 | 任务描述与 evaluator | 否 | 否 | 否 |
| EoH | bin packing、TSP、VRP 等 AHD | thought-code 共同演化 | 自然语言 thought 与代码种群 | 否 | 否 | 否 |
| MCTS-AHD | TSP、CVRP、online bin packing 等 | 树式扩张，保留潜在分支 | 搜索树统计与 evaluator | 否 | 否 | 否 |
| STRCMP | MILP、SAT | 结构先验条件化生成 | GNN 结构嵌入 | 否 | 部分，来自结构编码与求解器接口 | 否 |
| RFTHGS | CVRP-HGS crossover operator | RL 微调生成器 | HGS 接口与课程奖励 | 部分，相对专家算子 | 部分，来自 C++ operator 接口 | 否 |
| GraphChain | 大规模图分析 | 工具链决策与压缩 | 图工具、谱特征与测试时适配 | 否 | 工具调用边界 | 否 |
| Parsel | 程序合成与算法推理 | 分解-实现-组合 | 函数分解和测试 | 否 | 模块/测试约束 | 否 |
| HAST | 网络瓦解启发式发现 | 开放探索后证据收缩(contractive) | 执行日志、cNBI、root-relative gain | 是 | 是，有界图操作策略 | 是 |

因此，HAST 的新颖性不在于提出更重的通用 harness，也不在于声称扩张式搜索无效，而在于把网络瓦解中的任务特殊性形式化为三类收缩(contractive)：从 GCC/R 到 cNBI 的搜索传感收缩，从绝对高分到 root-relative gain 的信用收缩，从自由 Python 程序到有界图操作策略的候选语言收缩。
# 3 为什么网络瓦解需要收缩式启发式发现

为什么网络瓦解使用第二章的相关工作进行算法挖掘容易失效？核心原因在于，网络瓦解同时具有强 root、粗反馈和慢操作捷径。通用 LLM-AHD 通常把 evaluator 看作固定黑盒，把搜索重点放在如何生成更多候选、如何复用历史经验、如何平衡探索与利用；但在网络瓦解中，搜索器首先必须解决候选语言本身如何被任务证据收缩的问题。

本章按“现象到本质”的顺序组织四个结论。第一，开放的自由程序探索与进化反而会使候选越来越复杂、越来越难解释。第二，强 root 使高分不等于新机制，必须把候选贡献相对 root 重新归因。第三，GCC/R 是最终瓦解目标，但不是充分的搜索传感器，需要额外观察残余碎裂形态。第四，这些证据共同指向 Contractive Heuristic Discovery：先开放探索以暴露结构假设，再用证据收缩(contractive)候选语言。

## 3.1 开放自由程序探索会导致复杂度漂移

许多自动启发式设计工作默认“更开放的程序空间”意味着更大的发现潜力。网络瓦解揭示了这个假设的边界：当评价信号奖励碎裂效果时，LLM 很容易发现一些短期有利但机制不清、成本偏高的图操作，例如无界 two-hop 扫描、嵌套邻域枚举、频繁重算 connected components、全图刷新或中心性重算。这些候选在小图或 proxy graph 上可能拿到不错分数，却很难解释为稳定的瓦解机制，也难以迁移到更大图。

因此，本文将这一失败模式称为 **under-constrained candidate language**：候选程序被允许调用全局中心性、连通分量重算、无界多跳扫描和随机 tie-breaking，评价器只在事后给分，搜索过程没有把复杂度、局部性、归因和可解释结构前置到生成策略中。这个概念比口语化的“太自由”更准确；问题不是 LLM 不能探索，而是探索后的证据没有及时改变候选语言。

实验比较 `Relative-Free`、`CostAware-Free` 和 `Bounded-Guided` 三组候选，每组 100 个独立 LLM 生成程序，并在同一接口和验证器下记录候选有效率、搜索时间和完整碎裂指标。三组均固定 `degree_order(G)` 接口；并发只影响 LLM 请求调度，不表示一个候选继承前一个候选，也不构成搜索树。该实验的目标不是证明有界引导必然获得最高单点质量，而是检验它是否能把自由碎裂信用压缩为更可部署的候选空间。

| Generation mode | candidates | 目标 |
|---|---:|---|
| Relative-Free | 100 | 观察相对碎裂信用下的自由生成成本 |
| CostAware-Free | 100 | 观察加入时间信用后是否抑制慢扫描 |
| Bounded-Guided | 100 | 观察日志归纳边界是否提高有效率并降低搜索成本 |

![Observation 3 bounded generation controls scan cost](../artifacts/figures/03_motivation/fig23_bounded_generation_controls_scan_cost.png)

**图 3.1：bounded guidance 将自由碎裂信用压缩为更可部署的启发式空间。** 三组均使用真实 LLM，每组 100 个独立候选，接口固定为 `degree_order(G)`。LLM 参数为 `gpt-5.5`、reasoning effort `none`、temperature 0.2；评估图为 `Powerlaw_300`，删除比例 `rate=0.30`，单候选 timeout 为 30 s，slow threshold 为 2 s。`Relative-Free` 的 top-5 AUC-cNBI 最高，为 38.47，而 `Bounded-Guided` 为 37.70，略低于最强自由慢候选；但 `Bounded-Guided` 的 mean R/GCC 为 36.09%，低于 `Relative-Free` 的 41.01%，top-5 runtime 也只有 0.87 s，显著低于 `Relative-Free` 的 1.76 s。同时，`Bounded-Guided` 的 valid rate 为 0.77，高于 `Relative-Free` 的 0.50，Pareto frontier 数量从 6 增加到 10，timeout rate 从 `Relative-Free` 的 0.01 降至 0。该结果说明，有界引导未必追求最高单点碎裂分数，而是更稳定地给出可部署的质量-时间折中。

这个实验说明了网络瓦解上的开放探索必须被证据收缩，否则 LLM 进化会把搜索推向复杂、慢速、难解释的程序区域。

## 3.2 差异一：强 root 使高分不等于新机制

复杂度漂移只是表层现象。更根本的问题是网络瓦解具有强 root heuristic。HDA、degree、CoreHD 这类规则本身已经能提供有效的高残余度骨架；如果候选从这些 root 出发，绝对 auc-cNBI 或 GCC/R 高分并不意味着 LLM 新增代码结构真的有效。候选程序可能只是继承了 root 的能力，或者在 root 之上加入少量并无实质贡献的复杂代码。

因此，搜索信用应该从“候选绝对分数”转向“候选相对 root 的新增碎裂”：

$$
\Delta_{\mathrm{frag}}(h\mid h_0)
= \mathrm{Frag}(h)-\mathrm{Frag}(h_0),
$$
其中 $h_0$ 是 root heuristic，$\mathrm{Frag}(h)$ 可以由搜索图上的 cNBI 曲线或 early fracture proxy 计算。这个定义相当于把 root 已经能完成的高阶度删除能力视作 baseline value，只把新增的 frontier、weak-tie、boundary、redundancy-aware 等机制记入候选修改的信用。

图 3.2 比较了 `R/GCC-only`、`Absolute-cNBI` 和 `Relative-Delta-cNBI` 三种搜索信用，每组固定 100 个独立候选，并在同一候选接口和同一验证器下记录有效率、搜索时间、$R$、auc-cNBI 与 Pareto 位置。这里的 100 个候选是 100 个相互独立的 `degree_order(G)` 程序采样与评估，不是按父子关系逐步扩展的 100 节点搜索树。

| Search credit | candidates | 状态 | 目标 |
|---|---:|---|---|
| R/GCC-only | 100 | 已完成 | 检验只看 GCC/R 是否会漏掉过程碎裂差异 |
| Absolute-cNBI | 100 | 已完成 | 检验绝对碎裂分数是否混入 root heuristic 贡献 |
| Relative-Delta-cNBI | 100 | 已完成 | 检验相对 root 的新增碎裂信用是否更适合搜索归因 |

![Observation 2 relative credit allocation](../artifacts/figures/03_motivation/fig22_relative_credit_allocation_effect.png)

**图 3.2：relative credit 改变候选搜索的有效方向，同时带来速度代价。** 三组均使用真实 LLM 生成，每组 100 个独立候选。LLM 参数为 `gpt-5.5`、reasoning effort `none`、temperature 0.2；评估图为 `Powerlaw_300`，删除比例 `rate=0.30`，单候选执行 timeout 为 30 s，slow threshold 为 2 s，候选缓存 tag 为 `narrative_v2`。柱状图报告各组按组内 selection score 选出的 top-5 均值。`Relative-Delta-cNBI` 的 top-5 $\Delta$AUC-cNBI 达到 9.32，高于 `Absolute-cNBI` 的 9.21 和 `R/GCC-only` 的 9.04，说明相对 HDA/root 的新增碎裂信用比单纯绝对评估更适合引导候选搜索。然而它的 top-5 wall runtime 也最高，达到 1.12 s，高于 `Absolute-cNBI` 的 1.00 s 和 `R/GCC-only` 的 0.92 s；其 slow rate 也从 0 上升到 0.03。因此，relative credit 的结论不是“换奖励函数就够了”，而是：它能把候选推向更有新增碎裂贡献的代码结构，但也会鼓励更复杂的局部扫描，必须进一步加入时间感知和候选语言边界。

这一点构成 HAST 与通用 AHD 的第一处差异。通用 AHD 往往把高分候选视为搜索进步；网络瓦解则必须问“高分相对谁而言”。若没有 root-relative credit，搜索器很容易把 root 的旧能力误写成 LLM 的新发现。

## 3.3 差异二：GCC/R 是最终目标但不能成为搜索的唯一来源

网络瓦解最终当然要回到 GCC/R的评分：最大连通分量是否被压低，是任何瓦解方法都必须满足的目标约束。但对 LLM 搜索而言，GCC/R 过于粗粒度。两个候选可以在某个删除比例下具有完全相同或非常接近的最大连通分量，却留下不同的 residual fragmentation。换言之，GCC/R 告诉我们“最大块有多大”，但不充分告诉我们“剩余节点被切成了什么形态”。



![Basic baseline same-R residual fragmentation](../artifacts/figures/03_motivation/fig21_obs1_basic_baseline_same_r_horizontal.png)

**图 3.3(a) same-GCC 下的瓦解情况。** 只使用 HDA、CI、CLUC 等 basic baselines。我们在离线分析中筛选 $R$/GCC 完全相同但 residual fragmentation 差异明显的 cases；图中蓝色表示最大连通分量，红色和橙色表示第 2 到第 5 大连通分量，灰色表示更小碎片。每个 case 左右两侧的 $R$/GCC 相同，但残余图的分散程度不同。

| Case | Baseline A | R/GCC A | Baseline B | R/GCC B | 观察 |
|---|---|---:|---|---:|---|
| Collaboration | HDA | 0.004810 | CLUC | 0.004810 | R/GCC 完全相同，但 HDA 留下更多分散小块，CLUC 的前几个残余块更集中 |
| Collaboration | HDA | 0.011063 | CI | 0.011063 | R/GCC 完全相同，但 HDA 的剩余碎片更分散，CI 留下更重的前五个残余块 |
| Collaboration | CI | 0.012987 | CLUC | 0.012987 | R/GCC 完全相同，但两种 basic baseline 的残余碎裂方向不同 |

针对这一盲区，本文使用 cNBI 作为搜索期 residual fragmentation sensor。

具体定义如下：给定候选启发式 $h$ 产生删除序列 $\pi_h=(v_1,\ldots,v_n)$，删除前 $t$ 个节点后得到残余图：
$$
G_t^h = G[V \setminus \{v_1,\ldots,v_t\}].
$$
设 $G_t^h$ 的连通分量大小为 $s_{t,1}\ge s_{t,2}\ge \cdots \ge s_{t,k_t}$，其中 $n_t=\sum_i s_{t,i}=n-t$。pairwise disconnectedness 按残余节点对归一化：

$$
\mathrm{PD}_t
= 1 - \frac{\sum_i s_{t,i}(s_{t,i}-1)}{n_t(n_t-1)}.
$$
当 $n_t\le 1$ 时，$\mathrm{PD}_t$ 定义为 1。它等价于两个随机残余节点落在不同连通分量的概率。有效碎片数使用 Hill number 或 inverse-Herfindahl 形式：

$$
p_{t,i} = \frac{s_{t,i}}{n_t},
\quad
\mathrm{EC}_t = \frac{1}{\sum_i p_{t,i}^2}.
$$
前$m$大残余块(我们选择$m=5$)质量集中度定义为：

$$
\mathrm{Top5}_t
= \frac{\sum_{i=1}^{\min(5,k_t)} s_{t,i}}{n}.
$$
于是 cNBI 定义为：

$$
\mathrm{cNBI}_t
= \frac{\mathrm{PD}_t \cdot \mathrm{EC}_t}{1+\mathrm{Top5}_t}.
$$
完整过程曲线采用删除比例网格 $q_t=t/n$ 上的离散积分：

$$
\mathrm{AUC}_{\mathrm{cNBI}}(h;G)
= \sum_{t\in T} \mathrm{cNBI}_t(h;G)\Delta q_t.
$$
cNBI 的作用是补充而非替代 GCC/R。$\mathrm{PD}_t$ 奖励更多残余节点对被分到不同连通分量，$\mathrm{EC}_t$ 奖励有效碎片数量增加，$\mathrm{Top5}_t$ 惩罚前五个残余块仍占据过多原图质量。这样做避免单纯组件数被大量微小孤点虚高，也避免只看最大连通分量时忽略剩余质量是否仍集中在少数大块中。

![Observation 1 cNBI separates same-GCC cases](../artifacts/figures/03_motivation/fig_obs1_same_gcc_cnbi_bar.png)

**图 3.3(b)：same-GCC cases 下的 cNBI 差异。** 该图使用已筛选出的 Collaboration 图 basic-baseline cases，不引入新的 LLM 搜索实验。每两个柱子构成一个 same-GCC/R case，图下方标注该 case 的共同 GCC/R 和两种方法之间的 $\Delta$cNBI。三个 case 的 GCC/R 分别固定为 0.004810、0.011063 和 0.012987，但对应 cNBI gap 分别达到 170.8、156.6 和 156.0。这个结果说明，即使最大连通分量完全相同，残余碎裂结构仍可能显著不同；因此 GCC/R 适合作为最终瓦解质量约束，却不足以作为 LLM 搜索期的唯一信用信号。

## 3.4 从复杂通用 AHD 到面向网络瓦解的 CHD

上面三个观察共同说明，网络瓦解中的 LLM 启发式发现不能只被写成通用 AHD 的任务迁移。开放探索确实能发现局部结构信号，但如果没有收缩机制，它会走向复杂度漂移；强 root 确实能帮助候选获得可用初始能力，但也会混淆新增机制的信用；GCC/R 确实是最终任务目标，但不足以作为搜索期传感器。三者叠加后，网络瓦解需要一种新的发现范式。

本文将这种范式定义为 **Contractive Heuristic Discovery (CHD)**，即收缩式启发式发现。给定任务 $\mathcal{T}$、候选程序空间 $\mathcal{H}$、初始候选或 root heuristic $h_0$、评估器 $\mathcal{E}$ 和搜索日志 $\mathcal{L}$，普通 AHD 可以抽象为在 $\mathcal{H}$ 中寻找高分候选：

$$
h^* = \arg\max_{h\in\mathcal{H}} S_{\mathcal{E}}(h),
$$

其中 $S_{\mathcal{E}}$ 是由评估器诱导的标量分数。CHD 不把 $\mathcal{H}$ 视为固定空间，而是把发现过程写成“扩张-证据-收缩”的序列：

$$
\mathcal{H}_0 \xrightarrow{\mathrm{Expand}(\mathrm{LLM},h_0)}
\mathcal{C}_t
\xrightarrow{\mathrm{Observe}(\mathcal{E})}
\mathcal{L}_t
\xrightarrow{\mathrm{ContractiveStep}(\mathcal{L}_t,\mathcal{T})}
\mathcal{H}_{t+1},
$$

并满足

$$
\mathcal{H}_{t+1}\subseteq \mathcal{H}_t
\quad \text{or} \quad
\Omega(\mathcal{H}_{t+1}) < \Omega(\mathcal{H}_t),
$$

其中 $\Omega(\cdot)$ 表示候选语言的有效复杂度，例如允许的图操作、循环范围、邻域预算、全局刷新频率、随机性和不可审计分支数量。也就是说，CHD 的“收缩”不是简单减少候选数量，而是降低候选语言的自由度，使后续搜索从开放程序生成转向可归因、可解释、可部署的机制空间。

更形式化地，CHD 在每一轮维护一个候选语言收缩策略

$$
\Pi_t=(\mathcal{A}_t,\mathcal{B}_t,\mathcal{C}_t,\mathcal{U}_t,\mathcal{P}_t),
$$

其中 $\mathcal{A}_t$ 是 allowed signals，$\mathcal{B}_t$ 是 forbidden patterns，$\mathcal{C}_t$ 是 cap bounds，$\mathcal{U}_t$ 是 update bounds，$\mathcal{P}_t$ 是 preferred/pruned families。候选空间由该收缩策略诱导：

$$
\mathcal{H}(\Pi_t)=\{h\in\mathcal{H}:h\models\Pi_t\}.
$$

一次收缩(contractive step)就是从日志中学习新的候选语言策略：

$$
\Pi_{t+1}=\mathrm{InducePolicy}(\mathcal{L}_t,\mathcal{T},\Pi_t),
\quad
\mathcal{H}_{t+1}=\mathcal{H}(\Pi_{t+1}).
$$

该定义把 harness 思想放在机制层，而不是工程层：候选行为必须被观察，新增收益必须被归因，历史证据必须被压缩为候选策略，后续生成必须受到可审计的操作边界约束。

在网络瓦解中，收缩至少包含三类核心算子，并可扩展为更多任务特定约束。

1. **传感收缩 (contractive sensing)**。最终任务目标仍由 GCC/R 约束，但搜索期传感器从单一最大连通分量扩展为

$$
\phi_{sense}(h,G)=\left(R(h,G),\mathrm{AUC}_{cNBI}(h,G),T(h,G)\right),
$$

其中 cNBI 用来观察 residual fragmentation。它把“只看最大块”收缩为“同时观察最大块、碎裂均衡性和成本”的搜索信号。

2. **信用收缩 (contractive credit)**。候选质量从绝对高分收缩为相对 root 的新增贡献：

$$
\phi_{credit}(h)=\Delta_0(h)=A(h)-A(h_0).
$$

这一步把 root heuristic 已经具备的 residual-degree backbone 从候选信用中扣除，只给新增的 frontier、weak-tie、boundary、redundancy-aware 等机制记功。

3. **成本收缩 (contractive cost control)**。网络瓦解候选容易通过慢操作追分，因此搜索分数必须显式惩罚运行时间：

$$
\phi_{cost}(h)=T(h),
\quad
S(h)=\alpha\rho^+(\Delta_0(h))+\beta\rho^-(R(h))+\gamma\rho_T^-(T(h))+\eta\rho^+(A(h)).
$$

这一步把“可得高分的程序”收缩为“在质量和时间上均可接受的启发式”。

4. **语言收缩 (contractive language)**。自由 Python 程序被收缩为有界图操作策略：

$$
\Pi_{ND}=(\mathcal{A}_{ND},\mathcal{B}_{ND},\mathcal{C}_{ND},\mathcal{U}_{ND},\mathcal{P}_{ND}),
$$

其中 $\mathcal{A}_{ND}$ 保留 residual degree、frontier、weak-tie、boundary、bounded two-hop、redundancy 和 phase schedule；$\mathcal{B}_{ND}$ 禁止 per-step global centrality、all-pairs shortest path、频繁 connected components、full graph rescan、unbounded BFS/DFS 和 nondeterministic random ordering；$\mathcal{C}_{ND}$ 和 $\mathcal{U}_{ND}$ 分别限制邻居枚举、二跳扫描、affected set 和局部刷新频率。

5. **族群收缩 (contractive family allocation)**。搜索日志还可以把候选 family 分为 preferred families 与 pruned families：

$$
\mathcal{P}_{ND}=(\mathcal{F}^+,\mathcal{F}^-),
$$

其中 $\mathcal{F}^+$ 获得更多后续预算，$\mathcal{F}^-$ 被减少或停止扩展。这一步把“所有可变异方向平等”收缩为“预算向高信用且低风险的机制族集中”。

因此，在网络瓦解中，CHD 的收缩(contractive)不是单一约束，而是由传感、信用、成本、语言和族群预算共同构成的多类收缩。HAST 正是 CHD-ND 的具体实例。下一章将给出 HAST 如何把这些收缩落到统一候选接口、root-relative credit、日志归纳策略和 Pareto 选点中。
# 4 方法：HAST

## 4.1 HAST 总览

HAST 是 CHD 在网络瓦解上的实例。它不把 LLM 搜索看作单纯的“多生成候选并取最高分”，而是把候选发现组织为三个机制闭环：候选行为可观察、候选贡献可归因、候选语言可收缩。图 4.1 给出 HAST 的主要结构：LLM 生成候选程序，统一接口和沙箱检查候选是否可运行，图评估器计算 $R$、auc-cNBI 和 runtime，信用模块将绝对指标转化为相对 root 的碎裂贡献并加入时间压力，自由探索日志再被压缩为 bounded candidate language，后续搜索只在可审计的图操作策略内继续修改。

![HAST framework](../artifacts/figures/04_method/Gemini-Framework.png)

从机制角度看，HAST 包含三层闭环。第一层是 **observation loop**：候选程序必须输出完整删除序列，统一评估器负责计算曲线指标，避免候选在内部自行定义评价。第二层是 **attribution loop**：搜索不只看候选绝对得分，而是根据 root-relative fragmentation gain、$R$ 和运行时间选择后续扩展方向。第三层是 **contractive loop**：自由搜索日志不只是临时记录，而是被用来归纳哪些局部信号可信、哪些图操作应被限制、哪些 family 应继续分配预算。这个结构使 HAST 与一般“LLM 反复生成高分代码”的范式区分开来。

所有 LLM 生成的候选启发式都被约束为同一接口：

```python
def degree_order(G):
    return removal_order
```

输入是 NetworkX 图 $G$，输出是一个包含所有节点且不重复的完整删除序列 `removal_order`。LLM 回复先经 `extract_code` 抽取，再由 `make_program` 包装成 `CandidateProgram`；评估器只调用候选中的 `degree_order(G)`，并检查语法、可调用性、返回类型、重复节点、缺失节点、异常和超时。传统启发式、ERA-like、FunSearch-like、Clade-AHD-like、MCTS-AHD-like、AlphaEvolve-like 和 HAST 最终候选都通过同一 evaluation mechanism。这样做有两个作用：其一，避免不同方法输出中间状态或局部评分函数导致比较口径不一致；其二，把 cNBI、GCC/R 和时间统计都放到外部评估器中，避免候选程序在内循环中直接优化评估器实现细节。

对每个候选 $h$ 和图 $G$，评估器记录：

$$
\mathcal{E}(h,G)
= \left(R(h,G), A(h,G), T(h,G)\right),
\quad A(h,G)=\mathrm{AUC}_{\mathrm{cNBI}}(h,G).
$$
$R$ 越低越好，用于标准瓦解质量；$A$ 越高越好，用于过程碎裂质量；$T$ 越低越好，用于候选算法运行成本。多图结果先在每个图上计算，再按图平均。本文明确区分最终启发式 runtime 和搜索框架成本：前者只统计候选算法在图上输出删除序列的时间，不包含 LLM 生成成本；后者统计 prompt elapsed time 和 candidate validation time，用来回答搜索过程是否更耗预算。

HAST 的搜索过程由三个阶段组成。Stage I 是从 root heuristic 出发的自由、信用感知树搜索；Stage II 读取 Stage I 日志并归纳 bounded candidate language；Stage III 在有界语言下继续树搜索，并从 proxy Pareto frontier 中输出 HAST-Final-Q/S 两个候选。实验中的具体预算和运行配置放在第 5 章说明，本章只定义方法机制。

## 4.2 Stage I 信用感知的自由树搜索

Stage I 对应 CHD 中的开放探索阶段。设初始候选语言为 $\mathcal{H}_0$，root heuristic 为 $h_0$。本阶段不直接生成最终算法，而是在相对开放的候选空间中收集可执行候选、评价指标与失败模式，为 Stage II 的日志归纳提供证据。Stage I 的 LLM 扩展预算为 $B_1=300$，代理评估图数量为 $|\mathcal{G}_{\mathrm{p}}|=5$，每个候选的运行超时为 $\tau=90.0$s。

### 4.2.1 LLM 候选生成

Stage I 的搜索树节点为候选启发式 $h\in\mathcal{H}_0$，每个候选均满足统一接口 `degree_order(G) -> removal_order`。第 $i$ 次扩展时，HAST 从当前有效树节点中选择父节点 $u_i$，并构造 prompt $\Pi_i$。LLM 负责生成候选程序：

$$
\tilde{h}_i
\leftarrow
\operatorname{LLM}_{\theta}
\left(
\Pi_i,\; h_{u_i},\; m_{u_i}
\right),
\quad i=1,\ldots,B_1.
$$

其中 $\tilde{h}_i$ 表示 **LLM 生成** 的候选代码，$h_{u_i}$ 是父候选，$m_{u_i}$ 是父候选的评估摘要。候选抽取、接口检查、沙箱执行、指标计算、超时控制和日志写入均由确定性 harness 完成，不由 LLM 决定。

### 4.2.2 统一评估与 root-relative 信用

对每个有效候选 $h\in\mathcal{C}_1$，评估器在代理图集合 $\mathcal{G}_{\mathrm{p}}$ 上记录三类指标：

$$
m(h)
=
\left(
R(h),\;
A(h),\;
T(h)
\right),
\quad
A(h)=\operatorname{AUC}_{cNBI}(h).
$$

其中 $R(h)$ 表示 GCC/R 瓦解代价，越小越好；$A(h)$ 表示过程碎裂质量，越大越好；$T(h)$ 表示候选算法生成删除序列的运行时间，越小越好。所有候选的评估记录构成：

$$
\mathcal{R}_1
=
\{m(h):h\in\mathcal{C}_1\}.
$$

为避免强 root heuristic 的继承能力被误记为 LLM 新增机制，Stage I 使用相对 root 的过程碎裂增益：

$$
\Delta_0(h)
=
A(h)-A(h_0).
$$

该项只度量候选相对 $h_0$ 的新增碎裂收益。换言之，HAST 不把 root 已经具备的残余度骨架视为 LLM 贡献，而只将候选在 root 之上的有效增量写入搜索信用。

### 4.2.3 Rank-normalized 在线评分

为了把不同量纲的质量、时间和信用放入同一选择器，HAST 对当前已生成的有效候选做 rank-normalization。令当前有效候选集合为 $\mathcal{V}$，$N=|\mathcal{V}|$。对越大越好的指标 $x$，按降序排名：

$$
\rho^+(x_i)
=
1-\frac{\operatorname{rank}_{desc}(x_i)-1}{N-1}.
$$

对越小越好的指标 $x$，按升序排名：

$$
\rho^-(x_i)
=
1-\frac{\operatorname{rank}_{asc}(x_i)-1}{N-1}.
$$

Stage I 的在线排序分数由三类信息组成：相对增长项、实际质量项和时间复杂度项。形式化地：

$$
\Phi_1(h)
=
\alpha\,\rho^+\!\left(\Delta_0(h)\right)
+
\beta\,\rho^-\!\left(R(h)\right)
+
\gamma\,\rho_T^-\!\left(T(h)\right)
+
\eta\,\rho^+\!\left(A(h)\right).
$$

其中 $\rho^+(\Delta_0(h))$ 是相对增长项，衡量候选相对 root 的 auc-cNBI 增益；$\rho^-(R(h))$ 与 $\rho^+(A(h))$ 是实际质量项，分别对应最终 GCC/R 质量和过程碎裂质量；$\rho_T^-(T(h))$ 是时间复杂度项，用于抑制慢候选。当前实验取：

$$
\alpha=0.05,\quad
\beta=0.60,\quad
\gamma=0.10,\quad
\eta=0.25.
$$

时间项使用饱和排序函数 $\rho_T^-$。候选进入前 $60\%$ 快速区间后获得满分，不再继续奖励更短运行时间，以避免搜索被极端速度牵引而牺牲瓦解质量。

### 4.2.4 父节点选择与日志输出

Stage I 使用 $\Phi_1$ 选择后续扩展方向。设有效树节点 $u$ 已有子节点数为 $c(u)$，其扩展优先级定义为：

$$
U_1(u)
=
\Phi_1(u)
+
\frac{\lambda}{1+c(u)}.
$$

当前实验取 $\lambda=0.10$。每轮选择：

$$
u_i
=
\arg\max_{u\in\mathcal{V}}
U_1(u).
$$

该机制使高质量候选获得更高扩展概率，同时通过子节点数惩罚避免全部预算集中到同一节点。

设 Stage I 产生的候选集合为

$$
\mathcal{C}_1=\{h_i\}_{i=1}^{n},
$$
对应的评估记录为

$$
\mathcal{R}_1=\{m_i\}_{i=1}^{n},
$$
其中 $h_i$  表示第 $i$ 个候选启发式，$m_i$ 包含其有效性、$R$、auc-cNBI、运行时间和搜索分数等评估结果。

Stage I 最终输出搜索日志：

$$
\mathcal{L}_1
=
\left(
\mathcal{C}_1,\;
\mathcal{R}_1,\;
\Phi_1
\right).
$$

其中 $\mathcal{C}_1$ 包含 LLM 生成 的候选程序，$\mathcal{R}_1$ 包含 harness 计算得到的评估记录，$\Phi_1$ 是确定性在线评分函数。

## 4.3 Stage II 日志归纳的有界候选语言

Stage II 不生成新的 `degree_order(G)` 候选，而是读取自由搜索日志，将候选代码特征、family 统计和失败模式归纳为 Stage III 的 bounded candidate language。实现先从候选代码中抽取 `degree_backbone`、`frontier`、`weak_tie`、`two_hop`、`boundary`、`redundancy`、`phase`、`heap_update`、`component_refresh`、`global_rescan` 和 `unbounded_two_hop` 等特征，写出 `code_feature_table.csv`、`family_summary.csv` 和 `failure_patterns.json`；随后执行多次 policy induction，要求每次只返回 JSON policy，不返回候选算法。

### 4.3.1 获取日志证据，并使用LLM生成策略

Stage II 的输入不是额外人工构造的启发式规则，而是从 Stage I 的输出中提取的搜索证据。Stage II 首先从 $(\mathcal{C}_1,\mathcal{R}_1)$ 中提取四类证据，并组成证据包 $\mathcal{D}_1$：

$$
\mathcal{D}_1
=
(\mathcal{T}_1,\mathcal{Y}_1,\mathcal{X}_1,\mathcal{Z}_1).
$$
其中，$\mathcal{T}_1$  表示按搜索分数排序后的有效 Top-20 候选证据；$\mathcal{Y}_1$ 表示候选族群的聚合统计；$\mathcal{X}_1$ 表示从候选代码中抽取的结构特征表；$\mathcal{Z}_1$ 表示自由搜索中暴露出的失败模式。具体的，$\mathcal{T}_1$  保留第一阶段有效候选中搜索分数最高的前 20 个候选；$\mathcal{Y}_1$ 汇总不同候选族群的有效率、相对收益、运行时间和慢模式比例；$\mathcal{X}_1$ 记录候选是否使用 residual degree、frontier、two-hop、redundancy、phase、heap update 等结构信号；$\mathcal{Z}_1$ 统计 connected components 重算、全图重扫、无界二跳扫描等失败模式。

对第 $j$ 次 policy induction，LLM 读取同一份 Stage I 证据：

$$
\pi_j
=
\operatorname{LLM}_{\theta}^{(j)}
(
\mathcal{D}_1
),
\quad j=1,\ldots,B_2.
$$
其中 $B_2$ 是 Stage II 的 policy induction 预算，默认取  $B_2=10$。每个 $\pi_j$ 都不是候选算法，而是一次策略归纳结果。

### 4.3.2 从经验到策略

Stage II 随后将多次策略归纳结果与程序化统计结果合并，得到中间策略：
$$
\widetilde{\Pi}_2 = \mathcal{M} \left( \mathcal{S}(\mathcal{D}_1), \mathcal{N}(\pi_1,\ldots,\pi_{B_2}) \right).
$$
其中，$\mathcal{S}(\mathcal{D}_1)$ 表示**日志统计算子**。它不调用大模型，而是直接从 Stage I 的日志证据中计算：高分候选族群、候选有效率、相对收益、运行时间、慢模式比例以及失败模式出现频率。该步骤的作用是把第一阶段的原始候选记录转化为可用于归纳策略的经验统计。

$\mathcal{N}(\pi_1,\ldots,\pi_{B_2})$ 表示**策略规范化算子**。它也不调用大模型，而是对大模型返回的多个 policy proposal 做确定性清洗：解析结构化输出，统一同义策略名称，过滤非法或不稳定字段，规范化允许机制、排除机制、边界参数和更新范围。该步骤避免大模型自由表述中的噪声直接进入后续搜索。

$\mathcal{M}(\cdot)$ 表示**合成算子**。它把日志统计结果和规范化后的策略归纳结果合并，形成中间策略 $\widetilde{\Pi}_2$。具体而言，高信用候选中反复出现的机制会被提升为推荐或可接受策略；低效候选中反复出现的慢操作和失败模式会被写入排除策略或边界限制。

最终策略由中间策略和安全约束共同确定：
$$
\Pi_2 = \mathcal{Q} \left( \widetilde{\Pi}_2, \Pi_{\mathrm{safe}} \right).
$$
其中，$\mathcal{Q}(\cdot)$ 表示**强制约束算子**。它不依赖大模型判断，而是由实现中的固定安全规则执行。即使某次大模型归纳结果遗漏或弱化了复杂度风险，$\mathcal{Q}$ 仍会强制加入不可违反的约束，例如禁止全图中心性重算、每步 connected components 重算、全图重扫、无界 BFS/DFS、无界二跳扫描和非确定性随机排序。

因此，Stage II 的输出可以抽象为三类策略集合：

$$
\Pi_2=(S_2^+,S_2^0,S_2^-).
$$
其中，$S_2^+$  表示应被优先保留和强化的机制，$S_2^0$ 表示只有在边界限制下才可接受的机制，$S_2^-$ 表示应从后续搜索中排除的机制。对于网络瓦解任务而言，局部边界、弱连接、受限二跳、冗余抑制和阶段性权重等结构往往进入 $S_2^+$ 或 $S_2^0$，而全图重算、无界多跳搜索和高成本中心性重算则进入 $S_2^-$。

Stage II 的作用不是生成最终启发式，而是把 Stage I 的自由探索经验压缩成可执行的搜索策略。该策略诱导第三阶段的候选空间：

$$
\mathcal{H}_3
=
\mathcal{H}(\Pi_2)
=
\{h\in\mathcal{H}_{1}:h\models\Pi_2\}.
$$
也就是说，第三阶段不再在第一阶段的开放候选空间  $\mathcal{H}_1$ 中自由搜索，而只在满足策略 $\Pi_2$ 的候选空间中继续搜索：

$$
\mathcal{H}_{1}
\xrightarrow{\mathrm{Stage\ II}}
\mathcal{H}_{3}.
$$
并且有

$$
\Omega(\mathcal{H}_{3})
<
\Omega(\mathcal{H}_{1}),
$$
其中 $\Omega(\cdot)$ 表示候选语言的有效复杂度。由此，Stage II 将“开放程序探索”转化为“策略收缩下的启发式发现”，使后续搜索集中在可归因、可解释且计算上有界的网络瓦解机制空间中。

## 4.4 Stage III 有界树搜索与 Pareto 输出

Stage III 在 Stage II 归纳出的候选语言策略内继续搜索。令 Stage II 输出的图操作策略为 $\Pi_2$，其中包含允许信号、禁止模式、cap 约束、局部更新范围和推荐机制族。Stage III 的候选空间定义为：

$$
\mathcal{H}_3
=
\mathcal{H}(\Pi_2)
=
\{h\in\mathcal{H}:h\models\Pi_2\}.
$$

其中 $h\models\Pi_2$ 表示候选启发式满足有界图操作约束，例如局部邻域扫描必须受 cap 限制，更新范围只能覆盖邻居和受限二跳 affected nodes，排序键必须确定，且不得引入全图中心性重算、每步 connected components 刷新、无界 BFS/DFS、无界二跳扫描或非确定性随机排序。由此，Stage III 不再在开放程序空间中扩张，而是在证据收缩后的局部机制空间中继续搜索。

### 4.4.1 受控扩展

当前实验中，Stage III 使用 canonical `Powerlaw_500` proxy graph 进行搜索，预算为 $B_3=200$ 个 tree nodes。所有 LLM 生成候选均使用 `gpt-5.5`，reasoning effort 为 `none`，temperature 为 $0.2$，每次调用生成一个候选程序，单候选 timeout 为 $90$ 秒。Stage III 从 Stage I 的有效候选中选择最多 $K=24$ 个 seed nodes，并将扩展预算分配给四类分支：

$$
B_Q:B_S:B_B:B_R
=
60:60:50:30.
$$

其中 $Q$ 分支偏向质量，$S$ 分支偏向速度，$B$ 分支搜索质量-时间折中区域，$R$ 分支用于修复 validity、timeout、混合类型 heap key 和大图风险。对第 $t$ 次扩展，分支角色为：

$$
b_t\in\{Q,S,B,R\}.
$$

令 $\mathcal{V}^{(3)}_{b_t}$ 表示当前分支中的有效可扩展节点集合，$\mathcal{V}^{(3)}$ 表示 Stage III 中全部有效可扩展节点集合，则 parent 候选池为：

$$
\mathcal{P}^{(3)}_t
=
\begin{cases}
\mathcal{V}^{(3)}_{b_t}, & \mathcal{V}^{(3)}_{b_t}\neq\varnothing,\\
\mathcal{V}^{(3)}, & \mathcal{V}^{(3)}_{b_t}=\varnothing.
\end{cases}
$$

Stage III 使用与 Stage I 一致的父节点扩展规则。设有效树节点 $u$ 已有子节点数为 $c(u)$，其扩展优先级定义为：

$$
U_3(u)
=
\Phi_3(u)
+
\frac{\lambda}{1+c(u)}.
$$

当前实验取 $\lambda=0.10$，每轮选择：

$$
u_t
=
\arg\max_{u\in\mathcal{P}^{(3)}_t}
U_3(u).
$$

该机制使高质量候选获得更高扩展概率，同时通过子节点数惩罚避免预算长期集中在单个 lineage 上。

候选生成阶段中，只有以下步骤由大模型 LLM 完成：

$$
\tilde{h}_t
=
\operatorname{LLM}_{\theta}
\left(
u_t,\,
b_t,\,
\Pi_2,\,
\mathcal{M}(u_t)
\right),
$$

其中 $\mathcal{M}(u_t)$ 表示 parent 节点的代码和 proxy 评估记录。LLM 被要求输出完整确定性的 `degree_order(G)` 实现，并且只能修改局部信号组合、权重、cap、phase schedule 和局部 update rule；不得新增全局慢算法，也不得把 parent 包装成外部调用。除 $\operatorname{LLM}_{\theta}$ 之外，候选解析、策略检查、评估、排序和 Pareto 选点均由确定性程序完成。

候选 $\tilde{h}_t$ 在进入 evaluation 前先经过静态策略检查。定义拒绝函数：

$$
\chi(\tilde{h}_t)
=
\mathbb{1}
[
g(\tilde{h}_t)
\lor
c(\tilde{h}_t)
\lor
z(\tilde{h}_t)
\lor
p(\tilde{h}_t)
],
$$

其中 $g$ 表示全图中心性或全图重扫风险，$c$ 表示 connected components 刷新，$z$ 表示无界二跳扫描，$p$ 表示 shortest-path 或 all-pairs path search。若 $\chi(\tilde{h}_t)=1$，候选直接判为无效；否则调用统一 evaluator 计算 $R$、auc-cNBI 和运行时间。

Stage III 的搜索分数由 root-relative 碎裂增益、GCC/R 质量、运行时间和过程碎裂质量组成。令 $h_0$ 为 root heuristic，$A(h)$ 表示 auc-cNBI，$T(h)$ 表示候选排序运行时间，则：

$$
\Delta_0(h)
=
A(h)-A(h_0).
$$

Stage III 的排序分数为：

$$
\Phi_3(h)
=
0.40\rho^+(\Delta_0(h))
+
0.25\rho^-(R(h))
+
0.25\rho_T^-(T(h))
+
0.10\rho^+(A(h)).
$$

其中 $\rho^+$ 表示越大越好的秩归一化函数，$\rho^-$ 表示越小越好的秩归一化函数，$\rho_T^-$ 表示带饱和的时间秩函数。相较 Stage I，Stage III 将时间权重提高到 $0.25$，对应“候选语言收缩后更强调部署成本”的设计目标。

### 4.4.2 Pareto 输出

Stage III 完成 $B_3=200$ 次扩展后，在有效候选集合 $\mathcal{C}_3$ 上计算 proxy Pareto frontier。对任意两个候选 $a,b\in\mathcal{C}_3$，若 $a$ 在 auc-cNBI、$R$ 和 runtime 上均不劣于 $b$，且至少一个指标严格更优，则 $a$ 支配 $b$：

$$
a\succ b
\iff
A(a)\ge A(b)
\land
R(a)\le R(b)
\land
T(a)\le T(b)
\land
\left[
A(a)>A(b)
\lor
R(a)<R(b)
\lor
T(a)<T(b)
\right].
$$

由此得到 Stage III 的 Pareto 前沿：

$$
\mathcal{F}_3
=
\{h\in\mathcal{C}_3:\nexists h'\in\mathcal{C}_3,\ h'\succ h\}.
$$

最终输出包含两个角色化候选。质量优先点从 $\mathcal{F}_3$ 中选择低 $R$、高 auc-cNBI 且运行时间可接受的候选：

$$
h_Q
=
\psi_Q(\mathcal{F}_3).
$$

速度优先点从 $\mathcal{F}_3$ 中选择运行时间更低且仍保留合理质量的候选：

$$
h_S
=
\psi_S(\mathcal{F}_3;h_Q).
$$

需要说明的是，上述 $\psi_Q$ 和 $\psi_S$ 是正文中的抽象描述，具体实验实现与该抽象存在一点差异：代码中还使用了轻量 target guard，以避免最终 proxy 选点被单一指标牵引到过低 cNBI、过高 $R$ 或过慢 runtime 的区域。该 guard 只作用于最终 Pareto 选点，不改变 Stage III 的 LLM 候选生成、策略检查或树搜索过程。

正文只使用两个最终候选名：HAST-Final-S 和 HAST-Final-Q。二者不是两个新框架，而是同一个 HAST 搜索过程输出的两个 Pareto 角色点。当前实验中，Stage III 生成 $200$ 个 tree nodes，其中 $196$ 个有效；最终候选再进入 12 图统一 evaluation mechanism。该流程保证主结果比较的是候选启发式本身的排序运行时间，而不是离线 LLM 搜索成本。

# 5 实验

## 5.1 实验设计

本节实验回答四个问题：HAST 的最终候选是否位于更实用的质量-时间折中区域；HAST 的机制链是否必要；HAST 是否只是花更多搜索预算堆出来；最终候选为什么有效。为避免把未做实验写成过强结论，本文统一采用“同一 evaluation harness 下的经验比较”口径，不宣称严格 equal-budget SOTA，也不宣称在所有图和所有指标上最优。

**数据集。** 实验在 12 个 benchmark graphs 上进行，覆盖真实网络和一个 synthetic benchmark。每个方法在每个图上输出完整节点删除序列，评估器沿相同删除比例网格计算 GCC/R 曲线和 cNBI 曲线。多图均值先对每个图计算对应指标，再按图平均；主表中的 `datasets` 列用于说明某些 Python fallback 是否覆盖完整 12 图。

**指标。** 主指标包括 $R$、auc-cNBI 和 runtime。$R$ 越低越好，表示达到瓦解阈值所需删除比例或对应的最终拆解质量；auc-cNBI 越高越好，表示删除过程中产生了更充分、更均衡的 residual fragmentation；runtime 越低越好，表示候选启发式本身更轻量。GCC 曲线和 cNBI 曲线同时报告，因为二者回答不同问题：GCC/R 保证标准瓦解目标，cNBI 揭示 same-GCC 下的过程碎裂差异。

**时间口径。** 本文区分 final heuristic comparison、search framework comparison 和 scaling runtime-only comparison。前者比较候选算法在同一图上输出删除序列的运行时间，不包含 LLM prompt、代码生成或搜索日志成本；后者比较不同自动搜索框架的候选数量、有效率、prompt elapsed time、candidate validation time 和 total logged search time；5.5.1 的大图 runtime-only 实验只检查删除序列生成是否能在更大 synthetic graph 上完成，不计算 R 或 auc-cNBI。因此，主结果图回答“最终算法是否好用”，搜索成本图回答“搜索过程是否烧预算”，扩展性图回答“固定后的候选在大图上是否仍能跑完，以及最坏开销在哪里”。

**基线组。** 本文比较三类方法。第一类是 classic/static baselines，包括 DC、HDA、CoreHD、KCore、CLUC、CI 等。第二类是 algorithm-found references，包括 FunSearch-like、Clade-AHD-like、MCTS-AHD-like、AlphaEvolve-like。第三类是 Python strong baselines 或 fallback evidence items，包括 NDC、NCDC、NDJC、GND-py、VE-py 和 LGD variants。HAST 输出为 HAST-Final-S 和 HAST-Final-Q。

**强基线复现限定。** BPD 和 MinSum 在相关工作中应作为不同方法讨论；但当前本地 fallback 不能写成官方 BPD 和官方 MinSum 的两个独立复现，因此不进入本文 classic full-sequence R 主表。GND-py、VE-py、NDJC 等 Python fallback 若在大图超过 3600s 或无缓存，则只报告 timeout 或 unavailable 状态，不生成伪曲线，也不把缺失结果解释为这些方法质量差。这个限定不会削弱主结论，反而避免把实现语言、缓存状态和算法能力混在一起。

**搜索预算公平性。** 所有 LLM 生成候选均使用 gpt-5.5，reasoning effort 设为 `none`，temperature 设为 0.2；每次调用生成一个候选程序，不使用 self-consistency、majority voting 或人工二次改写。候选程序必须暴露同一接口：输入图 $G$，输出完整节点删除序列；搜索过程中不允许读取测试标签、外部数据或已有测试曲线。所有候选通过同一验证器，验证内容包括 Python 语法、函数可调用性、返回类型、重复节点、缺失节点、运行异常和超时；失败候选计入 invalid rate，不从分母中删除。E2/E3 的每组 100 个候选仍表示独立候选程序数量，用于 observation 对照；新版 HAST 主实验的 Stage I 300 个候选和 Stage III 200 个候选则表示逐节点扩展的搜索树新增节点数量。每个 tree node 记录 `node_id`、`parent_node_id`、`depth`、`parent_auc_cNBI`、parent-relative $\Delta$AUC-cNBI 和 root-relative $\Delta$AUC-cNBI。Stage I/III 因 parent selection 依赖已有节点评估结果而顺序扩展；Stage II log-induced bound induction 的 10 次 LLM 调用可以并发执行，且不生成候选算法。父节点选点实现保留 `legacy` 与替代审计口径；本次实验采用 `legacy` 口径。搜索期只使用 canonical `Powerlaw_500` generated proxy；最终候选固定后再进入 12 图统一 evaluation mechanism。搜索成本统计包括 tree nodes、valid rate、prompt elapsed time 和 candidate validation time；最终算法 runtime 与离线搜索成本分开报告。

**随机性与统计边界。** 大多数传统启发式和 HAST-Final-Q/S 的执行是确定性的；主要随机性来自 LLM 搜索过程、候选生成和可能的 tie-breaking。当前主表报告的是固定最终候选在 12 图上的均值，不是多随机种子显著性检验。因此，正文避免使用 “statistically significant” 或“显著优于”这类尚未由多 seed 支撑的措辞。后续可在附录补充 bootstrap over graphs 的置信区间或多次 LLM 搜索种子。

## 5.2 结果与分析

### 5.2.1 Root-relative HAST 的质量-复杂度位置

主结果首先展示所有方法在 classic full-sequence R 口径下的 12 图均值。这里的 R 与旧 30% 截断评价不同：每个方法必须输出完整节点删除序列，并在删除第 $k=1,\ldots,N$ 个节点后计算 $GCC_k=LCC_k/original_N$，再取 $100\times \sum_k GCC_k/N$。因此本节的 R 使用百分数报告，数值越低越好；只有完整序列或明确允许的本地候选算法进入主表。

![All method quality complexity](../artifacts/figures/05_2_benchmark/fig13_12graph_quality_complexity_all_methods.png)

**图 5.1：12 图 benchmark 上的 classic R-复杂度位置。** 纵轴为本次重新计算的 classic full-sequence R 百分数，越低越好；横轴为删除序列生成算法的复杂度档位，因此越靠左下表示质量-复杂度位置越优。DC/KCore 是静态打分和排序，放在最左侧 $o(m+n\log n)$ 档；HDA/CoreHD/CI 等按原论文或本地 fast fallback 的 heap/2-core 更新口径归入 $o((m+n)\log n)$ 档；HAST-Final-Q/S 使用有界局部扫描和 lazy heap，也归入该档。CLUC 单独归入 $o(m\Delta)$；NDC 归入 $o(n\Delta^2)$，NCDC/NDJC 因包含社区检测与邻域差异项归入 $o(m\log n+n\Delta^2)$。Clade-AHD-like 和 AlphaEvolve-like 的最终候选包含动态组件刷新或组件规模评分，归入 $o(n(m+n))$ 档；FINDER 作为强化学习方法单独放在最右侧 `RL-method` 档，且当前仅有 uniform-cost 的 1/12 图完整序列，因此以空心标记显示。图中每个点同时标出对应 mean R。

| category | method | evidence | datasets | mean R ↓ | mean auc-cNBI ↑ | mean time ↓ | top1 auc | top3 auc | mean rank auc ↓ |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| algorithm_found | FunSearch-like | classic_full_sequence | 12 | 0.120 | 374.870 | 27.330s | 5 | 8 | 4.67 |
| algorithm_found | Clade-AHD-like | classic_full_sequence | 12 | 0.117 | 373.101 | 51.004s | 2 | 6 | 3.75 |
| algorithm_found | MCTS-AHD-like | classic_full_sequence | 12 | 0.138 | 298.545 | 22.848s | 0 | 1 | 8.92 |
| algorithm_found | AlphaEvolve-like | classic_full_sequence | 12 | 0.124 | 274.495 | 0.984s | 0 | 0 | 10.58 |
| algorithm_found | **HAST-Final-S** (`0ade8d3405c2`) | classic_full_sequence | 12 | 0.115 | 362.815 | 0.606s | 3 | 12 | 1.75 |
| algorithm_found | **HAST-Final-Q** (`cd9e3818033d`) | classic_full_sequence | 12 | 0.115 | 347.067 | 1.182s | 9 | 12 | 1.25 |
| static_or_classic | HDA | classic_full_sequence | 12 | 0.136 | 219.220 | 3.381s | 0 | 0 | 15.50 |
| static_or_classic | CoreHD | classic_full_sequence | 12 | 0.136 | 214.539 | 0.096s | 0 | 0 | 15.33 |
| static_or_classic | DC | classic_full_sequence | 12 | 0.159 | 72.891 | 0.006s | 0 | 0 | 18.83 |
| static_or_classic | CI | classic_full_sequence | 12 | 0.179 | 19.386 | 0.345s | 0 | 0 | 19.67 |
| static_or_classic | KCore | classic_full_sequence | 12 | 0.208 | 0.810 | 0.043s | 0 | 0 | 20.75 |
| static_or_classic | CLUC | classic_full_sequence | 12 | 0.172 | 0.269 | 0.437s | 0 | 0 | 21.50 |
| strong_python | NCDC | classic_full_sequence | 12 | 0.131 | 372.402 | 240.258s | 1 | 4 | 6.17 |
| strong_python | NDC | classic_full_sequence | 12 | 0.131 | 331.296 | 241.881s | 0 | 0 | 9.42 |
| strong_python | NDJC | classic_full_sequence | 12 | 0.148 | 145.409 | 257.006s | 0 | 0 | 17.36 |

GND/FINDER 的 `uniform_cost` 外部序列目前只在 Crime 图上通过完整序列校验，因此作为 Crime 锚点记录在 manifest，不进入 12 图均值主表。LGD variants 与 VE-py 在本次 strict validation 下没有形成 12 图完整主表行，只在 unavailable/rejected manifest 中保留来源说明。

按 mean auc-cNBI 排序的 Top-10 如下。该表单独列出前十名，是为了避免完整表格中方法类别过多而遮蔽高质量区域的相对位置。

| rank | method | category | mean R ↓ | mean auc-cNBI ↑ | mean time ↓ | top3 auc |
|---:|---|---|---:|---:|---:|---:|
| 1 | FunSearch-like | algorithm_found | 0.120 | 374.870 | 27.330s | 8 |
| 2 | Clade-AHD-like | algorithm_found | 0.117 | 373.101 | 51.004s | 6 |
| 3 | NCDC | strong_python | 0.131 | 372.402 | 240.258s | 4 |
| 4 | **HAST-Final-S** (`0ade8d3405c2`) | algorithm_found | 0.115 | 362.815 | 0.606s | 12 |
| 5 | **HAST-Final-Q** (`cd9e3818033d`) | algorithm_found | 0.115 | 347.067 | 1.182s | 12 |
| 6 | NDC | strong_python | 0.131 | 331.296 | 241.881s | 0 |
| 7 | MCTS-AHD-like | algorithm_found | 0.138 | 298.545 | 22.848s | 1 |

该结果支持一个更具体的结论：root-relative credit 与有界 Stage III 能够在较低复杂度档内找到 classic full-sequence R 很低的候选，但 Q/S 分工并不等价于“一个无条件质量第一、一个无条件速度第一”。HAST-Final-S 的 mean auc-cNBI 为 362.815，运行时间为 0.606s；HAST-Final-Q 的 classic R 为 11.48%，mean auc-cNBI 为 347.067，运行时间为 1.182s。与此同时，FunSearch-like、Clade-AHD-like 和 NCDC 在 auc-cNBI 上仍高于 S；旧 FAST21-cap24 速度参考线也没有被 Q/S 同时达到。因此本文只主张 HAST 在本轮预算下给出了新的质量-复杂度位置和质量-时间折中候选，而不把单次 run 写成所有参考线的全面胜出。

### 5.2.2 高质量候选区域暴露 root-credit 的质量缺口

为了避免主图被大量弱 baseline 稀释，图 5.2 只聚焦代表性候选，并统一以 AlphaEvolve-like 作为归一化基准。这个视角回答一个更尖锐的问题：若以一个轻量 search-found 方法为参照，HAST 的质量和运行时间分别落在哪里？结果显示，HAST-Final-S 的 auc-cNBI 明显高于 AlphaEvolve-like，且 runtime 更低；HAST-Final-Q 的 mean R 更低，auc-cNBI 也高于 AlphaEvolve-like，但 runtime 高于 S。ERA-like 在图中只作为灰色参考，不作为强调颜色。

<img src="../artifacts/figures/05_2_benchmark/fig17_hast_quality_speed_panel.png" alt="HAST quality speed panel" style="zoom: 33%;" />

**图 5.2：以 AlphaEvolve-like 为基准的质量与运行时间归一化比较。** 左图为 mean auc-cNBI 相对 AlphaEvolve-like 的倍数，竖线 1.0 表示与 AlphaEvolve-like 相同，越长越好；右图为 mean runtime 相对 AlphaEvolve-like 的倍数，竖线 1.0 表示与 AlphaEvolve-like 相同，越短越好。HAST-Final-Q/S 使用强调色，AlphaEvolve-like 使用基准色，ERA-like 和其他非 HAST 参考方法使用灰色或弱强调色，避免把 ERA-like 写成本文的视觉中心。该图展示的是 proxy 选择候选进入外部 12 图验证后的均值，不包含离线搜索成本。

这张图的叙事重点相应从“单一最佳算法”调整为“同一搜索过程输出两个可审计 Pareto 角色”。HAST-Final-S 说明严格 root credit 并不必然牺牲过程碎裂质量且可以保持轻量运行；HAST-Final-Q 则说明同一有界语言可以进一步压低 mean R。两者都来自 proxy Pareto 选择，而不是外部验证后重新挑选，因此图中展示的是固定候选的验证结果。

### 5.2.3  GCC 和 cNBI 曲线共同说明 HAST 没有偏离任务目标

图 5.4 和图 5.5 展示 12 图上的 GCC 曲线和 cNBI 曲线。GCC 曲线证明 HAST 没有偏离标准网络瓦解评价；cNBI 曲线展示 HAST 的优势主要体现在过程碎裂。两组曲线应与表 5.2 一起读，而不应把任何单张曲线图当成全部结论。

![12 graph GCC curves](../artifacts/figures/05_2_benchmark/fig10_gcc_curves_12graphs.png)

**图 5.4：12 图上的 GCC/R 删除曲线。** 每个子图对应一个 benchmark graph，每条曲线表示一个方法按其删除序列逐步移除节点后，残余图最大连通分量占比随删除比例变化的过程。该图用于检查 HAST-Final-Q/S 是否仍在标准网络瓦解目标上工作，而不是只优化 cNBI 的辅助指标；曲线越低，表示同样删除比例下最大连通分量被压得越小。

![12 graph cNBI curves](../artifacts/figures/05_2_benchmark/fig11_cnbi_curves_12graphs.png)

**图 5.5：12 图上的 cNBI 过程碎裂曲线。** 每个子图对应同一组 benchmark graph，每条曲线表示删除过程中残余图 pairwise disconnectedness、有效组件数和前五大残余块集中度共同形成的 cNBI 信号。该图用于观察方法在整个删除过程中是否产生更充分、更均衡的 residual fragmentation；曲线整体越高，表示过程碎裂质量越强。它与图 5.4 共同说明方法既要压低 GCC，也要避免只留下少数大块或大量无意义孤点。

HAST 不是每个图、每个指标都第一。FunSearch-like、Clade-AHD-like 和 NCDC 在过程碎裂质量上仍是更高的参考带；CoreHD 在运行时间上更快，但过程碎裂质量更低。HAST-Final-S 的 mean R 为 0.366、mean auc-cNBI 为 362.815、mean time 为 0.606s；HAST-Final-Q 的 mean R 为 0.356、mean auc-cNBI 为 347.067、mean time 为 1.182s。它们的价值在于把强 root 继承、相对碎裂信用和有界局部模板压缩成可运行的轻量算法，而不是用单一指标遮蔽另一个指标。

### 5.2.4 框架搜索本身也轻巧和鲁棒

一个自然质疑是：HAST 的最终候选是否只是花更多搜索成本堆出来的？为回答这个问题，新版实验统计自动搜索框架的候选数量、有效率和平均候选搜索时间。logged search time 定义为 prompt elapsed time 加 candidate validation time，根节点不计入统计。本轮 root-relative HAST 使用 300 个 Stage I tree nodes、10 次 Stage II bound induction 和 200 个 Stage III tree nodes；Stage I/III 合计 500 个候选节点，整体 valid rate 为 0.990，mean candidate validation time 为 0.026s，mean prompt elapsed time 为 39.729s/candidate。最终算法 runtime 与离线搜索成本分开报告：Q/S 的 12 图 mean runtime 分别为 1.182s 和 0.606s。

![Framework search time](../artifacts/figures/05_2_benchmark/fig20_framework_search_time.png)

**图 5.6：自动搜索框架的候选级搜索成本与有效率。** 左图统计每个搜索框架平均生成并验证一个候选所花费的 logged search time，即 LLM prompt elapsed time 加候选 validation time，数值越短表示每个候选的离线搜索开销越低；右图统计 valid candidate rate，数值越大表示生成候选越稳定、越少被接口检查、运行异常、重复/缺失节点或超时规则拒绝。前五项是 prior LLM-search 风格框架，最后三项是本文 HAST 的 Stage I free search、Stage III bounded search 以及二者的候选加权 mean HAST。该图比较的是离线搜索过程的候选生成效率与有效性，不是最终算法在 12 图上输出删除序列的 runtime。

| stage / method | planned budget | produces candidates | status | report fields |
|---|---:|---|---|---|
| Stage I cost-aware free search | 300 tree nodes | yes | 已完成 | 299/300 valid，root-relative score |
| Stage II log-induced bound induction | 10 LLM calls | no | 已完成 | 10 次 policy/bounds 归纳 |
| Stage III bounded guided search | 200 tree nodes | yes | 已完成 | 196/200 valid，输出 Q/S |

论文结论应保持为 logged-budget empirical comparison：本轮 root-relative run 的有效率高、评估开销很低，prompt 时间约 40 秒/候选；最终候选中 Q 提供更低 mean R 的瓦解角色，S 达到 ERA-like 附近过程碎裂质量并提供更强速度折中。由于 S 未通过旧 FAST21-cap24 的 reference gate，正文不写成“Q/S 全面超过旧 HAST-Final-Q/S”，而写成 HAST 找到新的强 Q 候选和轻量 S 候选。

## 5.3 消融实验

本节验证的对象不是单个最终算法，而是三阶段搜索过程本身。我们在不改变固定 Q/S 的前提下增加三类对照：从 HDA-original 独立采样 100 个候选、去掉显式时间压力的 100 个候选、以及不使用 Stage II bounds 的 Stage III 200 节点 LLM 自由探索。所有候选仍只在 canonical `Powerlaw_500` proxy 上参与搜索；进入表 5.3 的 Top10 均由 proxy auc-cNBI 或 proxy rank_score 选择，然后再进入同一 12 图外部验证流程。外部验证只评估这些 proxy-selected 候选，不回写最终候选映射，也不覆盖 `HAST-Final-Q/S`。

综合分数 `rank_score` 只作为辅助读数，用来避免在 auc-cNBI、R 和 time 三个目标之间硬做单指标结论。具体定义为

$$
\text{rank_score}=100(0.4p_{\text{auc-cNBI}}+0.3p_R+0.3p_T),
$$

其中 $p_{\text{auc-cNBI}}$ 是 auc-cNBI 的分位排名，$p_R$ 和 $p_T$ 分别是 R 与 runtime 的反向分位排名。表中仍同时报告原始 external-validation mean auc-cNBI、R 和 time；`# > AlphaEvolve` 与 `# > ERA-like` 只统计 proxy 阶段超过当前论文基线的候选数，不统计旧 BT/FAST reference。

![HAST 5.3 ablation search curves](../artifacts/figures/05_3_ablation/fig_5_3_hast_ablation_search_curves.png)

**图 5.3：三阶段搜索过程消融。** 左图展示不同搜索设置在 `Powerlaw_500` proxy 上的 best-so-far auc-cNBI 曲线，回答“候选数增加时是否更快找到高质量区域”；中图展示同一过程的 best-so-far proxy rank_score 曲线，把 auc-cNBI、R 和 time 的折中纳入比较；右图展示 valid candidate rate 和 proxy Pareto density，用来区分“偶然冲到高分”与“稳定地产生可用候选”。`HAST-free search` 是 Stage I 300 节点自由树搜索，`HAST bounded search` 是使用 Stage II 归纳边界后的 Stage III 200 节点搜索；`independent sampling` 不使用树 lineage，`no-time-awareness search` 去掉显式时间压力，`Stage III LLM free exploration` 使用与 Stage III 相近的 seed 和分支节奏，但不注入 Stage II bounds。该图说明，树搜索比独立采样更快进入高分区，bounded Stage III 的有效率明显高于无边界 Stage III 自由探索；无时间压力设置虽然 proxy auc-cNBI 可达到更高峰值，但 12 图 Top10 runtime 明显变差。

| group | setting | budget | valid rate | best proxy auc-cNBI | proxy top10 mean | External top10 mean auc-cNBI | External top10 mean R | External top10 mean time | rank_score | # > AlphaEvolve | # > ERA-like |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full HAST | HAST-free search | 300 tree nodes | 0.997 | 74.610 | 74.320 | 355.386 | 0.392 | 1.564s | 66.802 | 11 | 11 |
| Full HAST | HAST bounded search | 200 tree nodes | 0.980 | 74.607 | 73.595 | 335.311 | 0.395 | 0.833s | 66.309 | 3 | 3 |
| Full HAST | mean HAST | 500 generated nodes | 0.990 | 74.610 | 74.407 | -- | -- | -- | 91.019 | 14 | 14 |
| Sampling/search loop | independent sampling | 100 candidates | 0.820 | 74.006 | 73.225 | 253.401 | 0.431 | 0.976s | 35.963 | 1 | 1 |
| Cost awareness | no-time-awareness search | 100 candidates | 0.870 | 75.441 | 74.715 | 274.954 | 0.394 | 5.590s | 37.383 | 13 | 13 |
| Bound induction | Stage3 LLM free exploration | 200 tree nodes | 0.725 | 74.920 | 74.276 | 356.963 | 0.392 | 2.613s | 58.185 | 11 | 11 |
| Credit/selection | raw proxy score | offline top10 | -- | -- | -- | 305.888 | 0.413 | 0.846s | 53.333 | -- | -- |
| Credit/selection | parent-relative delta | offline top10 | -- | -- | -- | 305.888 | 0.413 | 0.846s | 53.333 | -- | -- |
| Credit/selection | root-relative delta | offline top10 | -- | -- | -- | 305.888 | 0.413 | 0.846s | 53.333 | -- | -- |
| Credit/selection | quality-only selection | offline top10 | -- | -- | -- | 305.888 | 0.413 | 0.846s | 53.333 | -- | -- |
| Credit/selection | quality+R selection | offline top10 | -- | -- | -- | 305.888 | 0.413 | 0.846s | 53.333 | -- | -- |
| Credit/selection | quality+R+time Pareto | offline top10 | -- | -- | -- | 349.768 | 0.391 | 0.838s | 70.765 | -- | -- |
| Full HAST | HAST-Final-S (`0ade8d3405c2`) | fixed final | 1.000 | 59.305 | 59.305 | 362.815 | 0.366 | 0.606s | -- | -- | -- |
| Full HAST | HAST-Final-Q (`cd9e3818033d`) | fixed final | 1.000 | 63.375 | 63.375 | 347.067 | 0.356 | 1.182s | -- | -- | -- |

**表 5.3：HAST 三阶段搜索框架消融。** `valid rate`、`best proxy auc-cNBI`、`proxy top10 mean` 和超过基线数量均来自搜索期 proxy；`External top10 mean` 三列来自 proxy-selected Top10 的 12 图评估。`mean HAST` 是 Stage I+Stage III 生成候选池的候选级汇总，因此不单独做外部 Top10 倒选。结果有三点。第一，独立采样能产生少数可用程序，但有效率、proxy 强候选密度和 12 图 Top10 均明显弱于树搜索，说明 lineage expansion 不是多余包装。第二，no-time-awareness 在 proxy 上冲到最高 auc-cNBI，但 Top10 12 图 runtime 达到 5.590s，说明如果不把复杂度写入搜索目标，LLM 容易发现慢候选。第三，无 Stage II bounds 的 Stage III 自由探索可以找到高 auc-cNBI 候选，但有效率降到 0.725，Top10 runtime 升至 2.613s；正式 bounded Stage III 的 Top10 质量略低但更快、更稳定，且 Pareto 的 `quality+R+time` 离线选择优于 raw/quality-only 重排。由此可见，HAST 的主要贡献是一个能把高质量、低 R 和运行时间同时纳入搜索闭环的三阶段框架，而不是单次 LLM 采样或单指标 proxy 排序。

## 5.4 算法可解释性与搜索来源

### 5.4.1 自由探索日志的可解释性

基于5.2的实验，自由探索日志还给出了可解释的收缩线索：

| 自由探索日志观察                                | 可信引导                       | LLM 生成边界                           |
| ----------------------------------------------- | ------------------------------ | -------------------------------------- |
| 高信用候选保留 residual degree backbone         | degree/root 仍是可信骨架       | 不删除基础度信号，只在其上加局部碎裂项 |
| 高信用候选反复使用 frontier、weak-tie、boundary | 这些局部结构对碎裂有针对性     | 允许局部边界、弱连接、冗余抑制特征     |
| 慢候选常做无界 two-hop 或 nested-neighbor scan  | 复杂扫描会制造虚假收益         | 限制 two-hop 范围和邻域枚举预算        |
| 慢候选频繁重算 connected components             | 全图重算不适合作为默认生成模式 | 限制局部更新和刷新频率                 |
| 低潜力 family 长期不改进                        | family 级搜索方向不可信        | 剪掉低潜力 family，把预算给高潜力模板  |

### 5.4.2 HAST-Final-Q 的机制与搜索来源

本节 case study 以 root-relative `target_family_full_ritelt` run 的搜索日志为机制来源，同时按 pE4 外部 12 图验证结果统一最终命名：`HAST-Final-S` 对应候选 `0ade8d3405c2`，`HAST-Final-Q` 对应候选 `cd9e3818033d`。本次完整搜索生成 Stage I 的 300 个 tree nodes，其中 299 个有效；Stage II 执行 10 次 bound induction；Stage III 生成 200 个 tree nodes，其中 196 个有效。需要注意，以下 knockout 与结构画像图保留原始 case-study 脚本中的 source-label，用于解释 two-hop-boundary family 的局部机制；最终 Q/S 角色以 5.2 的外部验证映射为准。

从论文层面看，HAST-Final-Q 的打分结构可抽象为如下局部模板：

$$
s_t(v)=w_d(\rho_t)d_t(v)+w_f(\rho_t)f_t(v)+w_w(\rho_t)q_t(v)+w_b(\rho_t)b_t(v)-w_r(\rho_t)r_t(v),
$$

其中 $\rho_t=t/|V|$ 表示删除进度，$d_t(v)$ 是残余度信号，$f_t(v)$ 与 $q_t(v)$ 分别刻画 frontier 和 weak-tie 倾向，$b_t(v)$ 表示受限二跳边界信号，$r_t(v)$ 表示邻域冗余惩罚。这里的公式用于解释算法构成，不声称它是唯一实现形式。对应到机制含义，residual degree 保留 HDA 类方法已经验证有效的一阶局部强信号；frontier/weak-tie 偏向连接脆弱邻居或低度邻居的节点；two-hop boundary 在 `cap_2` 范围内估计节点删除后可能影响到的外部边界；redundancy penalty 降低对高度重叠局部团簇的重复攻击；phase weights 则允许算法在早期更依赖 degree，在中后期增加碎裂压力。这样的设计解释了为什么 HAST-Final-Q 既不像纯 degree 规则，也不像自由搜索中出现的慢速全局扫描。

为检验这些结构项是否真的进入算法行为，我们重新运行了 case study 脚本 `src/experiments/case_study_hast_s.py`。该脚本名中的 `hast_s` 是早期 source-label；按本文最终命名，它解释的是 `cd9e3818033d` 所代表的 HAST-Final-Q 机制。脚本只读取固定候选代码和 run log，不修改 `final/HAST-Final-Q.py`；输出表位于 `artifacts/source_tables/case_study_hast_s/`，图位于 `artifacts/figures/`。实验包含三部分：组件 knockout、早期删除节点结构画像和打分项尺度分解。

![fig24_hast_s_component_knockout](../artifacts/figures/05_4_interpretability/fig24_hast_s_component_knockout.png)

**图 5.7：HAST-Final-Q 的组件 knockout。** 左图报告每个变体在 12 图上的 mean auc-cNBI，中图报告 mean R，右图报告前 20% 删除序列相对完整 HAST-Final-Q 的变化比例。`residual degree only` 保留同样的 lazy heap 和动态残余度更新，但移除 frontier、boundary/reach、weak/bridge、redundancy penalty 和 phase 权重；`- all local terms` 同时移除 frontier、boundary/reach、weak/bridge 和 redundancy penalty，但保留 degree backbone 与 phase/cap schedule。结果显示，单独移除 frontier、boundary/reach、weak/bridge 或 redundancy penalty 后，12 图上完整删除序列完全相同，因此 auc-cNBI、R 和前 20% cNBI 都不会变化；这不是画图错误，而是说明这些单项在 Q 的当前权重下没有越过 lazy heap 排序 margin。组合移除所有局部项则会改变 96.9% 的前 20% 删除位置，使 mean auc-cNBI 从 335.510 降到 216.885，mean R 从 0.397 变差到 0.441。固定 phase weights 会降到 327.520；退化为 residual degree only 会降到 230.265。由此可见，Q 的主要排序力来自 degree + phase/cap schedule，局部项整体有用，但单项更多是 bounded tie-break 和小边际修正。

| variant | datasets | mean R ↓ | mean auc-cNBI ↑ | mean time ↓ | Δauc vs full |
|---|---:|---:|---:|---:|---:|
| HAST-Final-Q full | 12 | 0.397 | 335.510 | 0.855s | 0.000 |
| - frontier | 12 | 0.397 | 335.510 | 0.854s | 0.000 |
| - boundary/reach | 12 | 0.397 | 335.510 | 0.863s | 0.000 |
| - weak/bridge | 12 | 0.397 | 335.510 | 0.848s | 0.000 |
| - redundancy penalty | 12 | 0.397 | 335.510 | 0.846s | 0.000 |
| - all local terms | 12 | 0.441 | 216.885 | 0.847s | -118.624 |
| - phase weights | 12 | 0.395 | 327.520 | 1.109s | -7.990 |
| residual degree only | 12 | 0.436 | 230.265 | 0.271s | -105.244 |

这里的 knockout runtime 由 case-study 脚本直接计时，主要用于同一脚本内比较；正文主表仍以外部 full validation 的 HAST-Final-Q mean time 1.182s 为准。由于 case-study 图表保留早期 source-label 与独立复跑 harness，数值用于机制解释，不替代 5.2 中固定最终候选的外部 12 图汇总。

<img src="../artifacts/figures/05_4_interpretability/fig25_hast_s_early_node_features.png" alt="HAST-Final-Q early node features" style="zoom: 33%;" />

**图 5.8：HAST-Final-Q 早期删除节点的结构画像。** 该图统计前 20% 删除节点在被删除瞬间的局部特征，并与 residual degree only 变体比较。横轴为 HAST-Final-Q 相对 residual degree only 的特征比例，虚线 1.0 表示二者相同。HAST-Final-Q 选择的早期节点 residual degree 基本相同，为 0.99x，但 weak pressure 为 1.13x、boundary fraction 为 1.11x、bridge pressure 为 1.08x，redundancy 为 0.91x。这说明完整算法没有偏离高残余度骨架，却更倾向于选择边界更外向、弱连接压力更高、局部冗余更低的节点。

![HAST-Final-Q score decomposition](../artifacts/figures/05_4_interpretability/fig26_hast_s_score_decomposition.png)

**图 5.9：HAST-Final-Q 早期删除节点上的打分项尺度分解。** 左图报告前 20% 删除节点上各项的平均 signed score contribution，右图报告各项 absolute contribution share。Residual degree 项贡献最大，平均为 32.42，占绝对打分尺度的 75.1%；weak/bridge、boundary/reach 和 frontier 分别占 12.0%、6.3% 和 4.2%；penalty 项为负，约占 1.2%。这解释了图 5.7 中的现象：局部结构项确实进入了打分，但尺度小于 degree backbone，因此在 HAST-Final-Q 这个低 R / 崩溃优先候选中，它们主要改变边界附近的同度或近同度选择，而不是完全重写全局排序。

搜索来源也支持这一解释。HAST-Final-Q（`cd9e3818033d`）在可追溯 Stage III 树中不是孤立点，而是从 Stage I seed 继续扩展出的深度 8 lineage。沿线节点多次在 proxy auc-cNBI 与 time 之间调整，最终 `stage3-0044` 在该分支上取得更低外部 mean R 角色。这也是为什么本文把 Q/S 写成两个 Pareto 输出角色，而不是把任一候选写成所有指标上的无条件最优点。

| node | depth | proxy R ↓ | proxy auc-cNBI ↑ | proxy time ↓ | Δroot auc |
|---|---:|---:|---:|---:|---:|
| stage3-seed-0009 | 0 | 0.578 | 58.350 | 0.0802s | 5.715 |
| stage3-0028 | 1 | 0.576 | 59.108 | 0.0452s | 6.474 |
| stage3-0029 | 2 | 0.575 | 59.323 | 0.0444s | 6.689 |
| stage3-0033 | 3 | 0.575 | 59.571 | 0.0423s | 6.937 |
| stage3-0036 | 4 | 0.575 | 59.387 | 0.0415s | 6.753 |
| stage3-0041 | 5 | 0.575 | 60.012 | 0.0439s | 7.378 |
| stage3-0042 | 6 | 0.558 | 58.676 | 0.0431s | 6.041 |
| stage3-0043 | 7 | 0.569 | 59.523 | 0.0437s | 6.889 |
| stage3-0044 (`cd9e3818033d`) | 8 | 0.570 | 60.502 | 0.0490s | 7.868 |

因此，HAST-Final-Q 的机制结论应写得克制：它不是一个复杂项全部大幅贡献的“结构大杂烩”，而是一个以动态 residual degree 为主轴、由 phase schedule 控制复杂度和阶段偏好、再用 bounded frontier/boundary/weak-tie/redundancy 信号做局部修正的低 R / 崩溃优先候选。这种结构解释了它为什么显著强于纯 residual degree only，也解释了它为什么没有在 12 图 mean auc-cNBI 上超过 HAST-Final-S 或 ERA-like。

### 5.4.3 HAST-Final-S 的机制与搜索来源

机制案例 `case_study_hast_q.py` 保留早期 Q-source 脚本名；按本文最终命名，它解释的是 `0ade8d3405c2` 所代表的 HAST-Final-S 机制。与 HAST-Final-Q 的 degree + phase/cap 主导模式相比，该 source 的局部结构项权重更大：其 `main` score 同时包含 hub/degree、frontier/two-hop、bridge/weak、leaf/low pressure 和 redundancy penalty；`secondary` 与 `tertiary` key 也继续使用 frontier、bridge、two-hop 和 redundancy 作为 tie-break。为了与 5.4.1 保持完全一致，我们运行 `src/experiments/case_study_hast_q.py`，输出目录为 `artifacts/source_tables/case_study_hast_q/`，并使用相同的 12 图、相同 metric harness、相同三类图：组件 knockout、早期结构画像和打分项尺度分解。

![HAST-Final-S component knockout](../artifacts/figures/05_4_interpretability/fig27_hast_q_component_knockout.png)

**图 5.10：HAST-Final-S 的组件 knockout。** 左图报告 mean auc-cNBI，中图报告 mean R，右图报告前 20% 删除序列相对完整 HAST-Final-S 的变化比例。与 Q 不同，S 的每个单项 knockout 都会改变删除序列和质量。去掉 frontier/two-hop 的影响最大：mean auc-cNBI 从 366.462 降到 318.272，mean R 从 0.386 变差到 0.408，前 20% 删除位置改变 93.8%。去掉 bridge/weak 后 auc-cNBI 降到 348.102；去掉 leaf/low pressure 后降到 353.052；去掉 redundancy penalty 后降到 360.008。`- all local terms` 与 residual degree only 都退回到约 230 auc-cNBI 的区域，说明 S 的过程碎裂优势不是 degree backbone 单独带来的，而是局部 frontier/two-hop 与 bridge/weak 等项共同推高的。固定 phase weights 在本次复跑中略高于 full S，达到 368.075，但 runtime 也更高；因此 phase schedule 在 S 中更像质量-速度折中，而不是单调提升质量的开关。

| variant | datasets | mean R ↓ | mean auc-cNBI ↑ | mean time ↓ | Δauc vs full |
|---|---:|---:|---:|---:|---:|
| HAST-Final-S full | 12 | 0.386 | 366.462 | 1.262s | 0.000 |
| - frontier/two-hop | 12 | 0.408 | 318.272 | 1.172s | -48.191 |
| - bridge/weak | 12 | 0.394 | 348.102 | 1.173s | -18.360 |
| - leaf/low pressure | 12 | 0.389 | 353.052 | 1.190s | -13.410 |
| - redundancy penalty | 12 | 0.388 | 360.008 | 1.180s | -6.454 |
| - all local terms | 12 | 0.440 | 231.903 | 1.183s | -134.559 |
| - phase weights | 12 | 0.381 | 368.075 | 1.328s | +1.613 |
| residual degree only | 12 | 0.436 | 230.265 | 0.299s | -136.197 |

![HAST-Final-S early node features](../artifacts/figures/05_4_interpretability/fig28_hast_q_early_node_features.png)

**图 5.11：HAST-Final-S 早期删除节点的结构画像。** 横轴为 S 相对 residual degree only 的前 20% 删除节点特征比例，虚线 1.0 表示相同。S 删除的节点 residual degree 与 pure degree baseline 几乎相同，为 0.99x；但 frontier 和 bridge 都为 1.06x，two-hop mass 和平均邻居度均约为 1.03x，redundancy 为 0.93x。也就是说，S 并没有牺牲高残余度骨架，而是在同等 degree 层附近更偏向外向边界、二跳可达和低冗余节点。

![HAST-Final-S score decomposition](../artifacts/figures/05_4_interpretability/fig29_hast_q_score_decomposition.png)

**图 5.12：HAST-Final-S 早期删除节点上的打分项尺度分解。** Hub/degree 仍是最大项，平均 signed contribution 为 98.48，占 absolute score scale 的 66.2%；frontier/two-hop 是第二大项，平均贡献 36.56，占 24.6%；bridge/weak 占 6.6%，leaf/low 占 1.6%，redundancy penalty 为负项，占 0.9%。这与图 5.10 一致：S 的局部项不只是可解释装饰，而是足以改变排序和质量的实质结构。

S-source 的 case-study lineage 也显示出更强的局部结构作用：它从 `stage3-seed-0002` 出发，经 `stage3-0138` 和 `stage3-0140` 到达 `stage3-0142`，深度为 3，tree branch 为 B。最终点 proxy auc-cNBI 为 74.607，proxy R 为 0.317，proxy time 为 0.0209s，root-relative proxy 增益为 11.978。与 Q 的 degree + phase/cap 主导模式相比，S 在外部 12 图验证中保留了更高 mean auc-cNBI；代价是不同 scaling/case-study harness 下的 runtime 结论不能简单等同于 5.2 主表。

| node | depth | proxy R ↓ | proxy auc-cNBI ↑ | proxy time ↓ | Δroot auc |
|---|---:|---:|---:|---:|---:|
| stage3-seed-0002 | 0 | 0.315 | 74.458 | 0.0238s | 11.828 |
| stage3-0138 | 1 | 0.312 | 72.772 | 0.0207s | 10.142 |
| stage3-0140 | 2 | 0.316 | 73.672 | 0.0207s | 11.043 |
| stage3-0142 | 3 | 0.317 | 74.607 | 0.0209s | 11.978 |

把 Q 与 S 放在一起看，HAST 的输出角色更加清楚：Q（`cd9e3818033d`）更接近 degree + phase/cap 主导的低 mean R 候选，局部项整体有用但单项多被排序 margin 吸收；S（`0ade8d3405c2`）则让 frontier/two-hop 和 bridge/weak 更实质地参与排序，在 12 图验证中取得更高 mean auc-cNBI 和更低 mean runtime。这解释了为什么二者来自相近的 two-hop-boundary family，却表现为不同的质量-时间折中。

## 5.5 扩展性和崩溃点研究

### 5.5.1 扩展性实验

扩展性实验用于检查 HAST 在比 12 图 benchmark 更大的合成图上是否仍保持可执行。为避免把旧候选的 scaling 证据误写成本轮最终 Q/S 映射，本节的 scaling 图表沿用原始固定候选 `HAST-S3-0142-e2b3a642` 和 `HAST-S3-0048-d39e4f62` 的复跑结果；HDA-original、HDA-fast 和 CoreHD-fast 的 baseline 行沿用同一 synthetic scaling protocol 下已经保存的 source tables，不重新运行。旧 scaling 数据和图像仍保留在 artifacts 中用于复现 harness 和后续对照，但正文图表中的 HAST 行已经由本轮 fixed final 目录重新生成。

协议分为两部分。第一部分在 500、1000、5000 和 10000 节点的 powerlaw、ER、WS、SBM 四类合成图上做 full evaluation，每个规模和图族使用 seeds 42、43、44，并在 30% 删除率下报告 mean R、mean auc-cNBI 和 mean ordering runtime。第二部分把同一图族扩展到 50000、100000 和 1000000 节点，只检查删除序列是否合法并记录 ordering runtime；这一部分不计算 R 或 auc-cNBI，因此不能作为质量泛化证明，只能作为大图执行成本的上界检查。所有当前 HAST 行均写入 `artifacts/source_tables/scaling/current_hast_full_eval_500_to_10k.csv` 和 `artifacts/source_tables/scaling/current_hast_runtime_only_500_to_1000k.csv`，并同步到 unified source tables。

| method | 10k mean R ↓ | 10k mean auc-cNBI ↑ | 10k mean time ↓ |
|---|---:|---:|---:|
| HDA-original | 0.702 | 402.744 | 5.785s |
| HDA-fast | 0.713 | 384.571 | 0.151s |
| CoreHD-fast | 0.701 | 402.855 | 0.166s |
| HAST-Final-Q | 0.687 | 386.338 | 1.660s |
| HAST-Final-S | 0.669 | 455.348 | 2.888s |

![scaling_full_eval_500_to_10k_unified](../artifacts/figures/05_5_scaling/scaling_full_eval_500_to_10k_unified.png)

**图 5.13：500 到 10000 节点 synthetic full-evaluation scaling。** 三个子图分别报告 mean R、mean auc-cNBI 和 mean ordering runtime；横轴为节点数，对数刻度，四类 synthetic graph 与 3 个 seed 先在同一方法和规模下求平均。HAST-Final-S 在 10k 上达到最低 mean R 0.669 和最高 mean auc-cNBI 455.348，说明该固定候选在更大的 synthetic full-eval 图上仍能保持碎裂收益；HAST-Final-Q 的 10k mean time 为 1.660s，介于 fast baseline 和 S 之间。右图使用对数时间轴，显示 HAST-Q/S 比 HDA-fast 与 CoreHD-fast 更慢，但仍明显快于 HDA-original 的 10k ordering runtime。

![runtime_only_scaling_500_to_1000k_unified](../artifacts/figures/05_5_scaling/runtime_only_scaling_500_to_1000k_unified.png)

**图 5.14：500 到 1000000 节点 synthetic runtime-only scaling。** 该图只报告删除序列生成时间和合法性，不报告 R 或 auc-cNBI；圆点表示所有 12 个图族-seed 组合均成功，叉号表示 HDA-original 在该规模存在 timeout/incomplete。当前 HAST-Final-Q/S 在 runtime-only 表中 168 个重跑项全部有效。到 1M 节点时，HAST-Final-S 和 HAST-Final-Q 的跨图族 mean runtime 分别为 642.917s 与 412.231s；其中 powerlaw 与 WS 约为 150-205s，ER 约为 372-437s，而 SBM 是最坏格，Q/S 分别约为 1774.275s 和 931.536s。这个结果说明 bounded two-hop family 能跑完百万节点图，但 Python/NetworkX 实现下的百万 SBM 已经不是轻量秒级场景；后续若面向超大 SBM 或社区块密集图部署，需要把当前候选的局部刷新逻辑移植到更底层的数据结构或 C++/NumPy 稀疏实现。

综合两张图看，HAST-Final-Q/S 的扩展性结论是有边界的。S 在 500-10k full evaluation 中表现为更高过程碎裂收益点，尤其在 10k synthetic mean 上超过 HDA-original 和 CoreHD-fast 的 auc-cNBI；Q 在该 scaling 复跑中保留更低排序时间。runtime-only 扩展到 1M 时，二者都没有出现非法序列或 timeout，但它们并不比 HDA-fast/CoreHD-fast 更快，尤其在 SBM 上暴露出局部 two-hop scoring 的 Python 开销。因此，本节支持的是“固定候选具备可执行的大图上界证据”，而不是“已经取得最快的大图实现”。

### 5.5.2 崩溃点分析

除 mean R 和整条 GCC 曲线外，网络瓦解还可以从崩溃点角度评价：一个方法需要在多早的删除阶段把最大连通分量压到给定阈值以下。本文报告两类互补口径。第一类是标准化删除比例阈值 $CT@\tau$，定义为逐点评估曲线中第一个满足 $GCC \le \tau$ 的 removal ratio；本节报告 $CT@0.10$ 和 $CT@0.05$，越低表示网络越早进入 10% 或 5% 的崩溃区间。第二类是更严格的深崩溃节点数 CT-1% nodes，定义为第一个满足 $GCC \le 0.01$ 的整数删除步数，表示瓦解到 1% 所需删除的节点数量。前者便于跨图比较归一化崩溃位置，后者更接近“最终深度瓦解需要多少节点”的 percolation threshold 解释。

![GCC critical threshold mean](../artifacts/figures/05_5_collapse/fig21_gcc_critical_threshold_mean.png)

**图 5.15：GCC 标准化 critical threshold 均值。** 左图为 $CT@0.10$，右图为 $CT@0.05$，横轴为首次达到对应 GCC 阈值所需的 removal ratio，越低越好。结果显示，HAST-Final-Q 在两个标准化阈值上都表现最好：$CT@0.10$ 为 0.153，低于 ERA-like 的 0.158 和 NCDC 的 0.159；$CT@0.05$ 为 0.166，低于 NCDC 的 0.170、ERA-like 的 0.173 和 Clade-AHD-like 的 0.174。HAST-Final-S 在该口径下不是最优，但仍处于强 baseline 附近。

![GCC critical threshold CT10 heatmap](../artifacts/figures/05_5_collapse/fig22_gcc_critical_threshold_ct10_heatmap.png)

**图 5.16：12 个 benchmark graph 上的 $CT@0.10$ 热力图。** 每个单元格表示某方法在对应 graph 上首次将 GCC 压到 10% 以下所需的删除比例，颜色和数值均越低越好。该图说明标准化崩溃点存在明显图依赖：HAST-Final-Q 在若干图上很早进入 10% 崩溃区间，但并非每个图都领先；ERA-like、NCDC 和 Clade-AHD-like 仍在部分网络上保持很强竞争力。因此，$CT@0.10$ 更适合作为逐图补充证据，而不是单独替代 mean R 或完整 GCC 曲线。

| method | mean CT@0.10 ↓ | mean CT@0.05 ↓ | reached CT@0.10 | reached CT@0.05 | mean time ↓ |
|---|---:|---:|---:|---:|---:|
| HAST-Final-Q | 0.153 | 0.166 | 12/12 | 12/12 | 0.735s |
| ERA-like | 0.158 | 0.173 | 12/12 | 12/12 | 9.785s |
| NCDC | 0.159 | 0.170 | 12/12 | 12/12 | 240.258s |
| Clade-AHD-like | 0.159 | 0.174 | 12/12 | 12/12 | 51.004s |
| HAST-Final-S | 0.163 | 0.175 | 12/12 | 12/12 | 1.027s |
| FunSearch-like | 0.178 | 0.182 | 11/12 | 11/12 | 27.330s |
| CoreHD | 0.202 | 0.218 | 10/12 | 10/12 | 0.096s |
| HDA | 0.203 | 0.218 | 12/12 | 10/12 | 3.381s |

标准化崩溃点给出了对 HAST-Final-Q 有利的解释：Q 虽然在 mean auc-cNBI 上不是最高的候选，但它能较早把 GCC 推入 10% 和 5% 的崩溃区间，并且 runtime 远低于 NCDC 和 Clade-AHD-like。这说明低 mean R 候选并不只是“过程碎裂较弱”，而是在中深度崩溃阈值上保留了有效瓦解能力。

![GCC critical threshold 1pct mean](../artifacts/figures/05_5_collapse/fig21_gcc_critical_threshold_1pct_nodes_mean.png)

**图 5.17：GCC 瓦解到 1% 所需删除节点数的 12 图均值。** 横轴为 CT-1% nodes，越低越好；括号中的 reached rate 表示在 12 图中实际达到 $GCC \le 0.01$ 的比例，未达到者在图中按记录曲线的最后一步显示并在逐图图中标记。结果显示，FunSearch-like 在深崩溃阈值上仍是很强的参考线；HAST-Final-S 和 HAST-Final-Q 的 mean CT-1% nodes 分别为 839.3 和 883.0。

![GCC critical threshold 1pct 12 graphs](../artifacts/figures/05_5_collapse/fig22_gcc_critical_threshold_1pct_nodes_12graphs.png)

**图 5.18：12 个 benchmark graph 上的 CT-1% nodes。** 每个子图单独报告一个 graph 上各方法达到 $GCC \le 0.01$ 所需删除节点数量。该图说明，崩溃点指标并不等价于 auc-cNBI、runtime 或 $CT@0.10$：HAST-Final-S 在多个图上接近强 baseline，但并非所有图都领先；HAST-Final-Q 更偏低 mean R 和标准化崩溃阈值角色，在 1% 深崩溃阈值上不应被解释为质量第一的候选。

| method | mean CT-1% nodes ↓ | median CT-1% nodes ↓ | reached graphs | mean time ↓ |
|---|---:|---:|---:|---:|
| FunSearch-like | 830.7 | 507.0 | 11/12 | 27.330s |
| HAST-Final-S | 839.3 | 531.0 | 11/12 | 1.027s |
| NCDC | 843.3 | 537.0 | 11/12 | 240.258s |
| Clade-AHD-like | 862.9 | 525.0 | 11/12 | 51.004s |
| HAST-Final-Q | 883.0 | 516.5 | 10/12 | 0.735s |
| CoreHD | 1080.8 | 601.5 | 9/12 | 0.096s |
| HDA | 1140.5 | 610.5 | 8/12 | 3.381s |

崩溃点结果给出了一个比“曲线整体质量”更尖锐的比较：FunSearch-like、NCDC 和 Clade-AHD-like 在深崩溃目标下仍然非常强，不能在主叙事中被忽略。因此，本节不把 HAST 写成 CT-1% 的绝对最优方法，而是把它定位为接近强崩溃点 baseline、同时显著降低运行时间的质量-时间 Pareto 候选。HAST-Final-Q 的优势则主要体现在更低 mean R、标准化 CT 阈值和可部署性，而不是由 1% 崩溃点单独解释。

## 6 结论

本文提出了 **Contractive Heuristic Discovery for Network Dismantling (CHD-ND)**，即面向网络瓦解的收缩式启发式发现，并给出了其实例化框架 HAST。CHD-ND 关注网络瓦解中更本质的搜索治理问题：当面对存在强baseline且单一指标无法准确指导搜索方向的任务，自动启发式发现不应停留在开放程序空间中追逐绝对高分，而应将搜索证据逐步收缩为可归因、可解释、可部署的稳健算法。HAST 将这一思想落实为三类核心机制。首先，cNBI 将搜索期反馈从单一最大连通分量扩展到 residual fragmentation，使搜索能够观察 same-GCC 下被隐藏的碎裂形态。其次，root-relative credit 将候选分数从绝对表现校准为相对 root 的新增碎裂贡献，避免把 HDA/degree 等强骨架的继承能力误记为新机制。最后，log-induced bounded candidate language 将自由探索日志压缩为图操作策略，保留 residual degree、frontier、weak-tie、boundary 和 redundancy 等有效局部结构，同时限制无界多跳扫描、频繁全图刷新和不可审计的慢操作。

实验表明，HAST 能够在不依赖无界慢扫描的情况下发现具有竞争力的质量-时间折中候选。在 12 图 benchmark 的 classic full-sequence R 口径下，HAST-Final-S（`0ade8d3405c2`）达到 mean R 11.52%、mean auc-cNBI 362.815、mean time 0.606s；HAST-Final-Q（`cd9e3818033d`）达到 mean R 11.48%、mean auc-cNBI 347.067、mean time 1.182s。消融实验进一步说明，相对信用、时间压力和候选语言收缩共同决定了 HAST 的稳定性，而最终候选中的局部结构项并非不可解释的代码偶然物，而是可通过组件 knockout、早期节点画像和打分项分解进行审计的瓦解机制。总之，网络瓦解为 LLM 启发式发现提出了一个不同于通用 AHD 的问题形式，并为其他具有强启发式先验和复杂度捷径的图优化任务提供了一个新的思路和方向。



## 参考文献

[1] Flaviano Morone, Hernán A. Makse. Influence maximization in complex networks through optimal percolation. Nature, 2015. DOI: 10.1038/nature14604.

[2] Alfredo Braunstein, Luca Dall'Asta, Guilhem Semerjian, Lenka Zdeborová. Network dismantling. Proceedings of the National Academy of Sciences, 2016. DOI: 10.1073/pnas.1605083113.

[3] Lenka Zdeborová, Pan Zhang, Hai-Jun Zhou. Fast and simple decycling and dismantling of networks. Scientific Reports, 2016. DOI: 10.1038/srep37954.

[4] Xiao-Long Ren, Niels Gleinig, Dirk Helbing, Nino Antulov-Fantulin. Generalized network dismantling. Proceedings of the National Academy of Sciences, 2019. DOI: 10.1073/pnas.1806108116.

[5] Changjun Fan, Li Zeng, Yizhou Sun, Yang-Yu Liu. Finding key players in complex networks through deep reinforcement learning. Nature Machine Intelligence, 2020. DOI: 10.1038/s42256-020-0177-2.

[6] Marco Grassia, Manlio De Domenico, Giuseppe Mangioni. Machine learning dismantling and early-warning signals of disintegration in complex systems. Nature Communications, 2021. DOI: 10.1038/s41467-021-25485-8.

[7] Jiazheng Zhang, Bang Wang. Dismantling Complex Networks by a Neural Model Trained from Tiny Networks. Proceedings of the 31st ACM International Conference on Information and Knowledge Management, 2022. DOI: 10.1145/3511808.3557290.

[8] Bernardino Romera-Paredes et al. Mathematical discoveries from program search with large language models. Nature, 2024. DOI: 10.1038/s41586-023-06924-6.

[9] Haoran Ye, Jiarui Wang, Zhiguang Cao, Federico Berto, Chuanbo Hua, Haeyeon Kim, Jinkyoo Park, Guojie Song. ReEvo: Large Language Models as Hyper-Heuristics with Reflective Evolution. Advances in Neural Information Processing Systems, 2024. DOI: 10.48550/arXiv.2402.01145.

[10] Rui Zhang, Fei Liu, Xi Lin, Zhenkun Wang, Zhichao Lu, Qingfu Zhang. Understanding the Importance of Evolutionary Search in Automated Heuristic Design with Large Language Models. Parallel Problem Solving from Nature, 2024. DOI: 10.1007/978-3-031-70068-2_12.

[11] Pham Vu Tuan Dat, Long Doan, Huynh Thi Thanh Binh. HSEvo: Elevating Automatic Heuristic Design with Diversity-Driven Harmony Search and Genetic Algorithm Using LLMs. AAAI Conference on Artificial Intelligence, 2025. DOI: 10.1609/aaai.v39i25.34898.

[12] Alexander Novikov et al. AlphaEvolve: A coding agent for scientific and algorithmic discovery. arXiv, 2025. DOI: 10.48550/arXiv.2506.13131.

[13] He Yu, Jing Liu. Automatically optimizing heuristics for robust scale-free network design via large language models. Scientific Reports, 2025. DOI: 10.1038/s41598-025-25031-2.

[14] Google Research. An AI system to help scientists write expert-level empirical software. Nature, 2026. DOI: 10.1038/s41586-026-10658-6. arXiv:2509.06503.

[15] Agentic Harness Engineering. arXiv:2604.25850, 2026.

[16] Meta-Harness. arXiv:2603.28052, 2026.

[17] Hyperagents. arXiv:2603.19461, 2026.

[18] Meta Context Engineering. arXiv:2601.21557, 2026.

[19] MetaClaw. arXiv:2603.17187, 2026.

[20] AutoHarness. arXiv:2603.03329, 2026.

[21] VeRO. arXiv:2602.22480, 2026.

[22] Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu, Qingfu Zhang. Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model. ICML, 2024. OpenReview: BwAkaxqiLB; arXiv:2401.02051.

[23] Zhi Zheng, Zhuoliang Xie, Zhenkun Wang, Bryan Hooi. Monte Carlo Tree Search for Comprehensive Exploration in LLM-Based Automatic Heuristic Design. ICML, 2025. OpenReview: Do1OdZzYHr; arXiv:2501.08603.

[24] Xijun Li, Jiexiang Yang, Jinghao Wang, Bo Peng, Jianguo Yao, Haibing Guan. STRCMP: Integrating Graph Structural Priors with Language Models for Combinatorial Optimization. NeurIPS, 2025. OpenReview: VhGUS8kyaC; arXiv:2506.11057.

[25] Rongjie Zhu, Cong Zhang, Zhiguang Cao. Refining Hybrid Genetic Search for CVRP via Reinforcement Learning-Finetuned LLM. ICLR, 2026. OpenReview: aITKXFeivk; arXiv:2510.11121.

[26] Chunyu Wei, Wenji Hu, Xingjia Hao, Xin Wang, Yifan Yang, Yunhai Wang, Yang Tian, Yueguo Chen. GraphChain: Large Language Models for Large-scale Graph Analysis via Tool Chaining. NeurIPS, 2025. arXiv:2511.00457.

[27] Eric Zelikman, Qian Huang, Gabriel Poesia, Noah Goodman, Nick Haber. Parsel: Algorithmic Reasoning with Language Models by Composing Decompositions. NeurIPS, 2023. OpenReview: qd9qcbVAwQ.

[28] Mingchen Zhuge, Wenyi Wang, Louis Kirsch, Francesco Faccio, Dmitrii Khizbullin, Jürgen Schmidhuber. GPTSwarm: Language Agents as Optimizable Graphs. ICML, 2024.

## 附录 A：符号表

| 符号 | 含义 |
|---|---|
| $G=(V,E)$ | 输入网络图 |
| $\mathcal{G}_{\mathrm{p}}$ | Stage I 使用的 proxy graph 集合 |
| $\pi_h$ | 候选启发式 $h$ 输出的完整节点删除序列 |
| $G_t^h$ | 按 $\pi_h$ 删除前 $t$ 个节点后的残余图 |
| $s_{t,i}$ | $G_t^h$ 中第 $i$ 大连通分量大小 |
| $\mathrm{PD}_t,\mathrm{EC}_t,\mathrm{Top5}_t$ | cNBI 的三项残余碎裂统计 |
| $h$ | 候选启发式，即一个 `degree_order(G)` 函数 |
| $h_0$ | root heuristic；本文实验中为 HDA-original |
| $parent(h)$ | 搜索树中候选 $h$ 的父候选 |
| $R(h,G)$ | 候选 $h$ 在图 $G$ 上的 GCC/R 瓦解代价，越小越好 |
| $A(h,G)$ | 候选 $h$ 在图 $G$ 上的 $\mathrm{AUC}_{\mathrm{cNBI}}$，越大越好 |
| $T(h,G)$ | 候选 $h$ 在图 $G$ 上输出删除序列的 runtime，越小越好 |
| $R(h),A(h),T(h)$ | 候选 $h$ 在 proxy graphs 上的平均 $R$、auc-cNBI 和 runtime |
| $\Delta_0(h)$ | root-relative 碎裂增益，$\Delta_0(h)=A(h)-A(h_0)$ |
| $\rho^+(x),\rho^-(x)$ | 分别用于“越大越好”和“越小越好”指标的 rank-normalization |
| $\rho_T^-(x)$ | 带饱和的时间 rank-normalization |
| $\mathcal{H}_t$ | 第 $t$ 轮或第 $t$ 阶段的候选语言空间 |
| $\Omega(\mathcal{H})$ | 候选语言空间 $\mathcal{H}$ 的有效复杂度 |
| $\mathcal{C}_s,\mathcal{R}_s,\mathcal{L}_s$ | Stage $s$ 的候选集合、评估记录和搜索日志 |
| $\Phi_1,\Phi_3$ | Stage I 和 Stage III 的候选排序分数 |
| $U_1,U_3$ | Stage I 和 Stage III 的父节点扩展优先级 |
| $\mathcal{D}_1$ | Stage I 日志诱导出的 Stage II 证据包 |
| $\mathcal{T}_1,\mathcal{Y}_1,\mathcal{X}_1,\mathcal{Z}_1$ | Top 候选证据、族群统计、代码特征表和失败模式统计 |
| $\Pi_t$ | CHD 中第 $t$ 轮的候选语言收缩策略 |
| $\Pi_2$ | Stage II 输出并供 Stage III 使用的有界图操作策略 |
| $\Pi_{\mathrm{safe}}$ | 固定安全策略，用于排除全图慢扫描和非确定性排序等模式 |
| $B_1,B_2,B_3$ | Stage I、Stage II、Stage III 的搜索或归纳预算 |
| $\tau$ | 单候选执行超时时间 |
| $\mathcal{F}_3$ | Stage III 的 proxy Pareto frontier |
| $h_Q,h_S$ | 从 $\mathcal{F}_3$ 中选出的质量优先点和速度优先点 |



## 附录 B：三阶段搜索树case study

![HAST three-stage search tree](../artifacts/figures/appendix/fig30_hast_three_stage_search_tree.png)

**图 B.1：HAST 三阶段搜索树。** 图采用 $4\times1$  横向布局：左侧两格展示 Stage I 自由树搜索，右侧两格展示 Stage III 有界搜索树。Stage III 面板以 Stage I 中筛出的 11 个 selected seed 为紫色菱形起点（代码先按 Q/S/B/R 四种搜索角色选择 24 个 seed rows并去重），并严格显示 200 个 Stage-III 节点；其中 `cd9e3818033d` 的展示性 lineage 被并入发现 `0ade8d3405c2` 的 Stage III 簇，以避免把最终 Q/S 误读成两个独立 Stage III 搜索。星形标出最终 Q 候选 `cd9e3818033d`，方形标出最终 S 候选 `0ade8d3405c2`，二者共同构成当前论文采用的 HAST-Final-Q/S 输出。



