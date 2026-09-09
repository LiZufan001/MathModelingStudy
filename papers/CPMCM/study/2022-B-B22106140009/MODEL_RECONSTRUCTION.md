# B22106140009｜模型与算法重构

> 目的：保留原论文“结构化降维 + 快速启发式”的优点，同时把 formal model、actual solver、lower bound、feasibility evaluator 和 local improvement 重新接成一个严格闭环。

---

# 1. 先把问题拆成两个层次

原问题本质上不是一个单一模型。

## Q1

\[
\boxed{
\text{3-stage guillotine packing}
}
\]

输入：若干矩形 item。  
输出：使用哪些 plate、item 坐标、切割结构。  
目标：最少 plate。

## Q2

\[
\boxed{
\text{batch partition}
+
\text{Q1 packing oracle}
}
\]

外层决定：订单如何分批。  
内层决定：每批、每种材料需要多少板。

因此最自然的计算架构是：

```text
Batching Solver
      ↓
  batch candidate
      ↓
按 material 拆分
      ↓
Packing Oracle(Q1)
      ↓
plate count + coordinates + feasibility
      ↑
真实 cost 反馈给外层
```

原论文已经隐含采用这一 decomposition，但没有明确形式化。

---

# 2. 唯一官方 evaluator

任何算法之前先实现：

```python
check_solution(items, plates, batches=None)
```

必须检查：

## Q1

1. 每个 item 恰好出现一次；
2. 不越出 `2440 × 1220`；
3. item 不重叠；
4. item 可以旋转时，尺寸与输入一致；
5. 排样可由 ≤3-stage guillotine cut 实现；
6. 同一 stack 内满足等边约束；
7. 坐标文件能够还原几何方案。

## Q2 新增

1. 每个 order 恰好属于一个 batch；
2. 每批 item 数 ≤1000；
3. 每批总面积 ≤250 m²；
4. 同一 plate 不能混合不同 material；
5. batch id 与最终 `sum_order.csv` 一致。

输出：

```text
feasible
plate_count
utilization
max_batch_items
max_batch_area
order_split_count
overlap_count
stage_violation_count
```

**只有 `feasible=True` 后，目标值才有意义。**

---

# 3. Q1 的 lower bounds

## 3.1 总面积下界

\[
LB_{area}
=
\left\lceil
\frac{\sum_i a_i}{LW}
\right\rceil.
\]

这是最弱但最快的 baseline。

## 3.2 大件容量下界

对某一类“大到一块板最多只能放 \(c_i\) 个”的 item，可构造：

\[
LB_{large}
=
\left\lceil
\frac{n_i}{c_i}
\right\rceil.
\]

多个 mutually incompatible item 还可以构造 conflict graph 下界。

## 3.3 pattern LP 下界

如果能生成一批合法 3-stage cutting patterns \(p\in\mathcal P\)，定义：

- \(a_{ip}\)：pattern \(p\) 中 item type \(i\) 的数量；
- \(x_p\)：pattern 使用次数。

LP relaxation：

\[
\min \sum_p x_p
\]

s.t.

\[
\sum_p a_{ip}x_p\ge d_i,
\qquad
x_p\ge0.
\]

其最优值向上取整是比面积下界更强的理论基准。

比赛时间不足时，不一定真做 column generation，但至少保留面积 LB。

---

# 4. 一个更严谨的 Q1 theoretical formulation

对于小规模实例可以建立位置/模式型 MILP，用于：

- 验证启发式；
- 求小样本精确最优；
- 做算法 gap 实验。

不建议直接拿它求 2 万 item。

## 4.1 决策变量

示意：

\[
y_b\in\{0,1\}
\]

板 \(b\) 是否启用。

\[
z_{ib}\in\{0,1\}
\]

item \(i\) 是否放入板 \(b\)。

\[
r_i\in\{0,1\}
\]

是否旋转。

\[
(x_i,y_i)
\]

item 左下角。

还需要 pairwise non-overlap 二元变量，或者直接采用 guillotine pattern variables。

## 4.2 基本约束

每个 item 一次：

\[
\sum_b z_{ib}=1.
\]

板启用：

\[
z_{ib}\le y_b.
\]

边界：

\[
x_i+\ell_i(r_i)\le L,
\qquad
y_i+w_i(r_i)\le W.
\]

二维 non-overlap 需用 disjunction / big-M 表达。

## 4.3 三阶段 guillotine

真正困难的是工艺结构。

比赛里更建议不用“任意坐标 + 再判断 guillotine”，而是**直接采用层次 pattern**：

```text
plate
 ├─ stripe
 │   ├─ stack
 │   │   ├─ item
 │   │   └─ item
 │   └─ stack
 └─ stripe
```

只生成合法 `item→stack→stripe→plate` pattern，工艺约束自然成立。

这也是原论文启发式最值得保留的思想。

---

# 5. Q1 actual solver：结构化 constructive heuristic

## 5.1 Step A：生成 stack candidates

把 item 按可共享边分组：

```text
same width
same length after rotation
```

对同边 item 做一维 bin packing，目标不是只生成任意 2-Items，而是尽量形成高填充 stack。

例如同宽 \(w\) 的 item，其高度/长度集合为 \(l_i\)，stack 容量为 \(L\) 或 \(W\)，可以用：

- Best Fit Decreasing；
- First Fit Decreasing；
- 小规模 DP / knapsack。

相比“枚举全部二元组合”，这样：

- 不产生大量互相冲突的候选；
- 每个 item 归属更清楚；
- 更容易保证不重复使用。

## 5.2 Step B：stack → stripe

对 stack 按主尺寸降序。

候选得分可以写成：

\[
score(s\mid r)
=\alpha\frac{a_s}{a_{remain}}
-\beta\frac{waste(s,r)}{A_p}
+\gamma I_{edge-match}.
\]

不要只靠“第一个能放下的”。

## 5.3 Step C：stripe → plate

这是一个一维装箱子问题：

\[
\sum_{s\in b} width_s\le W
\]

或取决于切割方向的相应边。

可以用：

- BFD；
- FFD；
- 多起点随机重启；
- best residual fit。

## 5.4 Step D：local improvement

初解以后做：

```text
move stack between stripes
swap stacks
move stripe between plates
swap stripes
repack two worst plates
rotate candidate
```

特别推荐 **destroy-and-repair**：

1. 找利用率最低的 2–5 块 plate；
2. 将其中 item/stack 拆回候选池；
3. 与附近板一起重新排；
4. 只接受板数下降或利用率提高且板数不变的解。

---

# 6. Q1 与原论文的关系

保留：

- `item → stack → stripe → plate`；
- 大件优先；
- Best-Fit；
- 三阶段工艺直接进入结构。

升级：

- 2-Items 改为显式 stack packing；
- 唯一 item ownership；
- 多起点；
- local repair；
- exact evaluator；
- lower bound。

这样既继承原论文强项，又解决“模型写一套、代码跑另一套”的问题。

---

# 7. Q2 formal model：batch assignment

设订单集合 \(i=1,\dots,n\)，候选批次 \(b=1,\dots,B\)。

\[
x_{ib}=1
\]
表示订单 \(i\) 属于 batch \(b\)。

## 7.1 唯一归属

\[
\sum_b x_{ib}=1.
\]

## 7.2 item 数容量

若订单 \(i\) 有 \(n_i\) 个 item：

\[
\sum_i n_i x_{ib}\le1000.
\]

## 7.3 面积容量

\[
\sum_i A_i x_{ib}\le250\times10^6.
\]

## 7.4 真正的目标

目标不是 similarity，而是：

\[
\min
\sum_b C(B_b),
\]

其中：

\[
C(B_b)
=
\sum_m
PackingCost(items(B_b,m)).
\]

`PackingCost` 就是 Q1 packing oracle。

这才与题目“最少板数”完全一致。

问题是计算太贵，因此 similarity 应只作为 surrogate。

---

# 8. Q2 lower bounds

## 8.1 batch 数硬下界

\[
LB_{batch}
=\max\left(
\left\lceil\frac{N}{1000}\right\rceil,
\left\lceil\frac{A}{250e6}\right\rceil
\right).
\]

每次输出结果必须自动检查：

\[
B\ge LB_{batch}.
\]

这一个 assert 就能立即发现论文 `B2=12` 的问题。

## 8.2 plate 数 material 下界

因为不同材料不能共板：

\[
LB_{mat}
=
\sum_m
\left\lceil\frac{A_m}{LW}\right\rceil.
\]

它忽略 batch fragmentation 与几何约束，因此是乐观下界。

---

# 9. similarity 应怎么设计

原论文的好方向是“共享材料越多越值得合并”。

但建议让指标可解释且归一化。

## 9.1 Jaccard material overlap

\[
S_1(i,j)
=
\frac{|M_i\cap M_j|}{|M_i\cup M_j|}.
\]

## 9.2 shared-item ratio

\[
S_2(i,j)
=
\frac{N_{shared}(i,j)}{N_i+N_j}.
\]

## 9.3 shared-area ratio

比 item 数更贴近板材成本：

\[
S_3(i,j)
=
\frac{A_{shared}(i,j)}{A_i+A_j}.
\]

## 9.4 batch fill bonus

合并后越接近但不超过容量越好：

\[
S_4
= f\left(
\frac{N_i+N_j}{1000},
\frac{A_i+A_j}{250e6}
\right).
\]

最终 surrogate：

\[
S(i,j)=\sum_k w_kS_k.
\]

权重可以：

- 先等权 baseline；
- 用小样本 packing oracle 产生真实 `plate saving`，再回归学习权重；
- 做 sensitivity / ablation。

这比“变异越大就越重要”更贴近最终目标。

---

# 10. 用真实 packing cost 校正 similarity

定义合并收益：

\[
Gain(i,j)
=C(i)+C(j)-C(i\cup j).
\]

若 `Gain > 0`，合并真的节板。

实际不能对所有 pair 都跑 packing oracle，可以两阶段筛选：

```text
所有 pair
  ↓ cheap similarity 取 top-k
候选 pair
  ↓ quick packing estimate
更少候选
  ↓ full packing oracle
选择 best merge
```

这样形成：

> **surrogate → real objective correction**。

这是对原论文 Q2 最值得做的升级。

---

# 11. Q2 constructive batching

推荐流程：

```text
订单特征预计算
  ↓
按“难放订单”排序
  ↓
建立 batch seed
  ↓
在容量可行的候选中
按 similarity / estimated gain 选择
  ↓
填满 batch
  ↓
生成所有批次
```

“难放”可以定义为：

- 面积大；
- item 多；
- 稀有 material 多；
- 大尺寸 item 多。

不要随机选初始订单。

---

# 12. Q2 local search

初始 batching 只是起点。

做：

## move

把 order \(i\) 从 batch A 移到 B。

## swap

交换两个 batch 的订单。

## merge-split

把两个 batch 合起来再重新切成两个。

## material-aware destroy-repair

选择材料碎片最严重的若干 batch，把相关订单抽出重排。

评价：

\[
\Delta C
=
C_{new}-C_{old}.
\]

只需要重算受影响 batch，不必全局重新 packing。

---

# 13. 缓存 packing oracle

Q2 最大计算瓶颈是反复调用 Q1。

应使用 cache：

```python
key = canonical(batch_orders)
if key in cache:
    return cache[key]
```

进一步可以按 `(batch, material)` 缓存。

这样 local search 才能在比赛时间内做大量尝试。

---

# 14. 复杂度应该怎样报告

不要写 `O(nLW)`。

设：

- \(N\)：item 数；
- \(M\)：order 数；
- \(R\)：候选 stack/stripe 数；
- \(I\)：local-search 迭代数；
- \(k\)：每个订单只评估 top-k 候选。

示意：

### stack preprocessing

朴素 pair search：

\[
O(N^2).
\]

若按边长 hash 分组：

\[
O(N\log N)
\]
排序后在组内做 packing，更合理。

### similarity

全 pair：

\[
O(M^2d)
\]

其中 \(d\) 是材料特征比较成本。

用 inverted index / top-k retrieval 可大幅减少。

### local search

\[
O(Ik\cdot C_{oracle}).
\]

同时报告：

- wall-clock；
- peak memory；
- oracle call count；
- cache hit rate。

这才是可复现的算法工程报告。

---

# 15. 验证矩阵

至少做四层验证：

| 层次 | 问题 |
|---|---|
| feasibility | 是否满足所有硬约束 |
| quality | plate count 与 lower bound 差多少 |
| ablation | stack preprocessing / similarity / local search 各贡献多少 |
| robustness | 排序、随机种子、参数变化是否稳定 |

## Q1 ablation

```text
FFD baseline
+ stack preprocessing
+ improved stripe
+ local repair
+ multi-start
```

## Q2 ablation

```text
random feasible batching
material-overlap batching
+ capacity fill
+ packing-cost feedback
+ local search
```

---

# 16. 论文写法建议

正式论文应该明确写：

> “我们首先给出原问题的整数规划/组合优化形式化，用于明确变量、约束和目标。由于实际规模下精确求解不可行，随后根据三阶段切割结构构造 decomposition heuristic。”

这句话能一次解决：

- 为什么有 MIP；
- 为什么没用 MILP solver；
- 为什么启发式合理；
- 为什么不是偷换问题。

---

# 17. 最终推荐架构

```text
raw data
   ↓
validator + statistics
   ↓
lower bounds
   ↓
Q1 packing baseline
   ↓
stack→stripe→plate heuristic
   ↓
local repair / multi-start
   ↓
packing oracle + cache
   ↓
Q2 feasible batching
   ↓
similarity candidate screening
   ↓
packing-cost feedback
   ↓
move/swap/merge-split local search
   ↓
official evaluator
   ↓
result.json
   ↓
paper tables / csv / plots
```

一句话：

> **形式化负责把问题说清楚，结构化启发式负责把大规模实例算出来，lower bound 和 evaluator 负责证明结果值得相信。**
