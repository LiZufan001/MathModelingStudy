# 华为杯建模实战总手册｜从拿题到提交的统一决策框架

> 目标：把历年优秀论文里真正可迁移的经验压缩成一套**正赛可执行流程**。  
> 适用：研究生数学建模竞赛 / 华为杯，尤其适合三人队、建模与编程强、需要在有限时间内快速形成可信闭环的队伍。  
> 原则：**历史论文里的阈值、权重、超参数不直接迁移；只迁移方法结构、验证纪律和建模接口。**

---

# 0. 总纲：先把这 12 句话背下来

1. **先锁官方 evaluator，再建模型。**
2. **先检查 hard constraints，再比较 objective。**
3. **先做可信 baseline，再上高级算法。**
4. **先找结构，再找算法；结构通常比算法名更值钱。**
5. **复杂优化先写 evaluator / simulator，再写 optimizer。**
6. **数据题先定义“谁才是独立样本”，再切 train / validation。**
7. **时间序列只能让过去预测未来；同组样本不能随机拆散。**
8. **高精度物理题先查单位、参考系、时间尺度和量级。**
9. **测量值不等于真实状态；图像像素、雷达回波、插值网格都只是观测层。**
10. **近似模型必须有 invariant / feasibility / official-score 兜底。**
11. **下游决策最好接收 value + uncertainty + valid-domain，而不是一个裸点估计。**
12. **摘要、正文、表格、代码只能有一个结果源；禁止人工多处抄数字。**

如果比赛中只能保住一条主线，就是：

```text
Official task
   ↓
Evaluator + hard constraints
   ↓
Simple trustworthy baseline
   ↓
Exploit structure / mechanism
   ↓
Advanced model only where needed
   ↓
Strict validation
   ↓
Ablation / sensitivity / lower bound
   ↓
One-source results export
   ↓
Paper
```

---

# 1. 拿题后前 60–90 分钟：不要急着写算法

## 1.1 第一张纸只写 8 个东西

每道候选题统一填写：

| 项 | 必须写清楚 |
|---|---|
| 输入 | 文件、变量、单位、时间/空间分辨率 |
| 输出 | 每问最终必须交什么对象 |
| 官方指标 | RMSE / q90 / 成本 / 数量 / 概率 / 综合分等 |
| hard constraints | 违反即答案无效的约束 |
| soft objective | 可以权衡的目标 |
| 数据独立单位 | 人、实验、订单、时间窗、设备、路段、园林…… |
| 题目结构 | 图、时序、守恒、低秩、分块、聚类、物理机制、层次结构…… |
| 最大风险 | 数据脏、计算量、物理知识、标签少、验证难、附件大…… |

先把这张表写完，再讨论模型。

## 1.2 先判断“题型主骨架”，不要按题号猜

### A. 调度 / 组合优化 / 排样 / 组批
典型信号：大量离散决策、顺序、分配、覆盖、容量、冲突。

第一反应：

```text
可行性检查器
→ lower bound
→ 构造型 baseline
→ 结构化降维
→ local search / metaheuristic / MIP hybrid
```

参考：2022 C、2022 B。

### B. 物理机理 / 动态系统 / 高精度计算
典型信号：状态方程、几何、时延、轨迹、守恒、随机过程。

第一反应：

```text
单位/参考系账本
→ 可计算机理评价器
→ 解析/数值 baseline
→ 参数优化
→ invariant / external cross-check
```

参考：2020 F、2024 F。

### C. 数据预测 / 分类 / 信号学习
典型信号：训练集、标签、时序、分类、回归、无标签数据。

第一反应：

```text
独立样本单位
→ split protocol
→ majority/persistence/simple-tree baseline
→ feature/mechanism
→ ML
→ grouped / temporal validation
```

参考：2020 C、2024 B。

### D. 矩阵 / 算法复杂度 / 存储
典型信号：大矩阵、分解、近似、运算次数、硬件复杂度、压缩。

第一反应：

```text
官方复杂度账本
→ 结构诊断（低秩/稀疏/对称/块/FFT/Kronecker）
→ exact baseline
→ structured approximation
→ error-cost Pareto
```

参考：2021 A、2023 B。

### E. 图像 / 视频 → 下游决策
典型信号：检测、分割、跟踪只是前半问，后面还有几何/控制/重构。

第一反应：

```text
像素/检测结果
→ 物理标定
→ 状态估计
→ downstream model
→ end-to-end validation
```

参考：2024 E、2025 C。

### F. 多源环境场 / 风险 / 航路
典型信号：多传感器、插值/融合、预报、空间三维场、路径规划。

第一反应：

```text
observation operator
→ QC / alignment
→ probabilistic state
→ forecast + uncertainty
→ risk field
→ A*/Dijkstra baseline
→ chance/CVaR route
```

参考：2025 D 两篇。

### G. 主观评价 / 美学 / 舒适 / 吸引力
典型信号：软概念，没有直接标签，需要评分/排序/路线。

第一反应：

```text
概念 → 可观察机制
→ 状态/变化/结构/决策四类指标
→ 防刷分设计
→ calibration anchor
→ sensitivity + external consistency
```

参考：2025 F。

---

# 2. 选题：用“闭环难度”而不是“看起来会不会”判断

三道题比较时，对每题 0–5 分打分：

| 维度 | 低分好还是高分好 | 判断 |
|---|---|---|
| 题意歧义 | 低分好 | evaluator 是否明确 |
| 数据清洁度 | 高分好 | 能否快速读入/理解 |
| 可做 baseline | 高分好 | 2–3 小时内能否出第一版 |
| 可验证性 | 高分好 | 是否有真值/下界/机理/外部规律 |
| 我方知识匹配 | 高分好 | 是否有现成代码/知识 |
| 算力需求 | 低分好 | 是否必须重训练大模型 |
| 最终写作故事 | 高分好 | 各问能否形成连续链 |
| 最坏风险 | 低分好 | 卡在一个环节是否整题瘫痪 |

**优先选能形成“题意 → baseline → 改进 → 验证”闭环的题。**  
不要因为某题能堆更多高级算法就选它。

---

# 3. 建模第一原则：先写 evaluator，再写 model

## 3.1 所有题统一写 4 个函数

```python
def check_input(data):
    ...

def check_feasibility(solution, data):
    ...

def official_score(solution, data):
    ...

def sanity_report(solution, data):
    ...
```

### `check_feasibility`
只处理 hard constraints。

例：
- 批次数容量；
- 排样是否越界/重叠；
- 调度是否违反 FIFO/工艺规则；
- 航路是否进入禁飞区；
- 概率/相关系数是否超合法范围。

### `official_score`
**必须逐字对应题目公式。**

不要在模型代码里复制一份，在画图代码里再复制另一份。

### `sanity_report`
放不一定是题目要求、但能抓错的 invariant：

- `0 <= rho <= 1 + tol`；
- 概率和≈1；
- 守恒残差≈0；
- 单位数量级；
- 路径长度 ≥ 欧氏距离；
- 批次数 ≥ 面积/容量下界；
- RMSE 若变量范围 [0,1] 则不应 >1。

## 3.2 evaluator 必须先单元测试

至少做：

1. 人工构造一个能手算的小样本；
2. 完全正确解应得预期分；
3. 故意违反一条约束，必须被抓到；
4. 边界值测试；
5. 极端输入测试。

这一步能直接避免 2023 B 的 `norm`/`norm²`、2024 B 的 q10/q90、2024 F 的 χ² 公式之类灾难。

---

# 4. Baseline-first：高级模型的存在必须有理由

## 4.1 每问至少准备 1 个“笨但可信”基线

| 题型 | Baseline |
|---|---|
| 回归 | 均值 / 线性回归 / RF |
| 时序 | persistence `ŷ(t+h)=y(t)` |
| 分类 | majority / logistic / RF |
| 路径 | 直线 / Dijkstra / A* |
| 调度 | FIFO / greedy / earliest-ready |
| 排样 | FFD/BFD / area lower bound |
| 矩阵 | 原始 exact 算法 |
| 融合 | IDW / OI |
| 主观评分 | 单指标 / 等权模型 |

论文里高级模型的结论必须至少是：

```text
advanced - baseline = improvement
```

而不是只报高级模型自己的分数。

## 4.2 模型升级只允许因为“发现了明确失败模式”

例：

```text
baseline residual 呈非线性
→ 加 nonlinear learner

随机切分很好但跨设备崩
→ domain/group modeling

精确求解规模爆炸
→ decomposition / heuristic

NWP 有系统偏差
→ calibration layer

平均误差不错但危险峰值被抹掉
→ tail-aware loss / risk metric
```

**没有失败证据，就没有必要升级。**

---

# 5. 优化题统一套路

## 5.1 复杂调度：simulator-first

先写状态机：

```text
state
→ enumerate legal actions
→ transition
→ cost
→ next state
```

硬约束负责生成合法动作；软目标负责在合法动作中选。

这比把所有业务规则直接塞进一个巨大目标函数更稳。

## 5.2 任何近似优化先给 lower bound

常见下界：

- 面积/容量下界；
- 最短欧氏距离；
- 每类任务最少机器数；
- 松弛 LP/MIP；
- 忽略部分约束后的最优值；
- 信息论/矩阵秩下界。

报告：

\[
Gap = \frac{Obj-LB}{LB}.
\]

如果没有 known optimum，下界就是近似算法可信度的核心证据。

## 5.3 结构化降维优先于暴力 metaheuristic

典型：

```text
item → stack → stripe → plate
matrix → blocks / low-rank factors
vehicle → legal sequence groups
road grid → salient graph
raw events → state aggregates
```

先减少决策自由度，再搜索。

## 5.4 约束多时：构造可行解 + 局部改进

推荐：

```text
Greedy construction
→ repair
→ local search / tabu / SA
→ perturb
→ accept/reject
```

而不是让 GA/PSO 自己“学会”满足所有复杂约束。

## 5.5 多目标先画 Pareto，不要急着拍权重

如果题目本质是：

- 路径短 vs 风险低；
- 趣味高 vs 重复少；
- 存储少 vs 误差小；
- 成本低 vs 公平；

先输出 Pareto frontier。

只有必须给唯一方案时，再解释 preference / knee point / policy weight。

---

# 6. 数据题：最重要的是 split，而不是模型

## 6.1 第一问：谁才是“独立样本”？

常见错误：

```text
一次实验生成多行
→ 按行 random split
```

正确：按实验/人/订单/设备/路段/场次 group。

推荐：

```python
GroupKFold
GroupShuffleSplit
LeaveOneGroupOut
```

## 6.2 时间序列只能过去 → 未来

禁止：

```text
13:00 train
13:01 test
13:02 train
```

推荐：

- blocked split；
- rolling-origin；
- walk-forward；
- leave-one-day/event-out。

## 6.3 preprocessing 也必须在 fold 内 fit

以下都属于模型训练的一部分：

- scaler；
- imputer；
- PCA；
- feature selection；
- target encoding；
- threshold tuning；
- class resampling。

必须：

```text
train fold fit
→ transform validation
```

## 6.4 类别不平衡先报 baseline

先算：

\[
Accuracy_{majority}.
\]

再报：

- macro-F1；
- balanced accuracy；
- per-class recall；
- confusion matrix；
- exact-pair accuracy（多输出分类）。

## 6.5 安全任务不要只看 RMSE

风险事件要报：

- POD/Recall；
- FAR；
- CSI；
- tail quantile；
- calibration / Brier；
- lead time。

平均误差小但危险峰值漏掉，是失败模型。

---

# 7. 物理 / 工程题：先做“量纲账本”

## 7.1 每个关键变量至少写 4 列

| symbol | meaning | unit | frame/time-scale/domain |
|---|---|---|---|
| `r` | 位置 | km or m | GCRS/BCRS |
| `t` | 时间 | s/day | UTC/TT/TDB |
| `ρ` | 密度 | veh/km | road segment |
| `ε` | 耗散率 | m²/s³ | turbulence model |

## 7.2 三个强制 sanity check

### 数量级
结果是否在现实数量级？

### invariant
守恒、正定、范围、几何恒等式是否满足？

### independent cross-check
不能只做“正算→反算”自洽；尽量用另一套公式/库/下界交叉。

## 7.3 高阶修正必须服从误差预算

如果基础量误差 10 ms，就没必要把 10⁻⁹ s 修正写成核心贡献。

按误差量级排序：

```text
dominant error
→ second-order error
→ tiny correction
```

先解决大项。

---

# 8. 图像 / 视频 / 传感器题：观测 ≠ 状态

## 8.1 强制写 observation layer

```text
raw signal / pixel
→ detector / segmenter
→ calibration
→ physical quantity
→ state model
```

例：车辆像素位移不等于真实速度，必须有 homography / scale calibration。

## 8.2 上游精度要用下游指标验收

特征选择、通道选择、分割优化不能只报自己的局部指标。

必须继续跑最终任务：

```text
selected features
→ downstream classifier
→ final task metric
```

## 8.3 图像 → 几何 → 三维时传 uncertainty

建议接口：

```python
estimate = {
  "value": ...,
  "cov": ...,
  "quality": ...,
  "valid_domain": ...
}
```

不要从二维分割直接跳到一个看似精确的三维概率。

---

# 9. 多源融合 / 环境场 / 航路：四层分开

## 9.1 Observation
设备测了什么，不要直接叫 truth。

## 9.2 State estimation
IDW/OI/3DVAR/variational/Kalman。

输出至少：

```text
state mean
uncertainty
observation density
nearest-observation distance
effective resolution
```

**grid spacing ≠ effective resolution。**

## 9.3 Forecast
NWP/ML 都先做 bias correction / calibration。

特别是 NWP：

```text
NWP ≠ truth
NWP → bias calibration → forecast distribution
```

## 9.4 Decision
先 Dijkstra/A*，再考虑：

\[
\min E[J]+\lambda\operatorname{CVaR}_{0.95}(J)
\]

或 chance constraint：

\[
P(R\le R_{safe})\ge 1-\epsilon.
\]

高级风险规划必须和普通 A*/最短路在**同一 evaluator**下比较。

---

# 10. 主观评价题：Concept → Mechanism，而不是 Concept → AHP

## 10.1 四类机制扫描

任何“好看/有趣/舒适/协调/活力”先拆：

1. 状态：现在什么样；
2. 变化：前后变了多少；
3. 结构：整体如何组织；
4. 决策：人在其中如何行动。

## 10.2 指标设计强制问“怎么作弊”

例：
- 路径切短能否刷变化次数？
- 路线变长能否刷累计得分？
- 复制高度相关指标能否重复投票？
- 极端值会不会把 min-max 拉坏？

指标要有 denominator / cap / saturation / robust normalization。

## 10.3 “适量最好”用单峰效用

\[
S(x)=\exp\left[-\frac{(x-x^*)^2}{\sigma^2}\right]
\]

适合表达：过少与过多都差。

## 10.4 AHP 只表达价值偏好

推荐：

\[
w(\lambda)=\lambda w_{AHP}+(1-\lambda)w_{obj}
\]

其中 `w_obj` 可取 entropy/CRITIC/regression-derived。

必须扫权重并报告排名稳定性。

## 10.5 无标签评价的四层验证

```text
1. theoretical expected relation
2. simple baseline comparison
3. sensitivity / perturbation
4. frozen-parameter external object
```

不能只写“结果符合实际”。

---

# 11. 结果可信度：五级证据塔

从弱到强：

1. **内部自洽**：正算反算、曲线看起来合理；
2. **朴素 baseline**：比简单方法好；
3. **消融/敏感性**：知道提升来自哪里；
4. **独立验证**：独立对象/时间/设备/数据；
5. **边界证据**：最坏场景、lower bound、置信区间、tail risk。

尽量做到 3–5 层，不要停在第 1 层。

---

# 12. 统一实验协议

每一个模型实验至少记录：

```yaml
experiment_id:
code_commit:
data_version:
split_protocol:
seed:
preprocessing:
features:
model:
hyperparameters:
constraints:
metric_definition:
baseline:
result:
notes:
```

随机算法至少多 seed：

```text
mean ± std
best
worst
```

不要只挑最好的一次。

---

# 13. 推荐代码架构

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
├─ outputs/
│  ├─ metrics.json
│  ├─ tables/
│  └─ figures/
└─ paper/
```

## 13.1 单一结果源

所有表格和摘要数字从：

```text
outputs/metrics.json
```

自动生成。

禁止：

```text
运行结果
→ 人工抄到 Excel
→ 再抄正文
→ 再抄摘要
```

这正是历年优秀论文中出现结果版本漂移的根源之一。

## 13.2 输出对象要结构化

```python
result = {
    "feasible": True,
    "official_score": ...,
    "secondary_metrics": {...},
    "uncertainty": {...},
    "runtime": ...,
    "seed": ...,
    "config": ...
}
```

---

# 14. 图表模板：每张图必须回答一个问题

## 14.1 模型机制图
回答：变量如何传递？

```text
Input → State → Model → Decision → Validation
```

## 14.2 Baseline 对比表
回答：高级模型是否真的必要？

| Model | Primary metric | Secondary | Runtime | Feasible |
|---|---:|---:|---:|---|

## 14.3 Sensitivity curve
回答：参数是不是拍脑袋？

横轴参数，纵轴主指标；标稳定平台，不只标最佳点。

## 14.4 Error / residual plot
回答：模型在哪里失败？

- residual vs prediction；
- error by group/time/class；
- worst cases。

## 14.5 Pareto frontier
回答：两个目标怎样权衡？

## 14.6 Uncertainty map / interval
回答：哪里不可信？

## 14.7 Ablation table
回答：提升来自哪个组件？

| Variant | Metric | Δ |
|---|---:|---:|

## 14.8 Final decision figure
回答：最终答案是什么？

评委应该能在一张图里看到最终路线/分配/场/推荐位置。

---

# 15. 论文写法：按“判断”组织，不按算法名组织

## 15.1 每一问固定五段

1. **题意抽象**：本问本质是什么；
2. **为什么这个模型**：数据/机制/失败模式；
3. **模型与算法**：公式、输入输出；
4. **验证**：baseline、hard constraints、敏感性；
5. **结论与边界**：回答题目，不夸大。

## 15.2 不要写成算法展览

差：

```text
先介绍 RF
再介绍 XGBoost
再介绍 LSTM
再介绍 GA
```

好：

```text
因为 residual 呈非线性 → XGBoost
因为数据有时间依赖 → blocked validation
因为输出进入决策 → tail risk
```

## 15.3 摘要必须由最终结果自动回填

摘要每问：

```text
任务 → 方法 → 最关键结果 → 验证/边界
```

不写没在正文实验证明的高级术语。

---

# 16. 模型停止规则：什么时候不要再加模型

满足以下 4 条就应该收手，转向验证与写作：

1. hard constraints 全通过；
2. 比 baseline 有稳定提升；
3. 主要误差来源已经解释；
4. 再加复杂模型的边际提升小于验证/写作风险。

尤其最后 12–18 小时：

> **宁可给现有模型补一个严格验证，也不要再加一个未经消融的新模型。**

---

# 17. 三人队推荐工作流

适合“两人建模/编程 + 一人建模/写作”的队形。

## 阶段 A｜拿题与 baseline

- A：题意/evaluator/数据检查；
- B：独立做 baseline；
- C：搭论文骨架、符号表、题面要求清单。

## 阶段 B｜主模型

- A：核心模型 1；
- B：核心模型 2 / evaluator / 验证；
- C：实时写“为什么选这个模型”，同步图表占位。

## 阶段 C｜验收

交叉换手：

- 写代码的人不负责唯一验收自己的 evaluator；
- 写论文的人拿结果逐项追问来源；
- 第三人随机抽表格一行手算。

## 阶段 D｜收口

冻结模型后只允许：

```text
修 bug
补验证
补图
修解释
修排版
```

不允许无止境换算法。

---

# 18. 从 13 篇训练材料提炼出的“高价值模式”

| 模式 | 来源训练 | 正赛用途 |
|---|---|---|
| simulator-first | 2022 C | 复杂规则调度 |
| lower bound + heuristic | 2022 B | NP-hard 近似质量 |
| 机理评价器 + 策略降维 | 2020 F | 动态优化 |
| 总成本=调用次数×单次成本 | 2021 A | 算法复杂度 |
| 结构化分解优先 | 2023 B | 矩阵/硬件 |
| group/time split | 2024 B、2020 C | 防数据泄漏 |
| unit/frame/time-scale ledger | 2024 F | 高精度物理 |
| measurement→state→control | 2024 E | 视频/传感器决策 |
| estimate + uncertainty + domain | 2025 C | 2D→3D/概率 |
| grid spacing ≠ effective resolution | 2025 D | 环境场融合 |
| NWP/forecast 先校正 | 2025 D | 风险规划 |
| concept→mechanism→metric | 2025 F | 主观评价 |
| anti-gaming metric design | 2025 F | 综合评价/路径 |

---

# 19. 最危险的 20 个红旗

看到任何一个就停下来检查：

1. evaluator 公式和官方题面不完全一样；
2. 结果超出理论范围；
3. 单位换了但代码没换；
4. 秒直接加到“天”；
5. m/km 混用；
6. 同一实验多行随机切 train/test；
7. 时间序列随机切；
8. scaler/PCA 在全数据 fit；
9. q90 实际取 q10；
10. “准确率”其实只是多输出坐标平均；
11. 把训练误差叫验证误差；
12. 网格插值后宣称真实分辨率提高；
13. detector 输出直接当物理量；
14. 高级算法没有 baseline；
15. 报最优解但没证明 feasible；
16. 报“概率”却没有随机事件定义；
17. 相似度几乎全是 0.98+ 还不检查饱和；
18. 新增几十个公式但没有实验对应；
19. 摘要、正文、表格数字不同；
20. 附录代码缺数据时自动生成 synthetic data 继续跑。

---

# 20. 最终评分观：评委真正需要相信什么

一篇强论文最终要让评委相信四件事：

### 1. 你理解了题
官方目标和 hard constraints 没读错。

### 2. 你的模型为什么合理
结构、机理或数据证据支持选型。

### 3. 你的数字为什么可信
验证、baseline、下界、敏感性、独立测试完整。

### 4. 你的结论有多大边界
知道什么时候能用，什么时候不能用。

高级算法只能帮助第 2 点，不能替代 1、3、4。

---

# 21. 比赛现场最简流程

```text
读题
↓
写 evaluator / hard constraints
↓
数据与单位审计
↓
baseline
↓
找结构/机制
↓
主模型
↓
严格 split / lower bound / invariant
↓
ablation + sensitivity
↓
冻结
↓
自动出图表
↓
交叉复核
↓
提交
```

最后记一句：

> **模型可以近似，验证不能含糊；算法可以简单，证据必须完整。**
