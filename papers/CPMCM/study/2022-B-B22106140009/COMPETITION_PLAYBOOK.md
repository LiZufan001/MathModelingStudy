# B22106140009｜大规模排样 / 组批优化比赛速查

> 适用题型：二维/三维装箱、切割下料、车辆/订单组批、仓储分区、任务聚类后再优化、任何“外层分组 + 内层 NP-hard packing/scheduling”的问题。

---

# 1. 开题 30 分钟先回答 8 个问题

1. **独立对象是什么？** item / order / batch / plate？
2. **硬约束是什么？** 不满足就无效的条件全部列出。
3. **目标是真正的什么？** 板数、成本、时间，而不是 surrogate similarity。
4. **有没有层次结构？** item→stack→stripe→plate？
5. **有没有可封装的局部 pattern？**
6. **全局精确模型规模多大？** 是否必须 decomposition？
7. **能算什么 lower bound？**
8. **如何一键验证最终 solution？**

若第 8 个问题没有答案，先别写高级算法。

---

# 2. 看到 NP-hard 大规模题的标准路线

```text
原问题
  ↓
严格 formalization
  ↓
规模 / NP-hard 分析
  ↓
找结构与可分解模块
  ↓
简单可行 baseline
  ↓
constructive heuristic
  ↓
local improvement
  ↓
lower bound / small exact benchmark
  ↓
feasibility evaluator
  ↓
消融 + 稳健性
```

不要一上来：

```text
GA / PSO / SA / GWO
```

先问搜索空间能否被结构砍掉 90%。

---

# 3. Packing 题必须有的三个数字

## 3.1 总面积下界

\[
LB_{area}=\left\lceil\frac{A_{tot}}{A_{plate}}\right\rceil.
\]

## 3.2 分组属性下界

若不同 material/category 不能共容器：

\[
LB_{group}=\sum_g\left\lceil\frac{A_g}{A_{plate}}\right\rceil.
\]

## 3.3 实际板数

必须同时报：

```text
LB
solution
solution/LB
utilization
```

但只在 LB 真的是有效 lower bound 时使用；不要把乐观 LB 差值写成“最优性 gap”。

---

# 4. Grouping / batching 题必须先算容量下界

如果每批：

\[
N_b\le N_{max},
\qquad
A_b\le A_{max},
\]

则：

\[
LB_{batch}
=
\max\left(
\left\lceil\frac{N}{N_{max}}\right\rceil,
\left\lceil\frac{A}{A_{max}}\right\rceil
\right).
\]

写成程序 assert：

```python
assert n_batches >= batch_lower_bound
```

这是本篇 B2 问题给我们的最直接教训。

---

# 5. 工艺结构应直接变成数据结构

例如：

```text
item
  ↓
stack
  ↓
stripe
  ↓
plate
```

好处：

- 自动满足部分工艺约束；
- 大幅减少搜索自由度；
- 方便坐标恢复；
- 方便局部搜索；
- 论文解释清楚。

同类迁移：

```text
零件→工序块→机器队列
包裹→托盘→车辆
任务→批次→设备
SKU→箱→托盘→车
节点→社区→路线
```

---

# 6. Constructive heuristic 的可靠模板

## 初始化排序

优先“难放对象”：

- 面积大；
- 长边大；
- 稀有属性；
- 可选位置少。

## 放置评分

\[
score
=
-w_1\cdot residual
-w_2\cdot fragmentation
+w_3\cdot edge\_match
+w_4\cdot future\_flexibility.
\]

每次选择 score 最好且合法的位置。

## 多起点

不要只跑一个排序：

```text
area descending
max-side descending
random perturbation
rare-attribute first
```

取最好结果。

---

# 7. Local search 五件套

初始可行解后：

1. `move`：移动一个单元；
2. `swap`：交换两个单元；
3. `merge`：合并两个容器/批次；
4. `split`：重分一个坏容器；
5. `destroy-repair`：拆掉最差的一小片区域重建。

只重算受影响部分，别每次全局重跑。

---

# 8. 外层 grouping + 内层 solver 的通用结构

如果最终目标由下游求解器决定：

\[
\min_x C(x),
\]

但 \(C(x)\) 很贵，可以：

```text
cheap surrogate
   ↓ 筛 top-k
expensive evaluator
   ↓
选择真实最好
```

本篇对应：

```text
material similarity
   ↓
packing oracle
```

其他题：

```text
路线距离近似 → 精确调度仿真
风险评分 → Monte Carlo
聚类相似度 → downstream optimization
```

原则：

> **surrogate 负责快，real objective 负责最终决定。**

---

# 9. Similarity 不要只靠“客观赋权”包装

变异系数、熵权法只能说明数据分布特征，不天然代表最终业务目标的重要度。

正确验证：

```text
candidate similarity
  ↓
实际 downstream saving
  ↓
相关性 / 回归 / 消融
```

如果：

\[
Similarity\uparrow
\]

但真实 cost 没下降，就要改 surrogate。

---

# 10. Formal model 与 heuristic 的标准论文写法

推荐模板：

> “首先建立原问题的组合优化/混合整数规划形式，以明确目标和约束。规模分析显示，实际实例下直接精确求解代价过高，因此利用 XXX 工艺结构进行分解，并设计 XXX 构造式启发式求取高质量可行解。”

这样：

- 不假装 heuristic 解了完整 MIP；
- 又保留数学形式化价值；
- 解释了算法为什么合理。

---

# 11. 什么时候值得用 MILP solver

适合：

- 小规模 benchmark；
- 子问题；
- pattern selection；
- local repair；
- lower bound；
- 验证 heuristic。

不适合：

> 在几万 item、二维 non-overlap、stage、batch 全叠加以后，未经规模估计就直接求全局 MILP。

---

# 12. 结果表前必须过的 feasibility gates

```text
[ ] every item exactly once
[ ] every order exactly one batch
[ ] no overlap
[ ] inside boundary
[ ] guillotine/stage valid
[ ] same-material rule valid
[ ] batch item count valid
[ ] batch area valid
[ ] coordinate file reconstructs solution
```

任一失败：

```text
STOP
```

不允许继续比较 utilization。

---

# 13. 复杂度报告模板

至少区分：

```text
N = item count
M = order count
P = candidate patterns
I = local search iterations
C_eval = one evaluator cost
```

然后按真实代码写：

```text
preprocessing: O(...)
candidate generation: O(...)
initial construction: O(...)
local search: O(I * ...)
```

最后给：

```text
wall-clock
CPU/GPU
peak memory
random seed
```

不要用板长 2440 这样的物理量当算法复杂度自变量，除非算法真按每个毫米网格遍历。

---

# 14. 消融实验最小模板

## Packing

| Variant | plates | util | time |
|---|---:|---:|---:|
| simple FFD | | | |
| + stack | | | |
| + stripe heuristic | | | |
| + local repair | | | |
| + multi-start | | | |

## Batching

| Variant | batches | plates | util | feasible |
|---|---:|---:|---:|---|
| random feasible | | | | |
| material similarity | | | | |
| + capacity score | | | | |
| + packing feedback | | | | |
| + local search | | | | |

一张表能比大段“算法优越性分析”更有说服力。

---

# 15. 结果数据单一真源

计算程序只写：

```text
results.json
cut_program.csv
sum_order.csv
```

论文脚本读取 `results.json` 自动生成：

- 表格；
- 摘要关键数字；
- 图标题；
- lower bound；
- feasibility 状态。

避免出现本篇这样的：

```text
166 vs 229
381 vs 403
48 vs 130
```

---

# 16. 赛场 10 分钟自检

看到“排样 / 装箱 / 分组后优化”，迅速问：

```text
1. hard constraints 锁了吗？
2. lower bound 有吗？
3. simplest feasible baseline 有吗？
4. 能利用什么结构？
5. surrogate 和真实目标一致吗？
6. 有没有 local improvement？
7. final evaluator 独立了吗？
8. 表格是不是自动生成？
```

---

# 17. 本篇一句话迁移

> **对于巨大组合优化，优秀竞赛方案往往不是“精确求全局最优”，而是“结构化降维后快速构造可行解，再用下界、真实 evaluator 和局部改进把近似方案做得可信”。**
