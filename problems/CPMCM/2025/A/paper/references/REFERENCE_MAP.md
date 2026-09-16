# 2025 A 题参考文献映射表

> 目的：把每篇文献绑定到论文中的**具体用途**，同时规定它不能被拿来证明什么。正文引用前先查本表。

## 1. 调度与 DAG

### `graham1969multiprocessing`
- 用途：Q1/Q3 的 list scheduling、并行调度与“调度顺序会影响总性能”的经典背景。
- 可支持：precedence / multiprocessor scheduling 是经典组合优化问题，启发式排序是合理研究路线。
- 不可支持：不能据此声称本题 Q1 的 `V_peak` 目标具有 Graham 文中的近似比；目标函数不同。
- DOI: `10.1137/0117039`

### `hu1961parallel`
- 用途：有前驱约束任务的早期经典 sequencing/scheduling 背景。
- 可支持：带 ordering restrictions 的任务调度本身就是经典研究对象。
- 不可支持：不能把 Hu 的处理器模型直接等同于本题 L0/L1/UB 约束。
- DOI: `10.1287/opre.9.6.841`

### `kelley1961critical`
- 用途：Q3 中 critical path / precedence + duration 的理论出处。
- 可支持：在带持续时间和先后约束的网络中，关键路径刻画完成时间瓶颈。
- 不可支持：不能据此证明我们的 heterogeneous Pipe + memory-dependence evaluator 与传统 CPM 等价。
- DOI: `10.1287/opre.9.3.296`

### `topcuoglu2002heft`
- 用途：Q3 heterogeneous DAG scheduling 相关工作；说明异构资源下常用基于优先级/关键路径的启发式。
- 可支持：异构计算环境中的 DAG 调度通常需要同时考虑任务优先级与处理资源差异。
- 不可支持：我们没有实现 HEFT，正文不能写“采用 HEFT”。
- DOI: `10.1109/71.993206`

## 2. 连续内存、生命周期与 SPILL

### `wilson1995dynamic`
- 用途：Q2 连续动态内存分配、空闲块管理、external fragmentation 的理论背景。
- 可支持：动态分配中即使总空闲量足够，也可能因碎片缺少足够大的连续块。
- 不可支持：该文是通用 allocator survey，不是神经网络专用算法，也不直接给出本题最优策略。
- DOI: `10.1007/3-540-60368-9_19`

### `poletto1999linear`
- 用途：用 live interval 解释“生命周期不重叠即可复用同一有限资源”的编译器类比。
- 可支持：生命周期/活跃区间是资源复用决策的重要抽象。
- 不可支持：本题 buffer 是连续地址区间而非单个寄存器，不能写成“Q2 就是 linear scan register allocation”。
- DOI: `10.1145/330249.330250`

### `chaitin1981coloring`
- 用途：同时存活对象形成 interference 的经典来源；解释“重叠生命周期不能占用冲突资源”。
- 可支持：live-range overlap 可以抽象为干涉关系。
- 不可支持：我们的正式 Q2 不是图着色算法，不要把概念类比写成算法来源。
- DOI: `10.1016/0096-0551(81)90048-5`

### `chow1990priority`
- 用途：cost-aware spilling 的相关工作背景；说明 spill 决策不能只看是否冲突，还要考虑代价。
- 可支持：spill/保留决策可以基于收益与代价排序。
- 不可支持：本题的字节级 `ExtraTraffic`、COPY_IN 重载规则和连续窗口清空策略是题面特有的，不能归因于该文。
- DOI: `10.1145/88616.88621`

### `belady1966replacement`
- 用途：Q2 `q2_unit_cache_oracle.py` 中 Matmul 等大小 page 特例的离线最优 replacement oracle 理论依据。
- 可支持：在已知未来访问序列、等大小页面的经典 replacement 模型中，最远未来使用原则提供理论最优基准。
- 不可支持：**绝不能**据此声称完整 Q2（可变 Size、连续地址、碎片、不同 spill 成本）达到全局最优。
- DOI: `10.1147/SJ.52.0078`

### `sethi1975register`
- 用途：寄存器/有限快速存储分配的组合复杂性背景。
- 可支持：有限快速存储资源分配具有经典的组合优化困难。
- 不可支持：不能用这篇论文直接断言“本题 Q2 是 NP-hard”，除非论文里另给严格 reduction。
- DOI: `10.1137/0204020`

### `pisarchyk2020memory`
- 用途：神经网络推理中 intermediate tensor buffer sharing 的现代系统背景。
- 可支持：边缘/嵌入式 DNN 推理中，中间张量生命周期和 buffer sharing 会直接影响内存占用。
- 不可支持：该文的具体 allocator 不等同于本题 Q2，也不支撑我们的具体提升数字。
- arXiv: `2001.03288`

## 3. 多目标与 Pareto

### `ehrgott2005multicriteria`
- 用途：Q3 Traffic–Cycles 两目标、dominance 和 Pareto frontier 的数学背景。
- 可支持：当目标冲突时，可用非支配解集描述 trade-off，而不是强行指定唯一加权最优。
- 不可支持：本项目没有采用书中的某个特定求解器；只引用基本多目标优化概念。
- DOI: `10.1007/3-540-27659-9`

## 4. 正文推荐引用布局

- 问题背景 / Q1：`hu1961parallel`, `graham1969multiprocessing`
- Q1 方法：若介绍 list-scheduling 家族，可再引 `graham1969multiprocessing`
- Q2 建模：`wilson1995dynamic`, `poletto1999linear`, `chaitin1981coloring`
- Q2 SPILL / oracle：`chow1990priority`, `belady1966replacement`
- Q2 神经网络场景：`pisarchyk2020memory`
- Q3 关键路径：`kelley1961critical`
- Q3 异构调度相关工作：`topcuoglu2002heft`
- Q3 Pareto：`ehrgott2005multicriteria`

## 5. 明确不收入的“看起来相关”文献

当前不引用 NSGA-II、模拟退火、遗传算法等经典文献，原因不是它们不重要，而是**我们的正式算法没有使用这些算法**。为了让参考文献反映真实方法，不为“显得高级”而堆无关方法名。

同理，2025 A 题优秀论文属于竞赛参考/对照材料，单独存放于 `papers/CPMCM/2025/`，不混入理论文献 BibTeX；若后续正文需要做“相关竞赛方案比较”，再单独建立竞赛来源引用条目。
