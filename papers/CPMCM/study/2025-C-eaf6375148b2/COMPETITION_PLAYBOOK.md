# 2025 C｜图像裂隙 + 三维不确定性题比赛速查

> 适用：钻孔成像、裂纹/血管/道路病害/材料缺陷识别、二维几何参数提取、三维重构、空间连通性、不确定性与补充测点设计。

---

## 1. 起手先画对象升级链

```text
raw image
→ physical-scale image
→ candidate mask
→ fracture object
→ parameterized curve
→ detrended roughness
→ 3D geometry
→ posterior / uncertainty
→ connectivity graph
→ sensing decision
```

任何一问都要回答：上一问哪个中间量进入这一问。

---

## 2. 小样本图像题不要条件反射上深度学习

先检查：

```text
有多少独立图？
有没有 pixel labels？
有没有 external data？
train/test 是否重复或同源？
```

如果只有十几张无标签图：

```text
传统结构先验 baseline
+ 少量人工验证
+ synthetic stress test
```

通常比一个无法验证的 U-Net 更稳。

Frangi/Canny/Gabor/morphology 的价值在于有明确形状假设；但要说明它只能找 candidate，不自动等于语义真值。

---

## 3. pixel → physical unit 必须先做

```python
x_mm = x_px * sx
z_mm = z_px * sz
```

不要默认：

```python
sx == sz
```

如果图像是圆柱展开：

\[
\theta=x/r,
\]

并设置 periodic boundary：

```text
left edge ≡ right edge
```

---

## 4. 聚类和物理拟合要分工

推荐：

```text
connected fragments
→ coarse clustering
→ physical model fit
→ reject outliers / bad groups
→ robust refit
```

不要让 DBSCAN/K-means 直接承担最终物理分类。

对正弦裂隙：

\[
y=R\sin(2\pi x/P+\beta)+C.
\]

完整圆柱交线强先验：

\[
P\approx2\pi r.
\]

---

## 5. residual 小不等于参数可信

特别是数据缺失时，同时报：

```text
fit residual
missing ratio
parameter CI
condition number / bootstrap spread
```

一句纪律：

> **fit quality 与 identifiability 是两件事。**

---

## 6. roughness 先去宏观趋势

```text
observed profile
= macro geometry + micro roughness
```

先估 macro：

\[
m(x),
\]

再：

\[
r(x)=y(x)-m(x).
\]

否则坡度、弯曲、正弦包络会被错误算成表面粗糙度。

---

## 7. 采样方法必须保持指标定义不变

若：

\[
Z_2^2=\frac1L\int [r'(x)]^2dx,
\]

非均匀采样要：

\[
Z_2^2\approx
\frac{\sum slope_i^2\Delta x_i}{\sum\Delta x_i}.
\]

不要因为换成 equal-arc sampling 就继续简单等权平均。

**点怎么选**和**积分怎么加权**必须分开讨论。

---

## 8. 非线性指标不要先变换再平均

若：

\[
JRC=f(Z_2),
\]

分段时优先：

\[
Z_{2,total}^2=
\frac{\sum L_iZ_{2,i}^2}{\sum L_i}
\]

再：

\[
JRC=f(Z_{2,total}).
\]

不是默认：

\[
\sum w_iJRC_i.
\]

---

## 9. 经验公式必须有 calibration-domain flag

任何经验公式都建立：

```python
value_raw = estimator(...)
in_domain = lower <= value_raw <= upper
```

超域时不要静默输出。

例如 Barton JRC：

```text
classical reference range: 0–20
```

若 raw=31：

```text
31 (extrapolated; outside classical range)
```

而不是装作普通 JRC。

---

## 10. 2D→3D 优先找解析几何

圆柱上平面裂隙：

\[
X=X_0+r\cos\theta,
\quad
Y=Y_0+r\sin\theta,
\]

平面代入后天然给正弦：

\[
Z=C+R\sin(\theta+\beta).
\]

所以二维拟合参数和三维 plane orientation 应共享模型，不要重复独立估计。

---

## 11. Monte Carlo 三问

每次看到“Monte Carlo”，立刻问：

1. 随机变量是什么？
2. 分布从哪里来的？
3. 输出随机性对应什么现实事件？

如果输入分布是拍脑袋的：

> 多跑 100000 次也不会自动变成真实概率。

---

## 12. 方向随机变量不能忘球面

法向量：

\[
\|n\|=1,
\quad n\equiv -n.
\]

优先：

```text
strike/dip covariance
or tangent-plane perturbation
or Bingham distribution
```

不要三个分量独立高斯后不归一化。

---

## 13. score 和 probability 严格分开

如果只是：

```text
normalized distance
+ normalized angle
+ weighted sum
```

叫：

```text
connectivity score
```

只有定义了随机连通事件并有校准/生成模型时，才叫：

\[
P(connection).
\]

---

## 14. 连通性要考虑 finite extent

无限平面相交没有足够工程意义。

至少建立：

```text
center
orientation
finite radius/extent
```

然后计算/模拟 fracture patches 的实际接近/相交。

---

## 15. “最优补测点”必须有 optimization

正文要出现：

```text
objective
constraints
candidate region
cost
solver
baseline
marginal gain
```

推荐目标：

\[
\max\ Expected\ Uncertainty\ Reduction-\lambda Cost.
\]

三点最好 sequential greedy：

```text
选1 → 更新 → 选2 → 更新 → 选3
```

而不是不确定性热图前三个像素。

---

## 16. 最值得画的图

```text
1. segmentation failure-mode comparison
2. fit + uncertainty band
3. JRC convergence and calibration boundary
4. 3D fracture posterior cloud
5. connectivity graph with uncertainty
6. uncertainty map before/after each new borehole
7. marginal information gain curve
```

---

## 17. 赛末 Gate

```text
[ ] source / code / official problem version locked
[ ] px-mm conversion tested
[ ] periodic boundary tested
[ ] physical fracture criterion preserved
[ ] no train/test duplicate
[ ] high missingness parameter flagged
[ ] empirical formula domain checked
[ ] sampling measure unchanged
[ ] non-linear aggregation correct
[ ] unit normal maintained
[ ] Monte Carlo inputs justified
[ ] score/probability naming honest
[ ] finite extent considered
[ ] "optimal" has objective + constraints
[ ] every final number generated from one result source
```

---

## 18. 一句话

> **从二维图像一路做到三维概率模型时，最重要的不是模型越堆越高级，而是每次升维都保留物理尺度、误差来源和概率语义。**
