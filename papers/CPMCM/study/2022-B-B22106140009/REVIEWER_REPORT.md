# B22106140009｜指导老师 / 评审老师报告

> 本文件不是赛事官方评语，而是基于原题、论文全文、公开附录代码和仓库原始 CSV 进行的二次评审训练。

---

# 一、第一页后的 60 秒判断

如果我是评审老师，摘要读完会给出一个偏正面的初判：

> **作者明显理解了三阶段排样的结构，没有把上万矩形件直接扔给通用元启发式；Q1/Q2 也形成了可复用的工程链条，值得继续读。**

吸引点：

1. `item → stack → stripe → plate` 有明显题目针对性；
2. 2-Items 前处理不是装饰，而是在缩小搜索空间；
3. Q2 没有重新发明排样算法，而是复用 Q1；
4. similarity 与材料碎片化有工程解释；
5. 给出完整坐标方案、板数、利用率和代码；
6. Q1 利用率达到 93%–95%，肉眼看很强。

但读到公式、表格和附录后，我会把论文定位为：

> **“启发式设计强于数学形式化，工程结果强于验证闭环。”**

---

# 二、指导老师最值得表扬的 8 点

## 1. 看到了“切割阶段”是结构，而不是普通约束

把三阶段直接变成：

```text
item → stack → stripe → plate
```

这是正确的结构化建模意识。

## 2. 会先做 preprocessing

大量同边矩形意味着有天然局部组合结构。

先组合再排，比在原始 item 空间直接搜索更高效。

## 3. 不迷信精确求解

这种规模若真的构建完整二维 MIP，变量/约束会非常巨大。

作者实际使用 constructive heuristic，是合理的竞赛工程选择。

## 4. Q1 结果有下界意义上的含金量

重新计算后，A1–A4 只比纯面积下界多 4–6 张板。

即使这个下界很乐观，也足以说明方法不只是“跑出了一个能看的图”。

## 5. Q2 抓住材料碎片化

组批真正影响后续板数的核心之一，就是同 material 是否被 batch boundary 切碎。

用 shared material 做 similarity 有业务因果。

## 6. Q1 能变成 Q2 的 oracle

这是一种很好的模块复用：

```text
batching 决策
    ↓
packing evaluation
```

## 7. 输出不是停在“最优值”

最终给坐标和版式，符合工程题交付要求。

## 8. 运行时间意识强

即使复杂度理论写得不好，作者确实关心算法能否在比赛环境下快速跑完大数据。

---

# 三、评审老师最可能扣分的 A 级问题

## A1. Q1 所谓 MIP 不能表达二维三阶段排样

论文缺：

- assignment；
- non-overlap；
- orientation；
- plate use；
- guillotine tree；
- stage structure。

如果答辩时说“我们建立了完整 MIP 并求解”，我会追问：

> “请指出哪个变量表示 item 在哪块板、哪个约束保证两个矩形不重叠、哪个约束保证 3-stage guillotine？”

现有论文无法回答。

更好的答辩表述：

> “我们用整数规划形式化目标和部分资源约束；实际大规模求解采用针对工艺结构的 decomposition heuristic。”

## A2. Q2 的目标 K 与 assignment 没有连接

Q2 写利用率：

\[
E=\frac{\sum_iS_i}{KLW}.
\]

但没有模型把 \(x_{ib}\) 与 \(K\) 联系起来。

所以 formal model 并不能决定板数。

## A3. B2=12 批违反下界

这是最严重的结果问题。

原始数据：

\[
A_{B2}=5.7359\times10^9\text{ mm}^2.
\]

每批 ≤250e6，所以至少：

\[
23\text{ 批}.
\]

论文：12。

答辩追问会非常直接：

> “12 个批次平均每批面积约 478 m²，怎么满足 250 m² 上限？”

这必须有附件/勘误才能解释。

## A4. 公开组批代码从原始 CSV 无法直接复现

原始订单号是 `order539`，代码却与整数 `539`/`1...N` 比较。

如果没有未附的转换步骤，order grouping 为空。

---

# 四、B 级问题：不会直接否定论文，但降低可信度

## B1. similarity 规则三个版本

正文权重：

\[
0.4780/0.4955.
\]

代码：

\[
0.5/0.5.
\]

代码还多：

\[
Similarity>0.5.
\]

评委会问：

> “最终提交结果到底由哪一个版本产生？”

## B2. 变异系数权重不等于“对板数的重要性”

变异系数大，只说明数据分散，不等于该特征对 downstream packing cost 更重要。

更好的方法是：

- 小样本真实 packing gain；
- 回归/消融学习权重；
- sensitivity。

## B3. `≤` 被代码写成 `<`

损失一部分边界可行解。

## B4. Improved-Stripe 注释与实现不严格对应

“最长可行”实际是逻辑向量第一个 true，依赖隐含排序。

## B5. complexity 不是从代码循环推导

`O(nLW)`、`O(nLWK)` 缺乏标准算法含义。

---

# 五、C 级问题：赛末版本管理不足

- 2240 / 2440；
- A1 stripe：166 / 229；
- B2 order：381 / raw 403；
- B1 material：48 / raw 130；
- similarity denominator：`Xi+Xi` 疑似应为 `Xi+Xj`。

单个问题未必影响算法，但集中出现会让评委怀疑：

> **结果表、正文、代码是否来自同一个 final run？**

---

# 六、为什么这些问题没有掩盖论文的优点

因为评委还会看到一件很重要的事实：

> **Q1 的实际方案确实强。**

A1–A4：

```text
面积下界：84,83,84,82
论文板数：89,89,88,87
```

这比只写一套漂亮公式更有工程价值。

同时，Q2 的 plate count 与 total area 所算利用率是自洽的。

所以这篇不是“结果都是错的”，而是：

> **某些硬约束/复现信息没有被论文可靠证明。**

这种区分非常重要。

---

# 七、如果我是指导老师，赛中会设置哪些强制门槛

## Gate 1：模型—算法关系

学生必须能回答：

```text
formal model 是什么？
实际 solver 解的是不是同一个模型？
若不是，为什么 decomposition 合理？
```

## Gate 2：lower bound

每个实例必须自动报告：

```text
area LB
material LB
batch count LB
```

## Gate 3：feasibility

任何结果表生成前：

```python
assert feasible
```

## Gate 4：单一结果源

`results.json` 自动生成：

- 摘要数字；
- 正文表格；
- CSV；
- 图标题。

不允许人工重复抄数。

## Gate 5：原始数据直接运行

仓库 README 中应能：

```text
raw CSV
  ↓ one command
final result
```

不能依赖未写明的 Excel 手工改列。

---

# 八、12 个模拟答辩追问

## 1. 你们为什么称式 (3-2)–(3-4) 为混合整数规划？整数决策变量在哪里？

理想回答：承认 formal formulation 简化，实际核心是结构化 heuristic；补充完整理论模型。

## 2. 怎么保证 item 不重叠？

应指向 packing data structure / exact evaluator，而不是“从图上看没有重叠”。

## 3. 怎么证明生成方案一定 ≤3 stages？

应给出切割树结构证明。

## 4. 为什么只组合 2-Items，而不是直接生成更大的 stack？

应说明候选规模与质量折中，并用 ablation 支撑。

## 5. A1 的 89 张板好到什么程度？

应回答：area LB=84，因此 ≤5 张的绝对剩余空间，但不能叫 5 张最优性 gap。

## 6. 为什么 similarity 的权重由变异系数决定？

应说明这是 surrogate，并最好有 downstream plate-saving 验证。

## 7. 删除 M3 后为什么不重新归一化权重？

应解释或改成归一化。

## 8. 代码为什么是 0.5/0.5，而正文是 0.4780/0.4955？

必须说明 final version。

## 9. B2 12 批如何满足 250 m²/批？

这是必须能现场拿附件证明的问题。

## 10. B1 到底是 48 还是 130 种材料？

应由数据统计脚本给唯一答案。

## 11. 复杂度为什么是 O(nLW)？L/W 是矩形尺寸还是数据规模？

应重新按实际循环推导。

## 12. 如果 similarity 很高，但合并后 packing 反而多用板怎么办？

最佳回答：similarity 只是 candidate screening，最终由 packing oracle / local search 决定。

---

# 九、如果今天重新参赛，我会如何把它提升一档

保留原论文核心：

```text
stack→stripe→plate
material-aware batching
```

增加：

```text
area/material/batch lower bound
exact feasibility checker
BFD / multi-start baseline
packing oracle cache
batch move/swap/merge-split
real packing gain feedback
ablation
single-source result generation
```

然后论文叙事改为：

> **“完整组合优化形式化 → 规模分析证明精确求解困难 → 利用三阶段结构进行分解 → 快速启发式求可行解 → 下界与小规模精确解评价质量 → 局部搜索继续改进。”**

这会比“我们建立 MIP + 提出 heuristic”更加严谨。

---

# 十、评审结论

若只看**思路与竞赛工程价值**：高。  
若看**Q1 实际结果质量**：高。  
若看**完整 MIP 严谨性**：偏弱。  
若看**Q2 硬约束证明**：存在 A 级风险。  
若看**公开代码可复现性**：偏弱。  
若看**可迁移训练价值**：很高。

最值得指导学生记住的不是某个 similarity 公式，而是：

> **大规模组合优化可以大胆用结构化启发式，但越是近似算法，越要用 lower bound、feasibility checker 和真实目标反馈把可信度补回来。**
