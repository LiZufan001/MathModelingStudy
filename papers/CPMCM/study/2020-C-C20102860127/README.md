# 2020 C 国一论文精读：C20102860127

> 赛题：面向康复工程的脑电信号分析和判别模型  
> 参赛编号：`C20102860127`  
> 团队：李典泽、付银、程鑫（东南大学）  
> 奖项：全国一等奖  
> 原论文：[`../../2020/fulltext/C/C20102860127.pdf`](../../2020/fulltext/C/C20102860127.pdf)

---

# 0. 来源说明：为什么本轮精读这篇，而不是原路线点名的电子科大队

第二阶段路线最初点名的是电子科技大学贾召钱、殷康宁、王文超团队。电子科大官方新闻能够确认该队获得全国一等奖，并公开了较完整的方法摘要：

- 预处理：可视化、带通滤波、小波分析/滤波、异常值、冗余处理、数据切片、特征选择；
- Q1：SVM + 自设计神经网络；
- Q2：熵权法评估通道信息量；
- Q3：TSVM 半监督；
- Q4：K-means + 支持向量模型。

但是，截至本轮检索，当前仓库的 2020 C exact-match 国一全文以及公开优秀论文集合中都没有找到能把**贾召钱/殷康宁/王文超**与某一份完整 PDF 精确对应的版本。

因此本轮遵守一个原则：

> **没有全文就不冒充精读。**

真正逐页精读改用仓库中身份可核验的全国一等奖全文 `C20102860127`（东南大学）。电子科大队只作为官方方法路线对照，另见 [`UESTC_METHOD_COMPARISON.md`](UESTC_METHOD_COMPARISON.md)。

---

# 1. 指导老师先给结论

这篇最值得学的是它把四问组织成了一条相当完整的脑电数据建模链：

```text
原始 P300 EEG
   ↓
滤波 + 事件切片 + 标签构造
   ↓
Q1：P300 event classifier（RF）
   ↓
行/列投票 → 字符识别
   ↓
Q2：spike-and-slab + EP
   ↓
20 通道 → 13 通道
   ↓
Q3：S3VM
少量标签 + 大量无标签
   ↓
字符识别

另一条支线：
睡眠频带能量特征
   ↓
Q4：SVM / LightGBM / RF
   ↓
训练样本比例与睡眠分期
```

这是一篇很好的“**信号 → 样本 → 特征/通道 → 分类 → 半监督 → 泛化验证**”训练材料。

但如果从 2026 年更严格的评审/复现标准回看，最重要的问题也集中在验证链：

1. Q1 用了 5 轮投票，但题目明确要求在保证准确率同时“尽可能使用较少轮次”；论文没有给 1–5 轮准确率/ITR 曲线，实际上没有完整回答这个优化目标；
2. Q1 论文称对多数类随机下采样，但公开 RF 附录代码看不到相应下采样实现；
3. Q1 代码在 `train_test_split` 前对全训练数据 `fit` 标准化器，存在轻微 preprocessing leakage；更严重的是预测集又重新 `fit` 一个新的 StandardScaler，而不是复用训练尺度；
4. P300 窗口来自同一字符、同一被试、相邻重复闪烁，普通随机 event-level split 并不能代表对新字符/新 trial 的泛化；
5. 摘要写 KNN 84%，正文表格与复算为 80%；
6. Q2 的稀疏贝叶斯思想有价值，但通道选择如果在完整数据上完成后再评价，会有 feature-selection leakage 风险；
7. Q3 摘要写 S3VM 验证准确率 75.3%，正文明确写 67.3%；
8. Q3 说 13 通道 × 125 点的样本是 `10×75` 向量，维数明显不自洽；
9. Q3 没有给“同样 900 个有标签样本、不使用无标签数据”的监督基线，因此不能严格证明无标签样本带来了净增益；
10. Q4 所谓“交叉验证”从附录看更接近重复随机 holdout；图横轴是 `test data`，正文却多处把测试比例与训练比例混写；
11. Q4 用一两个百分点的波动直接解释为“训练样本更多导致过拟合”，证据不足；
12. LightGBM 附录代码按字面存在缺失 import、变量名不一致、缺逗号等问题，无法直接复现。

因此最正确的学习姿势是：

> **学它的问题链与任务衔接；把“评估单位、数据切分、预处理边界、标签预算和官方目标”做得比作者更严格。**

---

# 2. 原题四问到底在考什么

## 2.1 Q1：不是单纯二分类，而是“准确率 × 信息传输速率”

每个目标字符的 6 行 + 6 列各闪烁一次构成一轮，共 12 次刺激；实验最多 5 轮。

真正的链条：

```text
一次 flash
  ↓
是否诱发 P300？
  ↓
12 个 row/column event 的评分
  ↓
确定一行 + 一列
  ↓
确定字符
```

题目特别强调：

> 在尽可能少的轮次（≤5）下完成识别。

所以 Q1 至少有两个指标：

- character accuracy；
- rounds / time / ITR。

只报告五轮准确率并没有把题意吃透。

## 2.2 Q2：通道选择属于“降维但不能掉性能”

20 个通道中，每个被试选择：

\[
10\le k<20.
\]

同时还要给所有被试都较适用的一组通道。

这不是为了画一张通道权重图，而是一个约束优化问题：

\[
\min k
\quad\text{s.t.}\quad
\mathrm{Perf}(S)\ge \tau.
\]

或者更完整地做 accuracy / channel count Pareto frontier。

## 2.3 Q3：标签预算问题

题意不是简单“用 S3VM”。

它问的是：

> **多少标签已经够用？无标签样本能否补足剩余信息？**

所以关键实验应该是 label-budget curve：

\[
10\%,20\%,30\%,\ldots
\]

并且每个标签预算下比较：

- supervised-only；
- semi-supervised。

## 2.4 Q4：少样本睡眠分期

附件 2 共 3000 个样本、5 类：

- 清醒期 633；
- REM 599；
- 睡眠 I 期 562；
- 睡眠 II 期 604；
- 深睡眠 602。

类别相当均衡，因此 accuracy 的问题没有极端不平衡数据那么严重。

但题意仍然是：

> **尽可能少的训练样本 + 相对较高准确率。**

最自然的表达应是 learning curve，而不是只找一次最高点。

---

# 3. Q1：随机森林字符识别

## 3.1 信号预处理

作者设计：

- sampling rate：250 Hz；
- stopband：0.1 Hz 以下、30 Hz 以上；
- passband：0.2–20 Hz；
- stopband attenuation：80 dB；
- Butterworth IIR；
- 论文称最终为 46 阶带通滤波器。

每次 flash 后截取：

\[
125\text{ points}=500\text{ ms}
\]

作为 P300 事件窗口。

这与 P300 在刺激后数百毫秒出现的生理机制是对齐的。

### 指导老师评价

好处：

> **模型没有直接吃整段 EEG，而是先用事件时间戳把连续信号变成 task-aligned epoch。**

这是信号题非常关键的一步。

今天重新做，我会进一步加入：

- baseline correction；
- notch / mains-noise 检查；
- SOS 形式 IIR，避免高阶直接型数值问题；
- 明确 causal / zero-phase filtering；
- epoch rejection / artifact detection。

## 3.2 类别不平衡意识是对的

一轮 12 次 flash 中只有目标行和目标列对应 2 个 P300：

\[
P(y=1)=\frac{2}{12}=16.7\%.
\]

如果恒预测 0，event accuracy 就已有约：

\[
83.3\%.
\]

论文明确指出“84% accuracy”可能只是多数类假象，这是非常正确的判断。

作者称采用随机排列抽取多数类，使正负样本数量平衡。

### 但公开代码与正文不完全一致

公开 RF 代码构造所有 event 后直接：

```python
x_train, x_test, y_train, y_test = train_test_split(train_data, labels)
clf = RandomForestClassifier()
```

附录中没有看到正文所说的负类随机下采样步骤。

所以我们只能说：

> **论文方法声明包含下采样，但公开附录无法完整复现该步骤。**

不能把两者当成同一份执行实现。

## 3.3 “event classifier → 行列投票 → 字符”是正确任务分解

作者不是直接做 36 分类，而是：

1. 每个 row/column flash 预测 P300 / non-P300；
2. 每轮得到候选行、列；
3. 5 轮投票；
4. 由行列交点确定字符。

这比直接把字符作为黑箱 36 分类更贴合实验机制。

## 3.4 已知五字符验证

问题二官方给出了 char13–char17 真值：

```text
M, F, 5, 2, I
```

论文用它们作事后验证。

随机森林五位被试正确率：

```text
S1 100%
S2  80%
S3  80%
S4 100%
S5 100%
```

合计：

\[
\frac{23}{25}=92\%.
\]

KNN：

```text
80%, 60%, 100%, 80%, 100%
```

合计：

\[
\frac{20}{25}=80\%.
\]

### A 级论文一致性问题

摘要写：

> KNN = 84%

正文表格和正文结论却是：

> KNN = 80%

这是典型的摘要数字未随最终实验同步。

## 3.5 最大的题意缺口：没有真正优化轮次

论文始终使用题目允许的最大值：

\[
R=5.
\]

但 Q1 明确要求：

> 尽可能使用较少轮次。

真正应该至少报告：

| rounds | character accuracy | time | ITR |
|---:|---:|---:|---:|
| 1 | ... | ... | ... |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |
| 4 | ... | ... | ... |
| 5 | ... | ... | ... |

甚至可以设计 sequential stopping：

```text
每完成一轮
   ↓
累积 row/column posterior
   ↓
若 top1 - top2 margin > threshold
   ↓
提前停止
```

这会比固定 5 轮更直接回答命题人。

---

# 4. Q1 公开代码审计

## 4.1 preprocessing leakage

附录：

```python
scaler.fit(train_data)
train_data = scaler.transform(train_data)
x_train, x_test, ... = train_test_split(...)
```

也就是先用全数据求均值/方差，再切验证集。

正确顺序：

```text
split
 ↓
fit scaler on train only
 ↓
transform train / val
```

不过这里主模型是 RF，树模型本身通常并不需要 StandardScaler，因此该问题对 RF 数值结果的影响未必很大，但流程仍不规范。

## 4.2 更明显的问题：预测集重新 fit scaler

附录又写：

```python
scaler = StandardScaler()
scaler.fit(predict_data)
predict_data = scaler.transform(predict_data)
```

也就是说训练集和预测集分别建立了自己的坐标系。

一般监督学习应当：

```python
scaler.fit(X_train)
X_train = scaler.transform(X_train)
X_test  = scaler.transform(X_test)
```

不能让测试集自己决定变换参数。

## 4.3 随机 event split 并不等价于真实泛化

同一个字符、同一被试、相邻轮次的 EEG epoch 高度相关。

若随机把 event 拆到 train / val，两边会同时出现：

```text
same subject
same character
same recording session
adjacent repetitions
```

这更像“插值能力”，不是“新字符/新 trial 泛化”。

应该至少按：

```text
group = subject + character
```

或 trial 分组。

---

# 5. Q2：spike-and-slab + EP 通道选择

## 5.1 作者的思路

将 20 通道权重记为：

\[
w=(w_1,\ldots,w_{20}).
\]

为每个通道引入 support indicator：

\[
z_i\in\{0,1\}.
\]

spike-and-slab 的含义：

```text
z_i = 0 → 权重被压到 0，通道删除
z_i = 1 → 权重来自连续 slab，通道保留
```

然后用 Expectation Propagation 近似后验分布，按：

\[
P(z_i=1\mid D)
\]

排序。

这是一个比“看相关系数删通道”更系统的稀疏选择思路。

## 5.2 五被试结果 → common set

论文对每个被试分别选通道，再用“至少 3/5 被试选择”作为 common criterion。

最终 13 个通道：

```text
Fz, F3, F4,
C3, Cz, C4,
CP3, CP4, CP5, CP6,
P3, P4, P7
```

即编号：

```text
1,2,3,4,5,6,9,10,11,12,14,15,16
```

删除：

```text
7,8,13,17,18,19,20
```

删掉 35% 通道后，用 RF 对官方已知 char13–17 再验证，仍得到：

\[
92\%.
\]

这是一个很有说服力的工程结果：

> **降低 acquisition / compute complexity，同时没有看到验证精度明显下降。**

## 5.3 评审老师会追问什么

### 问题 A：为什么用 Gaussian regression 去拟合 binary P300 label？

如果 likelihood 是连续 Gaussian，而目标是 0/1，统计模型并不完全匹配。

今天更自然的做法：

- sparse logistic / probit；
- group lasso logistic；
- group sparse SVM；
- stability selection。

### 问题 B：channel selection 是否在 validation 外完成？

若用全标签数据先选通道，再报告同一批数据派生出的验证效果，会产生 selection bias。

严格做法：

```text
outer split
  ↓
train fold 内做 channel selection
  ↓
train classifier
  ↓
outer validation
```

### 问题 C：为什么 common set 是“3/5 多数票”？

这是合理启发式，但并不是优化得到的。

更严格：

\[
\min_S |S|
+\lambda\frac1{5}\sum_s Loss_s(S).
\]

或者直接画：

```text
channel count vs subject-wise accuracy
```

---

# 6. Q3：S3VM 半监督学习

## 6.1 数据设计

论文在 13 通道基础上：

- 10 个训练字符；
- 5 被试；
- 5 rounds；
- 每轮 12 flashes。

共：

\[
12\times5\times10\times5=3000\text{ event samples}.
\]

其中：

\[
900=30\%\text{ labeled},
\]

\[
2100=70\%\text{ unlabeled}.
\]

另外 2 个训练字符：

\[
12\times5\times2\times5=600
\]

作为 validation。

这是作者实验设计里比较好的一点：**不是拿真正 test labels 调参数，而是留出已知训练字符构造验证。**

## 6.2 S3VM 的基本逻辑

标准 SVM 只用有标签样本。

S3VM 还利用无标签样本，希望决策边界穿过低密度区域：

```text
少量 labeled
       +
大量 unlabeled
       ↓
避免切过高密度样本簇
       ↓
low-density separator
```

作者采用拉格朗日启发 + annealing，逐渐增强 unlabeled 样本权重。

## 6.3 两个明确的一致性问题

### ① 75.3% vs 67.3%

摘要：

\[
75.3\%.
\]

正文第 6.3 节明确写：

\[
67.3\%.
\]

必须视为结果版本不一致。

### ② `10×75` 维数不自洽

正文同时说：

- 13 channels；
- 每通道 125 points。

则原始展开维度应为：

\[
13\times125=1625.
\]

但文中写成“一个 `10×75` 的向量”。这无法从前述维数推出，应视为符号/编辑错误，除非存在未说明的进一步降维。

## 6.4 最缺的一组实验：same-label-budget baseline

作者画了：

```text
unlabeled sample count ↑
accuracy ↑
```

这能说明无标签数量与自身模型表现相关。

但要证明：

> “semi-supervised 比 supervised 更值得”

必须比较：

```text
900 labeled + 0 unlabeled   → SVM
900 labeled + 2100 unlabeled → S3VM
```

其余条件完全一致。

这组 baseline 在正文中没有被清晰给出。

---

# 7. Q4：睡眠分期

## 7.1 数据本身已经是 feature table

Q4 不是让选手从原始睡眠 EEG 做频谱，而是官方已经给出：

```text
Alpha 8–13 Hz
Beta 14–25 Hz
Theta 4–7 Hz
Delta 0.5–4 Hz
```

能量占比。

因此重点不是信号处理，而是：

> **少样本 multiclass classification + learning curve。**

## 7.2 三模型结果

论文最终比较：

| model | reported accuracy | runtime |
|---|---:|---:|
| SVM | 84% | 0.0193 s |
| LightGBM | 89% | 0.0210 s |
| RF | 89% | 0.0229 s |

作者综合选择 LightGBM。

## 7.3 “交叉验证”实际更像 repeated holdout

附录对 5 个类别分别执行：

```python
train_test_split(..., test_size=0.3)
```

再合并。

这相当于一种近似 stratified holdout。

论文又说每个比例重复 5 次取均值。

因此更准确的名称应该是：

> **repeated stratified random holdout**

而不是标准 k-fold cross-validation。

## 7.4 图的横轴是 test data，不是 train data

例如 LGBM 图峰值在：

\[
test=30\%.
\]

对应训练比例：

\[
train=70\%.
\]

但正文同时出现：

> “选取 30% 睡眠特征数据作为样本”

和：

> “最合适训练集样本数量在 75% 左右”

显然存在 train/test 口径混写。

## 7.5 “训练数据更多导致过拟合”证据不足

作者观察到某些 split 下：

```text
65% train accuracy > 70% train accuracy
```

于是解释为更多训练数据导致过拟合。

这不是可靠因果结论。

同一个固定模型通常增加 IID 训练数据并不会天然增加过拟合；2 个百分点完全可能来自：

- random split variance；
- class / feature distribution variation；
- hyperparameter interaction；
- test set size changed simultaneously。

正确做法是：

```text
固定 test protocol
每个 train fraction 重复多 seeds
mean ± std / CI
```

## 7.6 LightGBM 公开附录无法按字面复现

公开代码有多处明显问题：

- 未见 `import lightgbm as lgb`；
- 前文变量是 `train_data / trian_label / test_data / test_label`，后文却突然使用 `X_train / y_train / X_test / y_test`；
- `num_class: 5` 后缺逗号；
- 最后预测使用未定义 `test_x`。

所以：

> **89% 可以作为论文报告结果，但不能说公开附录已经提供完整可执行复现。**

---

# 8. 为什么这篇仍然是值得读的国一样本

## 8.1 四问衔接非常自然

它没有四问各做一个孤立模型，而是：

```text
Q1 classifier
  ↓
Q2 feature/channel reduction
  ↓
Q3 label-cost reduction
```

前三问实际上都围绕一个 P300-BCI 系统逐步降低成本。

这是非常值得模仿的论文故事线。

## 8.2 每个算法基本有“为什么”

- RF：非线性、高维、集成分类；
- sparse Bayesian：channel sparsity；
- S3VM：标签昂贵、无标签丰富；
- LightGBM/RF/SVM：tabular sleep features。

虽然验证还可以更严格，但不像典型“算法拼盘”。

## 8.3 能交付最终字符，而不是只报 event accuracy

P300 event classifier 最终被还原成：

```text
row + column → actual character
```

这是工程题里非常重要的一点：

> **中间机器学习指标不能替代最终业务输出。**

---

# 9. 如果我是指导老师，我会要求赛前补的实验

1. **Q1 rounds ablation**：1–5 轮 accuracy / ITR；
2. **grouped CV**：按 subject + character / trial 隔离；
3. **class imbalance ablation**：undersampling vs class_weight vs balanced RF；
4. **channel-count curve**：10–19 channels；
5. **nested channel selection**；
6. **supervised vs semi-supervised at equal label budget**；
7. **label-budget curve**；
8. **Q4 learning curve mean±std**；
9. **macro-F1 / per-class recall / confusion matrix**；
10. **一键可运行 appendix**。

如果这 10 项补齐，这篇在今天依然会是一份很强的信号 + 数据建模论文。

---

# 10. 可迁移到正式比赛的核心经验

## 经验 1：先定义“一个独立样本”

信号切片以后，epoch 数量会暴增，但：

```text
10000 epochs ≠ 10000 independent samples
```

必须追溯它们来自哪个 subject / session / trial / group。

## 经验 2：预处理必须在验证边界内

所有从数据学出来的东西：

```text
mean/std
PCA
feature selection
channel selection
threshold
hyperparameter
```

都只能在 train fold 内 fit。

## 经验 3：成本约束必须真的进入评价指标

Q1 不是只最大化 accuracy，而是：

```text
accuracy + rounds / ITR
```

Q2：

```text
accuracy + channel count
```

Q3：

```text
accuracy + label count
```

Q4：

```text
accuracy + train sample count
```

实际上四问有一个统一母题：

> **在资源受限条件下保持预测性能。**

这才是这篇论文最值得我们抽象出来的东西。

---

# 11. 一句话结论

> **这篇最值得学的是“围绕同一个识别系统逐步压缩轮次、通道、标签和训练样本成本”的问题链；最需要改进的是把资源成本真正纳入 evaluator，并用 group-aware、leakage-free 的验证证明压缩后性能仍然成立。**
