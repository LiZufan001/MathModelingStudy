# B22106140009｜排样、组批、下界与复现审计

> 目的：把这篇论文当成一次完整的“结果审计训练”。这里不评价文风，只回答四个问题：**结果是否可行、结果离下界多远、正文/代码是否一致、公开附件是否能从原始数据复现。**

---

# 1. 官方硬约束清单

## Q1

- plate：`2440 × 1220 mm`；
- guillotine cut；
- ≤3 stages；
- 同 stage 同方向；
- exact packing；
- 同一 stack 内 item 一条边相同；
- item 不可拼接。

## Q2 新增

- 一个 order 恰好属于一个 batch；
- 同一 plate 只能排同 material；
- 每 batch item 数 ≤1000；
- 每 batch 总面积 ≤250 m²。

任何结果都应先过这些 gate，再讨论利用率。

---

# 2. Q1 原始数据重算

原片面积：

\[
A_p=2440\times1220=2,976,800\ \mathrm{mm}^2.
\]

面积下界：

\[
LB_{area}=\left\lceil A_{tot}/A_p\right\rceil.
\]

| 数据 | item 数 | 总面积 mm² | 面积 LB | 论文板数 | 多于 LB | 论文利用率 | 复算利用率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | 752 | 248,685,614.55 | 84 | 89 | +5 | 93.87% | 93.8666% |
| A2 | 731 | 246,700,070.90 | 83 | 89 | +6 | 93.12% | 93.1171% |
| A3 | 823 | 249,244,736.80 | 84 | 88 | +4 | 95.15% | 95.1467% |
| A4 | 799 | 243,659,621.65 | 82 | 87 | +5 | 94.08% | 94.0838% |

结论：

> **Q1 板数与利用率数值自洽，而且相对最乐观面积下界只多 4–6 张板。**

因为 area LB 忽略工艺约束，所以不能据此证明接近最优，但已经能说明 heuristic 质量很高。

---

# 3. `dataA5`：只能标为数据版本疑点

当前仓库目录还存在 `dataA5.csv`：

- 743 行；
- 总面积约 248.46×10⁶ mm²；
- 纯面积 LB = 84。

论文只处理 A1–A4。

但：

- 原题 DOCX 只写“数据集 A”，没有列出具体文件数；
- 论文和不少当年公开解法都只出现 A1–A4；
- 当前 A5 的 material 字段又与 A1–A4 的结构明显不同。

所以正确处理是：

> **记录 provenance ambiguity，不能仅凭当前仓库存档认定论文漏做正式数据。**

正式复现历史题时，应保存原始下载包 hash / 来源 / 获取日期。

---

# 4. Q2 batch 数硬下界

每批：

\[
N_b\le1000,
\qquad
A_b\le250\times10^6\ \mathrm{mm}^2.
\]

所以：

\[
LB_N=\lceil N/1000\rceil,
\qquad
LB_A=\left\lceil A/(250e6)\right\rceil,
\]

\[
LB_{batch}=\max(LB_N,LB_A).
\]

| 数据 | item 数 | item LB | area LB | 强制 batch LB | 论文 batch |
|---|---:|---:|---:|---:|---:|
| B1 | 26,811 | 27 | 36 | **36** | 42 |
| B2 | 17,952 | 18 | 23 | **23** | **12** |
| B3 | 18,028 | 19 | 24 | **24** | 27 |
| B4 | 18,526 | 19 | 25 | **25** | 30 |
| B5 | 27,901 | 28 | 37 | **37** | 45 |

## A 级问题：B2=12 不可能满足官方容量

仅总面积：

\[
5.73588667548\times10^9 / 250\times10^6
=22.94...
\]

所以至少：

\[
23\text{ batches}.
\]

论文写 12。

这不是“解不够好”，而是：

> **若 12 是真实最终 batch 数，则方案不满足硬约束。**

目前无法从公开论文判断到底是表格笔误还是程序/附件版本问题，因此不能进一步断言。

正式比赛的最简单防线：

```python
assert batch_count >= ceil(total_area / MAX_BATCH_AREA)
assert all(batch.area <= MAX_BATCH_AREA)
assert all(batch.items <= MAX_BATCH_ITEMS)
```

---

# 5. Q2 plate 数与利用率复算

| 数据 | 总面积 mm² | 论文板数 | 论文利用率 | 原始数据复算 |
|---|---:|---:|---:|---:|
| B1 | 8,865,813,008.70 | 3462 | 86.03% | 86.0284% |
| B2 | 5,735,886,675.48 | 2270 | 84.88% | 84.8838% |
| B3 | 5,756,364,099.05 | 2298 | 84.15% | 84.1489% |
| B4 | 6,043,317,596.05 | 2392 | 84.87% | 84.8720% |
| B5 | 9,197,386,844.75 | 3733 | 82.77% | 82.7669% |

说明：

> 论文的 `total area / plate_count / utilization` 三个量彼此一致。

因此 B2 问题集中在 batch 约束/批次数，不是利用率算术错误。

---

# 6. 按 material 的 plate lower bound

Q2 要求不同材料不能共板。

因此：

\[
LB_{mat}=\sum_m\left\lceil\frac{A_m}{A_p}\right\rceil.
\]

| 数据 | area LB | material LB | 论文板数 | 比 material LB 多 |
|---|---:|---:|---:|---:|
| B1 | 2979 | 3051 | 3462 | 411 |
| B2 | 1927 | 2006 | 2270 | 264 |
| B3 | 1934 | 2026 | 2298 | 272 |
| B4 | 2031 | 2108 | 2392 | 284 |
| B5 | 3090 | 3193 | 3733 | 540 |

若只看 material LB 对应的理论利用率上限：

| 数据 | material-LB utilization upper bound | 论文利用率 |
|---|---:|---:|
| B1 | 97.62% | 86.03% |
| B2 | 96.06% | 84.88% |
| B3 | 95.45% | 84.15% |
| B4 | 96.31% | 84.87% |
| B5 | 96.76% | 82.77% |

不能把二者差值叫“最优性 gap”，因为 LB 没考虑：

- batch fragmentation；
- 三阶段；
- guillotine；
- geometry。

正确说法：

> **仍存在约 8–14 个百分点的“相对乐观下界空间”，其中有一部分是不可避免的结构损失。**

---

# 7. Q1 formal MIP 审计

论文 Q1 主要给出：

\[
\sum l_j\le L,
\qquad
\sum w_j\le W,
\]

以及余料限制。

缺失：

- plate assignment；
- binary plate use；
- coordinates；
- orientation；
- non-overlap；
- item demand satisfaction；
- guillotine cut tree；
- stage constraints。

结论：

> **不足以构成完整可执行二维三阶段 MIP。**

论文实际有效的求解器是后续启发式。

---

# 8. Q2 formal MIP 审计

Q2 给出了：

\[
\sum_b x_{ib}=1,
\]

\[
\sum_i n_i x_{ib}\le1000,
\]

\[
\sum_i A_i x_{ib}\le250e6.
\]

这部分作为 assignment constraints 是合理的。

但目标中使用总 plate 数 \(K\)，却没有变量/约束把：

```text
x_ib
  ↓
batch composition
  ↓
material-specific packing
  ↓
K
```

连接起来。

所以仍不是一个 integrated MIP。

更准确：

> **批次分配形式化 + packing heuristic oracle。**

---

# 9. 2240 / 2440 审计

官方：

\[
L=2440.
\]

论文 p.9 数据检查写“2240”，部分 MATLAB 注释也写“接近2240”。

但实际代码：

```python
L = 2440
```

以及：

```matlab
while(length < 2440)
```

利用率也是：

```matlab
sum(a)/(p*2440*1220)
```

所以：

> **属于文字/注释错误；现有证据反而显示实际求解按 2440。**

不要把它夸大成算法使用错误尺寸。

---

# 10. stripe count 版本冲突

同一章：

- 正文：A1 生成 **166** stripe；
- 表 4-1：A1 = **229** stripe；
- 后文再次说 **166**。

这是明确的结果同步问题。

比赛风险：

> 中间实验版本更新了结果表，但文字没同步，或反之。

---

# 11. 原始数据统计与论文表不一致

## B2 order count

论文表 6-1：

\[
381.
\]

原始 CSV unique order：

\[
403.
\]

B4 恰好也是 381，因此很像复制/粘贴错误。

## B1 material count

论文正文：48 种。  
原始 CSV：130 种。  
附录 similarity 代码：

```python
for i in range(1, 131):
```

也对应 130。

所以“48”明显不是当前原始数据的实际材料种数。

---

# 12. 附录 5：order 数据类型导致不能直接运行

CSV：

```text
item_order = order539, order317, ...
```

Pandas dtype：字符串。

代码：

```python
for i in range(1, len(set(data[:,4])) + 1):
    index = np.where(data[:,4] == i)
```

即字符串与整数比较。

当前所有 B 文件中，订单列都不存在与整数 `1..N` 直接相等的值。

所以：

> **公开代码缺少 `orderXXX → XXX` 的预处理，按字面无法构造正确 `order_list`。**

可能比赛实际代码有未附出的处理；这里只审计公开附件。

---

# 13. similarity 正文/代码审计

正文得到权重：

\[
0.4780,\quad0.4955,\quad0.0265.
\]

舍弃第三项后写：

\[
Similarity
=0.4780\frac{k_{ij}}k
+0.4955\frac{Y}{X_i+X_i}.
\]

其中 `Xi+Xi` 从上下文看很可能应为：

\[
X_i+X_j.
\]

代码则：

```python
similarity2 = num2 / len(all_material)
similarity1 = num / (len(group1[1]) + len(group2[1]))
s = (similarity1 + similarity2) * 0.5
```

区别：

1. 权重从 0.4780/0.4955 变成 0.5/0.5；
2. 正文两项权重删除 M3 后没有重新归一化；
3. 代码额外要求：

```python
similarity > 0.5
```

而正文算法描述是“从最高到次高尝试可行 merge”，没有论证 0.5 阈值。

因此最终实际相似度规则以公开代码和论文文字无法唯一确定。

---

# 14. capacity `<` vs `≤`

官方：

\[
N_b\le1000,
\qquad A_b\le250e6.
\]

代码：

```python
if num < 1000 and square < item_square:
```

合法边界解被人为排除。

这不是 feasibility 错误，而是**保守缩小可行域**，可能导致多 batch。

---

# 15. Improved-Stripe 代码审计

注释：

> “没有与之相等的，就找下一个长度最长的。”

代码：

```matlab
m = 1220-all_width;
[~, next_ind] = max(all_data(:,3) < m);
```

`all_data(:,3)<m` 是逻辑向量。

`max(logical_vector)` 返回最大逻辑值 1 及其**第一个出现位置**，并不是显式：

\[
\arg\max\{length_i: width_i<m\}.
\]

因为数组前面曾做排序，实际结果可能依赖这种排序而仍接近预期，但代码与注释的语义不是严格等价。

正式写法应该明确：

```matlab
feasible = find(all_data(:,3) <= m);
[~, k] = max(all_data(feasible,2));
next_ind = feasible(k);
```

---

# 16. complexity 审计

论文 Q1：

\[
O(nLW).
\]

Q2：

\[
O(nLWK).
\]

问题：L/W 是几何/数据长度量，不是清晰的循环规模。

## Q1 2-Items

若每个 item 与其他 item 比较：

\[
O(N^2).
\]

若先按边长 hash/sort，可降到更合理结构。

## Q2 similarity merging

公开代码每一轮：

```python
for i in orders:
    for j in later_orders:
        similarity(i,j)
```

是：

\[
O(M^2)
\]

pair comparisons。

合并后反复重算，朴素总量可能达到接近：

\[
O(M^3)
\]

的上界量级，再乘 similarity 内的材料检查成本。

因此“线性阶”结论不能从公开实现得到。

---

# 17. 审计结论分级

## A 级：会影响方案成立

- `B2=12` 与 batch 面积硬下界 23 矛盾；
- Q1/Q2 所谓 MIP 不是完整可求解原问题模型；
- 附录 5 原始 order 字符串与整数比较，不能直接复现 batching。

## B 级：影响方法复现/解释

- similarity 权重正文与代码不一致；
- `>0.5` threshold 未在正文论证；
- `<` 缩小官方 `≤` 可行域；
- Improved-Stripe “longest” 注释与实现不完全一致；
- complexity 推导与代码结构不对应。

## C 级：明显版本/文字同步问题

- 2240 vs 2440；
- A1 stripe 166 vs 229；
- B2 order 381 vs raw 403；
- B1 material 48 vs raw/code 130；
- similarity 分母 `Xi+Xi` 疑似笔误。

---

# 18. 赛前审计模板

以后我们自己的优化题提交前，必须程序自动打印：

```text
INPUT CHECK
- n_items
- n_orders
- n_materials
- total_area

LOWER BOUNDS
- plate_area_lb
- material_lb
- batch_item_lb
- batch_area_lb

FEASIBILITY
- all_items_once
- overlap = 0
- boundary_violation = 0
- stage_violation = 0
- order_split = 0
- max_batch_items <= limit
- max_batch_area <= limit

QUALITY
- plates
- utilization
- plates / lower_bound

REPRODUCIBILITY
- seed
- runtime
- git commit
- data hash
```

最后一句：

> **一个高利用率结果，若没有 hard-constraint audit 和 lower bound，只能说明“看起来不错”；不能说明它是一个可信的竞赛答案。**
