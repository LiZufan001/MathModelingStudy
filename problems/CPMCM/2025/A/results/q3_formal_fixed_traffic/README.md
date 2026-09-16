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
| Conv_Case1 | 3,852,543 | 3,781,664 | **3,749,777** | **-2.667485%** | 4,114,811 | 9,646 | 721,464 |

第一阶段 fresh-rerank critical-SPILL batch 对 Matmul0、Matmul1、FA1 第一轮即 no-op；对 FA0、Conv0、Conv1 分别额外降低 **617 / 5,436 / 14,338 cycles**。六组均在该基础 batch 算子上出现首个 no-improvement round。

Conv0 随后增加第二类 fixed-traffic 邻域：`critical SPILL single-switch bubble`。它只尝试把 critical path 上匹配的 `SPILL_OUT(MTE3)` / `SPILL_IN(MTE2)` 端点沿同 Pipe 向前冒泡一格，并对每个候选重新执行 strict Q2、official 与 residency-safe replay。以 `max_switches=4` 做 checkpointed saturation：

- `597,969 -> 597,051`：-918 cycles；
- `597,051 -> 596,988`：-63 cycles；
- `596,988 -> 595,302`：-1,686 cycles；
- 下一轮 no-op。

因此 Conv0 在 single-switch 邻域又累计降低 **2,667 cycles**，traffic/spill 完全不变；该点已由 formal acceptance 从旧正式 Problem3 输出完整重放并晋升。

Conv1 在旧正式点 `3,767,326` 之后增加 `fresh-rerank cycle-filtered critical-SPILL batch` post-pass。该算子先过滤会形成 singleton precedence cycle 的候选，再在剩余 critical-SPILL 前缀上重新排序并严格重放。连续 checkpoint 最终达到：

`3,767,326 -> ... -> 3,749,985 -> 3,749,863 -> 3,749,821 -> 3,749,777 -> no improvement`

相对旧正式点累计再降低 **17,549 cycles**；相对 promoted-Q2 raw 累计降低 **102,766 cycles（2.667485%）**。整个 post-pass 保持 spill count `9,646`、extra traffic `721,464` 与 exact SPILL records 不变，最终 safe cycles 为 `4,114,811`、safe-overlap errors 为 `0`。

## 正式算法链

通用主链：

1. 从 `solve_q2_promoted()` 取得固定 Q2 SPILL 方案；
2. formal zero-traffic optimizer：地址 portfolio、critical pipeline reschedule、critical-reuse recolor；
3. fresh-rerank critical-SPILL batch：按关键路径重新排序批量 SPILL serialization 变换；
4. 每个候选都要求 strict Q2 replay、SPILL/traffic 不变量、official 严格改善、residency-safe 合法；
5. 每轮重新计算 critical path，首个 no-improvement round 停止。

Conv0 在上述主链后追加已正式验收的 single-switch post-pass；Conv1 追加已正式验收的 cycle-filtered critical-SPILL post-pass。两者都不是 Conv 模板硬编码：候选来自当前 critical path 与 SPILL/Pipe/precedence 结构。

横向核查已经把 Matmul0 / Matmul1 / FA0 / FA1 从 `max_switches=4` 扩到 **top-8 单轮**。四组都得到 `candidate_count=0`：当前 official critical path 上不存在 single-switch 算子要求的 `SPILL_OUT(MTE3) -> SPILL_IN(MTE2)` 可翻转边，因此不继续机械扩宽到 16/32。

## Conv1 provenance 与独立验收

旧正式点 `3,767,326` 已由两条独立路径复现：

- deterministic saturated shortcut：从已验证的 21 个 saturated offset override 重建 `3,781,664`，再迭代 7 轮改善，第 8 轮 no-op；
- full formal chain：直接从 promoted Q2 经 deep formal zero-traffic 得到 `3,781,664`，再由正式 `src/q3_spill_batch_optimizer.py` 得到同样的 `3,767,326`。

新的 cycle-filtered post-pass 从这个已验证正式点继续 checkpoint 搜索。最终搜索 run `35056138452` 在 `3,749,777` 后首次出现 no-improvement；随后 formal acceptance run `35064897835` **不信任搜索 summary 本身**，重新：

1. 从源码构造 promoted Q2；
2. strict Q2 replay；
3. official-literal 与 residency-safe 双 evaluator 重放；
4. 对比 exact SPILL records、spill count 与 extra traffic；
5. 从 `3,749,777` 再独立执行一次同一 cycle-filtered 邻域，要求再次 no-improvement。

上述步骤全部通过，独立 recheck 得到 `improved=false / official=3,749,777 / safe=4,114,811 / safe_overlap_errors=0`。因此当前 Conv1 点已经从实验候选晋升为正式 fixed-traffic 结果。

## Problem3 输出

正式导出器：

`src/export_q3_formal_fixed_traffic.py`

基础 formal fixed-traffic 六组均已实际生成题面提交需要的：

```text
Problem3/<case>_schedule.txt
Problem3/<case>_memory.txt
Problem3/<case>_spill.txt
```

Conv0 新晋升点由 single-switch formal acceptance 重新生成完整 Problem3 三文件。Conv1 新晋升点也由 cycle-filtered formal acceptance 重新生成完整三文件。由于 GitHub Actions artifact 会过期，仓库额外永久保存 `q3_conv1_cycle_filtered_acceptance.json`，其中记录搜索/验收 provenance、正式 artifact digest 和三份输出的 SHA-256；当前正式 Conv1 输出 SHA 分别为：

- schedule：`54afb1046cd578bbee0597deafd8b3856202f039509fcb522ec5c9ffeeda302e`
- memory：`73272121bc6889751d466c263493a7650981c83c898fef4fee77eb2dce4bf1e5`
- spill：`cf705111ba94928b129d0a6c0c31fdc125415bd485c30abba65a96647cbf473c`

## 验收证据

- 五组基础 Problem3 导出：run `34747455829`，5/5 success；
- Conv1 旧 full formal：run `34745747473`，artifact `10314199173`，digest `sha256:dda2514dcb6764ddcfa8361ed513acd7494c7ab6c4fc1b0add09aecb95c2a7e7`；
- Conv1 cycle-filtered saturated search：run `35056138452`，artifact `10430574025`，digest `sha256:71eb5c172cec9910877e70032a558911cb0e8b2076595ff2668554ded9a18d8a`；
- Conv1 cycle-filtered formal acceptance：run `35064897835`，artifact `10434077125`，digest `sha256:3d4145d8fb223dbf1cb58f22268253f419ddcb8113cf670bebd602cb2075cf10`；
- Conv0 single-switch formal acceptance：run `34748384017`，artifact `10315385596`，digest `sha256:b7919290c4205ff75d83720abea7020bba57c14bc6489979816caff60d72df90`；
- Matmul/FA single-switch top-8 width check：run `34748782874`，4/4 success，四组 `candidate_count=0`；
- 完整 Q2 回归：run `34747286667`，success；
- Pareto dominance 只允许 `strict_valid=true` 候选参与支配判断，修复提交 `88263a87c0bad9b3221fb1598058210f0acee3cc`；
- `verify_q3_published_results.py` 负责校验 formal CSV/JSON、refined frontier、reconcile report 与 improvement arithmetic，promotion 后必须重新通过 CI。

## 结论边界

`saturated` 永远只针对指定邻域：

- 六组均对基础 fresh-rerank critical-SPILL batch 达到局部饱和；
- Conv0 额外对 `max_switches=4` single-switch bubble 达到局部饱和；
- Conv1 额外对 `max_switches=16` cycle-filtered critical-SPILL prefix 邻域达到 no-improvement，并由独立 acceptance 再次复查为 no-improvement；
- M0/M1/FA0/FA1 的 single-switch top-8 检查为 `candidate_count=0`；
- 这些都**不是 Q3 全局最优证明**。

后续若继续优化 Conv1，应切换到新的、可明确解释且保持 fixed-Q2 invariants 的 schedule operator，而不是继续机械重复已经 no-op 的 cycle-filtered 邻域。
