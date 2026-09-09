# C20102860127｜信号 + 小样本学习题比赛速查

> 适用：EEG / ECG / vibration / acoustic / sensor time series 等“连续信号 → 切片 → 分类”，尤其涉及通道选择、少标签、少样本。

---

# 1. 拿题后 30 分钟先回答 8 个问题

1. 连续记录的 sampling rate？
2. event / window 怎么定义？
3. 独立实验单位是什么：subject、session、trial 还是 epoch？
4. 标签是 event-level 还是 sequence-level？
5. 最终业务输出是什么？
6. 是否类别不平衡？
7. 题目要求压缩什么资源：时间、通道、标签、样本？
8. 官方勘误/补充说明有没有改数据范围？

---

# 2. 先画数据层级

```text
subject
  ↓
session
  ↓
trial / character
  ↓
event
  ↓
epoch / feature row
```

train/val split 不能穿透真正的独立层级。

---

# 3. baseline 顺序

信号分类先跑：

```text
simple filter
  ↓
fixed epoch
  ↓
LDA / logistic / SVM / RF
  ↓
official evaluator
```

不要第一小时直接：

```text
CNN / Transformer / complex wavelet zoo
```

除非 baseline 已锁定。

---

# 4. 类别不平衡检查

先计算：

\[
p_{majority}=\max_c \frac{n_c}{N}.
\]

如果你的 accuracy 只比 majority baseline 高一点，结果几乎没有意义。

备选：

```text
class_weight
undersampling
balanced ensemble
threshold tuning
```

指标：

```text
balanced accuracy
macro-F1
PR-AUC
minority recall
```

---

# 5. 信号 preprocessing 的比赛模板

```text
raw
 ↓
missing / artifact audit
 ↓
reference / detrend
 ↓
filter
 ↓
event-aligned epoch
 ↓
baseline correction
 ↓
feature / raw-window model
```

所有从数据 fit 的 preprocessing 放进 pipeline。

---

# 6. 资源约束题一定画 Pareto curve

## 时间 / rounds

```text
rounds vs accuracy
rounds vs ITR
```

## channels

```text
channel count vs accuracy
```

## labels

```text
label fraction vs accuracy
```

## training samples

```text
train fraction vs mean±std
```

不要用单点回答“尽可能少”。

---

# 7. 通道选择模板

```text
outer train
  ↓
channel ranking / sparse model
  ↓
choose k
  ↓
train classifier
  ↓
outer validation
```

然后报告：

```text
full channels baseline
selected channels
performance delta
channel reduction
```

---

# 8. 半监督最小实验

必须有：

```text
same labels, no unlabeled
vs
same labels + unlabeled
```

例如：

| model | labels | unlabeled |
|---|---:|---:|
| SVM | 30% | 0 |
| S3VM | 30% | 70% |

否则无法证明 semi-supervised 的价值。

---

# 9. Group split 速查

```python
GroupKFold
GroupShuffleSplit
StratifiedGroupKFold
LeaveOneGroupOut
```

常见 group：

```text
patient / subject
experiment_id
session
machine
batch
location
```

---

# 10. 论文至少放 5 张关键图

1. raw vs filtered signal；
2. target vs non-target aggregate waveform；
3. confusion matrix / PR curve；
4. resource-performance curve；
5. selected channels / feature importance stability。

---

# 11. 赛末 15 分钟数字检查

全文搜索：

```text
accuracy
精度
样本
通道
轮次
```

检查：

```text
摘要 == 正文 == 表格 == 结论
```

重点防：

```text
84 vs 80
75.3 vs 67.3
train 70% vs test 30%
```

---

# 12. 代码 clean-run gate

交付前：

```bash
python main.py --seed 42
```

必须从空结果目录生成：

```text
metrics.json
predictions.csv
figures/
```

不允许论文 appendix 里出现：

```text
undefined variable
missing import
manual copy result
```

---

# 13. 这篇带走的统一模板

```text
信号生成机制
    ↓
正确切片
    ↓
独立样本 / group
    ↓
可信 baseline
    ↓
资源约束
    ↓
feature/channel/label reduction
    ↓
最终业务指标
    ↓
严格 validation
```

> **先证明数据切分可信，再证明算法更准；先证明更准，再证明更省。**
