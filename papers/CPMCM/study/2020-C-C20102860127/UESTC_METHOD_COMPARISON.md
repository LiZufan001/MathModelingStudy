# 2020 C｜电子科大一等奖队官方方法路线对照

> 目标队：贾召钱、殷康宁、王文超（电子科技大学）  
> 证据范围：仅使用电子科技大学官方新闻公开的方法介绍。  
> **未找到能够与该队成员精确对应的完整论文 PDF，因此本文件不是“论文精读”，不臆测其参数、精度、公式和代码。**

---

# 1. 官方公开的方法链

电子科技大学官方介绍给出的信息：

## 数据预处理

- 脑电可视化分析；
- 带通滤波；
- 小波分析和滤波；
- 异常值处理；
- 冗余数据处理；
- 数据切片；
- 特征选择。

## Q1

- SVM；
- 自设计神经网络；
- 判断样本是否包含 P300；
- 推断字符。

## Q2

- 熵权法；
- 评估原始数据的信息量；
- 去除冗余通道。

## Q3

- TSVM；
- 利用部分无标签样本；
- 半监督识别字符。

## Q4

- K-means；
- 聚类并划分训练/测试；
- 支持向量模型训练与性能评价。

---

# 2. 与本轮精读的东南大学 C20102860127 对比

| 问题 | 电子科大官方方法摘要 | 东南大学 C20102860127 |
|---|---|---|
| preprocessing | bandpass + wavelet + 异常/冗余/切片/特征 | Butterworth bandpass + event epoch |
| Q1 | SVM + neural network | Random Forest + KNN comparison + vote |
| Q2 | entropy-weight channel information | spike-and-slab sparse Bayesian + EP |
| Q3 | TSVM | S3VM + annealing / Lagrangian heuristic |
| Q4 | K-means + SVM | SVM + LightGBM + RF |

---

# 3. 同题异解最值得学什么

## 3.1 Q1：模型不是第一决策，样本表示才是

两队模型不同：

```text
SVM / NN
vs
RF
```

但共同核心是：

```text
continuous EEG
 ↓
event-aligned representation
 ↓
P300 detection
 ↓
row/column → character
```

因此赛场上优先把样本构造做对，再比较分类器。

## 3.2 Q2：通道选择可以有完全不同的数学抽象

电子科大：

```text
information amount / entropy weight
```

东南大学：

```text
sparse support posterior
```

一个偏综合评价，一个偏统计稀疏建模。

真正 evaluator 应统一：

```text
channel count
+
downstream character accuracy
```

这样才能公平比较方法。

## 3.3 Q3：两队都抓住了 transductive/semi-supervised 结构

TSVM 与 S3VM 本质上属于同一类思路：

> 决策边界应尽量穿过无标签样本的低密度区域。

这说明 Q3 的“半监督”不是某队偶然堆出的算法，而是题面结构自然导出的方向。

## 3.4 Q4：最有争议的反而是 validation

电子科大公开摘要提到 K-means 聚类后划分训练/测试。

这值得特别警惕：

> 聚类可以作为数据结构探索，但不能因为“让 train/test 看起来分布均匀”就破坏独立泛化评价。

没有全文，不能评价该队具体实现；但我们自己的比赛协议仍应坚持：

```text
split protocol first
model training second
```

---

# 4. 为什么保留这份对照

因为只精读一篇优秀论文容易形成：

> “这道题就应该用 RF / sparse Bayesian / S3VM”

的错觉。

同题异解提醒我们：

> **优秀论文的价值是抽象方式，而不是算法唯一答案。**

2020 C 真正稳定的结构是：

```text
P300 event mechanism
→ feature / channel redundancy
→ label scarcity
→ sleep-stage small-sample classification
```

算法可以替换，问题结构不能忽略。

---

# 5. 使用边界

本文件关于电子科大队只记录校方公开信息。

不写：

- 未公开的准确率；
- 未公开的网络结构；
- 未公开的超参数；
- 未公开的最终字符；
- 未公开的代码。

以后若找到能够由封面参赛编号/成员精确验证的全文，再单独建立真正精读目录，不覆盖本轮东南大学材料。
