# Q3 Traffic–Cycles Pareto：当前正式结果

## 结论

本目录记录 2025 A 题问题 3 在 **promoted Q2** 基础上的 Traffic–Cycles 权衡结果。

当前采用双口径：

- `official_literal`：按题面 Appendix C 字面依赖计算，是论文/比赛的主目标；
- `residency_safe`：额外加入物理 residency lifetime 安全约束，作为硬可行性审计。

**所有 official 候选必须通过 `residency_safe`，但选优按 `official_literal_cycles`。** safe cycles 允许在仍然合法的前提下变大，例如 Conv0 当前 official 更优点的 safe cycles 略高于 formal core；这不构成拒绝理由。

---

## 1. coarse epsilon 实验仍保留为横向基线

统一粗搜索窗口为 `0 / 8 / 32 / 128 / 512`，流量预算为 `epsilon = 0% / 1% / 3% / 5%`。`q3_official_frontier.csv` 与 `q3_safe_frontier.csv` 仍保留这套统一实验，用于六组横向比较。

这些 coarse 点不是当前最终结果。后续 formal zero-traffic / recolor / critical-SPILL post-pass 已继续降低多个 case 的 fixed-traffic 周期，因此论文主结果应使用 `q3_refined_official_frontier.csv`。

---

## 2. 当前正式 fixed-Q2-traffic 点

正式路线：

`promoted Q2 -> formal zero-traffic core -> fresh-rerank critical-SPILL batch -> optional accepted single-switch post-pass`

整个后处理保持 promoted Q2 的 SPILL 身份/顺序、spill count、extra traffic 不变，只调整 Q3 调度序列；每个候选都重新执行 strict Q2、official-literal 与 residency-safe replay。

| case | extra traffic | formal core | final official | vs promoted-Q2 raw | final safe |
|---|---:|---:|---:|---:|---:|
| Matmul_Case0 | 28,800 | 133,682 | **133,682** | **-1.036408%** | 160,005 |
| Matmul_Case1 | 430,208 | 1,531,946 | **1,531,946** | **-0.174115%** | 1,669,574 |
| FlashAttention_Case0 | 54,016 | 188,562 | **187,945** | **-3.253288%** | 204,875 |
| FlashAttention_Case1 | 242,552 | 962,022 | **962,022** | **-0.075202%** | 1,026,634 |
| Conv_Case0 | 177,904 | 603,405 | **595,302** | **-6.415831%** | 789,619 |
| Conv_Case1 | 721,464 | 3,781,664 | **3,767,326** | **-2.211968%** | 4,112,665 |

critical-SPILL batch 对 Matmul0、Matmul1、FA1 第一轮即 no-op；对 FA0、Conv0、Conv1 分别额外降低 `617 / 5,436 / 14,338` cycles。六组最后一轮均为 no-improvement，因此对该 batch 算子具有局部饱和证据。

Conv0 随后用第二类固定流量邻域 `critical SPILL single-switch bubble` 继续搜索：`597,969 -> 597,051 -> 596,988 -> 595,302`，随后下一轮 no-op；相对 batch 终点再降低 **2,667 cycles**，traffic `177,904` 与 spill count `522` 完全不变。该结果已由 formal acceptance 从旧正式 Problem3 输出完整重放并通过 strict/safe gate。

Conv1 的 `3,767,326` 已由两条路线独立复现：deterministic saturated shortcut 与完整 promoted-Q2 -> deep formal chain，二者 final safe cycles 都是 `4,112,665`，spills 都是 `9,646`，traffic 都是 `721,464`。

更完整的方法与验收记录见：

`../q3_formal_fixed_traffic/README.md`

---

## 3. FlashAttention refined frontier

### FA0

旧 refined frontier 曾保留：

`w=1 -> traffic 55,036 / official 191,230`

新的 formal fixed-traffic 点已经达到：

`traffic 54,016 / official 187,945`

它同时 **更少 traffic 且更少 cycles**，所以旧 `w=1` 被严格支配并从当前 refined frontier 删除。FA0 现在只保留 fixed-traffic 点。

### FA1

FA1 的 formal fixed-traffic 点为 `242,552 / 962,022`，而两个更高 traffic / 更低 cycles 的 composition 点仍然不被支配：

| sequence | traffic | traffic delta | official cycles | vs raw | safe cycles |
|---|---:|---:|---:|---:|---:|
| 0 | 242,552 | 0 | **962,022** | **-0.075202%** | 1,026,634 |
| **1>1** | **244,048** | **+0.616775%** | **947,002** | **-1.635322%** | 958,676 |
| **2>1** | **245,060** | **+1.034005%** | **912,556** | **-5.213213%** | 936,070 |

其中 `2>1` 仍是最有价值的真实 trade-off：只增加约 `1.03%` 的额外搬运，official cycles 降低约 `5.21%`。

此前三阶段 `{1,2,3}^3` 的 27 个候选没有支配这两个两阶段点，因此当前 critical-window composition 算子族仍视为局部饱和，不继续机械增加第四阶段。

---

## 4. 推荐用于论文的 refined frontier

`q3_refined_official_frontier.csv` 已重新从正式 fixed-traffic evidence 与既有 trade-off 候选做二维 Pareto reconciliation，当前共 **8 行**：

- Matmul0：`28,800 / 133,682`；
- Matmul1：`430,208 / 1,531,946`；
- FA0：`54,016 / 187,945`；
- FA1：`242,552 / 962,022`、`244,048 / 947,002`、`245,060 / 912,556`；
- Conv0：`177,904 / 595,302`；
- Conv1：`721,464 / 3,767,326`。

Pareto 工具只允许 `strict_valid=true` 候选参与支配判断。此前发现 invalid 候选虽然不会被保留、却仍可能错误支配合法点；该 bug 已在提交 `88263a87c0bad9b3221fb1598058210f0acee3cc` 修复，并有独立回归测试锁住。

reconciliation 的 kept/dominated 与 formal artifact provenance 记录在：

`q3_refined_official_frontier_reconcile.json`

---

## 5. 验收证据

### formal fixed-traffic / Problem3 输出

- 五组基础非 Conv1 正式附件导出：run `34747455829`，5/5 success；
- Conv1 targeted Problem3 acceptance：run `34747404506`，success，artifact `10315405008`；
- Conv1 full formal：run `34745747473`，success，artifact `10314199173`；
- Conv0 single-switch formal acceptance：run `34748384017`，success，artifact `10315385596`；
- Conv0 accepted artifact digest：`sha256:b7919290c4205ff75d83720abea7020bba57c14bc6489979816caff60d72df90`。

### 全回归

- 完整 Q2/历史附件/ablation 回归：run `34747286667`，success；
- 当前 published-results consistency：run `34748431634`，success；
- refined-frontier reconciliation gate：run `34747219856`，success；
- formal exporter 与 spill-batch unit gates：success。

### 旧 refined 搜索证据仍保留

- FA fine search：run `34591060339`；
- FA two-stage composition：run `34591694741`；
- FA1 triple local search：run `34592563457`。

这些实验仍用于解释 FA1 的 higher-traffic trade-off；只是 FA0 旧 `w=1` 已被新的 fixed-traffic 点支配。

---

## 6. 结论边界与后续方向

当前可以说：

- formal fixed-traffic critical-SPILL batch 在六组 Appendix-E case 上都已到首个 no-improvement round；
- Conv0 又对 `max_switches=4` single-switch bubble 邻域达到 no-improvement；
- Conv1 final point已由两条路线独立复现；
- refined frontier 已经过 strict-valid-only Pareto reconciliation。

但**不能**声称整个 Q3 全局最优。single-switch 是否对 Matmul / FlashAttention 也有收益，需要逐 case 实测；新的 priority portfolio、联合变换或更宽邻域仍可能继续改善。
