# Q3 Formal Fixed-Traffic 方法笔记：Critical-SPILL Fresh-Rerank

## 1. 这一阶段到底在优化什么

问题 2 已经给出 promoted Q2 解：调度序列、连续地址、SPILL 身份与次数都合法，并且 extra traffic 已经尽量低。

问题 3 的 fixed-traffic 阶段不允许“多搬一点数据换时间”，而是在**完全保持 Q2 traffic/SPILL 决策不变**的前提下重新组织 Q3 的物理地址和流水序列，使题面 `official_literal` 总执行周期更短。

正式目标写成：

\[
\min T_{official}(S,A)
\]

约束至少包括：

\[
Traffic(S,A)=Traffic_{Q2},\qquad N_{spill}=N_{spill,Q2}
\]

以及 strict Q2、题面 Q3 依赖和 `residency_safe` 全部合法。

这里 `official_literal` 是比赛主目标；`residency_safe` 只做硬可行性门禁，不拿它替代官方目标排序。

---

## 2. 为什么从 critical SPILL 边入手

插入一次 SPILL 后，产生：

- `SPILL_OUT`：MTE3，片上缓存 -> DDR；
- `SPILL_IN`：MTE2，DDR -> 片上缓存；
- `SPILL_OUT -> SPILL_IN`：同一 SPILL 的固定依赖。

若 Q3 critical path 上出现：

```text
... MTE3 串行段 -> SPILL_OUT -> SPILL_IN -> MTE2 串行段 ...
```

说明当前总周期正在被“先等一批 MTE3，再换出，再换入，再排 MTE2”的串行结构卡住。

SPILL 本身不能删除，也不能改变其 buffer 身份，否则会破坏 Q2；但 **SPILL_OUT 在 MTE3 pipe 上与其它无强依赖任务的相对顺序仍可能调整**。

因此可以尝试把关键 `SPILL_OUT` 向前移动，让 DDR 换出更早开始，减少关键路径上的等待，而不增加一次 SPILL。

---

## 3. 哪些边能动，哪些绝对不能动

正式实现把依赖边分为：

1. 原始计算图依赖：固定；
2. SPILL 自身依赖：固定；
3. residency-safe 地址复用依赖：固定；
4. 同一 Pipe 的 serialization edge：其中一小部分可以作为局部搜索变量。

对 critical path 上的候选 `SPILL_OUT`，找到它在 MTE3 序列中的直接前驱：

```text
prev_MTE3 -> SPILL_OUT
```

只有当这条边不是上述固定依赖时，才允许试验反转：

```text
SPILL_OUT -> prev_MTE3
```

然后把新的约束图重新做确定性拓扑排序。

若反转造成环，候选立即拒绝。这一点非常重要：算法不是直接在数组里“交换两个节点”，而是在依赖图层面修改一个可变 serialization 关系，再重新得到合法拓扑序。

---

## 4. 为什么不是一个一个贪心，而是 batch prefix

多个关键 SPILL_OUT 之间会相互影响。

只移动一个候选时，新的局部空隙可能仍被旁边的 MTE3 串行段挡住；几个相关边一起反转，才可能真正改变关键路径结构。

因此每一轮先按 critical path 两侧的串行运行量打分：

\[
score_i = C^{left}_{MTE3,i}+C^{right}_{MTE2,i}
\]

按 score 从大到小排序后，不枚举指数级子集，只试有限前缀：

```text
1, 2, 4, 8, 16, 24, 32, 48, 64
```

这相当于一个很便宜的“组合强度扫描”：

- 小 prefix 测局部单点效应；
- 大 prefix 测多个串行瓶颈同时解除的协同效应；
- 不需要搜索全部 `2^K` 子集。

每个 prefix 都必须独立 strict replay。

---

## 5. Fresh-rerank 是本轮最关键的发现

最开始只在同一 critical path 上不断扩大 prefix，会遇到一个自然边界：原 critical path 上候选用完以后，再加边可能成环或者无收益。

但一旦接受一个 batch，**critical path 已经变了**。

新的 bottleneck 可能落在另一组 SPILL_OUT 上。因此正确流程不是：

```text
旧 critical path -> 一次排序 -> 一直扩大 prefix
```

而是：

```text
当前解
-> 重新计算 official critical path
-> 重新提取 / 排序 critical SPILL candidates
-> prefix portfolio
-> 接受严格改善
-> 再回到当前解重新计算
```

即 fresh-rerank coordinate descent。

直到某一轮所有 prefix 都没有严格改善，才把该算子记为局部饱和。

---

## 6. 正式接受条件

任何候选都必须同时满足：

1. strict Q2 replay 成功；
2. SPILL buffer 身份与顺序不变；
3. spill count 不变；
4. extra traffic 不变；
5. `official_literal` replay 成功；
6. official cycles **严格下降**；
7. `residency_safe` replay 成功；
8. physical overlap errors = 0。

所以这是一个“先可行、再比较”的优化器，不会为了漂亮 cycles 静默破坏内存语义。

需要注意：formal core 的地址 recolor 可以合法改变 `SPILL_IN NewOffset`。因此固定的是 SPILL **identity/order/count/traffic**；进入 spill-batch 第二阶段后，第二阶段必须精确保留 formal core 已经确定的完整 SPILL records。

---

## 7. 六组真实结果告诉我们什么

| case | formal core | spill-batch final | 第二阶段收益 | accepted rounds |
|---|---:|---:|---:|---:|
| Matmul_Case0 | 133,682 | 133,682 | 0 | 0 |
| Matmul_Case1 | 1,531,946 | 1,531,946 | 0 | 0 |
| FlashAttention_Case0 | 188,562 | **187,945** | 617 | 5 |
| FlashAttention_Case1 | 962,022 | 962,022 | 0 | 0 |
| Conv_Case0 | 603,405 | **597,969** | 5,436 | 10 |
| Conv_Case1 | 3,781,664 | **3,767,326** | 14,338 | 7 |

每个 case 的最后一轮都没有改善，因此当前 fresh-rerank critical-SPILL batch 算子在六组数据上都达到局部饱和。

这里有两个很适合论文讨论的结论：

- 算法不是 Conv 特判：FA0 也得到真实改善；
- 算法也不会强行改解：Matmul 与 FA1 没有收益时自然 no-op。

---

## 8. FA0 的 Pareto 结构为什么发生变化

此前 FA0 的 refined trade-off 有：

```text
traffic 55,036 / official 191,230
```

现在 fixed-traffic 就能达到：

```text
traffic 54,016 / official 187,945
```

新点同时 traffic 更低、cycles 更低，因此旧 trade-off 被严格支配。

这说明 Pareto 前沿不是一次搜索后永久固定的：**一旦 fixed-traffic baseline 被更强算法推进，所有 higher-traffic trade-off 都必须重新做 dominance reconciliation。**

这也是本轮专门加入 published-results consistency gate 的原因。

---

## 9. 复杂度与工程取舍

设当前增广图规模为 `|V'|, |E'|`，一轮最多测试 `P<=9` 个 prefix。

每个候选主要成本包括：

- 重新拓扑排序：约 `O(|V'|+|E'|)`；
- strict Q2 replay；
- official evaluator；
- 只有 official 有竞争力时再做 residency-safe evaluator。

因此总成本近似为：

\[
O(R\,P\,(|V'|+|E'|))
\]

乘上 evaluator / replay 的常数项。

Conv1 有 3.6 万原始节点、近万次 SPILL，增广图很大，所以完整 deep formal + spill-batch 会明显更慢。工程上保留 deterministic saturated snapshot，是为了在已验证第一阶段不变时避免每次重复 deep recolor，而不是绕过正式验证。

---

## 10. 论文中可以怎样表述

可以把方法概括为：

> 在固定问题 2 的换入换出决策与额外搬运量后，构造包含原始依赖、SPILL 依赖、物理地址复用依赖和流水串行约束的增广 DAG。针对当前关键路径上的 SPILL 串行瓶颈，选择不属于固定语义依赖的 MTE3 邻接约束作为局部搜索变量，通过分层前缀反转与确定性拓扑重排生成候选调度；每轮按官方周期严格选优，并在接受后重新计算关键路径和候选排序，直至局部无改善。

这比“用了贪心算法优化流水”更具体，也更容易解释为什么算法合法、为什么不增加 traffic、为什么能在 Conv/FA 上取得收益。

---

## 11. 不要夸大的边界

当前只能说：

- 该 batch 算子对六组数据均已达到 no-improvement round；
- Conv1 最终点已经由两条独立路线复现；
- 所有正式点均 strict-valid / residency-safe。

不能说：

- Q3 全局最优；
- 所有 schedule operator 都已经饱和；
- single-switch greedy 已证明无收益。

之前 single-switch greedy 长任务被 timeout/cancel，因此它没有形成 no-op 证据。若后续继续优化，应探索新的 schedule operator，而不是继续机械增加当前 batch 深度。
