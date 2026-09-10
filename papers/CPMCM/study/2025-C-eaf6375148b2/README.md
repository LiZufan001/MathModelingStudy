# 2025 C 证据级深读：Frangi 裂隙识别与三维概率重构

> 赛题：围岩裂隙精准识别与三维模型重构  
> 候选证据 ID：`graduate:paper:2025-C:eaf6375148b2`  
> 候选论文：`基于Frangi滤波的钻孔裂隙识别与三维概率重构`  
> 候选 PDF 指纹：91 页，SHA256 `eaf6375148b2dcc67f9491df2577e4e44a91c5ee32a028a1f4ff2f2860bc17f1`  
> **状态：证据级深读，尚未看到 PDF 封面，不能绑定为 `C25102900037`。** 详细来源见 [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md)。

---

# 0. 指导老师先给结论

这篇候选论文最值得学习的不是“用了 Frangi 和 Monte Carlo”两个模型名，而是它构造了一条很完整的**对象升级链**：

```text
像素灰度 / 纹理
      ↓
裂隙二值掩码
      ↓
连通片段 / 正弦参数
      ↓
去趋势粗糙轮廓 / JRC
      ↓
柱面三维点 / 裂隙平面
      ↓
带不确定性的平面参数
      ↓
连通性评分 / 概率重构
      ↓
全局不确定性场
      ↓
补充钻孔建议
```

这非常符合 2025 C 原题的真正结构：后问不是另起炉灶，而是不断把前问输出升级成更接近地下真实结构的对象。

候选论文有几处很值得高水平竞赛队模仿：

1. **Q1 没有强行深度学习。** 附件 1 只有 10 张、且无像素真值，作者实际试过 RF/SVM/XGBoost，发现训练数据泄漏和跨图泛化很差后，主动退回 Frangi + morphology；这是一种很成熟的“模型选择由数据条件决定”叙事。
2. **Q2 是“先聚合后提纯”。** 先把断裂的二值片段闭运算连接，再用质心 DBSCAN 粗聚类，初拟合后检测异常块，再精炼正弦参数；不是一次 least-squares 到底。
3. **Q3 知道宏观正弦趋势不能冒充微观粗糙度。** 先去掉正弦趋势，再研究 JRC；断裂处不强行插值，而是分段计算，避免虚构粗糙度。
4. **Q4 明确把“不确定性”当输出。** 不是只画一个确定的 3D 裂隙网络，而是用 Monte Carlo 扰动平面参数，继续向连通性和补钻传播。
5. 摘要把三条创新点单列，评审阅读成本低；正文每问先列核心挑战，再对应方法，叙事很清楚。

但是，如果我是严格评审老师，这篇最值得追问的恰恰也是 Q3/Q4：

- 原题给出的 Barton 标准 JRC 体系是 0–20，候选结果却出现 **16.28–39.36**，超过标准量程的部分如何解释？
- 分段后直接“按长度平均 JRC”是否符合 JRC 的非线性定义？
- 等弧长采样改变采样测度后，是否还在估计官方式 (3) 的同一个 `Z2`？
- “JRC 越大 → 平面法向量不确定性越大”的映射依据是什么？
- 对法向量三个分量独立加高斯噪声，是否仍保持单位法向量和球面几何？
- 用样本自身的 95% 区间线性映射距离/夹角到 `[0,1]`，得到的究竟是**概率**还是**归一化评分**？
- 最后三个补钻坐标来自不确定性云图目视选择，没有显式目标函数、工程约束和预期信息增益，是否真的称得上“最优”？

所以这篇最适合我们的学习姿势是：

> **学它“像素→几何→粗糙度→空间→不确定性→决策”的层级设计；同时把 sampling measure、probability calibration 和 experimental design 做得比它更严格。**

---

# 1. 原题真正要求什么

官方题面给出了非常明确的四层任务。

## Q1：像素级裂隙识别

需要区分：

- 真实裂隙；
- 天然纹理；
- 钻进痕迹；
- 泥浆污染；
- 图像拼接线。

而且题面还给了一个很重要的地质判据：

- 若“正弦状”曲线有明显张开，**裂隙宽度超过 1 mm**，且内部填充与岩石基质不同的水/气/异质材料，可判断为裂隙；
- 若两侧紧密贴合、岩石连续过渡，更可能是岩层界面。

因此 Q1 从来不只是“找黑色细线”，而是**视觉线结构 + 物理宽度 + 填充/连续性语义**。

## Q2：正弦状裂隙参数化

钻孔直径：

\[
D=30\text{ mm},\qquad r=15\text{ mm},
\]

周长约：

\[
L=\pi D\approx94.25\text{ mm}.
\]

展开图中，平面裂隙与柱面的交线呈正弦状，需要估计：

\[
(R,P,\beta,C).
\]

其中完整裂隙的周期理论上应接近钻孔周长：

\[
P\approx94.25\text{ mm}.
\]

## Q3：复杂裂隙 JRC

题目给 Barton 标准轮廓：

```text
JRC 0–2, 2–4, ..., 18–20
```

要求：

- 提取每条裂隙离散轮廓；
- 计算 JRC；
- 专门讨论不同离散采样方法；
- 讨论裂隙面积对粗糙度评价的作用。

因此“怎么采样”本身就是问题，不只是一个代码参数。

## Q4：多钻孔三维重构

6 个竖直钻孔采用 2×3 阵列，相邻孔间距 1000 mm：

```text
1# (500, 2000)   2# (1500, 2000)   3# (2500, 2000)
4# (500, 1000)   5# (1500, 1000)   6# (2500, 1000)
```

除 4# 深 5000 mm 外，其余 7000 mm。

题目不仅要三维图，还明确要求：

1. **相邻钻孔裂隙连通概率**；
2. **当前布局下高不确定性区域**；
3. 在资源限制下，按优先级给 **3 个最优补充钻孔位置**。

这实际上已经从 reconstruction 进入了：

\[
\boxed{\text{uncertainty-aware experimental design}}
\]

---

# 2. Q1：为什么 Frangi 在这里是有针对性的

## 2.1 作者的数据判断比模型名重要

第三方全文审读记录显示：作者曾尝试：

```text
RF / SVM / XGBoost
+ 手工图像特征
+ leave-one-out validation
```

但发现：

- 附件 2 与附件 1 存在重复/高度重合样本，导致数据泄漏；
- 去掉泄漏后，其余图上的泛化明显变差；
- 附件 1 本身只有 10 张图且没有像素级 ground truth。

最终作者没有继续堆机器学习，而是改成传统图像处理。

这个过程比“最终用了 Frangi”更值得学：

> **模型失败不是论文必须藏掉的东西；如果失败能解释为什么最终路线更合理，它反而是强证据。**

## 2.2 最终 Q1 链

记录中的 Q1 页码范围为 p.9–43，主流程：

```text
BT.601 grayscale
 ↓
illumination normalization
 ↓
multiscale Frangi
 ↓
Otsu
 ↓
morphology / area filtering / skeleton
 ↓
connected components + geometry
 ↓
prior mask for mud/seam directions
 ↓
second threshold + postprocess
 ↓
binary fracture mask
```

### 光照归一

候选对比四组预处理：

1. 仅灰度；
2. 灰度 + 对比度；
3. 灰度 + 光照归一；
4. 进一步去噪。

最终定性选择“灰度 + 光照归一”综合最好。

值得注意的是，作者没有像素真值，因此没有假装给出 Dice=0.95 之类数字，而是明确承认这是定性比较。这种**结论强度与证据强度一致**的写法值得模仿。

### Frangi

Frangi 的关键不是“医学图像算法”，而是 Hessian 的局部二阶结构。

对二维细长线/管状结构，一个方向沿裂隙变化较慢，另一个方向跨裂隙灰度变化强，常表现为：

\[
|\lambda_1|\ll|\lambda_2|.
\]

再通过类似 blobness 比和结构强度：

\[
R_B=\frac{|\lambda_1|}{|\lambda_2|},
\qquad
S=\sqrt{\lambda_1^2+\lambda_2^2},
\]

抑制块状背景、突出细长裂隙；多尺度 `σ` 取最大响应以兼容不同宽度。

这与“裂隙是延展的暗色带状/线状结构”的图像机理是匹配的。

## 2.3 评审老师会追什么

### 1. Frangi 能区分裂隙和岩层界面吗？

不一定。

两者都可能是正弦/线状暗结构，而原题明确给了：

```text
width > 1 mm
+ filling material difference
```

的地质判别条件。

所以更完整模型应该：

```text
Frangi candidate mask
       ↓
metric width / edge separation
+ inside-vs-rock appearance contrast
+ continuity across the curve
       ↓
fracture vs bedding-interface classifier/rule
```

### 2. 方向先验会误删真裂隙吗？

作者利用水平/垂直方向组件去除：

- 泥浆竖条；
- 拼接线横条。

这很实用，但真实裂隙也可能局部水平/垂直。

所以“hard mask”最好变为：

\[
P(\text{fracture}\mid image,orientation,context)
\]

或至少保留 uncertain mask，避免先验直接覆盖图像证据。

### 3. PSNR/SSIM 能验证裂隙增强吗？

只能部分验证图像变化，不能证明 fracture segmentation 更准。

没有标签时，更适合：

- 人工少量标注关键图；
- 合成裂隙注入；
- sensitivity：预处理改变是否导致 Q2 参数剧烈变化；
- downstream validation：不同 Q1 mask 对 Q2/Q3 的影响。

---

# 3. Q2：“先聚合后提纯”为什么值得学

全文审读记录给出的 Q2 为 p.44–55，共输出 34 条裂隙参数，并额外报告：

- 拟合误差约 0.05–0.96；
- 缺失比例约 7%–77%。

主链：

```text
binary fragments
 ↓ closing
larger connected fragments
 ↓
component centroids
 ↓ DBSCAN
coarse fracture groups
 ↓
initial sine fit
 ↓
outlier point/block detection
 ↓
refined nonlinear least squares
 ↓
R, P, beta, C + error + missing rate
```

这个设计的优点在于：

> **聚类不是最终答案，只负责把“可能属于同一条裂隙”的碎片放到一起；物理模型拟合再负责提纯。**

这和很多比赛中的：

```text
cluster → physical fit → reject → refit
```

是高度可迁移的。

## 3.1 物理尺度必须注意 x/y 各向异性

附件 1–3：

```text
244 × 1350 px
对应：94.25 mm × 500 mm
```

因此约：

\[
\Delta x\approx94.25/244\approx0.386\text{ mm/px},
\]

\[
\Delta y\approx500/1350\approx0.370\text{ mm/px}.
\]

这不是完全相同的比例。

所以拟合前必须先做：

\[
(pixel_x,pixel_y)\to(x_{mm},y_{mm}),
\]

不能在像素坐标里假设欧氏距离就是实际毫米距离。

## 3.2 DBSCAN 只按质心 y 聚类的风险

候选利用“同一裂隙片段垂直位置相近”的先验做粗聚类，适合大多数分离曲线。

但在：

- 两条裂隙相互交叉；
- 大振幅正弦覆盖很宽 y 范围；
- 两条不同裂隙中心线接近；

时，单纯 y proximity 可能：

```text
merge two fractures
or
split one fracture
```

更严格的替代路线：

- RANSAC/model-based clustering；
- Hough-like sine parameter voting；
- mixture of sinusoids + EM；
- graph clustering with position + orientation + local phase continuity。

## 3.3 报“缺失比例”是很好的习惯，但还差一步

论文中甚至有缺失约 71% 乃至更高的裂隙仍保留参数。

这时必须回答：

> 只剩不到 30% 的曲线，`P/R/β/C` 还可辨识吗？

建议用 synthetic missingness test：

```text
完整正弦真值
→ 随机/块状删除 10% ... 80%
→ 重拟合
→ 参数偏差 / CI
```

然后为参数输出附：

\[
\hat\theta\pm CI,
\]

而不是只给一个 point estimate。

---

# 4. Q3：去趋势是亮点，JRC 计算口径是风险核心

## 4.1 为什么必须去趋势

钻孔展开图中的正弦大波形主要来自：

> 平面裂隙与圆柱孔壁相交后的几何展开。

它并不等于裂隙面的微观 roughness。

候选做：

\[
y_{detrend}
=
 y_{raw}-[y_{fit}-\bar y_{fit}],
\]

将宏观正弦趋势与局部起伏分开。

这个思想非常正确：

> **先剥离结构尺度，再评价纹理尺度。**

同样适用于：

- 路面粗糙度去坡度；
- 时间序列去趋势；
- 表面形貌去基准曲面；
- 高频振动从低频漂移中分离。

## 4.2 分段而不是跨断裂插值

如果裂隙轮廓中断，而我们直接用 spline 把中间补上，插值曲线的斜率会进入：

\[
Z_2
\]

从而把算法虚构出来的形状当成真实岩面粗糙度。

候选选择分段计算，这个判断很成熟。

## 4.3 但“长度加权平均 JRC”未必数学闭合

若每段：

\[
Z_{2,i}^2
\approx
\frac1{L_i}
\int_{segment_i}
\left(\frac{dy}{dx}\right)^2dx,
\]

那么完整轮廓应先合并**粗糙度能量**：

\[
Z_{2,global}
=
\sqrt{
\frac{\sum_i L_i Z_{2,i}^2}
{\sum_i L_i}
}.
\]

再代入经验关系：

\[
JRC=f(Z_{2,global}).
\]

因为 `f` 是非线性函数，一般：

\[
\boxed{
\sum_i w_i f(Z_{2,i})
\ne
f\!\left(\sqrt{\sum_i w_i Z_{2,i}^2}\right)
}
\]

所以若论文做的是：

\[
JRC_{global}=\sum_i\frac{L_i}{L}JRC_i,
\]

它只是一个启发式聚合，并不严格等价于官方 `Z2 → JRC` 定义。

这是我们二次审计新增的关键点。

## 4.4 等弧长采样可能改变“被估计的积分”

候选发现等弧长采样比原始/等间距采样更稳定，并报告多个标准差下降，例如：

```text
0.45 → 0.36
2.89 → 2.16
0.67 → 0.39
```

工程上这说明重复采样数值更稳定。

但需要更深一层：官方 `Z2` 本质围绕：

\[
\left(\frac{dy}{dx}\right)^2
\]

在 x 方向的统计/积分。

若采样点改为“弧长 s 等间隔”，那么 x 间距并不均匀。高斜率区域会自然获得更多点。

如果仍然把各采样点 slope **等权平均**，实际近似的测度就从 `dx` 改向 `ds`，不是同一个量。

严格做法应是：

\[
Z_2^2
=
\frac1L\int
\left(\frac{dy}{dx}\right)^2 dx,
\]

对非均匀 x 网格使用加权 quadrature：

\[
Z_2^2
\approx
\frac{1}{\sum \Delta x_i}
\sum_i
\left(\frac{\Delta y_i}{\Delta x_i}\right)^2
\Delta x_i.
\]

因此：

> **“等弧长点更稳定”不能自动推出“等权代入原公式更正确”。**

更好的比较应保证所有采样方法最后估计的是同一个连续积分。

## 4.5 JRC 16–39 是本篇最大红旗之一

官方题面明确介绍 Barton 标准：

\[
JRC\in[0,20]
\]

并给 0–2 到 18–20 十档。

候选全文审读记录中的 27 条裂隙结果却为：

\[
\boxed{JRC\approx16.28\text{–}39.36}.
\]

这说明相当一部分结果超出标准量程。

这不一定说明程序“算错”——经验公式在数学上可能外推出 >20——但必须讨论：

1. 经验公式的校准域是不是 0–20？
2. 超过 20 应 clip、extrapolate，还是报告为 `>20`？
3. 图像尺度、去趋势、采样方式是否放大了 slope？
4. 是不是把 band width / pixel noise 也混进了轮廓？
5. 这些超域 JRC 再进入 Q4 uncertainty mapping 是否会放大二次偏差？

一个很强的赛场 sanity check 是：

```python
assert JRC_min >= physical_lower
flag(JRC > calibration_upper)
```

不要等评委发现。

## 4.6 宽度 vs JRC 的结论反而写得克制

候选没有因为某几条样本相关就硬说“裂隙越宽越粗糙”，而是利用反例指出：

> JRC 不是开度/宽度的唯一函数。

这个结论强度是合适的。

---

# 5. Q4：从 2D 展开图到 3D 平面

附件 4 的图像规格与附件 1–3 不同：

```text
864 × 9167 px / 1000 mm depth
DPI 232.85
```

候选先降采样到约 65.73 DPI，以和前三问的处理链兼容。

## 5.1 正确的柱面映射

横向展开距离 `x` 对应圆周弧长：

\[
\theta=\frac{x}{r}
=\frac{2\pi x}{2\pi r}.
\]

钻孔孔口 `(X_0,Y_0)` 已知，则孔壁点可写：

\[
X=X_0+r\cos\theta,
\]

\[
Y=Y_0+r\sin\theta,
\]

\[
Z=Z(y).
\]

候选把二维裂隙离散点映射成三维柱面点，再用最小二乘拟合平面。

这个路线物理上自然。

## 5.2 其实还可以更进一步：正弦与平面是解析对应

设平面：

\[
n_x(X-X_0)+n_y(Y-Y_0)+n_z(Z-Z_c)=0.
\]

代入圆柱：

\[
X-X_0=r\cos\theta,\qquad
Y-Y_0=r\sin\theta,
\]

得到：

\[
Z
=Z_c-rac{r}{n_z}
(n_x\cos\theta+n_y\sin\theta).
\]

它天然就是：

\[
Z=C+R\sin(\theta+\beta).
\]

所以：

> **Q2 的 `(R,β,C)` 与 Q4 平面法向量不是两个独立模型，它们之间有解析几何关系。**

今天重做时，可以直接由 Q2 参数给平面 orientation 初值/解析估计，再用三维点做 refinement，而不是完全重新拟合。

这样 Q2→Q4 的模型接口会更漂亮。

---

# 6. Q4 Monte Carlo：有“不确定性意识”，但概率模型还不够物理

候选把每个裂隙拟合平面的法向量设为随机量：

```text
mean = fitted normal
sigma = function(JRC)
```

审读记录中的 `σ` 大致线性映射到 `[0.01,0.11]`，然后 Monte Carlo 抽样，得到两平面夹角的分布。

这一步的优点非常明确：

> **不是把平面拟合误差藏掉，而是让不确定性继续进入连通性。**

但评审老师会继续问三个问题。

## 6.1 为什么 JRC 决定法向量误差？

粗糙度高可能使局部平面拟合更不稳定，这个方向有直觉。

但：

\[
JRC\rightarrow \sigma_n
\]

的具体线性映射不是从数据似然、重复测量或 bootstrap 推出来的。

因此它更像：

> uncertainty heuristic

而不是已校准 measurement error model。

更严格的 `σ` 应来自：

- Q2/Q3 像素/曲线 bootstrap；
- 平面拟合残差 covariance；
- segmentation perturbation；
- 不同采样方式的参数波动；
- 人工标注/重复扫描误差。

这样才能把 Q1 的不确定性真正传播到 Q4，而不是在 Q4 临时“造一个 σ”。

## 6.2 法向量三个分量不能随意独立高斯

法向量应满足：

\[
\|n\|=1.
\]

如果：

\[
n_x,n_y,n_z\overset{ind}{\sim}N(\mu_i,\sigma^2),
\]

则抽出的向量一般不在单位球面上，而且三个分量的独立性与 orientation geometry 不匹配。

至少应 normalize；更好的做法是：

- 在均值法向量的切平面上采样小角度扰动；
- 使用 von Mises–Fisher / Bingham 等球面方向分布；
- 直接对 strike/dip 的 covariance 采样。

## 6.3 “Monte Carlo”不等于“概率已校准”

Monte Carlo 只是一种传播随机输入的方法。

随机输入本身如果是人为规定的，最终得到很多 sample 也不会自动变成真实 posterior。

所以：

> **random simulation ≠ probabilistic calibration。**

---

# 7. 连通“概率”：更准确可能只是 score

候选使用两个核心指标：

1. 裂隙平面空间距离 `d`；
2. 法向量夹角 `θ`。

再根据 Monte Carlo 的 95% 区间把距离/角度分别线性映射到 `[0,1]`：

```text
lower bound → 1
upper bound → 0
outside → clip
```

最后：

\[
P=\frac{P_d+P_\theta}{2}.
\]

这个设计直观、容易解释，也能排序。

但从概率论角度有三个风险。

## 7.1 95% CI 不是“连通概率标尺”

95% 区间描述的是参数/样本分布不确定性，不代表：

\[
P(connection\mid d).
\]

用本批样本的区间作为 0–1 映射端点，会导致同一对裂隙在不同数据集里得到不同“概率”。

所以若没有 calibration data，更严谨的命名是：

> connectivity score / normalized compatibility score

而不是概率。

## 7.2 简单平均允许完全补偿

\[
P=(P_d+P_\theta)/2
\]

意味着：

```text
非常远 + 方向极匹配
```

可以和：

```text
非常近 + 方向很差
```

得到差不多的分数。

但物理连通通常存在必要条件。

可考虑：

\[
P=P_d\times P_\theta
\]

或：

```text
hard distance gate
→ orientation score
→ finite-extent intersection test
```

第三方审读指出，论文一组“角度好但距离远”的样本综合约 0.43，正好暴露这种补偿问题。

## 7.3 top-10 都挤在 0.82–0.84，区分度不足

如果最靠前的大量 pair 分数几乎一样，那么 ranking 对小参数变化会很敏感。

应报告：

- rank stability；
- bootstrap top-k frequency；
- sensitivity to weights/mapping；
- pairwise probability/score uncertainty。

---

# 8. “平面连通”还需要有限尺度

两个无限平面：

- 不平行时总会在某处相交；
- 但这并不意味着真实岩体中的两条有限裂隙连通。

现实裂隙应该有：

- finite radius / extent；
- persistence；
- termination；
- curvature；
- uncertainty。

所以更物理的模型可用 finite disk/patch：

\[
\mathcal F_i=(center_i,normal_i,radius_i)
\]

并在 Monte Carlo 中同时采样：

```text
orientation
center/depth
extent/radius
segmentation/fitting error
```

直接统计：

\[
P_{ij}
=\frac{\#\{\text{sampled fracture patches intersect/approach}\}}
{M}.
\]

这时“概率”才更接近真正的几何事件概率。

---

# 9. 不确定性云图很好，但补钻还没真正优化

候选做法大致是：

1. 取各钻孔对连线中点；
2. 以 Monte Carlo 夹角标准差作为不确定性；
3. 钻孔位置设低不确定性；
4. 对空间/平面区域做 IDW 插值；
5. 得到 uncertainty cloud；
6. 从高值区域给 3 个补钻位置。

这比“凭经验在中间打孔”好很多，因为至少有 uncertainty map。

但第三方全文审读明确指出：最后三个坐标主要是**从云图目视选择**，没有真正求解优化问题。

题目用词是：

> 在资源限制下，按优先级给出 3 个**最优**补充钻孔位置。

今天重做，应该定义：

\[
\max_{x_1,x_2,x_3}
\mathbb E[
H(\Theta\mid D)-
H(\Theta\mid D,y_{x_1},y_{x_2},y_{x_3})
]
-\lambda Cost,
\]

即 expected information gain。

如果计算太重，可以做 greedy surrogate：

```text
candidate grid
→ score uncertainty reduction
→ choose best x1
→ update expected uncertainty
→ choose x2
→ choose x3
```

再加入 hard constraints：

- 可施工区域；
- 与已有孔最小间距；
- 巷道边界；
- 最大钻深；
- 总预算。

这才真正回答“最优补钻”。

---

# 10. 为什么这篇候选很可能能进顶级评审视野

即使目前不能确认它就是 `C25102900037`，仅从完整模型链看，它具备明显的高水平竞赛特征：

### 1. 方法与数据规模匹配

只有 10 张无标注图时，主动放弃不可靠的监督 ML，是成熟判断。

### 2. 每问都保留中间可解释对象

不是直接：

```text
image → answer
```

而是保留：

```text
Frangi response
binary mask
clusters
sine parameters
roughness profile
JRC
plane normal
uncertainty
connectivity
```

非常方便评委检查。

### 3. Q3 对采样方法做了专门实验

题目明确要求“讨论采样”，作者没有一句话带过，而是扫描采样密度、比较 equal-arc 与原采样，并报告稳定性。

### 4. Q4 不只画漂亮三维图

把不确定性继续传到连通和补钻，这是非常关键的意识。

### 5. 论文敢写负结果

Q1 机器学习路线失败并发现 leakage 后主动改道，这比只留下成功模型更可信。

---

# 11. 如果今天我们队重做，我会怎么升级

完整路线：

```text
Official metric / geometry
    ↓
Q1 Frangi baseline + physical fracture rule
    ↓
small expert labels / synthetic validation
    ↓
probabilistic segmentation
    ↓
Q2 model-based clustering + robust sine fit
    ↓
parameter covariance / missingness stress test
    ↓
Q3 continuous detrended profile
    ↓
weighted quadrature Z2 + calibrated JRC domain
    ↓
Q4 analytic sine↔plane geometry
    ↓
orientation posterior on sphere
    ↓
finite fracture patch Monte Carlo
    ↓
calibrated connectivity probability / honest score
    ↓
posterior uncertainty field
    ↓
expected-information-gain drilling optimization
```

最关键的不是模型更复杂，而是让每层输出都同时带：

\[
\boxed{estimate + uncertainty + domain check}
\]

例如：

```text
beta_hat ± CI
JRC = 18.7, within calibration domain
normal ~ Bingham(...)
P(connect) = 0.71 ± 0.08
```

这会比一张确定性的三维裂隙图强很多。

---

# 12. 本篇暂时不能做的事情

由于候选 PDF 本体没有取得，以下动作必须等原文到手再做：

1. 封面队号核验；
2. 91 页逐页视觉扫描；
3. 每张表的具体数字回算；
4. 公式编号与排版错误核对；
5. 作者附件代码执行；
6. 三维结果图/不确定性云图视觉审查；
7. 对候选是否就是矿大冠军论文作最终认定。

因此本目录不把总路线正式推进为 10/13。

---

# 13. 一句话

> **这道题的高级之处不是“Frangi + Monte Carlo”，而是把像素识别一步步升级成带不确定性的地下空间推断；真正的难点则是确保每次对象升级都没有偷偷改变物理量、采样测度或“概率”的含义。**
