# Q3 official-oriented zero-traffic：修正 evaluator 后的六组正式结果

本目录冻结问题 3 在 **不增加 Q2 extra traffic、不改变 SPILL victim identity/order/count** 前提下的 official-oriented 优化结果。

## 方法

从 promoted Q2 解出发，每轮依次尝试：

1. fixed-traffic 物理地址 portfolio；
2. critical-bottom-level pipeline reschedule。

候选只有同时满足以下条件才允许接受：

- 独立 Q2 strict replay 合法；
- SPILL victim identity/order/count 与 extra traffic 不变；
- `residency_safe` evaluator 合法、物理 overlap 为 0；
- Appendix-C `official_literal` cycles **严格下降**。

因此 `residency_safe` 是硬安全门禁，不是比赛目标；允许 safe cycles 上升，只要候选依旧物理安全且 official cycles 真实下降。

## 六组结果

| Case | Q2 polish | Baseline official | Optimized official | Improvement | Extra traffic | Optimized safe |
|---|---:|---:|---:|---:|---:|---:|
| Matmul_Case0 | 0 | 135,082 | **133,682** | **1.036408%** | 28,800 | 160,005 |
| Matmul_Case1 | 0 | 1,534,618 | **1,531,946** | **0.174115%** | 430,208 | 1,669,574 |
| FlashAttention_Case0 | 1 | 194,265 | 194,265 | 0 | 54,016 | 205,088 |
| FlashAttention_Case1 | 0 | 962,746 | 962,746 | 0 | 242,552 | 1,026,762 |
| Conv_Case0 | 2 | 636,114 | **606,429** | **4.666616%** | 177,904 | 786,202 |
| Conv_Case1 | 3 | 3,852,543 | **3,784,892** | **1.756009%** | 721,464 | 4,119,420 |

六组 official cycles 合计：

- baseline：`7,315,368`
- optimized：`7,213,960`
- 减少：`101,408 cycles`
- 聚合下降：`1.386232%`

这些数字不能和旧版结果直接混用：Q2 promoted polish 已改变 FA0 / Conv0 / Conv1 的 schedule、SPILL 与 traffic；同时 `residency_safe` 已补上每个 residency epoch 的 `acquire -> release` lifetime 约束。

## 目标分离案例

Conv 最能说明为什么必须分开“安全门禁”和“官方目标”。

- Conv0：official `636,114 -> 606,429`，下降 `4.666616%`；safe `774,198 -> 786,202`，上升 `1.5505%`。
- Conv1：official `3,852,543 -> 3,784,892`，下降 `1.756009%`；safe `4,116,658 -> 4,119,420`，小幅上升 `0.0671%`。

两者最终 `safe_overlap_errors=0`，所以 candidate 仍严格物理合法。若用 safe cycles 直接替代官方目标，这两次真实 official 改善都会被错误拒绝。

## Conv 诊断

本轮 core artifact 同时显示：

- Conv0 原布局 safe reuse edges：`1,489`；
- Conv1 原布局 safe reuse edges：`24,504`；
- Conv0 / Conv1 的全局 address portfolio 中，只有 `best_fit` 能完整重着色，而且得到的 timing 与原 Q2 地址完全相同；`first_fit_low/high/next_fit` 都因连续空间不足失败；
- 单独 critical reschedule 的 safe cycles 分别退化到 `786,202` / `4,119,420`，但同一 reorder 在 official objective 下分别改善到 `606,429` / `3,784,892`；
- 第二轮 critical reschedule 均 `changed_positions=0`，说明当前 bottom-level rule 一轮即到固定点。

因此继续“增加 optimizer rounds”没有意义。Conv 下一步若继续优化，应改变 move/operator，例如围绕 critical path 与高压 MTE2 的局部 address-reuse / pipeline 联合变换，而不是再加全局重排轮数。

## 验收证据

Evaluator lifetime 修复：

- `1dae6f00825493bf4da32178642769766b4695a2`
- `457c94af80c38f7f92ed1447353bdf6f773cacf7`

CI 拆分：

- commit：`d07aaeb8d05d7ac7e15cd096b75d07f88b4e345d`
- main core workflow：`Test CPMCM 2025 A Q3`
- run：`34592734824`
- conclusion：`success`
- tests：58 passed
- 六组 baseline / address portfolio / critical reschedule / safe optimizer / official optimizer：全部 success
- artifact：`10260687417`
- digest：`sha256:6bd8cc9de178c32902d0d27ef31ac08c40663fc22267209106f06cc5536e1b06`

完整 per-step trace、address policy grid、pipeline critical 结果及官方输出保存在该 Actions artifact；仓库仅保留稳定的六组摘要。

更进一步的 traffic–cycles refined 结果见 [`../q3_pareto/README.md`](../q3_pareto/README.md)。
