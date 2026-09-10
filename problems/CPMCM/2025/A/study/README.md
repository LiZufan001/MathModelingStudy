# 2025 A题精读与建模路线：通用神经网络处理器下的核内调度问题

> 状态：赛前/模拟写题用分析稿 v1。本文先解决“题目到底在优化什么、三问如何衔接、代码应先实现什么、论文如何证明结果可信”。尚未实际运行本队算法，因此**不填写任何未经复算的六组结果数值**。

## 0. 一句话判断

这道题本质上不是单纯的“拓扑排序题”，而是一个逐层加约束的 **DAG 调度 + 连续内存分配 + 缓存换入换出（SPILL）+ 异构流水调度** 的组合优化问题：

1. **问题1**：先只研究“节点顺序”，在满足依赖关系和 L0 约束的前提下压缩缓冲区生命周期重叠，最小化峰值缓存驻留量；
2. **问题2**：把真实 L1/UB/L0 容量和连续地址约束加回来，必要时插入 SPILL，目标转为最小额外 DDR 数据搬运；
3. **问题3**：再把 Cube、Vector、MTE1/2/3、FIXP 等执行单元的并行流水真正纳入评价，在搬运量不显著恶化的前提下最小化总执行周期。

三问不是三套独立算法，而是同一调度器从“逻辑顺序”到“物理内存”再到“时间流水”的三层优化。

---

## 1. 已核实的题面规则

### 1.1 输入计算图

计算图是有向无环图（DAG） `G=(V,E)`。节点分两类：

- **操作节点**：`Id, Op, Pipe, Cycles, Bufs`；
- **缓存管理节点**：`Id, Op=ALLOC/FREE, BufId, Size, Type`。

依赖边 `(u,v)` 表示 `u` 必须先于 `v` 执行，因此最终调度序列首先必须是完整合法的拓扑序。

缓存类型包含：

- `L1`
- `UB`
- `L0A`
- `L0B`
- `L0C`

执行单元包含：

- 计算：`CUBE`, `VECTOR`
- 搬运/辅助：`MTE1`, `MTE2`, `MTE3`, `FIXP`

### 1.2 缓冲区生命周期

对缓冲区 `b`，逻辑生命周期从对应 `ALLOC(b)` 被调度开始，到 `FREE(b)` 被调度结束。

这一点非常关键：**问题1中的“驻留量”是由节点调度位置决定的，不是由流水时间轴直接决定的。**

为了避免后面把三个概念混在一起，代码中应明确分开：

- `schedule position`：节点在拓扑序中的位置；
- `logical liveness`：ALLOC 到 FREE 之间是否存活；
- `physical residency/address`：当前是否真正占用片上地址以及占哪个区间；
- `wall-clock cycle`：节点在某条 Pipe 上真正开始/结束的时钟周期。

### 1.3 问题1的目标

公开题面材料给出的驻留变化定义可写成：

```text
m(v) = +Size(v),  v 为计入驻留量的 ALLOC
       -Size(v),  v 为计入驻留量的 FREE
        0,        其他节点
```

给定合法调度序列 `S=(s1,...,sN)`，定义

```text
Vstay(k) = Σ_{i=1..k} m(si)
Vpeak    = max_k Vstay(k)
```

问题1就是在合法调度序列中尽量最小化 `Vpeak`。

现有公开高分方案、后续专利材料和题目解读对该问的一致解释是：**驻留量只统计 L1 与 UB；L1/UB 在问题1中暂不受实际容量上限约束；L0A/L0B/L0C 则保留特殊硬约束，同一类 L0 同时最多驻留一个缓冲区。**

因此建议我们实现时直接显式区分：

```text
Vstay = live_L1 + live_UB
```

而 L0 不加进 `Vstay`，只作为候选节点可行性过滤条件。

> 验收要求：正式写代码前，再从本仓库原始 DOCX/PDF 对这一条做一次人工逐字核对；若原题定义与这里存在差异，以原题为准。

### 1.4 问题2的真实容量

题目给出的缓存容量：

| Cache | Capacity |
|---|---:|
| L1 | 4096 |
| UB | 1024 |
| L0A | 256 |
| L0B | 256 |
| L0C | 512 |

每个缓冲区必须占用其指定缓存中的**连续地址区间**：

```text
[offset_b, offset_b + size_b)
```

两个生命周期重叠、且属于同一缓存池的缓冲区，其物理地址区间不得重叠；生命周期不重叠时可以复用同一地址。

因此问题2不仅是“总容量不能超”，还存在 **external fragmentation（外部碎片）**：总空闲空间可能足够，但没有一段足够长的连续区间容纳新 buffer。

### 1.5 SPILL 机制

空间无法继续分配时，可以把一个仍存活的 buffer 临时移出片上缓存，再在后续需要前搬回来：

```text
SPILL_OUT : cache -> DDR, 使用 MTE3
SPILL_IN  : DDR -> cache, 使用 MTE2
```

一次 SPILL 会改变：

- 调度序列（新增节点）；
- 依赖图（新增依赖）；
- 物理地址状态（SPILL_IN 后可以换新地址）；
- 总额外数据搬运量；
- 总执行周期。

题目明确规定了额外数据搬运量的两种计费：

```text
若 buffer 不是原始 COPY_IN 数据：一次 SPILL 的额外搬运 = 2 * Size
若 buffer 原本可由 COPY_IN 从 DDR 获得：一次 SPILL 的额外搬运 = Size
```

因此“换出最大 buffer”“换出最久不用 buffer”都不能单独作为正确目标；真正要最小的是**字节级额外搬运代价**，并且要兼顾本次 SPILL 是否真的形成可用的连续大块。

### 1.6 物理地址复用会反过来增加执行依赖

这是整道题最容易漏掉、但对问题3非常关键的一条。

若 `buffer b` 复用了此前 `buffer a` 的一段物理地址，则计算总执行时间时，需要加入：

```text
FREE(a) -> ALLOC(b)
```

即使原始计算图里二者没有数据依赖，物理地址复用也会制造新的串行关系。

所以：

> **更紧凑的内存布局不一定更快。**

问题2若极端追求地址复用，可能减少 SPILL，却在问题3里压缩了并行度、拉长 makespan。这正是问题3存在的原因。

---

## 2. 六组数据给我们的信息

本仓库已经收齐附录 E 的六组 JSON 与 CSV，并核验节点数/边数：

| Case | Nodes | Edges |
|---|---:|---:|
| Matmul_Case0 | 4160 | 7104 |
| Matmul_Case1 | 30976 | 55040 |
| FlashAttention_Case0 | 1716 | 2712 |
| FlashAttention_Case1 | 6952 | 11184 |
| Conv_Case0 | 2580 | 3869 |
| Conv_Case1 | 36086 | 85653 |

这意味着算法必须至少能稳定处理 **3.6 万节点、8.5 万边** 的稀疏 DAG。直接在所有节点全排列上跑 GA/SA/NSGA-II 是不可取的；搜索空间太大，而且绝大多数排列都不是拓扑序。

### 2.1 Matmul：规则、分块重复、数据复用明显

`Matmul_Case0` 开头反复出现：

```text
L1 COPY_IN
-> L0A/L0B MOVE
-> CUBE MATMUL
```

并存在较长生命周期的 L0C 累加/输出 buffer。

它适合研究：

- 分块次序改变对 L1 数据重复载入的影响；
- A/B 矩阵块的复用；
- 行优先、列优先、蛇形/之字形路径造成的不同 SPILL；
- MTE 与 CUBE 是否能流水重叠。

题目附录本身已经暗示：**Matmul 的块访问路径会直接决定重复搬运量。**

### 2.2 FlashAttention：最能暴露“只优化内存”的问题

`FlashAttention_Case0` 中同时能看到：

- `MATMUL / CUBE`
- `ROWMAX / SUB / EXP / ROWSUM / COMPACT / VECTOR`
- `COPY_IN / MTE2`
- `MOVE / MTE1`
- `COPY / MTE3 or FIXP`
- L1、UB、L0 之间的交错使用

因此它是问题3最值得重点观察的 case：

- 如果一味 FREE-first，可能压低驻留但破坏下一阶段预取；
- 如果 COPY_IN 太激进，又会抬高驻留甚至触发 SPILL；
- Cube 和 Vector 两条计算流水之间存在明显的交错空间；
- MTE1/2/3 的搬运可以被计算阶段隐藏一部分。

也就是说，FA 很适合展示我们算法的“软硬协同”价值，而不是只展示一个数字。

### 2.3 Conv：buffer 大小和 Cycles 高度异质

`Conv_Case0` 中可见：

- L1 buffer 从 1、2、16 到 384、768、1536 等多个量级；
- COPY_IN 从几十周期到 1600+ 周期；
- CONV 也从几十周期到 1800+ 周期。

这直接否定了几种过度简单的 SPILL 策略：

- 只按 `Size` 最大换出；
- 只按“最远下次使用”换出；
- 只按 buffer 数量最少换出。

正确策略至少应同时考虑：搬运代价、下一次使用距离、能释放的连续区间、后续关键路径/流水影响。

---

## 3. 这道题真正的难点

### 难点 A：调度顺序既决定生命周期，又决定后续内存和流水

同一个 DAG 有大量合法拓扑序。

某次选择普通计算节点本身 `m(v)=0`，看似不改变当前驻留量，但它可能：

- 解锁某个大 buffer 的 FREE；
- 解锁新的 ALLOC；
- 推动关键路径；
- 改变下一阶段可选节点集合。

所以简单的

```text
FREE > 普通节点 > ALLOC
```

只能当 baseline，不能当最终建模亮点。

### 难点 B：问题2不是普通 bin packing，而是带时间轴的动态连续区间分配

buffer 有生命周期；空闲区间动态产生、合并、复用。

我们实际面对的是：

> 给定/可调整的拓扑顺序下，为不同缓存池中的动态 live intervals 分配连续地址，在容量不足或碎片严重时允许付费切断 residency（SPILL）。

这比“所有物品一次装箱”更接近编译器 register allocation / memory planning。

### 难点 C：SPILL 的最优对象取决于“能否腾出一整段连续空间”

假设当前要分配长度 `q` 的 buffer。

即使某个 live buffer 很大、很久不用，把它换出也未必有意义——若它释放的位置与已有空洞无法连成 `q` 长度的连续区间，仍然无法完成申请。

因此更自然的建模不是“先选 victim”，而是：

1. 枚举/构造候选目标地址窗口 `W=[x,x+q)`；
2. 找出与 W 冲突的 live buffers 集合 `B(W)`；
3. 计算清空 W 所需的 SPILL 总代价；
4. 选择总代价最低的窗口与 victim 集合。

这会直接把“连续地址”和“SPILL 决策”绑在一起，比 Largest-first 更贴题。

### 难点 D：问题3存在真正的 Pareto 冲突

更少的地址复用约束，通常有利于并行，但需要更大的同时驻留空间；更激进地复用地址则可能减少 SPILL，却新增 `FREE -> ALLOC` 依赖。

因此问题3天然是：

```text
minimize ( TotalCycles, ExtraTraffic )
```

而不是简单把两个指标硬加成一个分数就结束。

---

## 4. 推荐的总体技术路线

建议采用“**独立评估器 + 可解释基线 + 分层启发式 + 局部/参数级搜索 + 小规模精确验证**”路线。

### 4.1 第一优先级：先实现独立 evaluator / validator

这是这几天写题最应该先做的组件。

优化器输出任何方案后，由另一个独立模块从零复算：

1. schedule 是否包含所有必须节点；
2. 是否满足原 DAG 拓扑约束；
3. L0 特殊约束是否满足；
4. 每个时刻每种 cache 的 live buffers；
5. 同时 live 的物理区间是否重叠；
6. SPILL 前后 buffer residency 是否正确；
7. SPILL 依赖是否按题目规则重连；
8. 地址复用产生的 `FREE -> ALLOC` 依赖是否补齐；
9. 总额外数据搬运量；
10. 每条 Pipe 的流水排布与最终总周期。

**optimizer 和 evaluator 必须分开写。**

不能让“产生答案的代码”同时充当“证明答案正确的代码”，否则一个共同 bug 会让错误结果自洽。

> 当前题面公开镜像中的 SPILL 节点编号/依赖重连公式，以及附录 D 的 SPILL Cycles 公式有图片公式未被文本抓取。实现问题2/3前必须从仓库原始 DOCX/PDF 逐式抄录并加入 evaluator 单元测试，不能凭二手代码猜。

---

## 5. 问题1：最小缓存驻留调度

### 5.1 数学模型

设合法调度序列为

```text
S = (s1, s2, ..., sN)
```

满足：

```text
(u,v) ∈ E  =>  pos(u) < pos(v)
```

对 L1/UB 类型 ALLOC/FREE 定义驻留增量 `m(v)`，则：

```text
Vstay(k) = Σ_{i=1..k} m(si)
```

目标：

```text
min_S  Vpeak(S)
Vpeak(S) = max_k Vstay(k)
```

并同时满足 L0A/L0B/L0C 的特殊驻留约束。

### 5.2 Baseline：Kahn + memory pressure

先实现一个绝对稳定的 baseline：

- Kahn 维护 ready set；
- FREE(L1/UB) 优先；
- 中性操作其次；
- ALLOC(L1/UB) 尽量延后；
- 先过滤掉会违反 L0 约束的候选；
- 最后用 node id 做 deterministic tie-break。

复杂度可做到 `O((V+E) log V)`，足以跑 3.6 万节点。

### 5.3 我们建议的改进：多因素 ready-node priority

对 ready 节点 `v` 定义多维特征，而不是只看 `m(v)`：

```text
f1(v): 当前驻留增量/减量
f2(v): 调度 v 后可直接或短距离解锁的 FREE 总大小
f3(v): critical-path / bottom-level 长度
f4(v): 是否会开启新的大 buffer 生命周期
f5(v): L0 状态匹配/冲突
f6(v): 后继扇出、剩余依赖数等“解锁能力”
```

推荐先采用**分层优先级**而不是一开始手调复杂权重：

```text
硬约束过滤
-> 优先可释放大内存的动作链
-> 再比较未来 1~L 步的峰值
-> 再比较关键路径推进程度
-> deterministic tie-break
```

其中最有价值的是一个很浅的 rolling lookahead：

- 对当前 ready set 中前 `K` 个候选分别尝试；
- 向前模拟 `L` 步；
- 比较局部峰值和可释放内存；
- 只保留少量 beam。

这比对 3 万节点全局跑元启发式更符合规模。

### 5.4 小图精确解用于证明算法质量

我们不能证明启发式全局最优，但可以在随机生成的 10~20 节点小 DAG 上：

- 枚举所有拓扑序，或用 DP / branch-and-bound 求精确最优 `Vpeak*`；
- 与 baseline、改进 greedy、beam search 对比；
- 报告最优差距：

```text
gap = (Vpeak_algo - Vpeak*) / Vpeak*
```

这会比“算法跑出来一个数”更有说服力。

---

## 6. 问题2：连续缓存分配 + SPILL

### 6.1 多缓存池独立维护地址区间

对每种 cache `t` 维护：

```text
free_intervals[t]
used_intervals[t] = (start, end, BufId)
```

ALLOC：寻找长度足够的连续空闲区；
FREE：释放并合并相邻区间。

建议至少实现并比较：

- First Fit
- Best Fit

Best Fit 往往能减少小碎片，但它不是最终答案，因为它不关心未来生命周期和问题3的复用依赖。

### 6.2 地址分配的可行性约束

对同一 cache 类型、生命周期重叠的两个 buffer `a,b`：

```text
[x_a, x_a+s_a) ∩ [x_b, x_b+s_b) = ∅
```

如果经历 SPILL，则一个 BufId 会出现多个 **residency epoch**，不能只用一个全局 `offset[b]` 表示内部状态。

建议内部模型写成：

```text
ResidencyEpoch = (BufId, begin_event, end_event, offset, size)
```

最后再按照题目附件格式导出初始 `memory.txt` 和每次 SPILL_IN 的 `spill.txt` 新 offset。

### 6.3 SPILL 窗口选择模型

当申请大小 `q` 时，枚举候选目标窗口 `W`：

```text
B(W) = 当前与 W 相交的 live buffers
```

基础代价：

```text
traffic_cost(b) = Size(b),   若 b 可由原 COPY_IN 重载
                  2Size(b),  否则
```

窗口基础目标：

```text
Cost(W) = Σ_{b∈B(W)} traffic_cost(b)
```

随后加入用于 tie-break / 二级排序的指标：

- victim 的 next-use distance：越久不用越适合换；
- victim 数量：减少过多 SPILL 节点；
- 清空窗口后与邻接 free block 合并的长度；
- victim 是否在关键路径附近；
- 对 MTE2/MTE3 的后续流水压力。

关键原则：**官方主指标是额外数据搬运量，其他量只能作为同等搬运代价下的次级判据或参数化改进，不能偷换目标。**

### 6.4 调度与分配要允许迭代

题目明确允许：如果问题1的顺序不利于问题2，可再次调整调度顺序。

因此建议：

```text
Q1 schedule
-> Q2 allocate/spill
-> 找出高 spill 压力区间
-> 对对应 DAG 局部做合法重排
-> 重新 allocate
-> 保留更优方案
```

局部重排只交换无依赖节点或重新运行局部 ready-set，天然保持拓扑合法，比全排列 GA 更稳。

### 6.5 碎片化只能作为解释/诊断指标

可以定义例如：

```text
Fragmentation(t,k) = 1 - LargestFreeBlock(t,k) / TotalFree(t,k)
```

但这不是题目官方优化指标。

论文里它最适合用于解释：

> 为什么“总空闲容量还够”却发生 SPILL，以及我们的分配策略为何优于 First Fit。

---

## 7. 问题3：流水时间 + 搬运量双目标优化

### 7.1 先构造 augmented DAG

在原 DAG 基础上加入：

1. SPILL 产生的依赖；
2. 地址复用产生的 `FREE(a)->ALLOC(b)` 依赖；
3. 同一 Pipe 上由调度顺序确定的串行执行关系。

对操作节点，若 `p(v)` 是对应 Pipe 上排在 v 前面的节点，则可按题目规则构造 earliest-start：

```text
start(v) = max(
    max_{u∈Pred(v)} finish(u),
    finish(p(v))
)
finish(v) = start(v) + Cycles(v)
```

最终：

```text
T = max_v finish(v)
```

这一步必须由独立 evaluator 复算。

### 7.2 不建议把问题3直接写成固定加权和

题目只说“总额外数据搬运量不显著增加”，并没有天然给出唯一权重。

更漂亮的论文表达是：

```text
min T
s.t. D <= (1+ε) D_Q2
```

其中 `ε` 作为实验参数扫描，而不是声称“官方规定 5%”。

例如可做：

```text
ε ∈ {0, 0.01, 0.03, 0.05, 0.10}
```

输出一条 `T-D` Pareto 曲线，再选择 knee point 作为最终提交方案。

### 7.3 优化动作应是“结构化合法动作”

建议的邻域操作：

- 交换两个互不依赖、且交换后仍满足拓扑序的节点；
- 在 ready set 中提升关键 Pipe 的节点；
- 在容量允许时提前 COPY_IN，以和 CUBE/VECTOR 重叠；
- 延后不急需的 ALLOC，降低驻留；
- 将 SPILL_IN 靠近下一次真实使用，减少驻留；
- 在 MTE3 空闲段安排 SPILL_OUT；
- 调整物理地址复用关系，减少人为 `FREE->ALLOC` 串行边。

如果采用 SA / NSGA-II，**搜索的对象应是这些局部动作、优先级参数或少量块级次序，而不是直接编码 3 万维节点排列。**

---

## 8. 可作为高质量参考的公开获奖线索

### 8.1 浙江工商大学全国一等奖/华为专项一等奖/数模之星提名团队

学校公开介绍显示，该队的总体框架是：

- 问题1：多策略协同启发式，压缩峰值缓存占用；
- 问题2：基于遗传编程的自适应缓存分配与 SPILL 决策；
- 问题3：模拟退火 + NSGA-II，多目标 Pareto 优化。

这说明高水平答案并不是“一个贪心从头跑到尾”，而是：

> **可扩展启发式产生可行解 + 数据驱动/搜索优化规则 + 最终多目标折中。**

但目前公开的是项目简介，不是完整论文，因此只能把它作为路线佐证，不能凭简介补造其具体公式和结果。

来源：

- https://sme.zjgsu.edu.cn/2025/1210/c333a209282/page.htm

### 8.2 贵州大学数模之星全国季军团队

公开材料称其提出：

- `MCBGS` 贪心调度；
- `MACDS` 多级缓存分配；
- `CPR-DOSA` 双目标调度优化。

其后公开的 MCBGS 相关专利进一步给出几个值得借鉴的核心点：

- Kahn 拓扑排序；
- 动态规划计算 critical path；
- L0 约束、memory-aware、critical-path 三类优先级；
- 高内存压力时自适应提高 FREE 类动作优先级；
- 增量维护 indegree / ready set，以保持近线性可扩展性。

这与我们上面推荐的 Q1 路线高度一致，也说明“关键路径 + 内存压力 + L0 硬约束”是非常自然的统一建模方向。

来源：

- https://eureka.patsnap.com/patent/CN121900817B

### 8.3 一个公开参赛代码仓库只能当 baseline，不当标准答案

公开仓库 `Zysishuiyears/2025Huaweicup_Cachenpuscheduling` 提供了：

- memory-pressure greedy；
- Best Fit + spill victim scoring；
- ASAP-style pipeline compression。

但其自身 README 明确说明当前实现是 heuristic、没有最优性保证、测试主要是 smoke test；整理后的 Q2 代码甚至用简化的单个 `SPILL` marker / `Cycles=1` 等内部表示，与题目正式 SPILL_OUT/SPILL_IN 规则并不等价。

因此可用它做：

- baseline 思路对照；
- 项目结构参考；
- 输出文件组织参考。

不能用它做：

- 官方 evaluator；
- “正确结果”的唯一依据；
- 直接复制后宣称完成问题2/3。

来源：

- https://github.com/Zysishuiyears/2025Huaweicup_Cachenpuscheduling

---

## 9. Verification Plan：这道题必须怎样验

### 9.1 静态输入检查

对六个 case 全部检查：

- node ID 唯一；
- edge 引用节点存在；
- DAG 无环；
- ALLOC/FREE 与 BufId 关系合法；
- Size/Type 一致；
- 操作节点引用的 BufId 存在；
- Pipe/Cycles 对操作节点完整。

### 9.2 问题1验收

- 输出长度 = 原图节点数；
- 每个节点恰好出现一次；
- 所有依赖边满足 `pos(u)<pos(v)`；
- L0 约束不违规；
- evaluator 独立复算 `Vpeak`；
- 对小图给出 exact optimum 与 heuristic gap。

### 9.3 问题2验收

对每个 schedule position / residency epoch：

- 每个 resident buffer 在正确 cache；
- `0 <= offset`；
- `offset+size <= capacity`；
- 同 cache、同时 resident 的区间无重叠；
- 操作执行时需要的 Bufs 均处于 resident 状态；
- SPILL_OUT/IN 成对且依赖合法；
- SPILL_IN 新 offset 合法；
- 独立复算 ExtraTraffic 与提交值一致。

### 9.4 问题3验收

- augmented DAG 无环；
- 原依赖全部保留；
- 地址复用依赖完整；
- 同一 Pipe 不重叠；
- 节点开始时间不早于所有前驱完成时间；
- SPILL Cycles 使用题面附录 D 精确公式；
- 独立复算 makespan；
- 对比 Q2：同时报告 `ΔT` 和 `ΔD`，不能只报百分比不给原值。

### 9.5 必做回归

六个官方 case 每次改算法后都重新跑：

```text
Matmul_Case0/1
FlashAttention_Case0/1
Conv_Case0/1
```

并保存：

- 参数；
- 随机种子；
- solver runtime；
- Git commit；
- 三问各自指标；
- 输出附件完整性检查。

---

## 10. 论文建议结构

正式模拟论文可按以下结构同步写：

### 摘要

直接给出三问的算法链与核心改进，不要大篇幅科普 NPU。

### 1 问题重述

把题意抽象成：

```text
DAG precedence
+ buffer liveness
+ contiguous memory
+ spill
+ heterogeneous pipelines
```

### 2 模型假设与符号

只做必要假设。尤其不要自行添加“SPILL 最多几次”“两指标权重固定”等题目未给规则。

### 3 问题1：峰值驻留优化

- 数学模型；
- baseline；
- multi-constraint greedy / lookahead；
- 复杂度；
- 六组结果；
- 小规模最优性 gap。

### 4 问题2：缓存分配与 SPILL

- 动态连续区间模型；
- Best Fit baseline；
- fragmentation-aware spill-window；
- 局部调度反馈；
- 六组 ExtraTraffic；
- 地址图/碎片图。

### 5 问题3：双目标流水优化

- augmented DAG；
- official timing evaluator；
- structured local search / SA / parameter-level NSGA-II；
- Pareto frontier；
- knee-point 方案；
- 与 Q2 的提升对比。

### 6 模型检验与消融

至少做：

- 去掉 critical path；
- 去掉 lookahead；
- First Fit vs Best Fit；
- Largest-victim vs next-use vs proposed spill-window；
- 不考虑 reuse edge vs 正确考虑 reuse edge（后者才是正式结果，前者仅用来说明影响）。

### 7 模型评价

优势重点写：

- 保证可行性；
- 近线性 baseline 能扩展到 36k 节点；
- 小图有精确解交叉验证；
- 三类图都使用同一套规则，满足泛化要求；
- 双目标不是拍脑袋加权，而是 Pareto 展示。

不足可以诚实写：启发式无全局最优保证，参数和局部搜索预算影响最终结果。

---

## 11. 建议的结果图表

这题图不需要很多，但下面几类非常值：

1. **Q1 驻留曲线**：横轴 schedule position，纵轴 Vstay；baseline 与 improved 两条曲线；
2. **Q2 地址-时间图**：横轴调度位置，纵轴 cache offset，不同 buffer 的 residency rectangle；一眼看出复用和碎片；
3. **SPILL 原因图**：发生 SPILL 前的 free intervals 与目标窗口；
4. **Q3 Gantt/流水图**：Cube、Vector、MTE1/2/3、FIXP 各一行；
5. **Pareto 图**：横轴 ExtraTraffic，纵轴 TotalCycles；
6. **消融表**：算法组件 vs 六组 case 指标。

其中第 2、4、5 类图非常适合体现“这不是普通拓扑排序”的技术含量。

---

## 12. 这几天模拟写题的推荐执行顺序

### 阶段 1：先把规则做对

先完成：

```text
parser
-> graph model
-> Q1 evaluator
-> Q2 memory validator
-> spill semantics
-> Q3 timing evaluator
```

在 evaluator 没有可信之前，不值得花时间调高级算法。

### 阶段 2：建立三个 baseline

```text
Q1: deterministic Kahn + memory pressure
Q2: Best Fit + 简单可解释 spill baseline
Q3: Q2 结果直接做 official timing
```

此时就能形成一篇“功能完整但结果一般”的保底稿。

### 阶段 3：只优化真正有收益的瓶颈

通过六组数据定位：

- 哪个 case Q1 峰值最差；
- 哪个 cache 导致最多 SPILL；
- 哪条 Pipe 是关键瓶颈；
- 哪些地址复用边造成大量串行。

再决定是增强：

- lookahead；
- spill-window；
- critical-path scheduling；
- SA/local search；
- NSGA-II 参数搜索。

不要为了“算法名高级”盲目堆模型。

### 阶段 4：最后冻结证据

最终提交前必须冻结：

- 六组 Problem1 schedule；
- 六组 Problem2 schedule/memory/spill；
- 六组 Problem3 schedule/memory/spill；
- evaluator 总表；
- 所有图表来源数据；
- 参数与随机种子；
- 论文中的数字与附件复算值逐项一致。

---

## 13. 当前最值得警惕的坑

- **坑1：**把 Q1 写成“FREE 优先即可”，没有分析普通节点如何解锁 FREE；
- **坑2：**用任意排列作为 GA 染色体，产生大量非法拓扑序；
- **坑3：**只检查总空闲容量，不检查连续区间；
- **坑4：**按 SPILL 次数优化，而不是按额外数据搬运量优化；
- **坑5：**所有 SPILL 都按 `2*Size` 计费，忽略 COPY_IN 类型 buffer 的特殊规则；
- **坑6：**一个 BufId SPILL 后仍只维护一个 offset，导致 residency epoch 错乱；
- **坑7：**问题3遗漏地址复用带来的 `FREE->ALLOC` 依赖；
- **坑8：**用问题2更紧凑的地址布局直接宣称问题3也更快；
- **坑9：**把博客/公开代码输出当官方最优值；
- **坑10：**针对 Matmul/FA/Conv 手写三套规则，失去题目明确要求的泛化性；
- **坑11：**只跑 unit test 就宣布完成，没有独立 evaluator、六 case 回归和提交文件复核；
- **坑12：**论文最后才开始写，导致符号、算法实现和结果指标对不上。

---

## 14. 我们当前建议的主方案

如果现在就确定一条最适合模拟赛落地的路线，建议是：

```text
Problem 1
Kahn ready-set
+ L0 feasibility filter
+ memory pressure
+ unlock-FREE potential
+ critical path
+ bounded lookahead / beam

        ↓

Problem 2
per-cache interval allocator
+ Best Fit baseline
+ fragmentation-aware spill-window search
+ next-use / copy-in cost tie-break
+ local topological reorder feedback

        ↓

Problem 3
independent official evaluator
+ augmented DAG
+ critical-pipe-aware local reorder
+ prefetch/spill timing adjustment
+ SA for local search
+ NSGA-II only on low-dimensional policy parameters / candidate solutions
+ Pareto frontier selection
```

这条路线的优点是：

- 第一天就能做出完整 baseline；
- 后续每个模块都能单独提升并做消融；
- 不依赖针对某一算子的硬编码；
- 能扩展到 3.6 万节点；
- 与公开数模之星团队披露的方法方向相符，但又不是直接照搬某篇未知全文；
- 最终论文有清晰的“模型—算法—验证—改进”故事线。

---

## 15. 下一步应产出的代码/证据

本分析之后，下一阶段建议仓库形成：

```text
A/
├── data/
├── study/
│   └── README.md                 # 本文
├── code/
│   ├── parser.py
│   ├── evaluator.py
│   ├── problem1.py
│   ├── problem2.py
│   ├── problem3.py
│   └── validators.py
├── results/
│   ├── baseline/
│   └── improved/
└── figures/
```

其中最先写的不是 `problem1.py`，而应是 `parser.py + evaluator.py + validators.py`。

---

## 16. 资料来源与证据等级

### A级：本仓库原始题面/附件

- `../A题：通用神经网络处理器下的核内调度问题.pdf`
- `../A题：通用神经网络处理器下的核内调度问题.docx`
- `../data/README.md`
- `../data/csv/`
- `../data/json/`

### B级：高校官方获奖介绍

- 浙江工商大学全国一等奖/华为专项一等奖/数模之星提名团队方法简介：
  https://sme.zjgsu.edu.cn/2025/1210/c333a209282/page.htm

### B级：赛后公开专利/方法披露

- 贵州大学 MCBGS 相关专利：
  https://eureka.patsnap.com/patent/CN121900817B

### C级：公开参赛代码，仅作方法对照

- https://github.com/Zysishuiyears/2025Huaweicup_Cachenpuscheduling

### C级：题面文本镜像，仅用于辅助检索图片公式

- https://developer.aliyun.com/article/1682735

> 规则冲突时，优先级始终是：**仓库原始题面 > 官方赛事/高校材料 > 赛后专利 > 公开代码/博客**。
