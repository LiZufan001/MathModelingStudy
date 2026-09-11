# Q3 Traffic–Cycles Pareto：修正 evaluator 后的正式结果

## 结论

本目录记录 2025 A 题问题 3 在 **promoted Q2** 基础上的 Traffic–Cycles 权衡结果。

2026-09-11 在 Conv 回放中发现 `residency_safe` 少了一类物理驻留生命周期约束：一个 buffer 的每个 residency epoch 必须显式满足 `acquire -> release`。修复后新增 repeated-SPILL 与 zero-duration epoch 反例测试，并重新执行六组 Q3 baseline、地址重着色、pipeline reschedule、safe/official zero-traffic optimizer 与双 Pareto gate。

当前采用双口径：

- `official_literal`：按题面 Appendix C 字面依赖计算，是论文/比赛的主目标；
- `residency_safe`：在 official 依赖外加入物理 residency lifetime 安全约束，作为硬可行性审计。

**所有 official 候选必须先通过 `residency_safe`，但选优按 `official_literal_cycles`。**

---

## 1. 六组 coarse epsilon frontier

统一粗搜索窗口为 `0 / 8 / 32 / 128 / 512`，流量预算为 `epsilon = 0% / 1% / 3% / 5%`。

### Official-literal coarse frontier

| case | epsilon | winner | traffic | official cycles | vs promoted-Q2 raw |
|---|---:|---:|---:|---:|---:|
| Matmul_Case0 | 0/1/3/5% | w=0 | 28,800 | **133,682** | **-1.036408%** |
| Matmul_Case1 | 0/1/3/5% | w=0 | 430,208 | **1,531,946** | **-0.174115%** |
| FlashAttention_Case0 | 0/1/3/5% | w=0 | 54,016 | **194,265** | 0 |
| FlashAttention_Case1 | 0/1/3% | w=0 | 242,552 | **962,746** | 0 |
| FlashAttention_Case1 | 5% | w=8 | 250,584 | **942,667** | **-2.085597%** |
| Conv_Case0 | 0/1/3/5% | w=0 | 177,904 | **606,429** | **-4.666616%** |
| Conv_Case1 | 0/1/3/5% | w=0 | 721,464 | **3,784,892** | **-1.756009%** |

其中 Matmul/Conv 的 `w=0` 仍会继续执行 official-oriented zero-traffic address/pipeline optimizer，所以 `w=0` 不代表“没有 Q3 优化”，而表示“不额外改变 Q2 traffic”。

### Safe 与 official 仍然不能混用

Matmul0 在 safe 口径下 5% 会偏向 `w=8`，safe cycles 为 `158,495`，但 official cycles 为 `136,214`，反而劣于 official winner `133,682`。

Matmul1 同样如此：`w=8` 的 safe cycles 为 `1,650,497`，但 official cycles 为 `1,537,478`，劣于 `w=0` 的 `1,531,946`。

修复后的 Conv1 `w=32` 已能通过 residency-safe 审计，不再是“物理 overlap 非法”；但它需要 traffic `739,552`（+2.507124%），official cycles `3,844,461`，仍被 `w=0` 的 `721,464 / 3,784,892` 严格支配。因此 Conv1 当前的结论应是“合法但无 Pareto 收益”，而不是旧版 README 中的 overlap 拒绝。

---

## 2. FlashAttention refined frontier

粗网格会漏掉最有价值的小窗口。随后进行了：

1. 单窗口 `w=0..16` fine search；
2. 两阶段 `1..5 x 1..5` composition search；
3. FA1 三阶段局部 `{1,2,3}^3` 搜索。

每个候选均执行：

`critical-window schedule -> strict Q2 allocation/replay -> residency_safe gate -> official zero-traffic post-optimization`

### FA0

正式 refined frontier：

| sequence | traffic | traffic delta | official cycles | official improvement | safe cycles |
|---|---:|---:|---:|---:|---:|
| 0 | 54,016 | 0 | 194,265 | 0 | 205,088 |
| **1** | **55,036** | **+1.888329%** | **191,230** | **-1.562299%** | 205,617 |

这里 `w=1` 的 safe cycles 略增，但仍严格通过 residency-safe 可行性门禁；official 目标显著改善。这正说明 safe 应是硬安全约束，而不是替代官方目标。

两阶段组合没有支配单 `w=1`，因此 FA0 在这里停止扩展搜索。

### FA1

两阶段组合把原单窗口前沿进一步严格改进：

| sequence | traffic | traffic delta | official cycles | official improvement | safe cycles |
|---|---:|---:|---:|---:|---:|
| 0 | 242,552 | 0 | 962,746 | 0 | 1,026,762 |
| **1>1** | **244,048** | **+0.616775%** | **947,002** | **-1.635322%** | 958,676 |
| **2>1** | **245,060** | **+1.034005%** | **912,556** | **-5.213213%** | 936,070 |

其中 `2>1` 是目前最重要的真实 trade-off：只增加约 **1.03%** 的额外搬运，就把 official cycles 降低约 **5.21%**。

三阶段 `{1,2,3}^3` 共 27 个新候选全部 strict-valid，但没有一个支配上述两阶段前沿：

- 最低 traffic triple：`1>1>1 = 245,376 / 954,063`；
- 最低 cycles triple：`1>3>1 = 253,276 / 924,162`；
- 对 `1>1`、`2>1`、`1>2` 的严格支配者数量均为 0。

因此当前 critical-window 算子族在 FA1 上已出现清晰的**局部饱和**，不继续堆第四阶段。

---

## 3. 推荐用于论文的 Q3 主结果

`q3_refined_official_frontier.csv` 是当前最适合论文/模拟写题直接引用的摘要：

- Matmul / Conv：保留 fixed-Q2-traffic official zero-traffic 最优点；
- FA0 / FA1：使用经过 fine/composition 搜索后的 refined Pareto 点；
- 所有点均已通过 strict Q2 replay 与 `residency_safe`。

注意：`q3_official_frontier.csv` / `q3_safe_frontier.csv` 仍只对应统一 coarse epsilon 实验，用于公平的六组横向比较；`q3_refined_official_frontier.csv` 才是专项搜索后的“当前最好已知前沿”。

---

## 4. 验收证据

### evaluator lifetime 修复

- `1dae6f00825493bf4da32178642769766b4695a2`
- `457c94af80c38f7f92ed1447353bdf6f773cacf7`
- 完整回归：58 tests passed
- 六组 promoted-Q2 -> Q3 residency-safe baseline：success
- address recoloring / critical reschedule / safe zero-traffic / official zero-traffic：success

### coarse dual Pareto

- workflow：`Test CPMCM 2025 A Q3 Pareto`
- run：`34590599567`
- head：`457c94af80c38f7f92ed1447353bdf6f773cacf7`
- conclusion：`success`
- artifact：`10196153856`
- artifact digest：`sha256:40a1f5a9f33d247355ecaff9cd4cc8bde06887fa7c3d257ed5d3923a7d60878e`

### FA fine search

- run：`34591060339`
- head：`9146b1bc808133764b584aa351e7d6c52dc766df`
- conclusion：`success`
- artifact：`10195731696`
- digest：`sha256:14e43d1c746bae35711ffea56df324037d3ea2d7677a350efc84c28ca7222bc2`

### FA two-stage composition

- run：`34591694741`
- head：`9153b973b67056925f2a71980185a577b2355e18`
- conclusion：`success`
- artifact：`10196023451`
- digest：`sha256:b995079593346b0ca6dce7adea12a6dbe83ddf81539b47d3ac5098fa4394f7d1`

### FA1 triple local search

- run：`34592563457`
- head：`cda3fc6f812985226522137fd7330de4051dfd51`
- conclusion：`success`
- 31 total candidates，27 triples，31/31 strict-valid
- artifact：`10196303433`
- digest：`sha256:f753b4d9030ab0abf5c2b5a8ce759a61aca2951ec369ca889afe6ea3e396f2ec`

---

## 5. 后续方向

当前不再继续增加 critical-window composition 深度。下一阶段若继续优化，应改变**搜索算子**而不是只堆阶段：

- FA：研究更直接的 Cube / Vector / MTE pipeline-priority portfolio；
- Conv：研究 address placement 与 pipeline order 的联合局部变换；
- Matmul：当前 zero-traffic 已稳定有收益，可优先作为论文消融/可解释案例，而不是继续重搜索。

CI 已将主 Q3 core gate 与 Pareto gate 拆分，避免每次核心修改重复跑完整 Pareto。
