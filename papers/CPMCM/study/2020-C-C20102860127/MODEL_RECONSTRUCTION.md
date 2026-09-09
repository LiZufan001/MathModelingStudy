# C20102860127｜模型与验证重构

> 目标：不是把 2020 年论文改成“2026 算法大礼包”，而是保留其正确的问题结构，把资源约束、数据边界和验证闭环补齐。

---

# 1. 四问其实可以统一成一个资源约束学习问题

令预测性能为：

\[
P(\theta),
\]

资源成本为：

\[
C(\theta).
\]

四问分别对应：

| 问题 | 性能 | 成本 |
|---|---|---|
| Q1 | character accuracy / ITR | rounds / recognition time |
| Q2 | character accuracy | EEG channel count |
| Q3 | character accuracy | labeled sample count |
| Q4 | sleep-stage accuracy/F1 | training sample count |

统一形式：

\[
\max P(\theta)
\quad\text{s.t.}\quad C(\theta)\le B,
\]

或者 Pareto：

\[
\min \bigl(1-P(\theta),C(\theta)\bigr).
\]

这一统一视角比“Q1 RF、Q2 贝叶斯、Q3 S3VM、Q4 LGBM”更值得迁移。

---

# 2. 数据层：先建立 provenance 与 group

P300 数据必须保留：

```text
subject_id
character_id
round_id
flash_id
row_or_column_id
event_time
label
```

定义：

```python
group_char  = (subject_id, character_id)
group_trial = (subject_id, character_id, round_id)
```

所有切片都继承这些字段。

不要把切完的 epoch 当成独立 IID 行。

---

# 3. P300 预处理重构

## 3.1 过滤

可保留论文的 0.1/0.2–20 Hz 基本思路，但实现建议：

```python
sos = butter(order, [low, high], btype='bandpass', fs=250, output='sos')
y = sosfiltfilt(sos, x)
```

要报告：

- transition band；
- filter order；
- causal / zero-phase；
- edge handling；
- reference / baseline。

## 3.2 epoch

对 flash onset：

\[
x_{s,c,r,f}\in\mathbb R^{k\times T}.
\]

例如：

\[
T=125\text{ points}=500\text{ ms}.
\]

可加：

- pre-stimulus baseline；
- amplitude rejection；
- robust clipping；
- artifact flag。

---

# 4. Q1：从 event score 到 sequential character decoder

## 4.1 event classifier

不必执着 RF。

竞赛安全 baseline：

1. shrinkage LDA；
2. RBF / linear SVM；
3. class-weight RF；
4. Logistic Regression。

目标不是 event accuracy，而是输出：

\[
p(y=1\mid x).
\]

## 4.2 类别不平衡

优先比较：

```text
class_weight
balanced RF
random undersampling
```

同时报告：

- ROC-AUC；
- PR-AUC；
- P300 recall；
- balanced accuracy。

不要用普通 event accuracy 单独评价。

## 4.3 row/column aggregate

对于第 \(r\) 轮的某一行/列 \(j\)：

\[
S_j^{(r)}=\sum_{t=1}^{r}\log\frac{p_{jt}}{1-p_{jt}}.
\]

预测：

\[
\hat r=\arg\max_{j\in rows}S_j,
\qquad
\hat c=\arg\max_{j\in cols}S_j.
\]

## 4.4 sequential early stopping

第 \(r\) 轮后计算：

\[
\Delta_r^{row}=S_{(1)}-S_{(2)},
\qquad
\Delta_r^{col}=S_{(1)}-S_{(2)}.
\]

若：

\[
\Delta_r^{row}>\tau_r,
\qquad
\Delta_r^{col}>\tau_c,
\]

则提前停止。

这样 Q1 的“尽量少轮次”真正进入算法。

## 4.5 ITR

36 字符选择任务常用 bit/selection：

\[
B=\log_2 36
+P\log_2P
+(1-P)\log_2\frac{1-P}{35}.
\]

结合平均识别时间 \(T\)：

\[
ITR=\frac{60}{T}B.
\]

正式比赛至少同时画：

```text
rounds vs accuracy
rounds vs ITR
```

---

# 5. Q1 正确 validation protocol

外层：

```text
hold out characters / trials
```

内层：

```text
train classifier
select hyperparameters
choose stopping threshold
```

不能 event-level 随机切片后直接称“泛化”。

若目标强调跨被试：

```text
Leave-One-Subject-Out
```

若系统允许 subject-specific calibration，则必须明确评价的是：

> within-subject generalization。

---

# 6. Q2：channel selection 重构

## 6.1 正确优化目标

令通道集合为 \(S\)：

\[
\min_S |S|
\quad\text{s.t.}\quad
Acc_s(S)\ge Acc_s(full)-\epsilon.
\]

对 5 被试同时考虑：

\[
\min_S |S|
+\lambda\frac1{5}\sum_{s=1}^{5}Loss_s(S).
\]

## 6.2 候选方法

若强调可解释与小样本：

- group lasso logistic；
- sparse group lasso；
- permutation importance + stability selection；
- recursive feature elimination；
- spike-and-slab logistic/probit。

通道是一个 group，不应把一个通道内的 125 time points 当作完全独立普通 feature。

## 6.3 nested selection

必须：

```text
outer train
   ↓
channel selection
   ↓
hyperparameter selection
   ↓
train final model
   ↓
outer val
```

每个 outer fold 都重新选通道。

## 6.4 stability

报告每个通道被选中的频率：

\[
\pi_j=\frac{\#\text{folds selecting channel }j}{\#\text{folds}}.
\]

common set 可定义：

\[
S_{common}=\{j:\pi_j>\tau\}.
\]

这比单次 3/5 多数票更稳健。

---

# 7. Q3：半监督必须证明“unlabeled 有用”

## 7.1 固定 label budget

对于每个比例：

\[
q\in\{10\%,20\%,30\%,40\%\},
\]

同时跑：

### Baseline A

\[
q\text{ labeled only}\to supervised SVM.
\]

### Semi-supervised B

\[
q\text{ labeled}+(1-q)\text{ unlabeled}\to S3VM.
\]

然后比较：

\[
\Delta(q)=Perf_{SSL}(q)-Perf_{SL}(q).
\]

只有 \(\Delta(q)>0\) 且稳定，才能说 unlabeled 帮到了模型。

## 7.2 label selection

不能简单“前 30%”。

应按：

```text
subject
character
round
class
```

分层/分组采样，多随机种子重复。

## 7.3 evaluation hierarchy

两层都报：

1. event-level P300 classification；
2. final character-level recognition。

最终任务指标优先级更高。

---

# 8. Q4：少样本睡眠分期重构

## 8.1 数据特点

5 类样本数约 562–633，比较平衡。

因此可采用：

```text
RepeatedStratifiedKFold
```

如果原始数据存在 subject_id，则必须：

```text
StratifiedGroupKFold / GroupKFold
```

以 subject 为 group。

## 8.2 learning curve

训练比例：

\[
10\%,20\%,\ldots,80\%.
\]

每个比例重复多次，记录：

\[
mean\pm std.
\]

选择最少训练量：

\[
q^*=\min\{q:Perf(q)\ge Perf_{max}-\epsilon\}.
\]

这比找一条随机曲线的峰值更符合题意。

## 8.3 指标

至少：

- accuracy；
- macro-F1；
- per-class recall；
- confusion matrix；
- Cohen's kappa（可选）。

睡眠相邻阶段的误判还可定义 ordinal cost。

---

# 9. 统一实验工程结构

```text
data/
  raw/
  processed/

src/
  preprocess.py
  features.py
  split.py
  q1_event.py
  q1_decoder.py
  q2_channel.py
  q3_ssl.py
  q4_sleep.py
  metrics.py

experiments/
  q1_round_curve.yaml
  q2_channel_curve.yaml
  q3_label_budget.yaml
  q4_learning_curve.yaml

results/
  metrics.json
  predictions.csv
  figures/
```

核心原则：

> 论文表格和摘要数字都从 `results/metrics.json` 自动生成。

---

# 10. 最关键的四条 invariants

```python
assert train_groups.isdisjoint(val_groups)
assert preprocessing_fit_data <= train_only
assert channel_selection_data <= train_only
assert final_metric == official_task_metric
```

如果四条都成立，才开始谈复杂模型。

---

# 11. 重构后的比赛主线

```text
官方题意 / correction
        ↓
定义 subject-character-trial group
        ↓
事件对齐 EEG preprocessing
        ↓
可信 event classifier baseline
        ↓
概率聚合 + sequential stopping
        ↓
round / ITR Pareto
        ↓
嵌套 channel selection
        ↓
channel-count Pareto
        ↓
固定 label budget 比较 SL vs SSL
        ↓
Q4 repeated learning curve
        ↓
最终资源-性能总表
```

这会把原论文的四个分散“算法任务”升级成一个统一的：

> **resource-efficient EEG learning system**。
