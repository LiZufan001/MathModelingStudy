# CPMCM 2025 A 论文章节施工图

> 状态：写作前结构冻结草案。这里只规定章节职责、公式、证据与图表，不撰写正式正文。
> 版式基线：2025 华为杯 LaTeX 模板；2026 官方《竞赛论文标准文档》发布后再做格式校准。

## 0. 写作总原则

- 三问写成**同一调度问题逐层增加约束**，不要写成三篇互不相干的小论文。
- 所有数值只引用 `results/` 正式发布数据；实验目录、日志和 README 中的中间点不直接当正式结果。
- 每个“最优”“提升”“不变”“饱和”都必须能落到 `CLAIM_LEDGER.md` 的证据条目。
- `best-known / promoted / locally saturated` 与“全局最优”严格区分。
- 摘要最后写；先完成方法、结果、验证，再从正文反向压缩摘要。

---

## 1. 摘要（最后写）

### 必须回答

1. 题目对象：通用神经网络处理器核内 DAG 的调度、片上连续内存与流水执行联合优化；
2. Q1：合法拓扑序下最小化 L1+UB 峰值驻留量；
3. Q2：加入真实容量、连续地址与 SPILL 后最小化额外 DDR 搬运量；
4. Q3：固定 Q2 SPILL/traffic 的前提下最小化 official cycles，并用 residency-safe evaluator 作可行性门禁；
5. 给出少量最能代表结果的数字，不罗列六组全部数据；
6. 明确方法的可复现验证，而不是写“效果显著”空话。

### 推荐数字

- Q1 Conv1：`310,408 -> 310,344`，减少 `64`，即 `0.020618%`；其余五组当前四策略 portfolio 与 baseline 持平。
- Q2 Matmul 两组总 extra traffic：`495,616 -> 459,008`，减少 `36,608`（`7.386%`）；六组 promoted traffic 以正式表为准。
- Q3 Conv0：`636,114 -> 595,302`（`6.415831%`）；Conv1：`3,852,543 -> 3,749,777`（`2.667485%`），且 Q2 traffic/SPILL records 不变。
- 若摘要空间有限，只保留 Q2 总改善 + Q3 Conv0/Conv1 两个代表数字。

### 禁止

- “获得全局最优解”；
- “所有实例均显著优于现有方法”；
- 把 FA1 higher-traffic trade-off 与 fixed-traffic 正式主链混成同一个结论。

---

## 2. 问题重述与背景

### 2.1 计算图与硬件对象

定义 DAG `G=(V,E)`；节点包括：

- 计算/搬运操作节点：`Op / Pipe / Cycles / Bufs`；
- 内存管理节点：`ALLOC / FREE / BufId / Size / Type`。

缓存类型：`L1 / UB / L0A / L0B / L0C`；执行单元：`CUBE / VECTOR / MTE1 / MTE2 / MTE3 / FIXP`。

### 2.2 三问的递进关系

- Q1：只优化逻辑调度顺序和逻辑生命周期重叠；
- Q2：加入真实物理容量、连续地址和 SPILL；
- Q3：再加入 Pipe 时间轴、地址复用依赖和流水并行。

### 图表

- 正文放 D1：`../diagrams/generated/pipeline_overview.pdf`。

### 章节目标

让评委在进入公式前就明白：三问是“逻辑顺序 → 物理内存 → 时间流水”的统一优化链。

---

## 3. 模型假设与符号说明

### 3.1 只保留必要假设

优先使用题面事实，避免增加无法验证的工程假设。可写的假设应限定为：

- 输入 DAG、节点属性与 buffer 元数据真实有效；
- `Cycles`、`Size`、Pipe 类型按题面给定，不人为修改；
- 评价严格采用题面口径和本仓库独立 evaluator 复算。

### 3.2 符号表 T2

正式写作时至少包含：

- `G=(V,E)`：计算图；
- `S=(s_1,...,s_n)`：合法调度序列；
- `m(v)`：Q1 驻留量增量；
- `R_k` / `R_peak`：第 k 个位置后的驻留量 / 峰值；
- `C_t`：缓存池容量；
- `o_b, z_b`：buffer 地址偏移 / 大小；
- `I_b=[o_b,o_b+z_b)`：连续地址区间；
- `T_extra`：额外 DDR traffic；
- `s_v, f_v`：Q3 节点开始/结束周期；
- `T_official`：题面 official 总周期；
- `T_safe`：residency-safe 辅助可行性评价。

---

## 4. 总体求解框架

这一节只讲共性，不提前重复各问细节。

### 4.1 统一框架

1. Parser 构建统一 DAG / buffer 模型；
2. Q1 产生合法调度顺序；
3. Q2 基于顺序做连续地址分配与必要 SPILL；
4. Q3 在固定 Q2 traffic/SPILL 的正式主链上做 timing-aware 重排与地址优化；
5. 每次 promotion 都通过独立 validator/evaluator、六组 replay 和 CI。

### 4.2 “候选生成”与“独立评价”分离

强调算法可以复杂，但 promotion 统一只信：

- validator；
- evaluator；
- 正式结果 CSV/JSON；
- 独立 replay。

这样可作为全文可信度主线。

---

## 5. 问题一：面向峰值驻留量的拓扑调度

### 5.1 数学模型

对合法拓扑序 `S=(s_1,...,s_n)`，定义：

```text
m(v) = +Size(v),  v 为计入驻留量的 L1/UB ALLOC
       -Size(v),  v 为计入驻留量的 L1/UB FREE
        0,        其他节点
```

```text
R_k = sum_{i=1..k} m(s_i)
R_peak(S) = max_k R_k
```

目标：

```text
min R_peak(S)
s.t. S 为 DAG 合法拓扑序；
     L0A/L0B/L0C 满足题面同类单驻留等硬约束。
```

### 5.2 为什么不是简单 FREE-first

说明普通操作虽 `m(v)=0`，但会改变后续可调度集合，可能更早解锁 FREE 或推迟大 ALLOC，因此需要比较多个合法调度策略。

### 5.3 确定性四策略 portfolio

按“从便宜到复杂”介绍：

1. `q1_baseline`：FREE → neutral → counted ALLOC 的确定性 Kahn 贪心；
2. `q1_pressure`：加入 release/downstream pressure；
3. `q1_frontier`：frontier/depth-first 风格，尽量完成局部生命周期；
4. `q1_lookahead`：只在多个正内存 ALLOC 同时 ready 时触发 bounded rollout，其他步骤仍保持贪心。

每个候选最后统一交给独立 `evaluate_q1()` 重算，不以启发式内部估计值作为结果。

### 5.4 小规模精确 oracle 的角色

- 用于验证 evaluator / 启发式语义；
- 不声称 3.6 万节点 Conv1 已精确求全局最优。

### 5.5 六组 promoted 结果

正式数据：`results/q1_promoted/q1_promoted_summary.csv`。

核心叙述：

- 五组 case 中 baseline 已经是当前四策略 portfolio 的 best point；
- Conv1 的 bounded lookahead 从 `310,408` 降到 `310,344`；
- 改善绝对量 `64`，相对 `0.020618%`；
- 外部公开 Problem1 schedule 经本 evaluator 独立重放，六组 peak 与 baseline 完全一致，只作为横向参照。

### 图表

- 主表 T1：`../tables/generated/key_results.tex`；
- Q1 详细表：`../tables/generated/q1_summary.tex`，优先放附录；
- Q1 六组柱图 `q1_peak_residency.pdf` 可放附录，不占正文版面。

### 结论边界

使用“当前确定性四策略 portfolio 的 promoted best-known 点”；禁止写“Q1 全局最优”。

---

## 6. 问题二：连续地址分配与最小额外 DDR 搬运

### 6.1 从逻辑生命周期到物理地址

每个 resident buffer `b` 在所属缓存池分配连续区间：

```text
I_b = [o_b, o_b + z_b)
0 <= o_b, o_b + z_b <= C_type(b)
```

同缓存池且 residency 重叠的两个 buffer 地址区间不能相交。

强调 external fragmentation：总空闲量足够并不代表存在足够长的连续区间。

### 6.2 SPILL 机制与代价

- `SPILL_OUT`：cache → DDR，MTE3；
- `SPILL_IN`：DDR → cache，MTE2；
- 根据题面 COPY_IN 来源规则计算额外字节量；
- 目标是最小 `extra_traffic`，不是最小 SPILL 次数。

### 图表

- 正文放 D2：`../diagrams/generated/q2_buffer_lifecycle.pdf`。

### 6.3 promoted allocator portfolio

按最终实现解释三层：

1. deterministic strict allocator baseline；
2. footprint-aware / reuse-aware 顺序与地址选择；
3. 小窗口 polish，对候选移动重新做 strict replay。

正式选择优先级：

```text
extra_traffic 最小
→ spill_count 较少
→ 其余 tie-break
```

避免把实验参数堆成主体；具体参数可以附录。

### 6.4 结果

正式数据：`results/q2_optimized/q2_optimized_summary.csv`。

重点：

- 六组 promoted extra traffic：`28,800 / 430,208 / 54,016 / 242,552 / 177,904 / 721,464`；
- Matmul 两组总 traffic `495,616 -> 459,008`，降低 `36,608`（`7.386%`）；
- Matmul 两组 SPILL `3,872 -> 3,586`；
- FlashAttention / Conv 四组 promotion 保持既有指标；
- “SPILL 次数”不是唯一目标，真正比较 byte traffic。

### 6.5 验证

- small Matmul unit-cache exact Belady oracle；
- archived competition Problem2 外部结果 strict replay；
- 地址区间、resident 状态、SPILL 顺序、extra traffic 独立 validator。

### 图表

- 主表继续用 T1；
- `q2_spill_count.pdf` / `q2_extra_traffic.pdf` 优先放附录；
- Q2 详细表：`q2_summary.tex`。

### 结论边界

写“promoted / best-known in tested portfolio”，不写“全局最少搬运量”。

---

## 7. 问题三：固定 Q2 搬运方案下的流水周期优化

### 7.1 timing 模型

定义每个节点的 `s_v / f_v`：

```text
f_v = s_v + Cycles_v
```

约束至少包括：

- DAG precedence；
- 同 Pipe 资源序列化；
- 地址复用引入的 `FREE(a) -> ALLOC(b)` 物理依赖；
- SPILL 节点及其 Pipe / precedence；
- residency-safe overlap 合法性。

### 7.2 双 evaluator 口径

必须明确：

- `official_literal`：题面 official cycles，**优化目标**；
- `residency_safe`：物理安全辅助重放，**硬门禁而非排序目标**。

因此不能因为 safe cycles 某次略升就否定 official 的严格改善，只要 safe overlap 仍为 0 且所有硬约束成立。

### 7.3 fixed-Q2 invariants

正式主链固定：

- SPILL identity / order；
- spill count；
- extra traffic。

所以 Q3 的正式改善不能靠“多搬一点数据换时间”。

### 7.4 优化算子

按两级介绍，避免把几十个实验 workflow 写进论文：

**通用 zero-traffic core**
- address portfolio / recoloring；
- critical pipeline reschedule；
- critical reuse reorder。

**局部 critical-SPILL post-pass**
- fresh-rerank batch；
- Conv0 single-switch bubble；
- Conv1 cycle-filtered critical-SPILL batch。

每个候选都重新 strict Q2 + official + residency-safe replay。

### 7.5 六组正式结果

正式数据：`results/q3_formal_fixed_traffic/q3_formal_fixed_traffic_summary.csv`。

| Case | promoted-Q2 raw | final official | reduction |
|---|---:|---:|---:|
| Matmul0 | 135,082 | 133,682 | 1.036408% |
| Matmul1 | 1,534,618 | 1,531,946 | 0.174115% |
| FA0 | 194,265 | 187,945 | 3.253288% |
| FA1 | 962,746 | 962,022 | 0.075202% |
| Conv0 | 636,114 | 595,302 | 6.415831% |
| Conv1 | 3,852,543 | 3,749,777 | 2.667485% |

### 正文图表

- F1：`../figures/generated/q3_official_improvement_pct.pdf`；
- T1：`../tables/generated/key_results.tex`；
- F2：`q3_raw_vs_final_cycles.pdf`，版面宽松时用，否则附录。

### 7.6 Conv0 / Conv1 局部饱和

可简述：

- Conv0 single-switch 邻域到首个 no-improvement；
- Conv1 cycle-filtered `max_switches=16` 邻域到首个 no-improvement，并由独立 formal acceptance 再跑一次得到 `improved=false`。

必须用“该邻域局部饱和”，不能把它扩写成 Q3 全局最优证明。

---

## 8. Traffic–Cycles 权衡扩展：FA1

这一节与 fixed-traffic 正式主链分开。

### 8.1 目的

展示若允许少量额外 DDR traffic，是否能换取更明显的周期下降。

### 8.2 三个正式 refined 点

- fixed traffic：`+0% traffic`，`962,022 cycles`，较 raw 降 `0.075202%`；
- `1>1`：`+0.616775% traffic`，`947,002 cycles`，降 `1.635322%`；
- `2>1`：`+1.034005% traffic`，`912,556 cycles`，降 `5.213213%`。

### 图表

- 正文 F3：`../figures/generated/q3_fa1_tradeoff.pdf`；
- 精确表：`../tables/generated/q3_fa1_tradeoff.tex`，正文或附录择一。

### 边界

这些 higher-traffic 点是权衡扩展，不能替换 fixed-Q2-traffic 六组正式主结果。

---

## 9. 模型验证、稳健性与可复现性

建议单独成节，而不是把验证散落得看不见。

### 9.1 Q1

- unit + exact-small-case oracle；
- 六组 fresh four-policy comparison；
- published-result verifier；
- 外部公开 Problem1 schedule 独立重放。

### 9.2 Q2

- strict address/SPILL replay；
- exact micro oracle；
- 六组 promoted regression；
- archived competition Problem2 外部附件 replay。

### 9.3 Q3

- official + residency-safe 双 evaluator；
- fixed-Q2 invariants；
- safe-overlap gate；
- Conv formal acceptance；
- published CSV/JSON/frontier/reconcile arithmetic verifier。

### 9.4 可复现资产

- 图、表、方法图均由仓库脚本生成；
- GitHub Actions 只拉 A 题 sparse checkout；
- 正式结果与论文资产构建分别有 CI gate。

这节只写关键机制，具体 run ID / SHA / artifact digest 可放附录“复现信息”。

---

## 10. 模型优点、局限与改进方向

### 优点应围绕

- 三问统一、递进而非割裂；
- 候选生成与独立评价分离；
- 连续地址 + fragmentation + SPILL 真实建模；
- Q3 维持 fixed traffic 的因果解释清晰；
- 六组大实例可实际运行并可复现；
- 通过 external replay / dual evaluator 减少“自己给自己打分”。

### 局限必须诚实写

- 大实例没有全局最优证明；
- Q1 Conv1 portfolio 改善很小，说明 baseline 已强但仍有搜索空间；
- Q2/Q3 的局部启发式仍依赖候选邻域；
- FA1 trade-off 目前只有少量正式 refined 点，不代表完整连续 Pareto 前沿。

### 改进方向

- 更强的受限 beam / LNS / CP-SAT 子问题；
- 对关键窗口做 exact/local MILP；
- 将 traffic 与 timing 联合做可控多目标搜索；
- 只在 evaluator 语义完全一致的前提下扩大搜索。

---

## 11. 结论

最后写，按三问分别一两句结论，再用一句总结“逻辑调度—物理内存—时间流水”的统一价值。

不要在结论首次出现新数字或新实验。

---

## 12. 参考文献

待正文方法术语确定后补 BibTeX。优先引用：

- DAG scheduling / list scheduling；
- register allocation / graph coloring / spilling；
- Belady / cache replacement（仅在对应模型处）；
- memory planning / contiguous allocation；
- heterogeneous pipeline scheduling；
- 多目标/Pareto（FA1 权衡节）。

不为了“文献数量”引入与正文算法无关的论文。

---

## 附录规划

### 附录 A：完整六组结果表

- `q1_summary.tex`
- `q2_summary.tex`
- `q3_summary.tex`

### 附录 B：补充图

- Q1 peak residency；
- Q2 spill count；
- Q2 extra traffic；
- Q3 raw vs final；
- Q3 global Pareto diagnostic overview。

### 附录 C：关键算法伪代码

只给核心决策逻辑，不大段粘 Python 源码：

- Q1 portfolio / bounded lookahead；
- Q2 allocation + SPILL；
- Q3 fixed-traffic local improvement。

### 附录 D：复现与验收信息

列：

- 正式结果文件；
- validator/evaluator；
- CI workflow；
- formal acceptance / artifact digest；
- 代码仓库版本。

---

## 写作顺序（真正开写时）

推荐顺序不是从摘要开始：

1. 第 5 节 Q1；
2. 第 6 节 Q2；
3. 第 7–8 节 Q3 / trade-off；
4. 第 9 节验证；
5. 第 4 节总体框架；
6. 第 2–3 节问题重述 / 假设符号；
7. 第 10–11 节优缺点与结论；
8. 最后写摘要和标题。
