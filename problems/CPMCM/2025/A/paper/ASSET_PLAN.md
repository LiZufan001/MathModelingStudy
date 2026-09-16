# CPMCM 2025 A 论文图表资产规划

更新时间：2026-09-16

本文件只规划论文证据资产，不撰写正文。最终图号/表号在 2026 官方《竞赛论文标准文档》发布并建立正式 manuscript 后再编号。

## 原则

1. **单一可信数据源**：只读取已经进入 `main` 且通过独立 validator/evaluator 与 CI 的正式结果。
2. **正文只放“解释方法”和“支撑核心结论”的图表**；回归、诊断、完整六组明细尽量放附录。
3. 数据图优先输出矢量 `PDF`；`PNG` 仅用于快速预览。
4. 图表脚本只做展示，不重新求解模型，不修改正式结果。
5. 如果 2026 官方格式与 2025 模板冲突，以 2026 官方规范为准。

## 正文优先资产

| ID | 类型 | 暂定内容 | 状态 | 数据/证据来源 | 目的 |
|---|---|---|---|---|---|
| D1 | 方法框图 | Q1 调度 → Q2 地址/SPILL → Q3 timing 优化的完整 pipeline | 待绘制 | `src/` + 已验收流程 | 让评委一页看懂三问关系 |
| D2 | 机制图 | Q2 连续地址分配、resident/SPILL/reload 生命周期示意 | 待绘制 | `q2_allocator.py` / `q2_validator.py` | 解释第二问核心机制 |
| F1 | 数据图 | 六组 Q3 fixed-traffic official-cycle 改善百分比 | 已生成 | `q3_formal_fixed_traffic_summary.csv` | 横向展示 Q3 有效性 |
| F2 | 数据图 | promoted Q2 raw cycles vs final Q3 cycles（log 轴） | 已生成 | 同上 | 同时体现绝对规模与改善 |
| F3 | 数据图 | FA1 refined Traffic–Cycles 局部权衡 | 已生成 | `q3_refined_official_frontier.csv` | 展示第三问“性能-搬运量”权衡 |
| T1 | 总结果表 | 六组 case 的规模、Q1 peak、Q2 SPILL/traffic、Q3 cycles/gain | 已生成 | Q1/Q2/Q3 三份正式 CSV | 正文主结果表 |
| T2 | 符号表 | 关键 buffer、resident、SPILL、traffic、cycle 等符号 | 待正式写作时生成 | 题面 + 模型定义 | 降低阅读门槛 |

正文默认不同时放 F1 和 F2 的全部信息：若版面紧张，以 **F1 + T1** 为主，F2 移附录。

## 附录 / 诊断资产

| ID | 文件 | 用途 |
|---|---|---|
| A-F1 | `q1_peak_residency.pdf` | 六组 Q1 峰值驻留量完整对照 |
| A-F2 | `q2_spill_count.pdf` | 六组 Q2 SPILL 次数 |
| A-F3 | `q2_extra_traffic.pdf` | 六组 Q2 额外 DDR traffic |
| A-F4 | `q3_refined_pareto.pdf` | 所有 case 放在同一坐标系的诊断总览；因量级差异大，不建议直接放正文 |
| A-T1 | `q1_summary.tex` | Q1 六组详细表 |
| A-T2 | `q2_summary.tex` | Q2 六组详细表 |
| A-T3 | `q3_summary.tex` | Q3 六组详细表 |
| A-T4 | `q3_fa1_tradeoff.tex` | FA1 trade-off 三个 refined 点的精确数值 |

## 当前不做成图的证据

- Q2 promotion 的 Matmul 总 traffic 从 `495,616` 降到 `459,008`、SPILL 从 `3,872` 降到 `3,586`：当前正式结果中没有逐 case baseline CSV，因此先作为文字/验收证据，不从 README 反向解析成图。
- Conv0 / Conv1 的局部搜索“no-improvement”饱和证据：保留在 acceptance/provenance 与实验记录中。除非正文需要说明局部搜索收敛过程，否则放附录证据，不为了好看人工拼曲线。
- CI run ID、artifact digest、SHA-256：用于可复现性说明/附录，不进入正文主图。

## 计划中的方法图

### D1 — 三问统一框架

建议结构：

```text
Appendix-E graph
      |
      v
Q1 topological scheduling
  minimize peak L1+UB residency
      |
      v
Q2 contiguous allocation + SPILL
  minimize extra DDR traffic
      |
      v
Q3 timing-aware reschedule/recolor
  minimize official cycles
  subject to fixed Q2 traffic/SPILL
      |
      v
validator + official evaluator + safe gate
```

### D2 — Q2 buffer 生命周期

至少画出：

```text
ALLOC -> resident interval -> use(s) -> optional SPILL -> reload -> FREE
```

并明确“连续地址区间”“SPILL 插入导致额外 traffic”“strict replay”三件事。

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
- 数据来源是正式 CSV；
- Actions 资产构建为 green。
