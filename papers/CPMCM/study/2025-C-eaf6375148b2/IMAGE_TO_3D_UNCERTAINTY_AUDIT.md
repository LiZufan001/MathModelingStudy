# 2025 C｜图像→几何→JRC→三维概率重构专项审计

> 本文件是二次数学审计，不把第三方全文审读记录冒充我们的逐页视觉核验。身份/来源边界见 [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md)。

---

# 1. 审计总框架

这类题最危险的不是某个算法“精度低”，而是对象在层层转换时悄悄换了含义：

```text
pixel
 ↓
mask
 ↓
curve
 ↓
physical curve
 ↓
roughness scalar
 ↓
3D plane
 ↓
random plane
 ↓
connectivity probability
 ↓
uncertainty field
 ↓
optimal drilling
```

每一步必须问：

```text
输入是什么对象？
单位是什么？
输出是什么对象？
变换是否一一对应？
误差从哪里来？
输出 uncertainty 如何传到下一层？
```

---

# 2. Q1：segmentation audit

## 2.1 Frangi 的适配性

2D Hessian：

\[
H_\sigma(x)=
\begin{bmatrix}
I_{xx} & I_{xy}\\
I_{xy} & I_{yy}
\end{bmatrix}
\]

设特征值按绝对值排序：

\[
|\lambda_1|\le|\lambda_2|.
\]

细长线结构理想情况下：

\[
|\lambda_1|\ll|\lambda_2|.
\]

Frangi vesselness 一类指标可写成：

\[
V_\sigma=
\exp\left(-\frac{R_B^2}{2\beta^2}\right)
\left[1-\exp\left(-\frac{S^2}{2c^2}\right)\right],
\]

\[
R_B=\frac{|\lambda_1|}{|\lambda_2|},
\qquad
S=\sqrt{\lambda_1^2+\lambda_2^2}.
\]

对多尺度：

\[
V(x)=\max_{\sigma\in\Sigma}V_\sigma(x).
\]

### 审计结论

Frangi 是**形状先验**，不是裂隙语义分类器。

它回答：

> 哪里像细长线/带？

而原题还要求区分：

> 这条线究竟是裂隙、岩层界面、泥浆、钻痕还是拼接线？

因此后续必须增加语义/物理判据。

## 2.2 原题 1 mm 规则不能丢

若像素裂隙宽度为 `w_px`，应通过物理尺度转换：

\[
w_{mm}=w_{px}\cdot s_{local}.
\]

再将：

\[
w_{mm}>1\text{ mm}
\]

作为裂隙证据之一。

但带宽不能简单在原图全局乘固定比例：

- 附件 1–3 x/y pixel scale 略不同；
- 宽度测量方向应尽量沿局部法线，而不是固定竖直方向。

推荐：

1. skeleton；
2. local tangent；
3. normal ray casting / distance transform；
4. 得到局部 opening width。

## 2.3 无标签时怎么验证

候选承认无像素真值，因此做定性比较，这比伪造 accuracy 好。

但还可以补三种弱监督验证：

### Expert micro-label

只人工标 3 张关键图的若干 patch，计算：

```text
precision / recall / Dice
false fracture rate
missed main-fracture rate
```

### Synthetic injection

把已知宽度/方向/曲率的人工裂隙注入真实岩石背景，看恢复率。

### Downstream stability

将 segmentation 参数扰动 ±10%/±20%，观察：

```text
Q2 R/P/beta/C
Q3 JRC
Q4 connectivity rank
```

是否稳定。

这才是真正的**跨层验证**。

---

# 3. Q2：curve fitting audit

## 3.1 pixel→mm 必须各轴分别换算

附件 1–3：

\[
244\text{ px}\leftrightarrow94.25\text{ mm},
\]

\[
1350\text{ px}\leftrightarrow500\text{ mm}.
\]

所以：

\[
s_x\approx0.3863\text{ mm/px},
\qquad
s_y\approx0.3704\text{ mm/px}.
\]

不能写一个 `pixel_size` 同时作用 x/y。

## 3.2 周期是强物理约束

完整平面裂隙在圆柱展开图上应：

\[
P\approx2\pi r=94.25\text{ mm}.
\]

因此拟合不是自由四参数 black-box：

- 完整裂隙可将 P 固定/强正则在 94.25；
- 缺失裂隙则 P 可估但应有 prior；
- 若 P 明显偏离，应作为“非平面/非完整/聚类错误”诊断。

## 3.3 周期边界是环形的

展开图的：

```text
x=0
```

和：

```text
x=94.25 mm
```

是同一条圆柱母线。

所以连通域/聚类应使用 periodic boundary condition。

否则跨左右边界的一条裂隙可能被错误切成两条。

## 3.4 缺失率高时参数不可辨识

候选报告缺失率最高约 77%。

应研究 Fisher information / bootstrap：

\[
Cov(\hat\theta)
\approx
(J^TJ)^{-1}\sigma^2,
\quad
\theta=(R,P,\beta,C).
\]

如果观测只覆盖很短相位区间，`R/P/β` 会高度相关，point estimate 即使 residual 小也不可靠。

因此：

> **低拟合误差 ≠ 参数可辨识。**

必须同时看 parameter CI / condition number。

---

# 4. Q3：JRC audit

## 4.1 宏观倾斜/正弦必须剥离

若原轮廓：

\[
y(x)=m(x)+r(x),
\]

其中：

- `m(x)`：宏观平面几何在展开图上的正弦趋势；
- `r(x)`：真正局部粗糙度；

那么直接对 `y(x)` 算 slope 会把 macro geometry 当 roughness。

候选 detrend 的方向正确。

## 4.2 中心线取列均值的潜在偏差

候选对每个 x 列取裂隙带 y 均值作为中心线。

若 band：

- 上下边界不对称；
- 有支叉；
- 有局部泥浆连接；

mean y 可能偏。

更稳健：

- median center；
- morphological skeleton；
- geodesic medial axis；
- robust spline centerline。

## 4.3 非均匀采样必须带 quadrature weight

连续定义目标近似为：

\[
Z_2^2=
\frac{1}{L_x}
\int_{x_0}^{x_1}
[y'(x)]^2 dx.
\]

对任意非均匀网格：

\[
Z_2^2
\approx
\frac{
\sum_i
\left(\frac{\Delta y_i}{\Delta x_i}\right)^2
\Delta x_i
}{
\sum_i\Delta x_i
}.
\]

如果改为 equal-arc sampling，却仍：

\[
\frac1{N-1}\sum slope_i^2,
\]

高坡度区域因为弧长更长会被重复赋更多权重，估计对象发生改变。

所以采样比较应拆成两层：

1. point placement；
2. numerical quadrature。

不能混为一个“采样算法”。

## 4.4 分段后应该合并 Z2 energy，而不是直接平均 JRC

设段长 `L_i`：

\[
E_i=L_iZ_{2,i}^2.
\]

则：

\[
Z_{2,total}=\sqrt{
\frac{\sum_iE_i}{\sum_iL_i}
}.
\]

最后：

\[
JRC=f(Z_{2,total}).
\]

而不是默认：

\[
JRC=\sum_i\frac{L_i}{L}f(Z_{2,i}).
\]

后者只有在 `f` 近似线性或作者把它明确定义为新的 composite index 时才成立。

## 4.5 JRC 超域检查

原题明确 Barton 标准范围：0–20。

候选：

\[
16.28\le JRC\le39.36.
\]

建议输出三列：

```text
raw_formula_JRC
calibrated_JRC
out_of_domain_flag
```

并与 Barton 标准轮廓做 external calibration。

如果公式产生 >20，可报告：

```text
raw estimator = 31.4
outside classical Barton calibration range
engineering class = >20 / extremely rough
```

而不是把 31.4 当作与 0–20 同口径的确定 JRC。

---

# 5. Q4：2D→3D geometry audit

## 5.1 柱面参数化

半径：

\[
r=15\text{ mm}.
\]

横向弧长：

\[
x\in[0,2\pi r].
\]

对应：

\[
\theta=x/r.
\]

若钻孔中心线坐标 `(X_0,Y_0)`：

\[
X=X_0+r\cos\theta,
\]

\[
Y=Y_0+r\sin\theta,
\]

\[
Z=Z(y).
\]

这一步必须明确：

- 图像 y 是向下孔深还是向上 z；
- 题面 z 正方向铅直向上；
- 若孔口 z=0、孔深 d>0，则通常：

\[
Z=-d
\]

或必须明确采用另一符号约定。

## 5.2 正弦参数与平面法向量解析对应

平面：

\[
n_x(X-X_0)+n_y(Y-Y_0)+n_z(Z-Z_c)=0.
\]

代柱面：

\[
Z=Z_c-rac{r}{n_z}(n_x\cos\theta+n_y\sin\theta).
\]

令：

\[
A=\sqrt{n_x^2+n_y^2},
\]

则振幅：

\[
R=r\frac{A}{|n_z|}.
\]

相位由 `(n_x,n_y)` 的方向决定。

因此 Q2 参数与 Q4 orientation 有显式对应。

### 建议

不要 Q2 拟合一次 `(R,P,β,C)`，Q4 又完全独立 fit plane。

应：

```text
Q2 sine fit
→ analytic plane orientation
→ 3D point residual refinement
→ covariance
```

实现真正跨问复用。

## 5.3 DPI 统一并不自动意味着物理标定完全统一

附件 4：

```text
864×9167 px / 1000 mm
232.85 DPI
```

降采样到 65.73 DPI 后，横向约变成 244 px，确实接近附件 1–3 横向规格。

但附件 1–3 的纵向：

\[
1350/500=2.7\text{ px/mm},
\]

而 65.73 DPI 对应：

\[
65.73/25.4\approx2.588\text{ px/mm}.
\]

所以“DPI 相同”不必然意味着 x/y 全部物理尺度完全相同。

第三方审读还指出候选 Q4 表中出现周期 93.9，而题面周长为 94.25，值得在全文到手后专门核查是否来自 resize calibration。

---

# 6. Orientation uncertainty audit

## 6.1 法向量必须在球面上

单位法向：

\[
n\in S^2,\qquad \|n\|=1.
\]

三个 Cartesian components 独立 Gaussian 并不尊重：

- unit norm；
- antipodal equivalence `n` 与 `-n` 表示同一平面方向；
- spherical covariance。

### 推荐 1：tangent-plane perturbation

在平均方向 `n0` 的切空间建立正交基 `(e1,e2)`：

\[
\delta=a e_1+b e_2,
\quad
(a,b)\sim N(0,\Sigma),
\]

再：

\[
n=\frac{n_0+\delta}{\|n_0+\delta\|}.
\]

### 推荐 2：Bingham distribution

因 `n` 与 `-n` 等价，Bingham 比普通 von Mises–Fisher 更自然。

## 6.2 uncertainty 应从上游数据推出来

优先做：

```text
segmentation bootstrap
→ curve refit
→ plane refit
→ empirical orientation distribution
```

而不是：

```text
JRC
→ 手工线性 sigma
```

JRC 可作为 heteroscedasticity covariate，但系数应校准。

---

# 7. Connectivity audit

## 7.1 score vs probability

一个值要叫：

\[
P(connection)=0.82
\]

至少需要：

- 随机事件定义；
- 概率空间；
- 参数分布有依据；
- mapping 经校准或由生成模型自然产生。

如果只是：

```text
distance normalized to [0,1]
angle normalized to [0,1]
average
```

应该叫：

\[
S_{conn}
\]

而不是 P。

## 7.2 用物理事件定义真正 Monte Carlo probability

定义有限裂隙片：

\[
F_i=(c_i,n_i,R_i).
\]

每次 Monte Carlo：

1. sample segmentation/curve parameters；
2. sample plane orientation；
3. sample finite extent `R_i`；
4. build two patches；
5. 判断两 patch 是否相交，或最近距离 < tolerance。

则：

\[
\hat P_{ij}
=
\frac{1}{M}
\sum_{m=1}^{M}
I(F_i^{(m)}\leftrightarrow F_j^{(m)}).
\]

这个概率含义清楚得多。

## 7.3 两指标不能无限补偿

建议：

```text
distance feasibility gate
AND
orientation compatibility
AND
finite extent overlap
```

或者 logistic / probabilistic graphical model，而非简单 arithmetic mean。

---

# 8. Uncertainty field and supplementary drilling audit

## 8.1 IDW cloud 是 visualization，不是 posterior

15 个钻孔对中点的不确定性通过 IDW 扩散成连续云图，可以作为探索性图。

但 IDW 假设：

> 距离近 → uncertainty 相似。

它没有显式使用地质结构 covariance。

可升级：

- Gaussian process；
- kriging；
- graph-based uncertainty propagation；
- posterior predictive entropy。

## 8.2 “最大不确定性”不一定等于“最佳打孔”

例如某处不确定性很大，但：

- 无法施工；
- 离已知危险区过近；
- 新孔观测与已有孔高度冗余；
- 对关键连通路径无影响；

则不一定值得打。

真正的价值应是：

\[
VOI(x)=
\mathbb E[
Loss(D)-Loss(D\cup y_x)
].
\]

然后：

\[
\max_{x_1,x_2,x_3}
VOI-\lambda Cost.
\]

## 8.3 三孔应 sequential，而不是一次挑前三高点

第一次打孔会改变 posterior；第二个最优点可能随之改变。

所以推荐：

```text
choose x1
→ hypothetically update / expected update
→ choose x2
→ update
→ choose x3
```

即 sequential design。

---

# 9. 误差传播总表

| 层 | 主要误差 | 应传递到 |
|---|---|---|
| 图像 | illumination / mud / seam / pixel noise | segmentation probability |
| Q1 | FP/FN / width bias | curve points |
| Q2 | cluster merge/split / missingness | sine parameter covariance |
| Q3 | detrending / sampling / scale | JRC uncertainty/domain flag |
| 3D | pixel-mm / depth / coordinate mapping | plane covariance |
| orientation | fit residual | normal distribution |
| connectivity | finite extent + orientation + position | pair probability |
| field | sparse boreholes | posterior uncertainty map |
| drilling | cost / feasibility / VOI | final ranked locations |

这张表就是本题最值得带走的“误差接口”。

---

# 10. 比赛前自动检查

```text
[ ] x/y pixel scale 独立记录
[ ] periodic boundary 处理
[ ] fracture-vs-layer 1 mm 物理判据没有丢
[ ] Q1 有人工/合成小验证
[ ] missingness stress test
[ ] P 约束/先验使用 94.25 mm
[ ] JRC 计算保持同一积分测度
[ ] 分段先聚合 Z2 energy
[ ] JRC >20 自动 flag
[ ] 2D→3D 坐标正负方向测试
[ ] normal 每个 sample 保持单位球面
[ ] Monte Carlo 输入分布有来源
[ ] score 不冒充 probability
[ ] finite fracture extent 进入连通
[ ] uncertainty map 不冒充 ground truth
[ ] 补钻有 objective + constraints + VOI
[ ] 三孔按 sequential update 而非目视 top-3
```

---

# 11. 一句话

> **三维概率重构真正难的不是把二维曲线画成三维面，而是让像素误差、拟合误差、粗糙度尺度和有限观测不确定性，以同一个概率语义一路传到“连不连、哪里再钻”。**
