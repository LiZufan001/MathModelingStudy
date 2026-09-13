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
| Conv_Case0 | 636,114 | 603,405 | **597,969** | **-5.996567%** | 787,783 | 522 | 177,904 |
| Conv_Case1 | 3,852,543 | 3,781,664 | **3,767,326** | **-2.211968%** | 4,112,665 | 9,646 | 721,464 |

其中第二阶段 critical-SPILL batch 对 Matmul0、Matmul1、FA1 第一轮即 no-op；对 FA0、Conv0、Conv1 分别额外降低 **617 / 5,436 / 14,338 cycles**。六组均在 fresh-rerank 后出现首个 no-improvement round，因此对当前 batch 算子均有局部饱和证据。

## 正式算法链

1. 从 `solve_q2_promoted()` 取得固定 Q2 SPILL 方案；
2. 运行现有 formal zero-traffic optimizer：地址 portfolio、critical pipeline reschedule、critical-reuse recolor；
3. 在当前 `official_literal` critical path 上识别 `SPILL_OUT -> SPILL_IN` 串行边界；
4. 按相邻 MTE3/MTE2 串行段权重对可移动 SPILL_OUT 排序；
5. 对 `1,2,4,8,16,24,32,48,64` 个候选前缀反转可变 MTE3 serialization edges，重新拓扑排序；
6. 候选只有同时满足以下条件才可接受：
   - strict Q2 replay 通过；
   - SPILL 身份/顺序、spill count、extra traffic 不变；
   - `official_literal` 周期严格下降；
   - `residency_safe` replay 通过且无 physical overlap；
7. 每接受一轮后重新计算 critical path 和候选排序，直到首个无改善轮停止。

这个 post-pass 不依赖 Matmul / FlashAttention / Conv 模板名。FA0 与 Conv0 的真实改善、Matmul/FA1 的自然 no-op 共同构成其通用性证据。

## Conv1 双路线复现

Conv1 是最大的 Appendix-E case。最终 `3,767,326` 已由两条独立路径复现：

- deterministic saturated shortcut：从已验证的 21 个 saturated offset override 重建 `3,781,664`，再迭代 7 轮改善，第 8 轮 no-op；
- full formal chain：直接从 promoted Q2 经 deep formal zero-traffic 得到 `3,781,664`，再由正式 `src/q3_spill_batch_optimizer.py` 得到同样的 `3,767,326`。

两条路径的 final safe cycles 均为 `4,112,665`，spill count 均为 `9,646`，extra traffic 均为 `721,464`。

## Problem3 输出

正式导出器：

`src/export_q3_formal_fixed_traffic.py`

它输出题面提交需要的三类文件：

```text
Problem3/<case>_schedule.txt
Problem3/<case>_memory.txt
Problem3/<case>_spill.txt
```

非 Conv1 五组已由 workflow `Export CPMCM 2025 A Q3 Formal Fixed-Traffic Outputs` 实际导出并通过 cycles ceiling、局部饱和、strict replay 与 residency-safe gate。Conv1 使用单独 targeted acceptance 同时生成最终三文件，避免再次运行更慢的完整 deep formal chain。

## 验收证据

- 五组正式 Problem3 导出：run `34747455829`，5/5 success；
- Conv1 full formal：run `34745747473`，artifact `10314199173`，digest `sha256:dda2514dcb6764ddcfa8361ed513acd7494c7ab6c4fc1b0add09aecb95c2a7e7`；
- 完整 Q2 回归：run `34747286667`，success；
- refined-frontier reconciliation gate：run `34747219856`，success；
- Pareto dominance 已修正为只允许 `strict_valid=true` 候选参与支配判断，修复提交 `88263a87c0bad9b3221fb1598058210f0acee3cc`。

## 结论边界

这里的 `saturated` 只表示 **当前 fresh-rerank critical-SPILL batch 算子** 已到首个无改善轮，不等于证明问题 3 的全局最优。此前 single-switch greedy 长 run 因超时取消，没有形成 no-op 证明；因此后续若继续优化，应视为探索新的 schedule operator，而不是继续堆当前 batch 深度。
