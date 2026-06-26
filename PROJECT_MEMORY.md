# CHD2026 项目记忆

## 运行环境策略，2026-06-25

- 后续所有 CHD2026 Python 命令必须使用 `E:\my_evns\py312_torch28\python.exe`。
- 除非用户明确修改环境策略，不使用系统 `python`、`py` 或 Codex 自带 Python 来验证 CHD2026。

## 目录与命名策略，2026-06-25

- baseline 包目录为了 Python 可导入性使用下划线：`ND_native_baseline` 对应 `ND-native-baseline` 任务边界，`IM_native_baseline` 对应 `IM-native-baseline` 任务边界。
- 新运行目录统一写入 `CHD2026/src/runs/YYYYMMDD-HHMMSS-任务-具体任务名字`，例如 `20260625-174725-ND-root-main`。
- 主运行只使用 root-relative `Delta AUC-cNBI`；parent-relative 仅作为消融实验和审计字段保留。
- 主配置文件使用 `src/configs/chd.yaml`。
- 主搜索文件使用直白阶段命名：`src/model/stage1_stage3_search.py`，不再使用 `e4/e6` 这类内部代号作为文件名。
- 完整验证入口使用 `src/scripts/run_full_validation.py` 和 `--run-full-validation`；不再保留旧阶段代号参数。

## 经典完整序列 R 策略，2026-06-24

- 经典 R 使用完整删除序列：删除节点 `k=1..N` 后计算 `GCC_k = LCC_k / original_N`，再计算 `classic_R_fraction = sum(GCC_k) / N` 与 `classic_R_percent = 100 * classic_R_fraction`。
- 不使用 30% 截断的 `point_evaluations` 作为完整序列 R 证据；截断或不完整行进入 `unavailable_or_rejected_inputs.csv`。
- 对无权图的 `native-strong-baseline` cost 子目录，只接受 `uniform_cost/<dataset>.txt` 作为删除序列；`random_cost` 和 `degree_cost` 是加权变体，不能进入无权经典 R 主表。
- `MaxCCList*.txt` 是 GCC 轨迹，不是节点删除序列。
- 除非用户明确改变策略并提供可信完整无权序列，否则 `PUCT`、`E26F`、`BPD/MinSum-fallback`、`BPD` 和 `MinSum` 不进入主结果行。
- 讨论该家族时使用论文名称 `ERA-like`，结果行中不要写 `ERA-like (PUCT)`。
- 保留 `CHD2026/artifacts/source_tables` 和 `CHD2026/src/runs/runs_paper_evidence_20260616` 作为可追溯输入。可以原地重建生成图或重算输出，但删除生成产物时要记录 manifest。
