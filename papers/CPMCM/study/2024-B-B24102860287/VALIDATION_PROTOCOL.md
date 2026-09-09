# B24102860287｜验证协议与指标审计

> 这份文件是本篇精读最重要的附加成果之一。用途：以后遇到“机器学习 + 多行同组数据 + 官方自定义指标”的题，直接按此检查，防止模型本身没问题，却因为数据泄漏或 evaluator 写错导致结论失真。

---

# 1. 第一原则：先定义“独立样本”是什么

2024 B 的 CSV 一行是一个 AP，但**独立实验单位并不是一行**。

一次实验 `test_id` 对应：

- 2AP：通常两行；
- 3AP：通常三行。

同组行共享大量条件：

```text
location
protocol
thresholds
traffic
AP topology
joint RSSI environment
```

所以必须先建立：

```python
group_id = source_file + '::' + str(test_id)
```

训练/验证必须按 `group_id` 隔离。

---

# 2. 对原论文随机切分的复核

我们对仓库原始训练 CSV 重算得到：

## 2AP

- 总行数：394；
- Q1 有 `seq_time` 标签：392 行；
- 独立实验组：196 组。

论文 2AP RF 使用：

```python
train_test_split(..., test_size=0.2, random_state=42)
```

按同样随机种子模拟后：

- 验证集约 79 行；
- 其中约 **82.3%** 的验证行，其同实验兄弟 AP 已经进入训练集。

## 3AP

- 总行数 / 有标签行数：858；
- 独立实验组：286 组。

论文 3AP RF 使用：

```python
test_size=0.05
```

模拟后：

- 验证集约 43 行；
- **100%** 验证行对应实验组在训练集中已经出现。

## Q3 2AP

论文代码：

```python
test_size=0.01
```

392 行只留下约 **4 行**。

同样模拟后，这 4 行：

- **100%** 与训练集共享实验组。

因此这种验证不能支撑“对新实验场景泛化良好”的强结论。

---

# 3. 正确的数据切分层次

## Level A：GroupShuffleSplit

比赛最快可用：

```python
from sklearn.model_selection import GroupShuffleSplit

gss = GroupShuffleSplit(
    n_splits=1,
    test_size=0.2,
    random_state=42,
)
```

`groups=group_id`。

优点：简单快速。

## Level B：GroupKFold

推荐正式实验：

```python
GroupKFold(n_splits=5)
```

得到：

\[
metric=mean\pm std.
\]

比一次随机划分更稳。

## Level C：场景外推测试

更加接近真正工程泛化：

```text
leave-one-location-out
leave-one-NAV-setting-out
leave-one-protocol/topology-combination-out
```

如果模型在这种测试上仍然稳定，才有资格说“泛化能力较好”。

---

# 4. 所有预处理器只能在训练 fold 上 fit

错误模板：

```python
X = imputer.fit_transform(X_all)
X = scaler.fit_transform(X)
X_train, X_val = split(X)
```

这会让验证集统计信息提前进入训练过程。

正确模板：

```python
X_train, X_val = split_by_group(raw_X)

imputer.fit(X_train)
X_train = imputer.transform(X_train)
X_val   = imputer.transform(X_val)

scaler.fit(X_train)
X_train = scaler.transform(X_train)
X_val   = scaler.transform(X_val)
```

最稳的是 sklearn `Pipeline`。

---

# 5. 官方 test 绝不能参与 preprocessing fit

论文 Q1 3AP 预处理流程中，训练数据与官方 test 曾在部分阶段先合并再统一编码/标准化，随后再拆开。

即使：

- RF 对尺度不敏感；
- one-hot 只看类别；

这种习惯仍属于 transductive preprocessing。

比赛应保持：

```text
train determines everything
official test only transform + predict
```

包括：

- 类别词表；
- imputer；
- scaler；
- PCA；
- feature selection；
- interpolation parameter；
- threshold tuning。

---

# 6. Q1 的正确评价体系

不要只有一个 MSE。

至少报告：

\[
MAE=\frac1N\sum_i|\hat y_i-y_i|,
\]

\[
RMSE=\sqrt{\frac1N\sum_i(\hat y_i-y_i)^2},
\]

以及：

\[
R^2.
\]

如果 `seq_time` 分布跨度大，可增加：

\[
MAPE.
\]

但目标接近 0 时需谨慎。

### 分场景

同时报告：

```text
2AP
3AP
TCP
UDP
location
NAV setting
```

防止平均值掩盖局部失效。

---

# 7. Q1 特征重要度的正确验证

原论文主要依赖 RF impurity importance。

建议三套并行：

## 7.1 impurity importance

仅作快速参考。

## 7.2 permutation importance

在独立 validation fold 上做：

```python
permutation_importance(model, X_val, y_val)
```

## 7.3 group ablation

按语义组删：

```text
AP↔AP RSSI
AP↔STA RSSI
thresholds
protocol
location/topology
traffic
```

报告：

\[
\Delta RMSE.
\]

只有当三者方向一致，才能比较有底气地说“AP↔AP RSSI 是首要因素”。

---

# 8. Q2：accuracy 必须先定义清楚

目标是一个 pair：

\[
(NSS,MCS).
\]

## 8.1 Exact pair accuracy

必须有：

\[
Acc_{pair}
=\frac1N\sum_i
\mathbf1(\hat NSS_i=NSS_i\land\hat MCS_i=MCS_i).
\]

代码：

```python
pair_ok = (
    (pred_nss == true_nss)
    & (pred_mcs == true_mcs)
)
pair_acc = pair_ok.mean()
```

## 8.2 单坐标准确率

分别报告：

```text
NSS accuracy
MCS accuracy
```

但不要把两者平均后称为 pair accuracy。

---

# 9. 类别不平衡下的 baseline

原始训练集重新统计：

| 数据 | `(2,11)` 占比 | `NSS=2` 占比 |
|---|---:|---:|
| 2AP | **63.52%** | **96.94%** |
| 3AP | **41.38%** | **98.02%** |

恒定预测 `(2,11)`：

| 数据 | exact pair accuracy | 坐标级 accuracy |
|---|---:|---:|
| 2AP | 63.52% | **80.23%** |
| 3AP | 41.38% | **69.70%** |

因此任何“86.73% accuracy”必须说明：

> 比哪个 baseline 提升多少？

否则这个数字单独看没有意义。

---

# 10. Q2 推荐额外指标

由于 MCS 有序、类别不平衡：

```text
pair accuracy
macro-F1
balanced accuracy
NSS accuracy
MCS accuracy
mean |MCS_pred - MCS_true|
confusion matrix
```

如果预测 PHY Rate：

```text
MAE in Mbps
relative error
mapping-back pair accuracy
```

---

# 11. Q3 官方指标：一定先写单元测试

题面：

\[
error_i=\frac{\hat y_i-y_i}{y_i}.
\]

90% 分位：

\[
q_{0.9}=Quantile_{0.9}(error).
\]

精度：

\[
Acc=1-q_{0.9}.
\]

推荐：

```python
def official_accuracy(y_true, y_pred):
    e = (y_pred-y_true)/y_true
    q90 = np.quantile(e, 0.90)
    return 1-q90, q90
```

---

# 12. 防止 10% / 90% 写反的测试

手工构造：

```python
errors = np.arange(100)/100
```

应满足：

```text
q10 ≈ 0.10
q90 ≈ 0.90
```

若代码：

```python
sorted_errors[int(N*0.1)]
```

得到的是 q10，而不是 q90。

这正是公开附录出现的问题。

---

# 13. signed error 与 absolute error 必须分开

官方文字写：

\[
(\hat y-y)/y.
\]

这有符号。

但很多人直觉上想评“误差大小”，会写：

\[
|\hat y-y|/y.
\]

两者不同。

建议比赛中同时计算：

```text
official signed q90
absolute-error q90
MAE/MAPE
```

论文主表仍以题目官方定义为准。

---

# 14. Q3 AP-level 和 system-level 必须分别算

## AP level

每个 AP 行：

\[
e_{e,i}=\frac{\hat y_{e,i}-y_{e,i}}{y_{e,i}}.
\]

对所有 AP 行求 q90。

## System level

先按实验聚合：

\[
Y_e=\sum_i y_{e,i},
\]

\[
\hat Y_e=\sum_i\hat y_{e,i}.
\]

再：

\[
e^{sys}_e=\frac{\hat Y_e-Y_e}{Y_e}.
\]

不能把 AP-level error 平均后冒充 system error。

---

# 15. Q3 训练指标不能冒充验证指标

错误结构：

```text
train batch
 ↓
collect training errors
 ↓
q90
 ↓
call it validation accuracy
```

正确：

```text
train fold -> fit model
validation fold -> predict once
validation predictions -> official evaluator
```

调参结束后，test 只推理一次。

---

# 16. 模型选择不能看 official test

推荐三层：

```text
training folds       -> fit
validation folds     -> choose model / hyperparameters
official test        -> final inference only
```

若要报告最终泛化估计：

\[
CV\ mean\pm std.
\]

不要把 test_set 输出图反过来用于调参数。

---

# 17. Q3 的输入变量需要做“题意许可清单”

建议赛中建立：

| 变量 | train 有 | test 有 | 题目明确允许输入 | 是否使用 |
|---|---|---|---|---|
| RSSI | ✓ | ✓ | ✓ | ✓ |
| topology | ✓ | ✓ | ✓ | ✓ |
| protocol | ✓ | ✓ | ✓ | ✓ |
| thresholds | ✓ | ✓ | ✓ | ✓ |
| true MCS/NSS | ✓ | ✓ | **Q3 明确允许** | ✓ |
| PER | ✓ | ✓(test1) | **未明确放行** | 谨慎 |
| seq_time | ✓ | 空 | Q1 目标 | 用 Q1 prediction |
| throughput | ✓ | 空 | 目标 | ✗ |
| num_ampdu | ✓ | 空 | 统计输出 | ✗ |
| ppdu_dur | ✓ | 空 | 统计输出 | ✗ |

这个表可以避免“文件里有数值，所以默认能用”的错误。

---

# 18. 论文中“>95%”应该如何重新验

如果我们要复核，不应直接尝试复刻论文曲线，而应：

```text
1. 按 group 切 5 folds
2. 所有预处理仅 fit train
3. 每 fold 训练同一模型
4. 得到真正 unseen experiment 的预测
5. 拼接 out-of-fold predictions
6. 对 OOF prediction 计算官方 q90
7. 分 AP-level / system-level
8. 再算 absolute q90 作为补充
```

只有此时得到的数字，才可以称为交叉验证意义上的泛化性能。

---

# 19. 赛前必须准备的 evaluator 测试模板

```python
def test_quantile_direction():
    e = np.linspace(0, 0.99, 100)
    assert np.quantile(e, .9) > np.quantile(e, .1)


def test_pair_accuracy():
    y = np.array([[2,11],[2,8]])
    p = np.array([[2,10],[2,8]])
    assert exact_pair_accuracy(y,p) == 0.5


def test_group_disjoint(train_groups, val_groups):
    assert set(train_groups).isdisjoint(set(val_groups))
```

正式比赛最好让这些 assert 在最终运行脚本中保留。

---

# 20. 一句话总原则

> **验证协议是模型的一部分，不是模型训练完以后随便补的一张图。**

一篇数据论文只要出现：

- 同组泄漏；
- preprocessing leakage；
- 指标方向写反；
- train metric 当 validation metric；

再漂亮的神经网络结构也无法补救结论可信度。
