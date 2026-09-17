# CPMCM 2025 A 论文图表资产规划

更新时间：2026-09-17

本文件维护论文证据资产的正文/附录取舍与数据来源。所有资产只读取已经进入 `main` 且通过 validator/evaluator 与 CI 的正式结果。

## 原则

1. **单一可信数据源**：图表不重新求解模型，不手抄正式指标。
2. **正文只放解释方法和支撑核心结论的图表**；完整六组细表、诊断图和 provenance 优先放附录。
3. 数据图优先输出矢量 `PDF`；`PNG` 仅用于快速预览。
4. 如果 2026 官方格式与当前 2025 版式基线冲突，以 2026 官方规范为准。

## 正文优先资产

| ID | 类型 | 内容 | 状态 | 数据/证据来源 | 目的 |
|---|---|---|---|---|---|
| D1 | 方法框图 | Q1 调度 → Q2 地址/SPILL → Q3 timing 优化完整 pipeline | 已生成并入正文 | `diagrams/scripts/generate_diagrams.py` + `src/` | 一页说明三问关系 |
| D2 | 机制图 | Q2 连续地址、resident/SPILL/reload 生命周期 | 已生成并入正文 | Q2 allocator/validator | 解释第二问核心机制 |
| F1 | 数据图 | 六组 Q3 fixed-traffic official-cycle 改善百分比 | 已生成并入正文 | `q3_formal_fixed_traffic_summary.csv` | 横向展示 Q3 有效性 |
| F2 | 数据图 | promoted Q2 raw cycles vs final Q3 cycles（log 轴） | 已生成，默认附录候选 | 同上 | 同时体现绝对规模与改善 |
| F3 | 数据图 | FA1 refined Traffic–Cycles 局部权衡 | 已生成并入正文 | `q3_refined_official_frontier.csv` | 展示性能-搬运量权衡 |
| F4 | 数据图 | Q3 formal core 与 critical-SPILL post-pass 阶段贡献分解 | 已生成并入正文 | `q3_formal_fixed_traffic_summary.csv` | 解释最终改善来自哪一阶段 |
| T1 | 总结果表 | 六组 case 的规模、Q1 peak、Q2 SPILL/traffic、Q3 cycles/gain | 已生成并入验证节 | Q1/Q2/Q3 正式 CSV | 正文总结果表 |
| T2 | 符号表 | buffer、resident、SPILL、traffic、cycle 等关键符号 | 已写入正文 | 题面 + 模型定义 | 降低阅读门槛 |

正文默认不同时放 F1 和 F2 的全部信息：当前以 **F1 + F4 + T1** 为主，F2 保留为附录/版面备选。

## 附录 / 诊断资产

| ID | 文件 | 用途 |
|---|---|---|
| A-F1 | `q1_peak_residency.pdf` | 六组 Q1 峰值驻留量完整对照 |
| A-F2 | `q2_spill_count.pdf` | 六组 Q2 SPILL 次数 |
| A-F3 | `q2_extra_traffic.pdf` | 六组 Q2 额外 DDR traffic |
| A-F4 | `q3_refined_pareto.pdf` | 所有 case 的诊断总览；量级差异大，不直接放正文 |
| A-T1 | `q1_summary.tex` | Q1 六组详细表 |
| A-T2 | `q2_summary.tex` | Q2 六组详细表 |
| A-T3 | `q3_summary.tex` | Q3 六组详细表 |
| A-T4 | `q3_fa1_tradeoff.tex` | FA1 三个 refined 点的精确数值 |

## 不做成正文主图的证据

- Conv0 / Conv1 局部搜索 no-improvement 证据保留在 formal acceptance/provenance 中；正文只说明局部饱和边界，不人工拼接“收敛曲线”。
- CI run ID、artifact digest、SHA-256 属于可复现性证据，放附录或公开仓库说明，不进入正文主图。
- Q1/Q2 的完整诊断柱图保留为附录候选；正文避免为了“图多”重复表达同一张总表的信息。

## 资产生成与验收

本地：

```bash
make -C problems/CPMCM/2025/A/paper assets
```

GitHub Actions：

`.github/workflows/build-cpmcm-2025-a-paper-assets.yml`

任何正文引用图/表都要求：
- 生成脚本可编译；
- 输出文件非空；
- 数据来源是正式 CSV/JSON；
- paper-assets Actions 为 green；
- 正式 manuscript 的 XeLaTeX workflow 能实际引用并生成 PDF。
