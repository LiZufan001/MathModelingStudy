# Q3 Formal Fixed-Traffic Results

本目录记录 2025 A 题问题 3 当前正式的 **fixed-Q2-traffic** 最优结果。

目标口径为题面 `official_literal` 总周期；`residency_safe` 不参与排序，但作为硬可行性门禁。整个 Q3 后处理保持 promoted Q2 的 SPILL 身份/顺序、SPILL 次数和 extra traffic 不变，因此这里的改善来自地址/流水/调度序列本身，而不是增加额外 DDR 搬运换取周期。

## 当前六组正式结果

| case | promoted-Q2 raw | formal core | final official | vs raw | final safe | spills | extra traffic |
|---|---:|---:|---:|---:|---:|---:|---:|
| Matmul_Case0 | 135,082 | 133,682 | **133,682** | **-1.036408%** | 160,005 | 225 | 28,800 |
| Matmul_Case1 | 1,534,618 | 1,531,946 | **1,531,946** | **-0.174115%** | 1,669,574 | 3,361 | 430,208 |
| FlashAttention_Case0 | 194,265 | 188,562 | **187,945** | **-3.253288%** | 204,875 | 316 | 54,016 |
| FlashAttention_Case1 | 962,746 | 962,022 | **962,022** | **-0.075202%** | 1,026,634 | 1,782 | 242,552 |
| Conv_Case0 | 636,114 | 603,405 | **595,302** | **-6.415831%** | 789,619 | 522 | 177,904 |
| Conv_Case1 | 3,852,543 | 3,781,664 | **3,767,326** | **-2.211968%** | 4,112,665 | 9,646 | 721,464 |

第一阶段 fresh-rerank critical-SPILL batch 对 Matmul0、Matmul1、FA1 第一轮即 no-op；对 FA0、Conv0、Conv1 分别额外降低 **617 / 5,436 / 14,338 cycles**。六组均在该 batch 算子上出现首个 no-improvement round。

Conv0 随后增加第二类 fixed-traffic 邻域：`critical SPILL single-switch bubble`。它只尝试把 critical path 上匹配的 `SPILL_OUT(MTE3)` / `SPILL_IN(MTE2)` 端点沿同 Pipe 向前冒泡一格，并对每个候选重新执行 strict Q2、official 与 residency-safe replay。以 `max_switches=4` 做 checkpointed saturation：

- `597,969 -> 597,051`：-918 cycles；
- `597,051 -> 596,988`：-63 cycles；
- `596,988 -> 595,302`：-1,686 cycles；
- 下一轮 no-op。

因此 Conv0 在 single-switch 邻域又累计降低 **2,667 cycles**，traffic/spill 完全不变；该点已由 formal acceptance 从旧正式 Problem3 输出完整重放并晋升。

## 正式算法链

通用主链：

1. 从 `solve_q2_promoted()` 取得固定 Q2 SPILL 方案；
2. formal zero-traffic optimizer：地址 portfolio、critical pipeline reschedule、critical-reuse recolor；
3. fresh-rerank critical-SPILL batch：按关键路径重新排序批量 SPILL serialization 变换；
4. 每个候选都要求 strict Q2 replay、SPILL/traffic 不变量、official 严格改善、residency-safe 合法；
5. 每轮重新计算 critical path，首个 no-improvement round 停止。

Conv0 当前在上述主链后追加一个已正式验收的 single-switch post-pass。它不是 Conv 模板硬编码：候选来自当前 critical path 与 SPILL/Pipe 结构；是否对其它 case 有收益仍需分别实测，不能由 Conv0 结果外推。

## Conv1 双路线复现

Conv1 是最大的 Appendix-E case。最终 `3,767,326` 已由两条独立路径复现：

- deterministic saturated shortcut：从已验证的 21 个 saturated offset override 重建 `3,781,664`，再迭代 7 轮改善，第 8 轮 no-op；
- full formal chain：直接从 promoted Q2 经 deep formal zero-traffic 得到 `3,781,664`，再由正式 `src/q3_spill_batch_optimizer.py` 得到同样的 `3,767,326`。

两条路径的 final safe cycles 均为 `4,112,665`，spill count 均为 `9,646`，extra traffic 均为 `721,464`。

## Problem3 输出

正式导出器：

`src/export_q3_formal_fixed_traffic.py`

基础 formal fixed-traffic 六组均已实际生成题面提交需要的：

```text
Problem3/<case>_schedule.txt
Problem3/<case>_memory.txt
Problem3/<case>_spill.txt
```

Conv0 新晋升点由 single-switch formal acceptance 重新生成完整 Problem3 三文件；旧 `597,969` 附件仍只作为该 post-pass 的可复现输入基线。

## 验收证据

- 五组基础 Problem3 导出：run `34747455829`，5/5 success；
- Conv1 targeted Problem3 acceptance：run `34747404506`，artifact `10315405008`，digest `sha256:7d64c9ff2d80a2b51d40b8e47abfb662dae58ca6daddcb8ffd125f7f36b12756`；
- Conv1 full formal：run `34745747473`，artifact `10314199173`，digest `sha256:dda2514dcb6764ddcfa8361ed513acd7494c7ab6c4fc1b0add09aecb95c2a7e7`；
- Conv0 single-switch formal acceptance：run `34748384017`，artifact `10315385596`，digest `sha256:b7919290c4205ff75d83720abea7020bba57c14bc6489979816caff60d72df90`；
- 完整 Q2 回归：run `34747286667`，success；
- 当前 published-results consistency：run `34748431634`，success；
- Pareto dominance 只允许 `strict_valid=true` 候选参与支配判断，修复提交 `88263a87c0bad9b3221fb1598058210f0acee3cc`。

## 结论边界

`saturated` 永远只针对指定邻域：

- 六组均对当前 fresh-rerank critical-SPILL batch 达到局部饱和；
- Conv0 额外对 `max_switches=4` single-switch bubble 达到局部饱和；
- 这些都**不是 Q3 全局最优证明**。

后续继续优化时，应优先横向验证 single-switch 对其它 case 的收益，再决定是否扩大候选宽度或开发新的 schedule operator。
