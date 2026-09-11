# 2025 A题 A2 算法来源与身份指纹降权追查

> 更新时间：2026-09-11  
> 对象：匿名候选 `A题-2-通用神经网络处理器下的核内调度问题.pdf`  
> SHA256：`d26284fb65c7c9cbdf6bae4a71dc1e9066bd95506184ae411918bc05f597ac22`  
> **目的：区分“公开已有算法家族”与“可能具有队伍身份价值的比赛特化结构”。本页不改变 `C / F+ / M`。**

## 1. 结论先行

A2 中两个最醒目的缩写：

- `ABQPSO`
- `DPEA`

都不能再作为强队伍身份指纹。

当前真正值得用于反绑定队伍的重点，应进一步收缩到：

> **NPU 问题特化的四段编码 `[seq|alloc|spill|offset]` + Repair `R1–R5` + `domain_greedy_results.txt` + 与这些结构直接对应的代码 / 专利 / 原 PDF。**

---

## 2. `ABQPSO`：公开已有同名算法，单词级指纹降权

2024 年 `Swarm and Evolutionary Computation` 已发表：

> Xiaotong Li, Wei Fang, Shuwei Zhu, Xin Zhang,  
> *An adaptive binary quantum-behaved particle swarm optimization algorithm for the multidimensional knapsack problem*  
> DOI: `10.1016/j.swevo.2024.101494`

公开来源：

- https://www.sciencedirect.com/science/article/pii/S2210650224000270
- https://dblp.org/rec/journals/swevo/LiFZZ24
- 江南大学方伟教师主页也列出该成果：
  https://ai.jiangnan.edu.cn/info/1008/2053.htm

公开摘要明确包含：

- adaptive BQPSO；
- adaptive repair operator；
- local search；
- local sparseness / diversity mechanism。

因此 A2 中单独出现：

- `ABQPSO`；
- adaptive repair；
- local search；
- diversity / niching；

都不足以识别参赛队。

### 2.1 A2 又并非简单逐字复现这篇 2024 ABQPSO

2024 ABQPSO 的公开描述强调：

- 连续粒子位置；
- 根据粒子平均位置将连续值映射为离散值；
- 面向 multidimensional knapsack problem 的 pseudo-utility repair。

而 A2 深读记录的是：

- `[seq|alloc|spill|offset]` 四段混合编码；
- 量子旋转 / 测量式更新；
- 针对 NPU 缓存、SPILL、地址、时序约束的五层 Repair `R1–R5`。

因此目前不能声称“A2 直接照搬 2024 ABQPSO”；只能确认：

> **ABQPSO 这个算法名称和 repair/local-search/diversity 组合本身已经是公开算法知识，身份唯一性很弱。**

---

## 3. `DPEA`：2022 年已有正式同名 Dual-Population Evolutionary Algorithm

IEEE Transactions on Intelligent Transportation Systems 2022（DOI 在线记录为 2021）：

> Chao Wang, Ziqiong Wang, Ye Tian, Xingyi Zhang, Jianhua Xiao,  
> *A Dual-Population Based Evolutionary Algorithm for Multi-Objective Location Problem Under Uncertainty of Facilities*  
> IEEE T-ITS 23(7): 7692–7707  
> DOI: `10.1109/TITS.2021.3071786`

来源：

- https://dblp.org/rec/journals/tits/0039W00X22.html
- https://www.researchgate.net/publication/351000446_A_Dual-Population_Based_Evolutionary_Algorithm_for_Multi-Objective_Location_Problem_Under_Uncertainty_of_Facilities

该文直接把算法命名为：

> **DPEA — Dual-Population Based Evolutionary Algorithm**

公开全文参数段还明确显示：

- 双种群协同进化；
- 两个种群之间存在信息交互；
- 使用 Simulated Binary Crossover (`SBX`)；
- 使用 Polynomial Mutation (`PM`)。

因此 A2 Q3 中：

- `DPEA`；
- dual population；
- `SBX`；
- polynomial mutation；

同样不能作为某个 2025 国一队的独特身份签名。

### 3.1 但 A2 也不能直接等同于 2022 DPEA

A2 当前审读的 Q3：

- convergence population；
- exploration population；
- external archive；
- Latin hypercube initialization；
- cooperative crossover；
- differentiated environmental selection。

2022 DPEA 的公开结构则针对 facility location：

- 两个种群分别处理 location / radius 决策；
- 两个种群交换 elite information；
- radius population 使用 SBX / PM。

所以目前正确表述是：

> **`DPEA + SBX + PM` 属于公开已有算法家族，不是身份指纹；但尚无证据证明 A2 就是直接基于上述 2022 DPEA 改写。**

---

## 4. 对郑州大学候选的影响：需要降一点“DPEA 加成”

此前郑州大学 `A25104590082`（李功平 / 张丽娜 / 杨龙）之所以被提高优先级，一个原因是李功平所在梁静优化网络在比赛前已有 dual-population constrained multi-objective evolutionary algorithm（DPCPRA）积累。

现在发现 `DPEA` 本身和 `SBX + PM` 在更早公开文献中就已存在后，应修正：

- 郑大团队的“双种群算法研究背景”依旧是真实正向证据；
- 但它只能说明技术生态相容；
- **不能因为 A2 也用了 DPEA / dual population / SBX / PM，就把郑大看成机制级强匹配。**

因此郑大继续保留在 A2 第一梯队候选池，但其身份权重应更多依赖：

- 李功平真实的调度 / 多目标优化研究背景；
- 未来是否出现 NPU / cache / spill / address allocation 特化成果；
- 是否命中 A2 Q2 的四段编码与 Repair 结构。

---

## 5. Q2 独特组合公开反查：目前没有命中新的 A2 队伍

本轮继续检索组合：

- `sequence / allocation / spill / offset`
- `ABQPSO + NPU`
- `quantum particle swarm + cache + spill`
- `Repair R1–R5 + NPU`
- `domain_greedy_results.txt`

目前没有找到能够绑定上海交通大学、郑州大学、合肥工业大学、北京理工大学等 A2 高优先级候选队的公开成果。

当前公开网络中高度命中：

> `NPU + SIMD + buffer address offset + SPILL + cache allocation`

的赛后专利，仍然是贵州大学 A3 已知链：

- `CN121901120A/B`《多级缓存架构下缓冲区地址分配与 SPILL 调度方法》
- 申请日：2026-03-26
- 发明人包括：李晖、田旭、覃国忠、杨通宇等。

来源：

- https://eureka.patsnap.com/patent/CN121901120A
- https://k-knowledge.kr/srch/read.jsp?id=285735547

这反过来强化了一个方法论判断：

> **如果 A2 对应队伍未来真的公开了赛后专利/论文，最值得寻找的是这种“题目对象 + 地址 / SPILL / cache + 特化求解结构”级别的复现，而不是泛泛的 PSO / tabu / multiobjective 关键词。**

---

## 6. 当前身份指纹权重建议

### 低权重：不要靠这些认队

- `ABQPSO`
- adaptive repair
- local search
- diversity / niching
- `DPEA`
- dual population
- `SBX`
- polynomial mutation
- tabu search
- Pareto optimization

### 中权重：需要组合出现

- quantum rotation / measurement 与 NPU cache allocation 同现
- convergence / exploration 双种群 + external archive
- spill-aware local search
- 多种缓存类型地址编码

### 高权重：优先追

- `[seq|alloc|spill|offset]` 同构四段编码
- Repair `R1–R5` 的约束职责逐层一致
- `domain_greedy_results.txt`
- A2 六个算例的 Q2/Q3 精确结果向量
- 同样的公式变量 / 约束编号组织
- 比赛代码 / 软件著作权 / 赛后专利复现
- 最终带 `A25...` 队号的原始 PDF 封面

---

## 7. 当前结论

1. **A2 仍保持 `C`。**
2. **没有新增正式 `M` 或 `F+`。**
3. `ABQPSO` 与 `DPEA` 两个醒目缩写均已被证明存在比赛前公开算法先例，因此身份权重应显著下调。
4. 郑大、上交、合工大、北理工等候选队仍可继续追，但不能再主要依赖“是否有 PSO / 双种群 / 多目标背景”排序。
5. 下一次真正能够显著提高置信度的证据，应来自 A2 的 **Q2 NPU 特化结构、文件残留、精确数值、参考文献来源链或原始封面 PDF**。