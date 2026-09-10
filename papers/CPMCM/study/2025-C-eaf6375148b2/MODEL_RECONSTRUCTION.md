# 2025 C｜统一模型重构

> 目标：不是复述候选论文，而是把本题重建成一个**可验证、可传播不确定性、可解释“概率”和“最优”**的统一模型。

---

# 1. 总体状态接口

定义每条候选裂隙的状态：

```python
FractureObservation = {
    "mask_prob": ...,        # Q1 pixel posterior / confidence
    "curve_points_mm": ...,
    "sine_params": ...,      # R, P, beta, C
    "sine_cov": ...,
    "rough_profile": ...,
    "Z2": ...,
    "JRC_raw": ...,
    "JRC_domain_flag": ...,
    "plane_mean": ...,
    "plane_cov": ...,
    "extent_prior": ...
}
```

核心纪律：

> **后一问不重新造一个与前问无关的对象，而是继续更新同一个 fracture posterior。**

---

# 2. Q1：physics-aware probabilistic segmentation

## 2.1 Frangi baseline

保留候选论文的强项：

```text
illumination correction
→ multiscale Hessian/Frangi
→ adaptive threshold
→ morphology
→ connected components
```

但最终不只输出 binary mask，而输出：

\[
p_{ij}=P(pixel_{ij}\in fracture\mid I).
\]

即使最后提交必须是黑白二值图，内部仍保留 probability/confidence map。

## 2.2 物理规则融合

原题指出裂隙与岩层界面的重要区别：

- 张开宽度；
- 填充材质；
- 两侧岩石连续性。

构造 component-level 特征：

\[
\phi_k=
(w_k,\Delta I_{inside-rock},continuity_k,orientation_k,Frangi_k,...).
\]

无标签时可用规则/弱监督评分：

\[
S_k=w_1f_{width}+w_2f_{fill}+w_3f_{line}+w_4f_{continuity}.
\]

其中 `width > 1 mm` 作为强物理证据，但不要单独一票否决所有窄裂隙像素；可以把它用于 component classification。

## 2.3 误差接口

Q1 输出：

```text
binary mask
pixel confidence
component confidence
uncertain regions
```

Q2/Q3 对 uncertain region 用 bootstrap perturbation，形成参数不确定性。

---

# 3. Q2：periodic model-based fracture decomposition

## 3.1 圆柱周期坐标

设：

\[
L_c=\pi D\approx94.25\text{ mm}.
\]

横坐标使用：

\[
x\in S^1
\]

而不是普通线段，即 `x=0` 与 `x=L_c` 相邻。

## 3.2 候选生成

可以保留：

```text
closing → components → DBSCAN
```

作为 fast baseline。

更稳健的正式模型：

### RANSAC sine mixture

每次随机从片段抽样，拟合：

\[
y=R\sin(2\pi x/P+\beta)+C,
\]

定义 point-to-model residual，寻找最大一致集。

提取一条后再对剩余片段重复。

### 或 EM mixture

\[
p(y_i\mid x_i)=
\sum_{k=1}^{K}\pi_k
N(y_i;f(x_i;\theta_k),\sigma_k^2)
+\pi_0p_{noise}.
\]

这样“属于哪条裂隙”与“裂隙参数”联合估计。

## 3.3 物理先验

完整平面裂隙：

\[
P\sim N(94.25,\sigma_P^2)
\]

或固定：

\[
P=94.25.
\]

若拟合 P 显著偏离，则标：

```text
non-planar / partial / wrong cluster / image distortion
```

## 3.4 robust refinement

目标：

\[
\min_\theta\sum_i\rho
\left(
\frac{y_i-f(x_i;\theta)}{\sigma_i}
\right),
\]

使用 Huber/Tukey loss，替代手工 `kσ` 也可。

## 3.5 covariance

通过：

- Jacobian approximation；
- residual bootstrap；
- segmentation bootstrap；

得到：

\[
\theta=(R,P,\beta,C),
\qquad
\theta\sim N(\hat\theta,\Sigma_\theta)
\]

（若分布明显非高斯就直接保存 empirical samples）。

这将直接成为 Q4 orientation uncertainty，而不是 Q4 再人为指定。

---

# 4. Q3：measure-consistent roughness estimation

## 4.1 先提取 robust centerline

对裂隙带使用 medial/skeleton line，转换为 mm：

\[
(x_i,y_i).
\]

## 4.2 macro geometry removal

利用 Q2：

\[
m(x)=\hat R\sin(2\pi x/\hat P+\hat\beta)+\hat C.
\]

去趋势：

\[
r(x)=y(x)-[m(x)-\bar m].
\]

这样保留局部粗糙起伏。

## 4.3 连续化而不是让采样点决定物理量

先拟合平滑但不过度平滑的 rough profile：

\[
\hat r(x)=Spline(x,r;\lambda).
\]

`λ` 由：

- GCV；
- bootstrap stability；
- 已知成像分辨率；

选择。

再直接数值积分：

\[
Z_2=
\sqrt{
\frac1{L_x}
\int[\hat r'(x)]^2dx
}.
\]

这样等间距、等弧长、自适应采样只是**数值积分策略**，不会改变指标定义。

## 4.4 断裂轮廓

若观测域：

\[
\Omega=\cup_j[a_j,b_j],
\]

则：

\[
Z_2^2=
\frac{
\sum_j\int_{a_j}^{b_j}[r_j'(x)]^2dx
}{
\sum_j(b_j-a_j)
}.
\]

不要跨 gap 插值，也不要先每段转 JRC 再线性平均。

## 4.5 JRC calibration

计算：

\[
JRC_{raw}=f(Z_2).
\]

再依据经验公式校准域：

```text
if 0 <= JRC_raw <= 20:
    status = within_Barton_range
else:
    status = extrapolated
```

最好将题面 Barton 标准轮廓数字化，作为 reference profiles：

\[
JRC_{cal}=
arg\min_{class}
D(profile,reference_{class})
\]

形成公式估计 + 标准轮廓双验证。

## 4.6 area/width 作为独立变量

题目要求讨论裂隙面积作用。

不要把面积硬塞进 JRC 公式，而应分析：

\[
JRC\perp? Area,
\]

或：

\[
JRC=g(width,area,depth,...)+\epsilon.
\]

并明确：

> JRC 是粗糙度，不是裂隙规模指标；面积/开度可以影响稳定性和连通，但不应未经证据改变 JRC 定义。

---

# 5. Q4：analytic 2D-to-3D mapping

## 5.1 正弦→平面解析关系

设钻孔半径 r，局部柱面：

\[
X=X_0+r\cos\theta,
\quad
Y=Y_0+r\sin\theta.
\]

平面：

\[
n_x(X-X_0)+n_y(Y-Y_0)+n_z(Z-Z_c)=0.
\]

得：

\[
Z=Z_c-\frac r{n_z}
(n_x\cos\theta+n_y\sin\theta).
\]

令：

\[
n_h=\sqrt{n_x^2+n_y^2},
\]

则：

\[
R=r\frac{n_h}{|n_z|}.
\]

所以可由 R 得倾角量级：

\[
\tan\delta\sim R/r.
\]

β 给水平投影方向。

这比完全独立做 plane fitting 更能体现题目结构。

## 5.2 uncertainty propagation

若已有：

\[
\theta=(R,P,\beta,C)
\]

的 posterior samples：

\[
\theta^{(m)}\sim p(\theta\mid image),
\]

每个 sample 直接转换：

\[
\theta^{(m)}\to plane^{(m)}.
\]

这样不需要拍脑袋指定：

\[
\sigma_n=f(JRC).
\]

JRC 可以作为额外的 local curvature/extent uncertainty，而不是唯一 uncertainty source。

---

# 6. 有限裂隙面模型

## 6.1 为什么不能只用无限平面

地下裂隙是有限 patch。

定义：

\[
F_i=(c_i,n_i,a_i,b_i,shape_i),
\]

可先简化为圆盘：

\[
F_i=(c_i,n_i,R_i).
\]

半径 prior 可根据：

- borehole trace length；
- crack width/roughness；
- geological prior；
- sensitivity scenarios；

确定。

## 6.2 真正连通事件

对每次 MC sample：

```text
sample two finite patches
→ calculate intersection / minimum distance
→ if distance < delta and overlap feasible: connected=1
```

于是：

\[
P_{ij}=E[I_{connected}].
\]

同时报告 Monte Carlo standard error：

\[
SE(\hat P)=
\sqrt{\frac{\hat P(1-\hat P)}{M}}.
\]

这样 `P=0.8` 才有严格概率语义。

---

# 7. 网络层：从 pairwise 到 fracture graph

建立图：

\[
G=(V,E),
\]

每个 fracture 是 vertex；边权：

\[
w_{ij}=P_{ij}.
\]

可以计算：

- expected connected components；
- percolation path probability；
- 顶板到巷道/水体的高风险路径；
- edge betweenness；
- uncertainty-sensitive critical fractures。

这样“连通概率”才真正服务工程风险，而不是只列 top-10 pair。

---

# 8. 不确定性场

目标不是对 15 个中点做漂亮插值，而是：

\[
U(x)=H[p(geology_x\mid D)].
\]

可选近似：

### Gaussian process

对 orientation / connectivity uncertainty 建 GP：

\[
f(x)\sim GP(m,k).
\]

### Kriging

若地质空间相关性可估，使用 variogram。

### Graph / DFN posterior

直接对 fracture-network posterior 的 predictive variance 做空间汇总。

---

# 9. 补钻 = Bayesian experimental design

设候选钻孔位置 x，新观测 `Y_x` 尚未知。

期望信息增益：

\[
EIG(x)=
H(\Theta\mid D)
-
E_{Y_x}
H(\Theta\mid D,Y_x).
\]

考虑成本：

\[
Utility(x)=EIG(x)-\lambda C(x).
\]

三孔序贯：

```text
x1 = argmax Utility(x|D)
D1 = expected/update posterior
x2 = argmax Utility(x|D1)
x3 = argmax Utility(x|D2)
```

hard constraints：

```text
inside feasible roof region
minimum spacing
maximum drilling depth
avoid forbidden utilities/structures
total budget
```

如果完整 Bayesian update 太重，比赛版可使用 surrogate：

\[
Score(x)=
\frac{
U(x)\cdot CoverageGain(x)\cdot CriticalPathImpact(x)
}{Cost(x)}.
\]

但必须说明它是 heuristic utility，不冒充精确 EIG。

---

# 10. 最终 evaluator

## Q1

```text
small-label Dice/F1
main-fracture recall
false-positive area
robustness across nuisance types
```

## Q2

```text
curve residual
parameter CI
missingness stress test
period/domain sanity
```

## Q3

```text
Z2 numerical convergence
JRC sampling sensitivity
Barton-domain flag
reference-profile comparison
```

## Q4

```text
3D geometry residual
posterior calibration / sensitivity
MC standard error
rank stability
network-level risk
expected uncertainty reduction after drilling
```

---

# 11. 比赛可落地的“中档版本”

若只有约 100h，不必做最复杂模型。建议：

```text
Q1: illumination + Frangi + morphology + physical width rule
Q2: periodic RANSAC sine fitting + bootstrap CI
Q3: detrend + spline derivative integral + JRC domain audit
Q4: analytic plane mapping + bootstrap Monte Carlo + finite-disk scenario
    + connectivity score/probability distinction
    + greedy information-gain drilling
```

这一套已经比“多个高级算法堆叠”更有说服力，因为四问共享同一 geometry/uncertainty interface。

---

# 12. 一句话

> **本题最好的统一模型不是四个算法，而是一个逐层更新的 fracture posterior：从“这个像素像不像裂隙”，一直更新到“这两条有限裂隙有多大概率连通、下一孔打在哪里最能减少不确定性”。**
