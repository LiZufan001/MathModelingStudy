# B24102860287｜模型与算法重构

> 目标：不是复刻原论文代码，而是在保留其“通信机理驱动特征工程”优点的基础上，把三个问题重构成一套**可解释、可验证、可复现**的统一模型。

---

# 1. 统一建模对象：一次实验，而不是一行 CSV

原数据中，一次实验 `e` 会产生多个 AP 行：

- 2AP：`i=1,2`；
- 3AP：`i=1,2,3`。

因此最自然的基本单位是：

\[
e=(location,protocol,thresholds,traffic,topology,RSSI\ network).
\]

每个实验内包含 AP 节点集合：

\[
\mathcal A_e=\{1,\ldots,K_e\},\quad K_e\in\{2,3\}.
\]

对 AP `i`，三个目标分别为：

\[
y^{(1)}_{e,i}=seq\_time_{e,i},
\]

\[
y^{(2)}_{e,i}=(MCS_{e,i},NSS_{e,i}),
\]

\[
y^{(3)}_{e,i}=throughput_{e,i}.
\]

这一步非常重要，因为：

> **数据切分、特征构造和模型结构都应尊重 experiment-level 依赖关系。**

---

# 2. Q1：从 carrier-sensing 机理构造发送机会特征

## 2.1 原始关系图

把网络表示为一个带权图：

\[
G_e=(V_e,E_e).
\]

节点包括 AP 与 STA，边权是 RSSI 统计。

对 AP `i` 与其他 AP `j`，构造：

\[
RSSI^{AP\to AP}_{j\to i}(t).
\]

对 AP/STA 关系同理。

---

# 3. 门限特征：不要只喂 RSSI 和 threshold 两列

题面给出 PD / ED / NAV 不同判决机制，因此建议构造：

## 3.1 超门限比例

\[
P_{NAV}^{j\to i}
=\frac1N\sum_t
\mathbf1\bigl(RSSI_{mean,j\to i}(t)>NAV_i\bigr),
\]

\[
P_{PD}^{j\to i}
=\frac1N\sum_t
\mathbf1\bigl(RSSI_{max,j\to i}(t)>PD_i\bigr),
\]

\[
P_{ED}^{j\to i}
=\frac1N\sum_t
\mathbf1\bigl(RSSI_{max,j\to i}(t)>ED_i\bigr).
\]

## 3.2 门限 margin

比“是否超过”更连续的量：

\[
M_{NAV}=RSSI_{mean}-NAV,
\]

并统计：

- mean margin；
- p10 / p50 / p90；
- positive margin ratio；
- minimum safety margin。

同理构造 PD/ED margin。

## 3.3 RSSI 分布特征

每条 RSSI 序列不要只留 mean/max：

```text
mean
std
min/max
p10/p25/p50/p75/p90
IQR
coefficient of variation
threshold exceedance ratio
burst length above threshold
```

若确实要保留时间序列，应使用真实 timestamp 对齐，而非仅按 index 拉伸。

---

# 4. Q1 的物理 baseline

发送机会可以先用一个解释性 baseline：

\[
\widehat{s}_{e,i}
=f\left(
traffic_i,
\sum_{j\ne i}P^{j\to i}_{sense},
K_e,
protocol,
location,
thresholds
\right).
\]

其中 `P_sense` 可由 PD/NAV/ED 综合得到。

最简单：

- linear / GAM；
- RandomForest；
- CatBoost。

正式比赛不必一上来深度学习。

---

# 5. Q1 推荐模型：grouped tree ensemble

训练：

```python
groups = source_file + ':' + test_id
GroupKFold(n_splits=5)
```

候选：

```text
RandomForest
ExtraTrees
CatBoost
LightGBM/XGBoost
```

模型选择指标：

\[
MAE,\ RMSE,\ MAPE
\]

同时报告 experiment-level fold 方差。

---

# 6. Q1 的解释不应该只靠 impurity importance

至少三层：

## 6.1 permutation importance

随机打乱某组特征，看验证误差恶化：

\[
I_j=L_{perm(j)}-L_{base}.
\]

## 6.2 group ablation

例如去掉全部 AP↔AP RSSI：

\[
\Delta L_{AP-AP}
=L_{without\ AP-AP}-L_{full}.
\]

## 6.3 SHAP

用来展示：

- 哪些 RSSI/margin 值使 seq_time 上升；
- 门限变化方向是否符合物理常识。

这才能把“重要”升级为“可解释”。

---

# 7. Q2：先判断 transmission regime，再预测 MCS/NSS

原题明确区分：

1. 主要同步发送：邻 AP 干扰少；
2. AP 互不听：可能同时发送，存在邻区干扰；
3. 部分互听：混合状态。

因此更自然的 Q2 结构是：

```text
carrier-sensing graph
        ↓
P(sync), P(async), P(mixed)
        ↓
state-conditioned SINR / SIR
        ↓
AMC target
        ↓
NSS → MCS
```

而不是把所有样本默认放进一个固定 SINR 矩阵。

---

# 8. 正确处理多干扰源功率

若 AP `i` 向 STA `s` 发送：

信号功率：

\[
P_s=10^{RSSI_{i\to s}/10}.
\]

干扰功率：

\[
P_I=\sum_{j\ne i}q_{ij}\,10^{RSSI_{j\to s}/10},
\]

其中 `q_ij` 可以表示 AP `j` 同时发送的概率，由 Q1 / sensing graph 估计。

噪声：

\[
P_N=10^{N_{dBm}/10}.
\]

于是：

\[
SINR_{dB}
=10\log_{10}\frac{P_s}{P_I+P_N}.
\]

若题面明确允许某场景忽略底噪、只有一个干扰源，才退化为：

\[
SINR_{dB}\approx RSSI_s-RSSI_i.
\]

---

# 9. Q2 不建议把 NSS/MCS 当普通无序 25 类

## 9.1 NSS 先预测

\[
\hat NSS=g_1(x).
\]

由于训练集中 NSS=2 极多，需要：

- class weight；
- balanced accuracy；
- macro-F1。

## 9.2 条件预测 MCS

\[
\hat MCS=g_2(x,\hat NSS).
\]

MCS 本身具有有序关系：

\[
0<1<\cdots<11.
\]

可使用：

- ordinal regression；
- ordered logit；
- CatBoost regression 后取整；
- cumulative ordinal classifier。

## 9.3 或预测 PHY Rate，但保留歧义

若预测：

\[
\widehat{R}_{PHY},
\]

反解 `(NSS,MCS)` 时不能简单假定一一映射。

建议：

\[
(\hat n,\hat m)
=\arg\max_{(n,m):R(n,m)\approx \hat R}
P(n,m\mid x).
\]

即用上下文概率解决同速率对应多个组合的问题。

---

# 10. Q2 如果想用深度学习，图模型比“人工矩阵 CNN”更自然

网络本身是图：

```text
AP0 ─ RSSI ─ AP1
 │             │
RSSI          RSSI
 │             │
STA0          STA1
```

因此可考虑：

- GNN；
- DeepSets；
- attention over AP/STA node pairs；
- permutation-invariant set encoder。

优势：

> 2AP/3AP 的节点数量变化不需要靠 padding/resize 假造二维图像结构。

但比赛时间有限时，树模型 + 统计特征通常更稳。

---

# 11. Q3：先写物理吞吐 baseline，再让 ML 学 residual

吞吐量本质：

\[
Throughput
=\frac{successful\ payload\ bits}{observation\ time}.
\]

可拆成：

\[
Throughput
\approx
AirtimeShare
\times PHYRate
\times MACEfficiency
\times SuccessRate.
\]

其中：

\[
AirtimeShare\approx \frac{seq\_time}{test\_dur}
\]

或由 Q1 的发送机会模型进一步修正；

\[
PHYRate=R(MCS,NSS).
\]

`MACEfficiency` 由：

- packet length；
- protocol；
- RTS/CTS；
- header/ACK；
- aggregation；

决定。

`SuccessRate` 若 PER 被题意允许使用：

\[
1-PER.
\]

如果 PER 不允许，则必须从基本信息预测，而不能直接读真实统计值。

---

# 12. 推荐 hybrid residual 模型

先建立：

\[
T^{phys}_{e,i}
=f_{phys}(seq\_time,MCS,NSS,traffic,packet\ length,\ldots).
\]

再学习：

\[
r_{e,i}=T_{e,i}-T^{phys}_{e,i}.
\]

使用 ML：

\[
\hat r=g(x).
\]

最终：

\[
\hat T=T^{phys}+\hat r.
\]

好处：

1. 模型更容易解释；
2. 物理 baseline 保证量级合理；
3. ML 只修正未建模的复杂效应；
4. 小数据时比纯 CNN 更稳。

---

# 13. Q3 模型候选优先级

建议按比赛时间排序：

```text
1. physics baseline
2. CatBoost / XGBoost residual
3. RandomForest / ExtraTrees
4. MLP
5. 真正有时间轴时再用 1D CNN / Transformer
6. 真正有图结构时再用 GNN
```

不要因为论文用了 CNN 就默认 CNN 是本题最优归纳偏置。

---

# 14. 官方 evaluator 必须独立

```python
def official_error(y_true, y_pred):
    return (y_pred - y_true) / y_true


def official_q90(y_true, y_pred):
    e = official_error(y_true, y_pred)
    return np.quantile(e, 0.90)


def official_accuracy(y_true, y_pred):
    return 1 - official_q90(y_true, y_pred)
```

如果担心官方描述对 signed error 有歧义，再额外报告：

```python
q90_abs = np.quantile(np.abs(e), 0.90)
```

但绝不能只算自己定义的版本而不说明。

---

# 15. 系统吞吐量 evaluator

题目还要求所有 AP 吞吐量之和：

对每次实验 `e`：

\[
Y_e=\sum_{i\in\mathcal A_e}y_{e,i},
\]

\[
\hat Y_e=\sum_{i\in\mathcal A_e}\hat y_{e,i}.
\]

然后再对**实验级**误差计算 CDF：

\[
e_e=\frac{\hat Y_e-Y_e}{Y_e}.
\]

注意不能把 AP 行随机混在一起再求系统总和。

---

# 16. 一套可复现训练框架

```text
raw CSV
  ↓
attach source_file + experiment_id
  ↓
GroupKFold outer split
  ↓
fit preprocessors ONLY on train fold
  ↓
Q1: mechanism features → seq_time
  ↓
Q2: sensing regime + RSSI/SIR → NSS/MCS
  ↓
Q3: physical throughput baseline + residual learner
  ↓
AP-level official evaluator
  ↓
experiment-level system throughput evaluator
  ↓
mean ± std across folds
  ↓
final refit on all train
  ↓
one-shot official test inference
```

---

# 17. 必做消融

| 版本 | AP↔AP RSSI | threshold margins | Q1 seq_time | MCS/NSS | PER | ML residual |
|---|---|---|---|---|---|---|
| A | ✓ |  |  |  |  |  |
| B | ✓ | ✓ |  |  |  |  |
| C | ✓ | ✓ | ✓ |  |  |  |
| D | ✓ | ✓ | ✓ | ✓ |  |  |
| E | ✓ | ✓ | ✓ | ✓ | ✓/按题意 |  |
| F | ✓ | ✓ | ✓ | ✓ | ✓/按题意 | ✓ |

回答：

> 每增加一个模块，90% 分位误差到底下降多少？

这比单报一个最终 >95% 有说服力得多。

---

# 18. 本篇重构后的核心范式

```text
业务机制
   ↓
可计算的物理特征
   ↓
严格 group split
   ↓
简单可靠 baseline
   ↓
必要时再加 ML
   ↓
官方 evaluator
   ↓
消融 + 跨场景验证
```

一句话：

> **Mechanism first, validation second, model complexity last.**
