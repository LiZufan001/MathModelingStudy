# Q3 official-oriented zero-traffic：critical-reuse recolor 正式六组结果

本目录冻结问题 3 在 **不增加 promoted-Q2 extra traffic、不改变 SPILL victim identity/order/count** 前提下的 official-oriented 优化结果。当前正式版本在原有 address / pipeline optimizer 之后增加了 generic critical-reuse initial-offset recolor post-pass，并以 `residency_safe` 作为物理合法性硬门禁、Appendix-C `official_literal` cycles 作为唯一排序目标。

## 方法

从 promoted Q2 解出发：

1. fixed-traffic 物理地址 portfolio；
2. critical-bottom-level pipeline reschedule；
3. 当前两步到达 fixed point 后，执行 greedy critical-reuse recolor post-pass：每轮只在当前 official critical path 上选择 reuse target，枚举有限个安全 initial offsets，最多接受一个严格改善 candidate，然后重新计算下一轮 critical path；
4. recolor 接受后再尝试一次 post-recolor critical reschedule；只有 official cycles 继续严格下降才接受。

候选必须同时满足：

- 独立 Q2 strict replay 合法；
- SPILL victim identity/order/count 不变；
- `extra_traffic` 完全不变；
- `residency_safe` evaluator 合法且 `safe_overlap_errors=0`；
- Appendix-C `official_literal` cycles **严格下降**。

因此 `residency_safe` 是硬安全门禁，不是比赛排名目标。`official_literal` 输出仍会出现固定的 `literal_overlap_errors=20` 诊断项；该字段属于 literal scoring semantics，不能替代 physical-residency 安全检查。本轮六组最终解均为 `safe_overlap_errors=0`、`valid=true`。

## 六组正式结果

| Case | Q2 polish | Baseline official | Optimized official | Improvement | Extra traffic | Optimized safe | Recolor rounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Matmul_Case0 | 0 | 135,082 | **133,682** | **1.036408%** | 28,800 | 160,005 | 0 / 1 |
| Matmul_Case1 | 0 | 1,534,618 | **1,531,946** | **0.174115%** | 430,208 | 1,669,574 | 0 / 1 |
| FlashAttention_Case0 | 1 | 194,265 | **188,562** | **2.935681%** | 54,016 | 204,875 | 3 / 4 |
| FlashAttention_Case1 | 0 | 962,746 | **962,022** | **0.075202%** | 242,552 | 1,026,634 | 15 / 16 |
| Conv_Case0 | 2 | 636,114 | **604,665** | **4.943925%** | 177,904 | 785,887 | 16 / 17 |
| Conv_Case1 | 3 | 3,852,543 | **3,781,664** | **1.839798%** | 721,464 | 4,113,775 | 21 / 22 |

`Recolor rounds` 为“accepted / attempted”；四个有收益 case 都在最后一轮无改善后自然饱和。Matmul 两组第一轮即无收益，因此 generic operator 自动 no-op，没有为了制造变化而接受等价地址。

六组 official cycles 合计：

- promoted-Q2 baseline：`7,315,368`
- 当前 optimized：`7,202,541`
- 减少：`112,827 cycles`
- 聚合下降：`1.542328%`

相对上一版正式 Q3 `7,213,960`，本轮 recolor 再减少 `11,419 cycles`（约 `0.158290%`）：

- FlashAttention_Case0：再减 `5,703`
- FlashAttention_Case1：再减 `724`
- Conv_Case0：再减 `1,764`
- Conv_Case1：再减 `3,228`
- Matmul 两组：保持不变

## Conv 与 recolor 诊断

原 address + pipeline optimizer 在 Conv 上已经到达固定点：Conv0 / Conv1 的第二轮 critical reschedule 均 `changed_positions=0`。新的 recolor 改变的是 initial address reuse 关系，而不改变 schedule/SPILL traffic 语义，因此能够继续突破该 fixed point。

- Conv0：pipeline 先将 official `636,114 -> 606,429`；recolor 再到 `604,665`，16 个 move 被接受，第 17 轮饱和。safe `786,202 -> 785,887`。
- Conv1：pipeline 先将 official `3,852,543 -> 3,784,892`；recolor 再到 `3,781,664`，21 个 move 被接受，第 22 轮饱和。safe `4,119,420 -> 4,113,775`。
- 两组 recolor 后再做一次 critical reschedule 都没有进一步降低 official cycles，因此 post-reschedule 被严格拒绝。

这说明当前继续简单增加 address/pipeline outer rounds 没有价值；有效增益来自改变 reuse-edge structure 的新 operator。

## scorer 性能与正确性

Conv1 暴露出旧 `OfficialFastContext.score()` 的瓶颈：每个 candidate 都重新逐 ALLOC、逐字节构造完整 `official_literal_reuse_edges`。当前实现改为 exact incremental edge-support scorer：单 buffer initial-offset move 只更新两类可能变化的 reuse support——移动 ALLOC 的 incoming reuse，以及旧/新区间每个字节遇到的第一个后续 ALLOC。第一个后续 ALLOC 覆盖该字节后，candidate 与 baseline 的 last-owner 状态重新汇合，因此更后的 ALLOC 无需重放。

安全边界保持不变：

- scorer 只用于 candidate screening；
- 多 buffer offset 同时变化时自动退回 full scorer；
- 所有可能获胜的 candidate 仍执行完整 `official_literal` replay、`residency_safe` replay 和 Q2/SPILL/traffic invariant 检查；
- differential tests 逐 offset 对比 incremental scorer 与 full evaluator，latest focused tests 通过。

实际 CI 中，FA1 的完整 strict optimizer 从此前约 `85.7 s` 降至本轮 `44.3 s`，Conv0 从约 `27 s` 降至 `15.0 s`；Conv1 深搜最终在 `1238.25 s` 内完成 22 轮 strict acceptance，没有降低 validator 强度。

## 验收证据

Production recolor integration：

- integration commit：`294c0c079ac4470cec62874897022241ebbcb05e`
- incremental scorer + differential gate HEAD：`23c6ceae81fe153afd775d8115071762af43c88b`
- branch：`agent/q3-pipeline-20260911`

Latest core regression：

- workflow：`Test CPMCM 2025 A Q3`
- run：`34669296270`
- conclusion：`success`
- full tests、promoted-Q2 baseline、address policies、pipeline critical、safe optimizer、official optimizer、artifact upload：全部 success

Dedicated strict recolor matrix：

- workflow：`Test CPMCM 2025 A Q3 Official Recolor`
- run：`34669296302`
- conclusion：六个 case **6 / 6 success**
- HEAD：`23c6ceae81fe153afd775d8115071762af43c88b`

Per-case artifact：

| Case | Artifact ID | Digest |
|---|---:|---|
| Matmul_Case0 | `10289817485` | `sha256:d496e035f1fcd19bba287ec7913becd5504c33e7d0d70df7a62003e92f667bed` |
| Matmul_Case1 | `10289872436` | `sha256:b35b5b336598acbf6e041605c169e0d109bc7457f90a4a5a81e651a141164d41` |
| FlashAttention_Case0 | `10290196070` | `sha256:a0288646829cb5d7310c1705c7f141d02994e229ac5657fb13d038d8b0d86fba` |
| FlashAttention_Case1 | `10290996134` | `sha256:a225882c8a84a16c89a668fe75d34aa6e23685c946900d94c040589e6f06249e` |
| Conv_Case0 | `10290626424` | `sha256:0cdf1539ef54de318222421bd290cc943c2b621b56470e49ec81e6a62de474be` |
| Conv_Case1 | `10290956356` | `sha256:c5c31382869e26b5a0afdbc0107ec45a8103360d12176b6187f45ed0d1c1efa7` |

`q3_official_zero_traffic_summary.csv/json` 为上述同一 matrix run 的六个 per-case artifact 合并结果；`q3_official_zero_traffic_trace.json` 保存每个 case 的完整正式 transformation trace，避免只保留汇总数字而丢失 acceptance provenance。

更进一步的 traffic–cycles refined 结果见 [`../q3_pareto/README.md`](../q3_pareto/README.md)。
