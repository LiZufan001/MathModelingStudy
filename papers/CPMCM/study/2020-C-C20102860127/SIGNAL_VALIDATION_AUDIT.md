# C20102860127｜信号学习验证与复现审计

> 这份文件专门回答：**这类 EEG / 时序切片 / 半监督题，结果到底怎样才算可信？**

---

# 1. 先锁定官方补充说明

2020 C 官方赛中补充说明：

- `S2_test_event.xlsx` 缺少 char22 event；
- `S3_test_data.xlsx` 缺少 char22 raw data；
- 因此 S2、S3 只要求 char13–char21；
- S1、S4、S5 仍要求 char13–char22；
- 同时影响 Q1 与 Q3。

所以总待识别目标数：

\[
10+9+9+10+10=48.
\]

论文摘要写“48 个目标字符”，结果表对 S2/S3 char22 用 `/`，这一点是**严格遵守官方更正**，值得表扬。

---

# 2. 一个最容易犯错的概念：epoch 不是独立样本

P300 数据存在层级结构：

```text
subject
 └─ character
     └─ round
         └─ flash event
             └─ 125-point EEG epoch
```

如果把最后一级 epoch 随机拆 train / val：

```text
同一个 subject
同一个 character
同一个 recording block
相邻 repetitions
```

可能同时出现在两边。

这会把 validation 变成“见过同环境后的插值”。

## 推荐 split

### subject-specific model

```python
group = (subject_id, character_id)
```

按字符留出。

### cross-subject model

```python
group = subject_id
```

Leave-One-Subject-Out。

---

# 3. Q1：不能只看 event accuracy

正样本率：

\[
2/12=16.7\%.
\]

恒输出 non-P300：

\[
Accuracy\approx83.3\%.
\]

因此 event-level 至少报告：

```text
balanced accuracy
P300 recall
precision
PR-AUC
ROC-AUC
```

最终还必须报告：

```text
character accuracy
rounds used
ITR
```

---

# 4. Q1 论文数字一致性审计

## RF

前五已知字符 × 5 被试：25 个字符判断。

表 4-7：

```text
100%, 80%, 80%, 100%, 100%
```

所以：

\[
23/25=92\%.
\]

摘要与正文一致。

## KNN

表 4-9：

```text
80%, 60%, 100%, 80%, 100%
```

所以：

\[
20/25=80\%.
\]

正文也写 80%。

但摘要写：

\[
84\%.
\]

结论：

> **KNN 摘要数字与正文最终表不一致。**

---

# 5. Q1 appendix pipeline audit

公开代码：

```python
scaler.fit(train_data)
train_data = scaler.transform(train_data)
x_train, x_test, ... = train_test_split(...)
```

问题：validation 参与了 scaler 参数估计。

随后测试：

```python
scaler = StandardScaler()
scaler.fit(predict_data)
predict_data = scaler.transform(predict_data)
```

问题：test 使用自己的均值/方差，而不是 train transform。

严格流程：

```python
X_train, X_val = split(...)
scaler.fit(X_train)
X_train = scaler.transform(X_train)
X_val   = scaler.transform(X_val)
X_test  = scaler.transform(X_test)
```

补充：RF 本身对单调 feature scaling 不敏感，所以 StandardScaler 并非 RF 必需；但**验证边界错误仍然是流程问题**。

---

# 6. 正文“下采样”与 appendix 不完全对应

正文明确说：

> 随机排列抽取多数类，使 0/1 样本数量相等。

但公开 RF appendix 中：

```text
构造全部 labels
→ StandardScaler
→ train_test_split
→ RandomForestClassifier
```

没有看到 balancing step。

因此复现报告应写：

> 方法声明与公开代码存在缺口；无法确认论文最终 92% 对应哪一个训练版本。

不能擅自替作者补代码后再说“已复现”。

---

# 7. Q1 的官方资源目标没有闭环

题目要求：

> 尽可能少轮次，≤5。

论文最终始终用 5 rounds。

缺少：

```text
1 round
2 rounds
3 rounds
4 rounds
5 rounds
```

的 accuracy / ITR 对比。

因此 evaluator 应写成：

```python
def evaluate_q1(predictions):
    return {
        'char_acc': ...,
        'mean_rounds': ...,
        'itr': ...,
    }
```

---

# 8. Q2：feature selection 本身也属于 training

错误模式：

```text
all data
 ↓
select channels
 ↓
train/val split
```

正确：

```text
outer train
 ↓
select channels
 ↓
train classifier
 ↓
outer val
```

否则 validation label 已通过通道选择间接影响模型。

对于 common channel set，也应在 outer train subjects 上确定，再验证新 subject / held-out character。

---

# 9. Q2 输出审计

论文 common set：

```text
Fz,F3,F4,C3,Cz,C4,CP3,CP4,CP5,CP6,P3,P4,P7
```

共：

\[
13\text{ channels}.
\]

满足题目：

\[
10\le k<20.
\]

用 13 通道 RF 验证官方已知 char13–17：

\[
92\%.
\]

但表 5-3 标题写成“KNN 算法前五个测试数据精度表”，正文却明确说此处是随机森林。

这是另一个**表题版本错误**。

---

# 10. Q3 数字一致性审计

摘要：

\[
75.3\%.
\]

正文：

> “经过半监督学习的分类器在验证集上的平均准确率达到 67.3%。”

即：

\[
67.3\%.
\]

两者差：

\[
8.0\text{ percentage points}.
\]

这不是四舍五入。

必须视为版本冲突。

---

# 11. Q3 维数审计

正文说：

- 13 channels；
- 125 points / channel。

原始展开：

\[
13\times125=1625.
\]

但论文写：

> 一个 `10×75` 的向量。

\[
10\times75=750.
\]

没有给出从 1625 → 750 的映射过程。

因此：

> **维度描述无法复现。**

如果确有降维，应明确写：

```text
method
input shape
output shape
fit scope
```

---

# 12. Q3 半监督效果要做 paired baseline

论文固定：

```text
900 labeled
2100 unlabeled
```

严格实验：

| 方法 | labeled | unlabeled | metric |
|---|---:|---:|---:|
| supervised SVM | 900 | 0 | ... |
| S3VM | 900 | 2100 | ... |

并重复多 seeds。

然后：

\[
\Delta=Acc_{S3VM}-Acc_{SVM}.
\]

论文当前无标签样本数量曲线有价值，但不能替代这个对照。

---

# 13. Q4 原始数据审计

附件 2 共有：

| stage | n |
|---|---:|
| Wake | 633 |
| REM | 599 |
| N1 | 562 |
| N2 | 604 |
| Deep | 602 |

总数：

\[
3000.
\]

最大类占比：

\[
633/3000=21.1\%.
\]

因此 89% accuracy 明显高于 majority baseline，不是类别极不平衡造成的虚高。

但 accuracy 仍不足以说明每一睡眠阶段表现。

---

# 14. Q4 “交叉验证”命名审计

appendix：

```python
train_test_split(class_2, test_size=0.3)
train_test_split(class_3, test_size=0.3)
...
```

再合并。

这是：

> class-wise stratified random holdout

若重复 5 次取均值，可以称：

> repeated stratified holdout

但不是标准 k-fold cross-validation。

---

# 15. Q4 train/test 比例口径

图横轴明确标：

```text
test data
```

所以：

```text
x=0.30 → 30% test, 70% train
```

正文却有“选取 30% 数据作为样本时最高 89%”等表述，同时又说最合适训练量约 75%。

正确写法：

```text
train_fraction = 1 - test_fraction
```

所有图表统一使用一个口径。

---

# 16. Q4 “更多训练数据导致过拟合”不能这么证明

观察：

```text
65% train → 84%
70% train → 82%
```

不能推出：

```text
more training data causes overfitting
```

需要：

- same fixed test set；
- nested subsets of train data；
- many random repetitions；
- confidence interval。

否则 train/test composition 同时变化，无法做因果解释。

---

# 17. Q4 LightGBM appendix 审计

公开页面可直接看到：

1. 未导入 `lightgbm as lgb`；
2. `X_train, y_train, X_test, y_test` 未由前文生成；
3. 参数字典 `num_class: 5` 后缺逗号；
4. 最后用未定义 `test_x`；
5. 前文变量还存在 `trian_label` 拼写。

因此：

> **公开 appendix 不是一个能 copy-run 的最终复现脚本。**

正式比赛至少在提交前做：

```bash
python appendix.py
```

从空环境一键运行。

---

# 18. 推荐的统一 validation checklist

```text
[ ] 官方勘误是否应用
[ ] independent group 定义是否正确
[ ] train/val/test group 是否隔离
[ ] scaler/filter learned params 只在 train fit
[ ] feature/channel selection 只在 train fit
[ ] hyperparameters 只用 train/inner-val
[ ] class imbalance evaluator 正确
[ ] Q1 final character metric 已报告
[ ] Q1 round/ITR 已报告
[ ] Q2 channel-count tradeoff 已报告
[ ] Q3 same-label-budget baseline 已报告
[ ] Q4 learning curve 有 mean±std
[ ] final appendix clean-run
[ ] abstract/table/conclusion 数字自动同步
```

---

# 19. 一句话

> **信号题最危险的“数据泄漏”往往不是偷看 test label，而是同一段连续记录切出来的大量相似 epoch 被随机分到了训练和验证两边。**
