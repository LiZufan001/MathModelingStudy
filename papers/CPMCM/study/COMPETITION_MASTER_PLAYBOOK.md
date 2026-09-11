# 华为杯建模实战总手册 v2｜把开放问题研究得科学、清楚、可信

> 这不是模型大全，而是一套正赛研究方法。  
> **最高原则：数模的核心不是求一个标准答案，也不是展示高级算法，而是在开放问题上建立一条可审计、可追问、证据与结论匹配的研究链。**  
> **说服力是结果，不是方法。** 评委信服，应当来自研究判断有依据、方法有针对性、证据能区分、结论不过界。  
> 历史论文中的具体阈值、权重、超参数不直接迁移；只迁移研究结构、方法选择逻辑、验证纪律和建模接口。  
> 论文叙事专项见 [`NARRATIVE_AND_ARGUMENTATION_GUIDE.md`](NARRATIVE_AND_ARGUMENTATION_GUIDE.md)。

---

# 0. 先把“拿奖逻辑”想对

没有标准答案，不代表结果随意。

比赛真正评价的不是：

```text
你的数值 = 标准答案？
```

而是：

```text
你为什么这样理解问题？
→ 为什么这样数学化？
→ 为什么选这个方法？
→ 什么证据支持它？
→ 结论能说到哪里？
```

因此真正的主线是：

\[
\boxed{
\text{Observation}
\rightarrow
\text{Judgment}
\rightarrow
\text{Model}
\rightarrow
\text{Evidence}
\rightarrow
\text{Boundary}
}
\]

简称 **OJME-B 研究链**。

- **Observation**：题意、数据、机理、结构、失败现象；
- **Judgment**：我们认为真正关键的矛盾是什么；
- **Model**：把判断变成变量、约束、关系、算法；
- **Evidence**：baseline、下界、实验、独立验证、敏感性、不确定性；
- **Boundary**：结论适用到哪里，哪些只是近似/情景/评分。

## 0.1 两个极端都要避免

### 只有故事，没有验收

```text
想法漂亮
→ 公式很多
→ 没有 baseline / 独立验证 / 边界
```

这不是科学研究。

### 只有验收，没有洞察

```text
evaluator 完美
→ 代码无 bug
→ 随机试十个算法取最高分
```

这也不是高水平建模。

真正有竞争力的是：

> **有洞察的问题抽象 + 有针对性的方法 + 有区分力的证据 + 高效清楚的表达。**

---

# 1. 拿题后前 60–90 分钟：建立“研究问题画布”

每道候选题先填这 10 项：

| 项目 | 必须回答 |
|---|---|
| 现实对象 | 到底在研究什么系统/过程/行为 |
| 每问输出 | 题目最终要求交什么对象 |
| 核心矛盾 | 精度-成本？风险-距离？信息-资源？ |
| hard constraints | 违反即失效的条件 |
| 官方评价 | 题面真正如何计分/判定 |
| 数据独立单位 | 人、实验、订单、设备、时间段、园林…… |
| 机理/结构 | 守恒、图、层次、低秩、工艺、时序、空间 |
| 最简单 baseline | 2–3 小时能否得到可信第一版 |
| 可验证证据 | 真值、下界、外部对象、规律、反事实？ |
| 最大风险 | 最可能让整题崩掉的环节 |

然后每人独立写一句：

> **“我认为这道题最关键的不是 ______，而是 ______。”**

三个人比较这句话，比先讨论“用 XGBoost 还是 LSTM”更有价值。

---

# 2. 选题：优先选“能形成研究闭环”的题

不要只问“我们会不会”。

重点比较：

1. 能否快速形成**清楚的问题判断**；
2. 能否做一个可信 baseline；
3. 是否存在可用的验证证据；
4. 各问能否自然递进；
5. 我们有没有机会提出 1–2 个真正有辨识度的表示/状态/结构；
6. 最坏情况下是否仍有可提交方案。

高奖题不一定是最复杂的题，而往往是你们能把：

```text
理解 → 方法 → 证据 → 叙事
```

做得最完整的题。

---

# 3. 第一版模型：先形成可信“研究地基”

## 3.1 evaluator-first 是执行纪律，不是最高原则

在明确了研究判断以后，立即实现：

```python
def check_input(data): ...
def check_feasibility(solution, data): ...
def official_score(solution, data): ...
def sanity_report(solution, data): ...
```

它们的作用不是“定义研究思想”，而是防止研究链建立在错误数字上。

## 3.2 Baseline 的意义不是凑对照，而是建立因果理由

每问至少一个最简单可信 baseline：

| 题型 | baseline |
|---|---|
| 回归 | 均值 / 线性 / RF |
| 时间序列 | persistence |
| 分类 | majority / logistic |
| 路径 | 直线 / Dijkstra / A* |
| 调度 | FIFO / greedy |
| 排样 | FFD/BFD + area lower bound |
| 矩阵 | exact algorithm |
| 融合 | IDW / OI |
| 综合评价 | 单指标 / 等权 |

高级模型只有在 baseline 暴露明确失败模式后才升级。

## 3.3 结果不是“答案”，而是证据

我们用结果回答：

- 假设是否自洽；
- 哪个机制真的重要；
- 高级模型是否解决了已知失败模式；
- 近似解离理论极限多远；
- 结论对参数是否稳定；
- 哪些场景会失败。

所以没有标准答案，也仍然必须严肃对待结果。

---

# 4. 模型升级的唯一正当理由：解决一个已识别问题

合法升级理由主要有五类：

### 结构理由

低秩、稀疏、分块、工艺层次、守恒、图结构。

### 统计理由

非线性、异方差、类别不平衡、组相关、时序依赖。

### 计算理由

精确算法规模不可承受，需要 decomposition / heuristic。

### 信息理由

单源信息不足、标签昂贵，需要融合/半监督/surrogate。

### 决策理由

平均预测误差不足以保障安全，需要 tail risk / uncertainty。

差的升级：

> “为了提高精度，我们采用 XGBoost。”

好的升级：

> “线性基线在高值区系统低估，残差呈稳定非线性，因此使用树提升模型拟合该残差；改进主要集中在原失败区间。”

---

# 5. 七类题型的稳健研究骨架

## 5.1 调度 / 排样 / 组合优化

```text
规则与 hard constraints
→ feasibility simulator
→ lower bound
→ greedy construction
→ structure-aware reduction
→ repair / local search
→ gap + robustness
```

核心叙事：**为什么原问题规模大，以及题目结构如何允许降维。**

来源经验：2022 C、2022 B。

## 5.2 物理 / 动态系统

```text
单位/参考系
→ 机理状态模型
→ invariant
→ baseline evaluator
→ 控制/设计变量
→ independent cross-check
→ error budget
```

核心叙事：**先把物理地基做准，再让优化器重复调用。**

来源经验：2020 F、2024 F。

## 5.3 数据 / 信号学习

```text
独立样本定义
→ split protocol
→ baseline
→ mechanism-informed features
→ model
→ group/time validation
→ resource / error analysis
```

核心叙事：**为什么这些特征或模型能表达系统机制，而不是模型赛马。**

来源经验：2020 C、2024 B。

## 5.4 矩阵 / 算法工程

```text
官方 cost ledger
→ bottleneck profiling
→ structure reuse
→ structured approximation
→ single-kernel optimization
→ storage / compute co-design
→ error-cost Pareto
```

核心叙事：**不断追问“现在真正贵在哪里”。**

来源经验：2021 A、2023 B。

## 5.5 图像 / 视频 → 空间或决策

```text
raw pixel
→ detection / segmentation
→ physical calibration
→ state / geometry
→ uncertainty
→ downstream task
→ end-to-end validation
```

核心叙事：**研究对象不断升级，而不是每问换一个视觉算法。**

来源经验：2024 E、2025 C。

## 5.6 多源环境场 / 风险航路

```text
observation operators
→ QC / alignment
→ reference / state estimate
→ uncertainty
→ forecast calibration
→ risk field
→ baseline route
→ chance / CVaR decision
```

核心叙事：**监测—预报—决策越长，不确定性越要一起往后传。**

来源经验：2025 D。

## 5.7 主观评价 / 美学 / 舒适度

```text
soft concept
→ observable mechanism
→ local state / change / structure
→ anti-gaming metric
→ calibration anchor
→ score / Pareto decision
→ sensitivity + external object
```

核心叙事：

\[
\boxed{Concept\rightarrow Mechanism\rightarrow Metric}
\]

而不是 `Concept → AHP`。

来源经验：2025 F。

---

# 6. 验证：不是证明“标准答案正确”，而是检验研究判断

建立五级证据塔：

1. **内部自洽**：范围、守恒、正定、round-trip；
2. **简单 baseline**：是否真的比朴素方案好；
3. **消融 / 敏感性**：提升来自哪里，参数是否稳定；
4. **独立验证**：独立时间、设备、对象、实验组；
5. **边界证据**：lower bound、最坏情况、置信区间、tail risk。

尽量做到 3–5 层。

## 6.1 数据验证纪律

先定义谁才是独立样本，再 split。

- 同一实验多行 → group split；
- 同一被试多个 epoch → subject/trial-aware split；
- 时间序列 → past → future；
- scaler / PCA / feature selection → fold 内 fit。

## 6.2 物理验证纪律

维护：

```text
symbol | meaning | unit | frame/time-scale | valid range
```

强制检查：

- 数量级；
- invariant；
- 独立公式/库/数据交叉验证；
- 高阶修正是否小于基础误差。

## 6.3 优化验证纪律

同时报告：

\[
\boxed{Feasibility + Objective + Lower\ Bound/Reference}
\]

随机算法多个 seed，不能只给一次最好结果。

## 6.4 主观评价验证纪律

没有真值时至少做：

```text
理论应然关系
→ simple baseline
→ 权重/阈值 sensitivity
→ frozen-parameter external object
```

---

# 7. 论文叙事：把“为什么”写在“怎么做”之前

完整专项见 [`NARRATIVE_AND_ARGUMENTATION_GUIDE.md`](NARRATIVE_AND_ARGUMENTATION_GUIDE.md)。

每一问建议采用七段研究链：

1. **核心矛盾**：本问真正难在哪里；
2. **观察/诊断**：什么事实支持我们的理解；
3. **建模判断**：因此把问题抽象成什么；
4. **数学模型**：变量、状态、约束和关系；
5. **求解方法**：怎样高效算；
6. **验证/边界**：为什么相信，哪里不能用；
7. **接口**：本问输出怎样进入下一问。

## 7.1 最小叙事单元

一段话尽量形成：

```text
观察 / 困难
→ 判断
→ 方法
→ 证据
→ 边界 / 下一步
```

## 7.2 多问之间必须有桥

常见桥：

- **输出桥**：前问状态成为后问输入；
- **限制桥**：后一问放宽前问假设；
- **资源桥**：高成本 reference → 低成本 surrogate；
- **决策桥**：预测 → 控制/优化；
- **不确定性桥**：估计误差 → 风险决策。

如果只能用“针对问题二，我们……”连接，说明整篇主线还不够清楚。

## 7.3 公式是论证节点

公式前回答：

> 为什么需要这个量？

公式后回答：

> 它增大/减小意味着什么？怎样进入下一步？

不要连续堆公式，再统一解释。

## 7.4 失败实验可以写，而且常常应该写

只要失败：

- 揭示一个事实；
- 改变后续路线；
- 在严格协议下得到；

它就是研究证据。

2025 C 的 ML 退回 Frangi、2025 D 的低 R² LSTM 转向其他数据源，都比“假装一开始就选对”更有研究味。

## 7.5 创新优先写在哪里

优先级：

```text
新问题表示
> 新状态/变量
> 新结构利用
> 新模型接口
> 新验证设计
> 针对性组合
> 改进算法名
```

评委通常更容易记住“你怎么看问题”，而不是“你把哪个算法改了一个系数”。

---

# 8. 回顾精读论文：真正值得学习的叙事模式

| 论文 | 真正的研究主线 | 叙事技巧 |
|---|---|---|
| 2022 C | 复杂规则 → 动态状态机 → 合法动作 → 调度策略 | 先重新定义题目本质 |
| 2020 F | 几何质心 evaluator → 控制 → 初始设计 → 姿态复用 | 基础模块逐问复用 |
| 2021 A | 重复计算 → 单次成本 → 存储 → 端到端 | 连续追问主导瓶颈 |
| 2024 B | WLAN 机理 → 特征 → 发送机会 → 速率 → 吞吐量 | 机理驱动特征，不做算法赛马 |
| 2023 B | butterfly → 稀疏 → 量化 → 联合 → Kronecker → 残差 | 约束逐层增加 |
| 2022 B | item → stack → stripe → plate → packing oracle → batch | 用工艺结构解释启发式必要性 |
| 2020 C | 轮数/通道/标签/样本 | 用“资源效率”统一分散小问 |
| 2024 F | 轨道 → 时间/参考系 → 时延 → 相位 → NHPP | 前问状态自然传后问 |
| 2024 E | measurement → state → forecast → control → sensor redesign | 完整闭环叙事 |
| 2025 C | pixel → geometry → roughness → uncertain 3D → drilling | 研究对象不断升级 |
| 2025 D | rich reference → constrained surrogate → field → forecast → route | reference hierarchy；失败实验推动选择 |
| 2025 F | 软概念 → 机制 → 指标 → 路径/评分 → 泛化 | 抽象概念先机制化 |

这些论文并非每个公式都正确。真正值得学的是：**它们如何让“为什么这样研究”成为整篇的骨架。**

---

# 9. 摘要：不是算法目录，而是压缩研究故事

摘要顺序建议：

```text
现实问题 + 关键困难
→ 核心建模洞察
→ 各问沿主线如何推进
→ 最关键证据/结果
→ 决策意义或适用边界
```

每问压缩成：

```text
任务 → 判断 → 方法 → 证据
```

## 30 秒测试

把摘要里所有算法名删掉。

如果评委仍能理解：

- 你认为问题本质是什么；
- 各问怎么连接；
- 有什么关键判断；
- 为什么值得相信；

说明摘要真正有建模思想。

---

# 10. 结论：证据能支持多少，就说多少

维护 claim ladder：

| 证据 | 合法结论 |
|---|---|
| self-consistency | 内部关系一致 |
| baseline comparison | 当前协议下更优 |
| independent test | 对未参与建模对象有泛化证据 |
| assumed intervention + simulation | 在该假设下模型预测改善 |
| real intervention | 才能更强谈实际效果 |

特别警惕：

```text
score ≠ calibrated probability
simulation ≠ empirical causality
grid spacing ≠ effective resolution
approximate optimum ≠ global optimum
```

知道自己不能说什么，本身就是科学性。

---

# 11. 实验与代码：让研究链可复核

推荐架构：

```text
project/
├─ data/
├─ src/
│  ├─ io.py
│  ├─ preprocess.py
│  ├─ features.py
│  ├─ model.py
│  ├─ solver.py
│  ├─ evaluator.py
│  ├─ baselines.py
│  └─ plotting.py
├─ configs/
├─ experiments/
└─ outputs/
   ├─ metrics.json
   ├─ tables/
   └─ figures/
```

实验记录至少包含：

```yaml
experiment_id:
code_commit:
data_version:
split_protocol:
seed:
assumptions:
model:
hyperparameters:
metric_definition:
baseline:
result:
interpretation:
next_decision:
```

这里新增 `interpretation` 和 `next_decision`：

> **实验不只是存一个数字，还要记录这个数字改变了什么研究判断。**

## 11.1 单一结果源

```text
experiment
→ metrics.json / csv
→ tables / figures / abstract numbers
```

禁止人工多处抄数字。

---

# 12. 三人队：按“研究职能”协作，不只是按代码/写作分工

## 初期

- A：题意、官方口径、研究问题画布；
- B：独立 baseline、数据诊断；
- C：论文骨架、符号表，同时记录每个选择“为什么”。

## 中期

- A：主模型/机理；
- B：第二路线、验证、反例；
- C：实时把 `Observation → Judgment → Method → Evidence` 写进正文。

## 后期

交叉验收：

- 写模型的人不能唯一验证自己的 evaluator；
- 写论文的人追问每个关键数字来源；
- 第三人随机手算表格、公式、单位；
- 对每个“显著、有效、概率、最优、提升”追问证据等级。

---

# 13. 停止规则：什么时候不再加模型

满足以下条件后，优先冻结：

1. 研究主线已经清楚；
2. hard constraints 全通过；
3. baseline 被稳定战胜或其作用已解释；
4. 主要结论有至少 2–3 层证据；
5. 主要失败模式与适用边界已经知道；
6. 再加复杂模型的收益小于验证/写作/复现风险。

最后 12–18 小时优先：

```text
补证据
补解释
补图表
查公式
查单位
查摘要数字
做交叉审计
```

而不是再换主模型。

---

# 14. 赛末一票否决级红旗

出现任何一个先停下：

1. 官方 metric 代码与题面不一致；
2. hard constraint 没有独立检查；
3. 同组/同人/同实验随机切 train-test；
4. 时间序列未来信息泄漏；
5. scaler/PCA/feature selection 全数据 fit；
6. 秒/天、m/km、dB/linear、参考系混用；
7. 插值网格被写成真实分辨率；
8. detector 输出直接冒充物理量；
9. 高级模型没有 baseline；
10. “概率”没有随机事件/校准定义；
11. “最优”没有可行性/下界/条件说明；
12. 情景仿真写成实测因果；
13. 摘要、正文、表格、代码数字不同；
14. 公式很多但没有任何实验/结论依赖它；
15. 结论中的形容词比证据更强。

最终审计使用 [`FINAL_AUDIT_CHECKLIST.md`](FINAL_AUDIT_CHECKLIST.md)。

---

# 15. 最终评价观：评委真正评价的是研究判断力

我不认为“只要让评委信服即可”足够准确，因为它可能把目标误导成包装。

更准确是：

> **让评委沿着研究链检查以后，关键步骤不需要靠脑补，且能看出你在不确定条件下做出了有水平的判断。**

评委实际上在判断：

1. **问题理解有没有洞察**：是否抓住真正机制/矛盾；
2. **建模选择是否有依据**：不是会什么用什么；
3. **证据是否有区分力**：能否真正支持你的解释；
4. **多问是否是一项连续研究**：而不是算法拼盘；
5. **结论是否校准**：知道假设、近似、概率、因果、最优的边界；
6. **表达是否高效**：评委能低成本重建你的研究逻辑。

高奖论文往往只需要 1–2 个真正亮点，但整条研究链不能有致命断点。

最后把整套手册压成一句：

> **不是证明“我有答案”，而是证明“我知道怎样科学地研究这个没有标准答案的问题”；模型可以近似，算法可以简单，但研究判断必须有依据，证据必须完整，结论必须不过界。**
