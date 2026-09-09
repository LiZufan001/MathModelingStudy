# 比赛速查：从 B24102860287 提炼的“机理 + 数据驱动”题打法

> 适用：通信、工业、交通、能源、设备监测等题目——有明确业务机制，又给大量实测数据，希望预测/评价一个工程指标。

---

# 0. 什么时候想到这篇

题目若同时出现：

- 多个物理/协议变量；
- 阈值判决；
- 同一次实验产生多行关联数据；
- 多问之间存在上游→下游关系；
- 需要解释特征重要性；
- 需要预测；
- 官方给自定义评价指标；
- 数据量不算大但特征很多；

优先采用：

> **mechanism-driven feature engineering + grouped validation + simple baseline first**

---

# 一、开题后第一小时：先画两张图

## 图 1：业务机制图

例如 WLAN：

```text
RSSI / threshold
      ↓
carrier sensing
      ↓
send opportunity
      ↓
SINR / channel quality
      ↓
MCS,NSS / PHY rate
      ↓
throughput
```

## 图 2：数据生成图

```text
experiment e
 ├─ AP0 row
 ├─ AP1 row
 └─ AP2 row
```

必须回答：

> 哪些 CSV 行并不独立？

---

# 二、先建“字段许可表”

| 字段 | 训练可见 | 测试可见 | 推理时允许 | 类型 |
|---|---|---|---|---|
| 原始输入 | ✓ | ✓ | ✓ | input |
| 中间标签 | ✓ | ? | 看题意 | intermediate |
| 最终目标 | ✓ | ✗ | ✗ | target |
| 特殊放行字段 | ✓ | ✓ | 题面明确 | allowed extra |

原则：

> **文件里存在一个字段，不等于比赛规则允许把它当输入。**

---

# 三、官方 evaluator 必须比模型先写

```text
题面公式
 ↓
独立 Python function
 ↓
人工小样例
 ↓
unit test
 ↓
锁定不再修改
```

尤其检查：

```text
min/max 方向
10% / 90%
signed / absolute
百分数 / 小数
per-row / per-group
mean / sum
```

---

# 四、阈值机制最常用的特征模板

若业务有：

```text
measurement x
threshold τ
```

不要只使用 `x_mean` 和 `τ`。

优先构造：

\[
margin=x-\tau,
\]

\[
P_{over}=P(x>\tau),
\]

以及：

```text
mean margin
min margin
p10/p50/p90 margin
above-threshold run length
crossing count
```

这是从业务规则直接导出的高价值特征。

---

# 五、功率/分贝题的 10 秒检查

看到 dB/dBm：

### 可以直接做差

因为差表示比值：

\[
P_1(dBm)-P_2(dBm).
\]

### 不能直接做功率和

错误：

\[
-60+(-70).
\]

正确：

\[
10\log_{10}
\left(10^{-60/10}+10^{-70/10}\right).
\]

多干扰源同理。

---

# 六、同一实验多行：禁止 row random split

如果：

```text
一个病人多条记录
一台设备多个传感器
一个订单多件商品
一次网络实验多个 AP
一场比赛多个球员
```

都要警惕 group leakage。

使用：

```python
GroupKFold
GroupShuffleSplit
```

group 必须对应真实独立实体/实验。

---

# 七、预处理器 fit 的黄金规则

```text
train：fit + transform
validation：transform only
test：transform only
```

适用于：

```text
imputer
scaler
PCA
feature selector
encoder
normalization statistics
interpolation hyperparameters
```

---

# 八、类别不平衡：先算傻瓜 baseline

任何分类前先打印：

```python
y.value_counts(normalize=True)
```

如果最大类占 70%，模型 accuracy=75% 并不惊艳。

必须比较：

```text
majority baseline
macro-F1
balanced accuracy
confusion matrix
```

---

# 九、当分类标签本身有结构时，不要强行 one-hot

例如：

```text
MCS 0~11
风险等级 1~5
故障严重度
价格档位
容量等级
```

考虑：

```text
ordinal regression
continuous surrogate regression
hierarchical classification
multitask learning
```

2024 B 的经典案例：

```text
25-class (MCS,NSS) collapse
        ↓
转向 PHY Rate / 层次化建模
```

---

# 十、什么时候 CNN 是合理的？

问两个问题：

## 1. 邻接有意义吗？

图像：相邻像素有意义。

时间序列：相邻时间点有意义。

频谱：相邻频率有意义。

## 2. 平移局部模式可复用吗？

若只是：

```text
age, RSSI_mean, protocol, nav, mcs, loc_id...
```

按 DataFrame 列顺序排成向量，Conv1d 未必合理。

表格数据优先：

```text
CatBoost
LightGBM/XGBoost
RF/ExtraTrees
MLP
```

---

# 十一、机理模型和 ML 怎么结合

最推荐：

```text
physics / rule baseline
        ↓
residual = truth - baseline
        ↓
ML learns residual
```

即：

\[
\hat y=f_{physics}(x)+g_{ML}(x).
\]

优点：

- 解释清楚；
- 量级不容易崩；
- 小数据更稳；
- 可做消融。

---

# 十二、特征重要性报告模板

不要只给：

```text
feature A = 82%
```

至少：

| 特征组 | impurity importance | permutation Δloss | remove-group Δloss |
|---|---:|---:|---:|
| A | | | |
| B | | | |
| C | | | |

三种结果方向一致，解释才稳。

---

# 十三、多问题串联必须写“接口表”

| 上一问输出 | 下一问是否使用 | 如何使用 |
|---|---|---|
| Q1 prediction | Q2 | feature / probability / constraint |
| Q1 prediction | Q3 | feature |
| Q2 prediction | Q3 | 若题面允许真实值，则说明为何不用预测值 |

避免论文说“结合 Q1”，代码却没有任何 Q1 变量。

---

# 十四、插值/重采样必须做敏感性

若把序列固定到长度 `L`：

```text
L=128
256
384
512
640
```

至少试 3 个。

报告：

```text
validation metric
runtime
memory
```

否则 `L=540` 只是经验超参数。

---

# 十五、正式比赛的验证阶梯

## Level 0
傻瓜 baseline。

## Level 1
随机 group holdout。

## Level 2
5-fold GroupKFold。

## Level 3
跨场景：leave-location-out。

## Level 4
消融。

## Level 5
敏感性 / robustness。

不要一开始花 6 小时调神经网络，却还停留在 Level 0 的验证质量。

---

# 十六、数据题论文的推荐结构

```text
1. 业务机制 / 数据生成机制
2. 数据质量与独立样本定义
3. 特征工程
4. baseline
5. 改进模型
6. validation protocol
7. ablation / feature interpretation
8. official metric
9. test prediction
10. limitations
```

验证方法不要藏在“模型求解”最后两句话里。

---

# 十七、赛中 15 分钟审计清单

- [ ] 一行数据真的独立吗？
- [ ] group 是否跨 train/val？
- [ ] test 是否参与 fit？
- [ ] target-derived 特征是否泄漏？
- [ ] 测试时这个字段真的可获得吗？
- [ ] majority baseline 是多少？
- [ ] 官方 q10/q90 有没有写反？
- [ ] signed / absolute 是否一致？
- [ ] pair accuracy 是否真的要求两个坐标同时正确？
- [ ] dBm 功率和是否先转线性？
- [ ] CNN 邻域是否有真实语义？
- [ ] 正文声称的机制是否真的进入代码？
- [ ] 上一问结果是否真的进入下一问？
- [ ] 是否有至少一个简单模型 baseline？
- [ ] 是否保留 OOF predictions 方便统一复算？

---

# 十八、比赛现场一句话

> **数据题最危险的不是模型不够复杂，而是模型“看到了不该看到的数据”，或评价器“算了一个不是题目要求的指标”。**
