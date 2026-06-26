# CHD2026 包清单

这个包是从旧 `HAST2026/main` 中整理出的 CHD / 复杂网络代码与文档快照，目标是形成新的、清晰的软件边界。

## 已包含

- `src/model/`：当前网络瓦解实例的 CHD 三阶段主实现。
- `src/baselines/`：按任务划分的原生 baseline 与共享 AHD 风格搜索策略，包括 `ND_native_baseline/`、`IM_native_baseline/` 和 `AHD/`。
- `src/experiments/`、`src/scripts/`、`src/metrics/`、`src/plotting/`、`src/configs/`、`src/tests/`。
- `src/runs/`：统一运行记录根目录，包括从旧工作区迁移的精选论文证据包。
- `network/`：完整本地图数据目录，包含原始和处理后的图数据。
- `artifacts/`、`analyze_past_results/`、`related_work/`、`docs/`：支撑文档、源表、图片、报告和分析材料。
- `src/runs/runs_paper_evidence_20260616/`：从旧工作区复制并整理的论文证据包，包含 motivation、12 图 benchmark、搜索来源/消融、Q/S 可解释性、scaling、critical threshold / collapse point 和候选 lineage 材料。

## 已排除

- `.git/`、IDE 元数据、pytest/cache 目录。
- `src/runs/` 外的大型原始运行产物。
- 尚未接入 CHD2026 源代码的跨任务规划材料。
- 过期探针脚本、绑定个人本地绝对路径的旧分析脚本，以及不再作为论文复现入口的 dated exploratory scripts。

## 源码边界

`CHD2026` 是新的软件与文档包边界。baseline 和原生方法原则上保持方法实现不重写，只调整目录、导入路径和任务边界。
