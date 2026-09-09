# 2024 B 国一论文精读：B24102860287

> 赛题：WLAN 组网中网络吞吐量建模  
> 参赛编号：`B24102860287`  
> 团队：栾兴、徐泽辰、徐明晖（东南大学）  
> 奖项：全国一等奖；提名“数模之星”答辩；华为专项一等奖  
> 原论文：[`../../2024/fulltext/B/B24102860287.pdf`](../../2024/fulltext/B/B24102860287.pdf)

---

# 0. 指导老师先给结论

这篇论文最值得学的不是“随机森林 + CNN”本身，而是它试图把 WLAN 的协议机理逐层转成可学习特征，再把三个问题串成一条完整预测链：

```text
网络拓扑 / 门限 / RSSI / 流量
          ↓
Q1：信道接入与发送机会 seq_time
          ↓
Q2：传输方式 / 干扰 → PHY Rate → (MCS,NSS)
          ↓
Q3：发送机会 + 真实(MCS,NSS) + 其他信息 → throughput
```

其最有训练价值的思路是：

> **不要把原始 RSSI 直接扔进模型；先理解 PD、ED、NAV、同步/异步传输、AMC、PHY Rate 等通信机制，再构造能够反映这些机制的特征。**

但是，对原题、正文、90 页论文附录代码和原始数据进行交叉核验后，这篇同样必须批判性学习。最重要的问题集中在**验证设计与实现口径**：

- Q1 正文声称使用“按树误差加权”的改进随机森林，但公开附录代码实际调用的是标准 `RandomForestRegressor`，未见逐树加权实现；
- 数据是“一次实验对应 2 或 3 条 AP 行”的组结构，但训练/验证采用随机按行切分，导致同一实验的兄弟 AP 同时进入训练集和验证集；
- Q2 的 3AP 验证准确率代码按 `NSS`、`MCS` 两个坐标分别计正确，而不是要求整个 `(NSS,MCS)` 对同时正确；
- Q2 把由 RSSI 差构造的量普遍称为 SINR，但 3AP 多干扰源的功率并未在线性域合并；
- Q3 公开代码将排序误差的 **10% 分位点**当成题面要求的 **90% 分位点**，并且使用的是训练批次误差；
- Q3 2AP 只留 `1%` 数据作验证，对当前训练规模约等于 **4 行**，且这 4 行全部与训练集存在同一实验组；
- Q3 代码把 `per` 作为输入，而原题明确说“统计信息”为模型输出，只特别允许 Q3 使用真实 `(MCS,NSS)`；真实 PER 是否允许作为输入至少存在很高的题意风险；
- Q3 的 1D CNN 实际是在一个扁平特征向量上卷积，相邻“特征位置”并不天然等价于时间邻域，正文所说的“时间序列局部模式”与实现并不完全一致。

因此，这篇最正确的学习方式是：

> **学习“机理驱动特征工程 + 多问题复用 + 失败后重构目标”的思路；不要照搬其数据切分、指标实现和 CNN 选择。**

---

# 1. 原题三问真正考什么

## 1.1 问题一：发送机会

输入是：

- 同频 AP 数量和拓扑；
- TCP / UDP 等业务流量；
- PD / ED / NAV 门限；
- AP↔AP、AP↔STA、STA↔STA 的 RSSI 测量序列；
- 发射功率等基础信息。

输出：

\[
seq\_time
\]

即 AP 在一次测试中实际发送数据帧序列的总时长。

同时要求回答：

> 哪些输入因素最影响 AP 获得发送机会？影响强弱如何排序？

这不是纯回归题，而是“**解释 + 预测**”双任务。

## 1.2 问题二：最常使用的 (MCS,NSS)

WLAN 的 AMC 会根据实际信道质量不断调整调制编码方式和空间流数。题目要求从网络基本信息、RSSI 和门限，以及 Q1 对发送机会的分析出发，预测一次实验中出现次数最多的：

\[
(MCS,NSS).
\]

物理逻辑是：

```text
是否同步发送 / 是否发生邻区干扰
            ↓
接收端 SINR
            ↓
AMC 自适应选择 PHY Rate
            ↓
(MCS,NSS)
```

## 1.3 问题三：吞吐量

最终预测：

\[
Throughput.
\]

题目明确允许使用实测的真实 `(MCS,NSS)` 作为输入，因为 Q2 受小尺度信道快速变化影响，本身可能无法很高精度地预测速率。

最终评价不是 RMSE，而是**误差 CDF 的 90% 分位点**。

题面定义：

\[
error=\frac{\widehat y-y}{y}\times100\%.
\]

找到满足

\[
P(error\le ERROR)=90\%
\]

的 `ERROR`，再定义模型精度：

\[
Accuracy=1-ERROR.
\]

因此，“90% 分位点到底有没有算对”是 Q3 的核心验收项。

---

# 2. Q1：最值得学习的是“门限机制 → 统计特征”

论文没有只把 RSSI 序列取一个平均值，而是根据题面明确给出的信道接入规则构造特征。

## 2.1 NAV 对平均天线 RSSI

题目规定 NAV 判决采用多天线 RSSI 的平均值，因此作者统计：

\[
P_{over\_nav}
=\frac{\#\{RSSI_{mean}>NAV\}}{N}.
\]

它可以近似表达：

> 另一个节点的信号有多大比例会触发虚拟载波监听，从而使本 AP 延迟发送。

## 2.2 PD / ED 对最大天线 RSSI

PD/ED 判决使用最大天线 RSSI，因此类似定义：

\[
P_{over\_pd},\qquad P_{over\_ed}.
\]

这种处理很值得迁移：

> **当题面给出阈值判定机制时，不要只把“测量值”和“阈值”分别作为两个特征；应该主动构造“超过阈值的比例、距离阈值的 margin、分位数”等机制特征。**

## 2.3 低于 PD 的接收功率

作者还将低于 PD 的 RSSI 转到线性功率域做统计，用来表达无法被解码、但仍可能形成背景能量的信号。

这个方向是正确的，因为：

\[
dBm
\]

本身是对数单位，涉及功率叠加时应转为线性域。

---

# 3. Q1 随机森林：结果很醒目，但解释不能过度

论文给出的主要特征影响：

### 2AP

| 特征组 | 影响 |
|---|---:|
| AP 与 AP 间 RSSI | **87.96%** |
| AP 与 STA 间 RSSI | 7.01% |
| 协议类型 | 2.32% |
| 网络拓扑 | 1.27% |
| 发射功率 | 1.22% |
| NAV 门限 | 0.18% |
| BSS 编号 | 0.04% |

### 3AP

| 特征组 | 影响 |
|---|---:|
| AP 与 AP 间 RSSI | **74.94%** |
| AP 与 STA 间 RSSI | 18.14% |
| 协议类型 | 5.12% |
| 网络拓扑 | 0.74% |
| 发射功率 | 0.72% |
| NAV 门限 | 0.19% |
| BSS 编号 | 0.16% |

物理解释是可信的：AP↔AP 的互听关系直接决定 CSMA/CA 下是否让步、同步还是异步发送，因此与发送机会高度相关。

但“87.96%”不能解读成严格因果贡献 87.96%。附录使用的是随机森林 `feature_importances_`，属于基于 impurity decrease 的特征重要度。它存在：

- 连续/高基数变量偏置；
- 高相关特征之间会互相分摊或争抢重要度；
- 无法证明因果关系。

因此更严谨的论文措辞应是：

> “在当前随机森林和当前特征编码下，AP↔AP RSSI 特征组贡献了约 87.96% 的 impurity-based importance。”

最好再用 permutation importance、SHAP 和 ablation 交叉验证。

---

# 4. Q1 正文与公开实现的第一处明显断裂：加权随机森林

正文 3.2.4 明确提出：

- 传统随机森林树等权；
- 本文根据每棵树的预测误差赋权；
- 最终使用

\[
\hat y=\frac{\sum_i\omega_i f_i(x)}{\sum_i\omega_i}.
\]

但附录 `Q1_randomforest_analysis_3AP.py` 实际代码是：

```python
rf = RandomForestRegressor(n_estimators=200, random_state=42)
rf.fit(X_train, y_train)
y_pred = rf.predict(X_test)
```

没有看到：

- 单树误差计算；
- `ω_i`；
- 自定义加权 ensemble；
- 多个场景模型再加权的实现。

2AP 附录同样直接使用标准 `RandomForestRegressor`。

因此我们只能得出：

> **论文提出了加权随机森林思想，但公开附录无法验证最终结果确实由该改进模型产生。**

不能直接说作者比赛内部一定没实现，因为论文附录可能不是最终运行工程的完整快照。

---

# 5. 更严重的问题：随机按行切分造成组泄漏

原始数据并不是独立同分布的一行一个实验。

一次 `test_id` 对应：

- 2AP：通常 2 行；
- 3AP：通常 3 行。

这些行来自**同一次物理实验**，共享：

- loc / topology；
- protocol；
- threshold；
- 流量条件；
- 同一组 AP↔AP / AP↔STA RSSI 背景。

但附录 Q1 使用：

```python
train_test_split(...)
```

直接按行随机切分。

我们对原始训练数据重新核算：

| 数据 | 有标签行数 | 独立实验组 | 论文式验证比例 | 验证行中同组已出现在训练集的比例 |
|---|---:|---:|---:|---:|
| 2AP Q1 | 392 | 196 | 20% | **82.3%** |
| 3AP Q1 | 858 | 286 | 5% | **100%** |

也就是说，模型验证时大量样本其实是在问：

> “同一次实验的另一个 AP 已经在训练集里了，我能不能预测当前 AP？”

而不是更重要的：

> “面对一个从未见过的新实验条件，我还能不能预测？”

### 正确做法

至少使用：

```python
GroupShuffleSplit / GroupKFold
```

并以：

```text
(source_file, test_id)
```

作为 group。

更强的测试还应做：

- leave-one-location-out；
- leave-one-NAV-setting-out；
- topology/protocol 组合外推。

这才真正测试泛化。

---

# 6. Q2：论文有一个非常值得学的“失败 → 重新定义目标”过程

作者一开始把 `(MCS,NSS)` 编码成 25 类，直接分类。

结果模型迅速坍缩到：

\[
(NSS=2,MCS=11)
\]

几乎不再改变。

这不是偶然。我们重新统计原始训练集：

### 2AP

- `(2,11)` 占 **63.52%**；
- `NSS=2` 占 **96.94%**。

### 3AP

- `(2,11)` 占 **41.38%**；
- `NSS=2` 占 **98.02%**。

严重类别不平衡会让普通分类器很容易靠主类获得看似不错的 accuracy。

作者没有强行坚持原模型，而是重新观察物理意义：

```text
(MCS,NSS)
   ↓
对应 PHY Rate
```

转而预测连续的 PHY Rate，再反推 `(MCS,NSS)`。

这个“失败后重构 target”的动作非常值得学习：

> **当分类标签具有明确的有序/物理连续含义时，不一定要坚持 one-hot 分类，可以转成有序回归、连续物理量预测或层次化预测。**

---

# 7. 但 PHY Rate → (MCS,NSS) 并不是天然一一映射

20 MHz 的速率表中存在重叠，例如：

\[
17.2=(NSS1,MCS1)=(NSS2,MCS0),
\]

\[
34.4=(NSS1,MCS3)=(NSS2,MCS1),
\]

\[
51.6=(NSS1,MCS4)=(NSS2,MCS2),
\]

\[
68.8=(NSS1,MCS5)=(NSS2,MCS3),
\]

\[
103.2=(NSS1,MCS8)=(NSS2,MCS4).
\]

论文观察到 2AP 数据里“PHY Rate >100 Mbps 时 NSS=2，<100 Mbps 时 NSS=1”，这只是**数据集中的经验规律**，并非 PHY Rate 表本身的数学唯一映射。

我们重新映射训练集后也发现真实歧义：

- 2AP 的 `68.8 Mbps` 同时出现 `(1,5)` 与 `(2,3)`；
- 3AP 的 `51.6 Mbps` 和 `68.8 Mbps` 都出现多个 `(NSS,MCS)` 组合；
- 论文的 `100 Mbps` NSS 经验规则在训练集上约有 **1%** 样本违反。

因此更稳的做法是：

1. 先预测 `NSS`；
2. 再条件预测 `MCS | NSS`；

或直接做 ordinal / multitask learning，而不是把 PHY Rate 当绝对唯一编码。

---

# 8. Q2 的“86.73%准确率”必须问：到底怎么算的？

3AP 附录验证代码：

```python
predicted = torch.round(outputs)
correct += (predicted == targets).sum().item()
total += targets.numel()
accuracy = correct / total
```

`targets` 有两个坐标：`NSS` 和 `MCS`。

这段代码实际统计的是：

\[
\frac{\#\text{正确的坐标个数}}{2N},
\]

而不是：

\[
\frac{\#\{\hat NSS=NSS\ \land\ \hat MCS=MCS\}}{N}.
\]

如果 NSS 对、MCS 错，一个样本仍获得 50% 正确。

这在当前数据极不平衡时尤其危险：仅恒定预测 `(2,11)`，我们重新计算得到：

| 数据 | pair accuracy | coordinate accuracy |
|---|---:|---:|
| 2AP | 63.52% | **80.23%** |
| 3AP | 41.38% | **69.70%** |

因此正文所说的 **86.73%** 如果来自这套坐标级 evaluator，就不能等价解释为“86.73% 的样本完整 `(MCS,NSS)` 预测正确”。

比赛中必须同时报告：

- exact-pair accuracy；
- NSS accuracy；
- MCS accuracy；
- macro-F1 / balanced accuracy；
- confusion matrix。

---

# 9. Q2 的 SINR：机理方向正确，物理实现需要更严谨

题目本身针对“两 AP 互不听”的情况明确允许忽略底噪，并用 RSSI 差近似 SINR：

\[
SINR_{dB}\approx RSSI_{signal}-RSSI_{interference}.
\]

所以在 2AP 的特定场景下，RSSI 差是有题面依据的。

但论文推广到一般情况时写成：

\[
RSSI_s-(RSSI_i+Noise),
\]

若这些量都以 dBm 表示，则功率不能直接在 dBm 中相加。

一般正确形式应先进入线性域：

\[
SINR_{dB}
=P_{s,dBm}
-10\log_{10}\left(
\sum_j10^{P_{j,dBm}/10}+10^{N_{dBm}/10}
\right).
\]

而公开 3AP 代码实际计算的是多个**两两 RSSI 差**：

```python
sinr_0 = signal - interferer_0
sinr_1 = signal - interferer_1
```

更准确的名称应是：

> pairwise SIR margin / RSSI margin

而不是完整多干扰源 SINR。

### 更大的机理问题

干扰是否存在本身取决于 Q1 所分析的“同步 / 异步发送概率”。

所以真正更强的 Q2 应该使用：

\[
P(sync),\quad P(async)
\]

构造状态混合模型，而不是默认所有邻 AP 始终同时形成干扰。

---

# 10. Akima 插值到 540：工程上方便，但要证明它没有制造假结构

论文把不同长度的 RSSI 序列统一 Akima 插值到 540 点，其依据是观察到最长序列约 521，向上取到 540。

优点：

- CNN 输入尺寸统一；
- Akima 比高阶样条更不容易过冲；
- 能保留原序列大体变化趋势。

但需要问：

> 原始 RSSI 序列的“第 20 个采样点”和另一次实验的“第 20 个采样点”真的对应同一个物理时间吗？

若长度差来自：

- 测量时长变化；
- 异常值过滤；
- 丢采样；
- 不同记录间隔；

直接按归一化索引插值可能创造人为的平滑“时间结构”。

更好的比赛验证：

- 统计量特征 baseline（mean/max/std/quantile/threshold ratio）；
- Akima-540；
- 其他长度 256/384/512/640；
- mask + variable-length model；

做一次消融即可证明 540 是否真的有价值。

---

# 11. Q3：论文的思想链很好

论文在 Q3 试图把：

- 发送机会；
- PHY Rate / `(MCS,NSS)`；
- PER；
- TCP/UDP；
- RTS/CTS；
- 竞争窗口；
- 聚合机制；

统一解释为吞吐量来源。

其基本工程 intuition 是对的：

\[
Throughput
\approx
\frac{\text{成功有效载荷}}{\text{总占用时间}}.
\]

并且 Q3 按题面许可直接使用真实 `(MCS,NSS)`，而不是强行把 Q2 的预测误差继续传下去，这是非常聪明的“尊重题目接口”的做法。

---

# 12. 但 Q3 正文讲的“协议模型”没有完全进入代码

正文大量讨论：

- CWmin / CWmax；
- 二进制指数退避；
- DIFS；
- RTS/CTS；
- AMPDU / AMSDU；

但 2AP 主预测代码 `cnn_predict3.py` 的实际输入构造是：

```python
X = data.drop(columns=[
    'throughput',
    'other_air_time',
    'ppdu_dur',
    'num_ampdu'
])
X['target_PHY_rate'] = map(nss, mcs)
```

也就是说：

- `other_air_time` 被删；
- `ppdu_dur` 被删；
- `num_ampdu` 被删；
- 没有显式 CW / DIFS 状态；
- 真实 `per` 却被保留下来。

所以论文的协议解释更多属于**机理叙事**，并没有全部落实成最终预测器的显式变量。

比赛时必须建立“文字—变量—代码”三列表，确保正文每个声称进入模型的机制都能在代码中找到对应变量。

---

# 13. Q3 最大的评审问题：CDF 90% 分位点算反了

题面要求 90% 分位点。

但附录 2AP、3AP 都写：

```python
sorted_errors = np.sort(all_errors)
threshold_index = int(len(sorted_errors) * 0.1)
top_10_percent_error = sorted_errors[threshold_index]
acc = 1 - top_10_percent_error
```

对升序排列：

```text
0.1*N
```

对应的是 **10% 分位点**，不是 90% 分位点。

正确应近似为：

```python
q90 = np.quantile(errors, 0.90)
accuracy = 1 - q90
```

而且论文代码中的 `errors` 是：

```python
abs((prediction-target)/target)
```

题面定义的是有符号 `error`。若我们认为官方真实意图是误差幅值，也必须在论文中说明并额外报告官方口径，不能无声替换。

---

# 14. 更严重：所谓 Q3 “accuracy”来自训练误差，不是验证误差

附录在每个 epoch 的训练循环里收集：

```python
for X_batch, y_batch in train_loader:
    outputs = model(X_batch)
    ...
    all_errors.extend(...)
```

随后直接计算 `acc`。

因此论文 loss/accuracy 文件中记录的 accuracy 实际基于**训练批次**。

2AP 虽然随后另有 `test_loader`，但并没有用这个验证集重新计算题面 CDF accuracy。

更何况 2AP 使用：

```python
test_size=0.01
```

在当前 392 条有标签数据上，仅约 **4 行**。

我们模拟论文的 `random_state=42` 划分发现：这 4 条验证行 **100% 都与训练集共享同一个实验组的另一 AP 行**。

因此正文“2AP 和 3AP 验证准确率超 95%，体现良好泛化能力”的表述，不能由公开附录代码严格支持。

---

# 15. 3AP Q3 甚至没有真正的标签验证集

3AP 公开脚本：

```python
train_data = ...training...
test_data = ...official test...
X_train = train_data.drop(columns=['throughput'])
y_train = train_data['throughput']
X_test = test_data.drop(columns=['throughput'])
y_test = test_data['throughput']
```

官方 test 的 `throughput` 本来就是空值。

所以：

```python
test_loss = criterion(y_pred, y_test_tensor)
```

并不能形成有效的监督验证。

这进一步说明：论文的“validation accuracy”与真正的 unseen labeled validation 之间存在实现断裂。

---

# 16. 一个很容易被忽略的题意风险：Q3 是否可以使用真实 PER？

原题在总说明里把：

- `(MCS,NSS)`；
- PER；
- seq_time；
- throughput；

归入测试中收集的帧统计信息，并将其描述为模型输出。

Q3 随后特别写：

> 允许采用实测中统计的数据帧真实 `(MCS,NSS)` 作为模型输入变量。

它**没有同样明确放行 PER**。

但官方 `test_set_1` 中确实填入了真实 PER，而论文 Q3 代码也把 `per` 保留为输入。

这里存在两种解释：

1. 官方既然在 test_set_1 给了 PER，就默认允许使用；
2. 题面只明确开放 `(MCS,NSS)`，PER 仍属于不应使用的输出统计量。

在没有官方澄清时，评审最安全的做法是：

> **主模型不要依赖真实 PER；若使用，应在论文中明确说明题意解释，并额外给一个不使用 PER 的版本。**

尤其因为 PER 与成功传输和吞吐量高度相关，它可能显著降低预测难度。

---

# 17. Q3 用 1D CNN 卷积“特征顺序”，理由并不充分

2AP `cnn_predict3.py` 的输入流程是：

```python
X = numerical_tabular_features
X = scaler(X)
X = expand_dims(X, axis=2)
X = permute -> [batch, 1, feature_count]
Conv1d(kernel_size=2)
```

因此卷积核滑动的是：

```text
第1个表格特征、第2个表格特征、第3个表格特征……
```

不是原始 RSSI 时间序列。

如果只是改变 DataFrame 列顺序，CNN 的局部邻接关系也会改变。

这说明正文“3×1 卷积捕捉相邻时间步模式”的解释与公开实现并不一致。

对这种表格特征，更自然的 baseline 应包括：

- CatBoost / LightGBM / XGBoost；
- RandomForest / ExtraTrees；
- MLP。

只有当输入确实是时间轴或有明确空间邻接意义的矩阵时，CNN 才具有强归纳偏置优势。

---

# 18. 为什么这篇仍然能成为顶级获奖论文？

必须把“论文整体水平”和“附录审计问题”分开。

它的整体竞赛优势非常明显：

## 18.1 题目理解完整

三问的物理链被统一成：

```text
信道接入 → 发送机会 → 速率 → 吞吐量
```

## 18.2 不是纯黑箱

作者真正使用了：

- NAV / PD / ED；
- RSSI 门限；
- AP 互听；
- 同步 / 异步传输；
- AMC；
- PHY Rate；
- PER / 业务流量；

来解释为什么构造这些变量。

## 18.3 能诊断失败模型

直接 25 分类塌缩后，没有硬凑，而是改成 PHY Rate 表征。

## 18.4 工程交付非常完整

论文附有大量：

- 预处理代码；
- RF/CNN 训练代码；
- 结果表；
- 图；
- 最终测试集预测。

## 18.5 论文故事非常顺

评委容易理解：

> “先解释谁能发，再解释用多高速率发，最后预测总吞吐量。”

这在竞赛评审中价值很大。

因此更准确的评价是：

> **这是一篇“问题链设计和工程完成度很强、验证协议和实现一致性不足”的高水平竞赛论文。**

---

# 19. 如果我是指导老师，今天让我们团队重做

我会要求按这个顺序：

```text
Step 1  建立 experiment-level group key
Step 2  official evaluator 单独锁死
Step 3  按机理构造 threshold / margin / topology 特征
Step 4  Q1 用 RF / CatBoost baseline + grouped CV
Step 5  用 permutation / SHAP / ablation 验证“AP↔AP RSSI最重要”
Step 6  Q2 先做 transmission-regime / sensing-graph 特征
Step 7  用正确线性功率计算 aggregate interference
Step 8  层次预测 NSS → MCS，或 ordinal model
Step 9  Q3 先写 airtime / payload 的物理 baseline
Step 10 用 ML 只学习物理 baseline 的 residual
Step 11 使用 GroupKFold + leave-location-out
Step 12 最后一次性在官方 test 上推理
```

---

# 20. 我们真正应该带走的 10 条经验

1. **机器学习题先画机制图，再画模型结构图。**
2. 门限类问题主动构造 `margin / exceedance ratio / quantile`。
3. 同一次实验产生多行数据时，必须按 experiment/group 切分。
4. RF importance 不是因果贡献百分比。
5. 类别严重不平衡时，accuracy 先和 majority baseline 比。
6. 有序标签应考虑 ordinal / regression / hierarchical formulation。
7. dBm 只能做差描述比值；多个功率相加先转线性域。
8. CNN 的卷积邻域必须有真实语义，不能因为“数据是矩阵”就自动合理。
9. 官方 evaluator 必须写成唯一真源，并用手工小样例测试 10%/90% 等边界。
10. **任何“泛化良好”的结论，都必须先证明验证集真正独立。**

---

# 21. 本篇定位

如果前三篇分别训练：

- 2022 C：状态仿真 + 调度；
- 2020 F：机理 + 动态优化；
- 2021 A：矩阵结构 + 算法复杂度；

那么 2024 B 最适合训练的是：

> **机理驱动的数据建模 + 特征工程 + 严格验证。**

这篇真正值得我们提升的地方不是“以后也用 CNN”，而是：

> **看到数据题时，既不能只讲物理不做预测，也不能只堆模型不懂业务；最强的方案是把业务机制做成可验证特征，再用严格独立的验证协议判断模型是否真的有效。**
