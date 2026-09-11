# 2025 A题 A1 / A2 方法指纹追查

> 更新时间：2026-09-11  
> 用途：记录匿名 A1 / A2 全文与公开人员、论文、专利、代码之间的反向身份线索。  
> **本页不改变正式全文统计，也不把研究假设升级为 `F+` / `M`。**

## 0. 验真边界

正式 `M` 仍严格要求：拿到实际完整 PDF，且 PDF 首页/封面保留真实参赛编号；参赛编号、队员、学校必须与官方全国一等奖名单 exact match。

官方一等奖白名单见：[`../_research/official_awards/FIRST_PRIZE_2024_2025.csv`](../_research/official_awards/FIRST_PRIZE_2024_2025.csv)。

当前正式 `M` 总量不变；本页只用于缩小 A1 / A2 的身份搜索空间。

---

## 1. A2：重新定义高价值指纹

匿名候选：

- `A题-2-通用神经网络处理器下的核内调度问题.pdf`
- 98 页
- SHA256：`d26284fb65c7c9cbdf6bae4a71dc1e9066bd95506184ae411918bc05f597ac22`

已审读的方法链：

- Q1：优先规则贪心 + 禁忌搜索；`swap / insert / reverse` 邻域；结果写入 `domain_greedy_results.txt` 供 Q2 读取。
- Q2：`ABQPSO` 四段编码 `[seq|alloc|spill|offset]`；量子旋转；自适应参数；罚函数；五层 Repair `R1–R5`；局部搜索；niching。
- Q3：F / T 双目标；拉丁超立方初始化；`DPEA` 收敛/探索双种群；外部存档；协同交叉；SBX + 多项式变异；差异化环境选择。

### 1.1 `ABQPSO` 单独降权

2024 年 `Swarm and Evolutionary Computation` 已发表：

> Xiaotong Li, Wei Fang, Shuwei Zhu, Xin Zhang,  
> *An adaptive binary quantum-behaved particle swarm optimization algorithm for the multidimensional knapsack problem*.

公开摘要中的算法本身已经包含：

- adaptive binary QPSO；
- adaptive repair；
- local search；
- diversity / local sparseness 机制。

来源：

- <https://www.sciencedirect.com/science/article/pii/S2210650223001920>

因此：

> **`ABQPSO` 以及“自适应修复 + 局部搜索 + 多样性”不能继续作为队伍身份的强唯一指纹。**

更有辨识度的 A2 组合应改为：

> `[seq|alloc|spill|offset]` 四段编码 + Repair `R1–R5` + `domain_greedy_results.txt` + Q3 的具体双种群结构。

---

## 2. A2 ↔ 郑州大学 `A25104590082`：新增优先研究假设

官方全国一等奖队：

- 参赛编号：`A25104590082`
- 郑州大学
- 李功平 / 张丽娜 / 杨龙

### 2.1 官方赛后复盘：李功平主攻算法，第三问确实是最大计算瓶颈

郑州大学党委研究生工作部 2026-04-13 官方报道明确：

- 三人选择 2025 A题“通用神经网络处理器核内调度”；
- 李功平认为赛题贴合自己的研究方向；
- 李功平主攻算法实现；
- 第三问面对超大规模数据集，优化算法在服务器运行很久仍无结果；
- 团队先简化算法保证完整解，再逐步优化。

来源：

- <https://www5.zzu.edu.cn/ygb/info/1087/10472.htm>

这与 A2“Q3 使用群体进化搜索、计算开销明显更大”的形态相容，但**仅属于行为/技术栈一致性证据，不足以绑定论文。**

### 2.2 李功平与梁静优化团队存在直接导师关系

郑州大学机械与动力工程学院 2023 年博士招生公示：

- 李功平
- 专业：机械
- 方向：高端智能装备设计与制造
- 指导教师：**梁静**

来源：

- <https://www5.zzu.edu.cn/mech/info/1055/2614.htm>

梁静郑州大学官方主页公开研究方向：

- 进化计算
- 群集智能
- 机器学习
- 集成学习

并长期参与智能仿真优化与调度方向。

来源：

- <https://www5.zzu.edu.cn/eie/info/1065/2406.htm>

### 2.3 李功平本人已有“调度 + 多目标优化”公开研究痕迹

公开专利能够把李功平直接放进梁静 / 岳彩通 / 于坤杰优化网络：

1. `CN114529223A`《一种解决通用约束的城轨交通司机排班问题的方法》
   - 发明人包含：梁静、冯登攀、**李功平**、岳彩通、于坤杰等。
   - <https://patents.google.com/patent/CN114529223A/zh>
2. `CN114757044A/B`《一种多模态多目标的路径规划算法/方法》
   - 发明人包含：梁静、岳彩通、常亚鑫、**李功平**、于坤杰等。
   - <https://patents.google.com/patent/CN114757044A/zh>

此外，第二届全国博士后创新创业大赛“知人善用-人员调度智能化”项目团队名单中同时出现：岳彩通、梁静、于坤杰、毕莹、于明渊、**李功平**、乔康加、随旭东。

这说明李功平在比赛前就有明确的**调度优化 / 进化优化 / 多目标优化**技术背景，而不是比赛时临时接触这一类方法。

### 2.4 梁静团队比赛前已有“双种群进化”技术积累

2024 年 `Expert Systems with Applications`：

> Kangjia Qiao, Zhaolin Chen, Boyang Qu, Kunjie Yu, Caitong Yue, Ke Chen, Jing Liang,  
> *A dual-population evolutionary algorithm based on dynamic constraint processing and resources allocation for constrained multi-objective optimization problems*.

论文提出双种群算法 `DPCPRA`：

- main population / auxiliary population；
- dynamic constraint processing mechanism；
- dynamic resource allocation scheme；
- constrained multi-objective optimization。

来源：

- <https://www.sciencedirect.com/science/article/pii/S0957417423022091>

2026 年同一研究网络又公开：

> Caitong Yue, Wenhao Ye, Jing Liang, Mengmeng Li, Kunjie Yu, Ying Bi, Boyang Qu,  
> *A Robustness Indicator-Based Dual-Population Evolutionary Algorithm for Multimodal Multiobjective Optimization*.

该文算法名为 `GLR-MMEA`，同样采用双种群，但**不是 A2 的 `DPEA`**。

来源：

- DOI `10.1109/TSMC.2026.3662059`
- <https://dblp.org/rec/journals/tsmc/YueYLLYBQ26.html>

### 2.5 对照后为什么仍不能升级

A2 Q3 当前审读得到的结构：

- convergence / exploration 双种群；
- 外部存档；
- 拉丁超立方初始化；
- 双种群协同交叉；
- SBX + polynomial mutation；
- 差异化环境选择。

郑大既有 `DPCPRA` 的核心则是：

- main / auxiliary 双种群；
- 两种不同约束处理职责；
- dynamic constraint processing；
- dynamic resource allocation。

二者确实共享“双种群约束多目标进化”的技术母体，但机制并非逐项复现；而 SBX + polynomial mutation 在双种群多目标算法中也属于常见算子。

因此当前最严格、最合理的结论是：

> **`A2 ↔ A25104590082`（郑州大学）是目前值得提高优先级的研究假设，但仍没有独特算法名、代码、题名、专利或封面队号形成直接绑定。继续保持 A2 原状态 `C`，不升级 `F+`。**

---

## 3. A1：`Chaitin + graph coloring + spill` 单独同样应降权

A1 当前主要指纹：

- Q1 拓扑合法邻域模拟退火；
- Q2 Chaitin 图着色；
- ILP / rounding；
- Spill；
- Q3 MILP / 搬运量上界约束下执行时间优化。

但“Chaitin graph coloring + spill”本身是经典编译器寄存器分配技术链，至少从 1980 年代已经公开：

- IBM / G. J. Chaitin：*Register allocation & spilling via graph coloring*。
  <https://research.ibm.com/publications/register-allocation-andamp-spilling-via-graph-coloring>
- US4571678A：*Register allocation and spilling via graph coloring*。
  <https://patents.google.com/patent/US4571678A/en>

因此：

> **不能因为某支国一队或实验室公开资料出现 graph coloring / register allocation / spill 就认定为 A1。**

A1 后续应优先寻找更窄的组合指纹：

- 同一公开成果同时出现 `Chaitin + ILP/Rounding + spill + NPU/cache allocation`；
- 与 A1 六个 case 的具体数值结果一致；
- 代码中出现同样的模型变量、约束组织或文件名；
- 赛后专利/论文复现 A1 特有的分层求解结构。

---

## 4. 西安电子科技大学队：新增作品描述，但暂不能绑定 A1/A2

官方一等奖白名单中的西电 A题队：

- `A25107010062`
- 万昊 / 聂耀 / 李九辉

公开报道中，聂耀把团队作品描述为：

> **“面向 SIMD 架构 NPU 的核内调度时空联合优化”**

目前尚未找到该队公开论文、代码或足够细的算法链，因此这条标题级线索暂时不能与 A1/A2 绑定。

后续若发现“时空联合优化”对应的公开论文 / 专利 / GitHub，应重新比较 A1/A2 的：调度顺序、缓存地址、SPILL 与执行时间联合优化结构。

---

## 5. 下一轮优先级

### P0：郑州大学 A2 假设做“独特机制”验证

重点搜索：

- `李功平 + NPU / SIMD / 核内调度 / cache / spill`
- `李功平 + DPEA / dual-population / 双种群`
- 梁静 / 岳彩通 / 于坤杰团队 2025-09 之后的专利、论文、软件著作权、项目页
- 是否出现 A2 特有：`[seq|alloc|spill|offset]`、Repair `R1–R5`、`domain_greedy_results.txt`

只有出现这些**罕见组合**之一，才值得进一步提升身份置信度。

### P1：若重新取得 A2 PDF，优先核参考文献

重点确认 A2 是否引用：

- 2024 ABQPSO 原论文；
- 郑州大学梁静团队 DPCPRA / 其他双种群论文；
- PlatEMO / SBX / polynomial mutation 等来源。

参考文献不能证明身份，但可以判定 A2 的算法来源链，避免把公开已有算法误当队伍原创指纹。

### P2：A1 改查“组合结构”而非单词

停止单搜：

- `Chaitin`
- `graph coloring`
- `spill`

改为：

- NPU + register allocation + ILP/randomized rounding + spill；
- 六个 case 结果数值；
- 分层 ILP / rounding 的特定公式或变量；
- 赛后专利/论文中的同构模型。

### P3：继续追封面原 PDF

无论任何方法指纹多强，最终 `M` 仍只接受：

> **原始完整 PDF 封面参赛编号 ↔ 官方全国一等奖队伍 exact match。**

---

## 6. 本轮结论

1. **没有新增正式 `M`。**
2. **A1 / A2 均未完成身份绑定。**
3. A2 的 `ABQPSO` 单词级指纹已降权，应使用组合指纹。
4. 新增最值得继续的人员链：**郑州大学 `A25104590082` 李功平 → 梁静优化团队 → 调度 / 多目标 / 群体智能 → 比赛前已有双种群进化研究积累**。
5. 但 A2 的 DPEA 与郑大已有 DPCPRA / GLR-MMEA 并非同一算法，目前只应作为**高优先级研究假设**，不能升级 `F+`。
6. A1 的 Chaitin / graph coloring / spill 同样不是唯一身份指纹，下一步必须寻找 NPU 场景下的独特组合证据。
