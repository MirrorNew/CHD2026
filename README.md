# CHD2026 主项目

这是独立的 CHD2026 实现工作区，目标是让 CHD 作为复杂网络任务框架存在，而不是旧实验树的附属目录。

## 目录内容

- `src/model/`：当前网络瓦解实例的 CHD 三阶段搜索、候选验证、阶段2边界归纳、排序和 Pareto 选择。
- `src/baselines/`：按任务划分的 baseline。`ND_native_baseline/` 放网络瓦解原生基线，`IM_native_baseline/` 放影响力最大化原生基线，`AHD/` 放 9 个跨任务 LLM AHD 搜索策略。
- `src/metrics/`：GCC/R、NCC、cNBI、AUC-cNBI、最终指标和运行时间汇总。
- `src/scripts/`：命令入口，只保留 smoke test、主搜索、完整验证、scaling、审计和论文产物导出等 wrapper。
- `src/configs/`：固定实验参数，当前主配置为 `chd.yaml`。
- `src/experiments/`：当前论文实验和表格入口；过期日期脚本不放这里。
- `src/plotting/`：从已记录 CSV 重画论文图。
- `src/runs/`：统一运行记录根目录。
- `docs/`：论文草稿、实验计划和复现说明。
- `network/`：smoke test 和图表重建所需图数据。
- `artifacts/`：论文表格、图片和审计报告；位置保持在项目根目录，不放入 `src/`。

## 架构边界

```text
CHD2026/
├── src/
│   ├── model/                # CHD 三阶段主实现
│   ├── baselines/            # ND/IM 原生基线与 AHD 搜索策略
│   ├── metrics/              # 瓦解曲线和指标汇总
│   ├── configs/              # 固定种子、图集、LLM 设置和预算
│   ├── experiments/          # 当前实验入口和表格协议
│   ├── plotting/             # 当前论文图重画
│   ├── scripts/              # 命令入口
│   ├── runs/                 # 本地运行记录
│   └── tests/
├── network/                  # 图数据
├── artifacts/                # 论文表格、图片、报告
└── docs/                     # 草稿与复现说明
```

标准流程是：`src/configs -> src/model + src/baselines + src/metrics -> src/experiments 或 src/scripts -> src/runs 和 artifacts -> src/plotting`。

新运行目录统一写入 `src/runs/YYYYMMDD-HHMMSS-任务-具体任务名字`，例如 `20260625-174725-ND-root-main` 或 `20260625-174725-IM-smoke`。论文表格和图片继续写入 `artifacts/`。

## 固定 CHD 搜索预算

- 阶段1：成本感知自由搜索，从 HDA-original 根节点顺序扩展 300 个搜索树节点。
- 阶段2：基于日志的边界归纳，10 次 LLM 调用，只归纳 policy/bounds，不生成候选算法。
- 阶段3：有界引导搜索，从阶段1选择的父节点顺序扩展 200 个搜索树节点。
- 当前主运行只使用 root-relative `Delta AUC-cNBI`；parent-relative 只作为消融实验和审计字段保留。
- LLM 设置：`gpt-5.5`，reasoning effort `none`，temperature `0.2`，OpenAI-compatible base URL `https://api.ritelt.com/v1`。

## 本地数据策略

以下内容只作为本地文件保留，不应提交到 GitHub：

- 大型图输入；
- `artifacts/`；
- `src/runs/`；
- 原始 LLM 日志和大型 CSV。

GitHub 只应包含源代码、配置、文档和轻量 fixture，以及我的所有图。

## 快速检查

所有 CHD2026 Python 命令默认使用指定环境：

```powershell
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/smoke_test.py
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_ahd_baselines.py --task im --run-name ahd-smoke
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_full_validation.py --prepare-only --datasets Powerlaw_500
```

`smoke_test.py` 会检查 baseline、指标、候选执行、阶段2 policy 归纳和最终 Pareto 标签是否连通。

## 真实 LLM 运行

真实 LLM 调用必须显式开启，并从环境变量读取密钥：

```powershell
$env:HAST_LLM_API_KEY = "<your-api-key>"
$env:HAST_LLM_BASE_URL = "https://api.ritelt.com/v1"
$env:HAST_LLM_MODEL = "gpt-5.5"
$env:HAST_LLM_REASONING_EFFORT = "none"
$env:HAST_LLM_TEMPERATURE = "0.2"
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py --execute
```

不要提交 API key。`.env` 和 `*.key` 已作为本地密钥文件忽略。

不带 `--execute` 时，主搜索只准备运行目录并验证数据连线：

```powershell
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py --execute
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py --execute --run-full-validation
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_full_validation.py --stage3-final-dir src/runs/YYYYMMDD-HHMMSS-ND-root-main/final
```

若要做 parent-relative 消融，可保持同预算、同模型、同超时、同数据集，仅切换 `--delta-credit-mode parent`：

```powershell
& 'E:\my_evns\py312_torch28\python.exe' src/scripts/run_main_search.py --run-name parent-relative-ablation --execute --run-full-validation --delta-credit-mode parent
```

已有非空运行目录默认拒绝覆盖，除非显式传入 `--allow-existing-run-dir`。每个运行目录都会写 `input_parameters.json`，记录 CLI 输入和解析后的配置，但不保存 API key。

## 完整实验形状

1. 动机观察2：`R/GCC-only`、`Absolute-cNBI`、`Relative-Delta-cNBI`，每组 100 个候选。
2. 动机观察3：`Relative-Free`、`CostAware-Free`、`Bounded-Guided`，每组 100 个候选。
3. CHD 主搜索：300 + 10 + 200 节点预算，阶段3固定 `HAST-Final-Q/S`，完整验证只评估这两个冻结候选。
4. 消融：相对 credit、时间惩罚、阶段2边界、阶段1-only 父节点选择、有界家族约束。
5. Scaling：500 到 10k 做完整评估，500 到 1000k 做 runtime-only。
6. 论文产物刷新：按 `docs/15_chinese_paper_full_cn.md` 中引用的图表清单刷新。

## 本地溯源资产

可复现实验所需旧运行记录保存在 `src/runs/` 和 `artifacts/`。公开论文中使用 `ERA-like` 作为名称；原始 CSV 中可能仍使用 `PUCT` 作为内部 key，导出脚本会映射为 `ERA-like`。
