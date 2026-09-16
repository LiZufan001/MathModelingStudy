# Q2 optimized：footprint 基线 + 通用 polish portfolio

## 当前正式结论

2026-09-11，正式 Q2 路径已从单一 pure-footprint 调度升级为 `solve_q2_promoted()`：先生成已经验收的 footprint-aware 基础顺序，再对同一顺序尝试一个很小的、图结构通用的 `window = {0,1,2,3}` polish portfolio；每个候选都重新通过严格 Q2 allocator + 独立 validator replay，最后按官方目标择优。

正式入口仍为：

```bash
python problems/CPMCM/2025/A/src/batch_q2.py \
  --strategy optimized \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q2-optimized-results
```

生产实现位于：

- `src/q2_optimized.py`：footprint-aware 基础调度；
- `src/q2_promoted.py`：`POLISH_WINDOWS = (0,1,2,3)`、严格分配、候选择优与 exact regression；
- `src/q2_allocator.py` / `src/q2_validator.py`：正式分配器与独立重放验证器。

## 选择规则

对每个 polish window：

1. 先生成合法拓扑顺序；
2. 要求 `q1_peak` 不高于 footprint 基础顺序；
3. 完整运行严格 Q2 allocator；
4. `q2_validator` 独立 replay 必须通过；
5. 在有效候选中按下列字典序选最优：

```text
extra_traffic
→ spill_count
→ q1_peak
→ changed_positions
→ smaller window
```

因此 **SPILL 次数不是主目标**。只要官方额外 DDR traffic 更低，即使发生更多次、但每次更便宜的 SPILL，也可能是更优解。

## 六组 Appendix-E 正式结果

| case | q1_peak | raw baseline traffic | footprint-only traffic | promoted traffic | promoted spills | polish window | changed positions | strict valid |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Matmul_Case0 | 9,216 | 34,816 | 28,800 | **28,800** | 225 | 0 | 0 | True |
| Matmul_Case1 | 34,816 | 460,800 | 430,208 | **430,208** | 3,361 | 0 | 0 | True |
| FlashAttention_Case0 | 26,728 | 55,188 | 55,188 | **54,016** | 316 | **1** | 1,004 | True |
| FlashAttention_Case1 | 106,992 | 242,552 | 242,552 | **242,552** | 1,782 | 0 | 0 | True |
| Conv_Case0 | 80,170 | 178,212 | 178,212 | **177,904** | 522 | **2** | 1,318 | True |
| Conv_Case1 | 310,408 | 724,630 | 724,630 | **721,464** | 9,646 | **3** | 20,976 | True |

相对上一版 footprint-only promoted 基线：

- 六组总 traffic：`1,659,590 → 1,654,944`；
- 进一步减少 `4,646`，即 **-0.279949%**；
- FA0：`55,188 → 54,016`，减少 `1,172`（**-2.123650%**）；
- Conv0：`178,212 → 177,904`，减少 `308`（**-0.172828%**）；
- Conv1：`724,630 → 721,464`，减少 `3,166`（**-0.436913%**）；
- Matmul0/1 与 FA1 自动选择 `window=0`，没有为追求“统一改动”而退化。

相对原始六组 baseline：

- 总 traffic：`1,696,198 → 1,654,944`；
- 减少 `41,254`，即 **-2.432145%**。

六组 `q1_peak` 均保持不变。

## 一个重要现象：traffic 与 spill count 不等价

polish 后：

- FA0：spill `301 → 316`，但 traffic `55,188 → 54,016`；
- Conv0：spill `493 → 522`，但 traffic `178,212 → 177,904`；
- Conv1：spill `9,550 → 9,646`，但 traffic `724,630 → 721,464`。

这说明“最少 SPILL 次数”不是题目二的正确代理目标。不同 buffer 的 `Size`、COPY_IN 可重载属性不同，一个较多次数但较低字节成本的方案可以严格优于较少次数方案。论文中应直接优化并报告 `ExtraTraffic`，spill count 只作为解释性统计量。

## 正式验收证据

本轮 production acceptance：

- branch：`agent/q3-pipeline-20260911`
- acceptance head：`9dae83afe64820258c234638dc38a0bba9d77e85`
- workflow：`Test CPMCM 2025 A Q2`
- run：`34588951162`
- conclusion：`success`
- `Generate promoted Q2 optimized solutions with exact regression gates`：success
- Matmul exact uniform-page Belady oracle：success
- 六组 baseline / optimized strict replay：success
- archived Problem 2 solution audit：success
- spill profile / order ablation：success
- artifact upload：success

Artifact：

- name：`cpmcm-2025-a-q2-validation`
- artifact id：`10194890328`
- SHA-256：`b0e4b54dc2d3041753eb802e1597842464d1e2888785bf5eb07c9204936c4542`

本目录的 `q2_optimized_summary.csv` 保存该 production artifact 的实际六组输出；`q2_optimized_summary.json` 保存机器无关的验收元数据与核心指标。运行时间只用于工程 profiling，不作为算法回归门槛。

## 后续修改的硬门禁

后续 Q2 改动只有同时满足以下条件，才允许替换当前正式策略：

1. 全部单元 / oracle / regression tests 通过；
2. 六组 Appendix-E 输出均可生成；
3. 独立 `q2_validator` strict replay 全部通过；
4. Matmul uniform-page 场景继续与 exact oracle 对账；
5. 六组 `q1_peak` 不得无意上升；
6. 以 `extra_traffic` 为主目标，不能以 spill count 偷换目标；
7. 所有声称的提升必须保存同口径 baseline、CI run 和可复现 artifact。
