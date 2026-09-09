# C20102860127｜指导老师 / 评审老师报告

> 不是赛事官方评语，而是基于原题、官方补充说明、43 页论文正文/附录和睡眠数据结构做的二次评审训练。

---

# 一、如果我是评审老师：第一页后的 60 秒判断

第一印象会是：

> **作者理解了四问背后的统一主题——降低 BCI/分类系统的数据与采集成本，同时维持识别性能。**

吸引我继续读的地方：

1. P300 任务从 flash event 一直落到 final character，而非停在二分类；
2. 明确认识到 P300 正负样本 1:5 的类别不平衡；
3. Q2 不是普通相关系数删通道，而是用 sparse Bayesian support；
4. Q3 能自然从“标签昂贵”引出 semi-supervised；
5. Q4 用三类模型横向比较；
6. 对 S2/S3 char22 缺失严格遵守官方更正；
7. 附录公开了较多代码。

但我会很快圈出一句：

> **Q1 的题眼是“尽可能少轮次”，为什么全文几乎都固定用 5 轮？**

这会成为核心追问。

---

# 二、指导老师最值得表扬的 8 点

## 1. 事件对齐而不是盲目整段建模

利用 flash timestamp 切 500 ms P300 epoch，是对生成机制的正确利用。

## 2. 意识到 accuracy paradox

作者明确指出恒预测多数类即可约 84% event accuracy，因此必须处理不平衡。

这是非常好的基本功。

## 3. 行/列解码尊重实验协议

先 P300 event，再 row/column vote，再 character，比直接 36-class 更可解释。

## 4. Q2 把“通道有没有用”写成稀疏支持

`spike-and-slab` 的 support indicator 与 channel selection 的业务含义高度对应。

## 5. Q2 真正做了下游验证

删 7 个通道后，不只说“后验概率很漂亮”，而是重新跑字符识别，已知字符仍有 92%。

这叫 downstream validation。

## 6. Q3 不是为了用半监督而用半监督

题面就是“标签昂贵、无标签丰富”，S3VM 的方法类型与问题结构匹配。

## 7. Q4 做了 train/test proportion 探索

虽然实验设计可改进，但至少意识到题目核心不是纯最高 accuracy，而是少训练样本。

## 8. 论文链条完整

前三问围绕一个 P300 系统逐问压缩资源，而不是四个孤立算法。

---

# 三、A级风险：会直接影响结论可信度

## A1. Q1 没有完成“最少轮次”核心评价

固定 5 轮只能证明：

> 在允许上限内能识别。

不能证明：

> 已经尽量少用轮次。

必须补 1–5 轮 accuracy / ITR / early-stop。

## A2. Q1 validation unit 过细

随机 event split 容易让同一 subject-character-session 的高度相关片段跨 train/val。

建议按 character/trial group。

## A3. Q3 75.3% / 67.3% 冲突

摘要与正文差 8 个百分点，无法同时成立。

## A4. Q3 缺 same-label-budget supervised baseline

没有：

```text
900 labeled SVM
vs
900 labeled + 2100 unlabeled S3VM
```

不能严格证明 unlabeled data 的贡献。

## A5. LightGBM appendix 不能直接执行

变量和语法问题说明公开 appendix 并非最终可运行版本。

---

# 四、B级风险：不会推翻整篇，但会削弱论证

## B1. KNN 84% / 80% 冲突

摘要 84，正文表格 80。

## B2. channel selection 没有 nested validation

若先选通道再验证，有 selection bias 风险。

## B3. common set 的 3/5 majority 是 heuristic

合理，但没有证明优于 2/5、4/5 或直接 joint optimization。

## B4. Q3 维数写成 10×75

与 13×125 不一致。

## B5. Q4 repeated holdout 被称为 cross-validation

术语不精确。

## B6. train/test fraction 文本混写

图横轴 test data，正文有时按 train data 解读。

## B7. 更多训练数据 → 过拟合的解释证据不足

应该用固定 test protocol 与置信区间。

---

# 五、C级问题：写作与复现工程

1. 表 5-3 标题写 KNN，正文实际讨论 RF；
2. StandardScaler 在 train split 前 fit；
3. test data 又重新 fit scaler；
4. appendix 变量命名不统一；
5. 随机种子、RF 参数报告不足；
6. 多处“准确率”没有明确 event-level / character-level。

---

# 六、为什么这些问题没有抹掉这篇的训练价值

国赛评审看到的不只是现代 ML benchmark rigor。

这篇仍然具备：

- 对 EEG 生成机制有基本理解；
- 完成四问；
- 有算法递进；
- 有最终字符输出；
- 有通道压缩后的下游验证；
- 有半监督的题意对应；
- 有多模型比较；
- 工程量和论文完整度较高。

所以更准确的评价：

> **系统建模链与任务完成度强，现代统计验证严谨性偏弱。**

---

# 七、如果我是指导老师，赛中会设 6 个硬门槛

## Gate 1：官方 evaluator 先锁

Q1：

```text
character accuracy
mean rounds
ITR
```

Q2：

```text
accuracy
channel count
```

Q3：

```text
accuracy
label count
```

Q4：

```text
accuracy/macro-F1
train fraction
```

## Gate 2：独立样本定义必须写在白板上

```text
subject / session / character / trial / epoch
```

谁是 group，必须赛前统一。

## Gate 3：所有 learned preprocessing 进入 pipeline

不能 validation 参与 scaler / PCA / feature/channel selection。

## Gate 4：每个高级方法都要有低成本 baseline

```text
RF vs logistic/LDA
sparse Bayesian vs simple ranking
S3VM vs SVM
LGBM vs RF/SVM
```

## Gate 5：资源约束必须画 curve

不能只报某个单点。

## Gate 6：摘要数字自动从结果表生成

杜绝 84/80、75.3/67.3。

---

# 八、模拟答辩 12 问

## Q1

**你们为什么固定用 5 轮？如果 3 轮已经 90%，5 轮 92%，哪个更符合题意？**

应答：补 rounds-accuracy-ITR curve，并给 early-stop threshold。

## Q2

**83% 的 event accuracy 可能全预测 0，你们为什么用 accuracy？**

应答：balanced accuracy / recall / PR-AUC + final character accuracy。

## Q3

**同一字符切出来的 epoch 是否同时进入训练和验证？**

应答：按 subject-character/trial 分组切分。

## Q4

**为什么随机森林需要 StandardScaler？为什么 test 重新 fit scaler？**

应答：RF 本身不需要；重新 fit test scaler 应修正为 train-fitted transform。

## Q5

**你们说做了负类下采样，为什么 appendix 看不到？**

应答：必须提供最终统一可运行代码，或承认 appendix 版本不完整。

## Q6

**通道后验概率高，就一定代表字符识别最优吗？**

应答：不一定，因此必须 downstream classifier validation。

## Q7

**为什么 3/5 被试选择就定义为 common channel？**

应答：目前是 heuristic；可通过 cross-subject performance 选择阈值或做 joint sparse optimization。

## Q8

**为什么 binary label 使用回归 likelihood，而不是分类 likelihood？**

应答：可重构 sparse logistic/probit；原方法主要借用 spike-and-slab 支持选择思想。

## Q9

**S3VM 的 67.3% 与摘要 75.3% 哪个才是真的？**

应答：必须回到唯一结果源；当前论文公开版本存在冲突，不能强行解释。

## Q10

**如何证明 2100 个无标签样本真正有帮助？**

应答：相同 900 labels 下 supervised SVM vs S3VM paired comparison。

## Q11

**为什么训练数据更多反而过拟合？**

应答：单次曲线不能证明因果；需要固定 test set、nested training subset、mean±std。

## Q12

**如果只允许你保留这篇一个创新点，你保留什么？**

推荐回答：

> 把四问统一成“资源受限的 EEG 学习系统”：轮次、通道、标签、训练样本都作为资源成本，与识别性能做 Pareto 权衡。

---

# 九、评审式总评

### 建模逻辑

**强。** 四问前后关联清楚。

### 方法针对性

**较强。** 大部分算法与任务结构匹配。

### 结果验证

**中等。** 有比较和下游验证，但 split / baseline / 资源曲线不足。

### 可复现性

**偏弱。** appendix 存在实现缺口和代码错误。

### 比赛迁移价值

**高。** 尤其适合训练信号类、切片数据、特征选择、半监督和资源约束建模。

---

# 十、评审老师的一句话

> **思路是一套完整系统，不是算法拼盘；但如果今天再交一次，我最希望补的不是更复杂的网络，而是更严格的 group-aware validation 和资源-性能曲线。**
