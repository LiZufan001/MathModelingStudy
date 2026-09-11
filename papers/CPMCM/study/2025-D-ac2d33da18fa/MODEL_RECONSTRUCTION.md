# MODEL_RECONSTRUCTION｜从多源观测到风险航路的统一重构

这份文件不是照抄候选论文，而是把它的 `a→b→c→d/e→route` 重新整理成一套更一致、可复现、能传播不确定性的模型。

---

# 1. 统一问题定义

令低空区域：

\[
\Omega\subset\mathbb R^3,
\]

时间：

\[
t=1,\ldots,T.
\]

真正想知道的不是某一种设备的读数，而是一个潜在湍流状态场：

\[
x(\mathbf r,t).
\]

`x` 可以选成：

- `log ε`；
- TKE；
- 经标定后的无量纲 risk index；

但**全篇必须固定一种主状态变量**。

推荐：

\[
x=\log(\varepsilon+\varepsilon_0),
\]

因为：

- `ε>0`；
- 分布通常偏态；
- log 空间更容易做 Gaussian assimilation；
- 最后可映射为风险概率。

所有传感器统一写成：

\[
y_s=H_sx+b_s+\epsilon_s,
\]

其中：

- `s`：传感器/资料源；
- `H_s`：观测算子；
- `b_s`：系统偏差；
- `ε_s`：观测+代表性误差。

这一步能避免“不同物理量插值完直接平均”。

---

# 2. 数据层：先做时空坐标账本

每条观测统一记录：

```text
source
station / radar
UTC/local time
x, y, z
native_resolution
value
unit
QC flag
uncertainty
```

必须分开：

- native grid spacing；
- native effective resolution；
- analysis output spacing。

例如：

```text
output Δx = 100 m
```

只能代表分析网格，不代表：

```text
information resolution = 100 m
```

---

# 3. Q1 重构：rich-sensor teacher → reduced-sensor student

## 3.1 teacher a 不叫 truth

用风廓线 + 微波辐射计构造 reference：

\[
y^{(a)}(z,t).
\]

物理特征可包含：

\[
\theta=T(P_0/P)^\kappa,
\]

\[
Ri=
\frac{(g/\theta)\partial_z\theta}
{(\partial_zu)^2+(\partial_zv)^2+\eta},
\]

其中加入小的：

\[
\eta>0
\]

防止弱风切变时分母数值爆炸。

速度脉动必须定义平均窗口：

\[
u'(t)=u(t)-\bar u_{W}(t),
\]

而不是模糊写“减去平均值”。

TKE：

\[
k=\frac12(u'^2+v'^2+w'^2).
\]

最终 teacher 应输出：

\[
\mu_a(z,t),\qquad \sigma_a(z,t).
\]

不是只有一个点估计。

## 3.2 student b

输入只来自风廓线：

\[
X_b=\{
\text{spectral width},
\text{shear},
\text{wind},
\text{SNR},
\text{temporal variance},
\ldots
\}.
\]

预测：

\[
\hat y_b=f_\phi(X_b).
\]

可用：

- RF；
- XGBoost；
- GAM；
- small neural net；

模型名不是重点。

## 3.3 损失函数要认识 teacher uncertainty

候选式思路相当于：

\[
\min\sum_i(\hat y_{b,i}-y_{a,i})^2.
\]

更好的：

\[
\min\sum_i
\frac{(\hat y_{b,i}-\mu_{a,i})^2}
{\sigma_{a,i}^2+\sigma_0^2}.
\]

teacher 越不确定，该 pseudo-label 权重越低。

## 3.4 验证切分

禁止把全部时空点随机打散作为唯一结果。

推荐四层：

```text
V1  random split          debugging only
V2  blocked time split    temporal generalization
V3  leave-one-site-out    spatial generalization
V4  extreme-event holdout tail-risk generalization
```

最终论文主要报 V2–V4。

---

# 4. Q2 重构：probabilistic multi-source analysis

定义某时刻背景场：

\[
x_b\sim N(\mu_b,B).
\]

多源观测：

\[
y\sim N(Hx,R).
\]

OI / 3DVAR 的核心不是名字，而是：

\[
J(x)=
\frac12(x-x_b)^TB^{-1}(x-x_b)
+
\frac12(y-Hx)^TR^{-1}(y-Hx).
\]

解：

\[
x_a=x_b+K(y-Hx_b),
\]

\[
K=BH^T(HBH^T+R)^{-1}.
\]

## 4.1 `R` 不应是全域常数

对于每个观测：

\[
R_i=
\sigma_{instrument,i}^2
+
\sigma_{represent,i}^2
+
\sigma_{QC,i}^2.
\]

可以依赖：

- range；
- SNR；
- beam height；
- weak echo；
- terrain blockage；
- temporal offset。

这样 X/S 波段权重自然从误差里来，不需要全域写死 `0.6/0.4`。

## 4.2 背景协方差 `B`

水平与垂直尺度应分开：

\[
B_{ij}=\sigma_b^2
\exp\left(-\frac{d_{h,ij}^2}{2L_h^2}
-\frac{d_{v,ij}^2}{2L_v^2}\right).
\]

参数：

\[
L_h,L_v,\sigma_b
\]

必须做 sensitivity 或由 empirical variogram / innovation statistics 估计。

## 4.3 输出不止 analysis mean

至少输出：

\[
\mu_a(\mathbf r),
\]

和分析误差：

\[
P_a=(I-KH)B.
\]

即：

```text
field value
+ uncertainty field
+ observation-density map
+ effective-resolution map
```

---

# 5. 湍流量的物理口径

## 5.1 ε

Kolmogorov inertial-range：

\[
D_{LL}(s)=C_2(\varepsilon s)^{2/3}.
\]

反演：

\[
\varepsilon=
\frac1s
\left(\frac{D_{LL}}{C_2}\right)^{3/2}.
\]

需要检查：

- `s` 是否位于惯性子区；
- 局地各向同性是否可接受；
- urban / surface layer 是否违反假设；
- `C_2` 的取值敏感性。

## 5.2 不要把 `ε^(1/3)` 直接写成无量纲 TI

\[
[\varepsilon^{1/3}]=m^{2/3}/s.
\]

如果只是风险代理，记成：

\[
I_\varepsilon
=\operatorname{scale}(\log\varepsilon).
\]

如果要传统 turbulence intensity：

\[
TI=\frac{\sigma_U}{\bar U}.
\]

两者不能混用。

## 5.3 风险状态统一

最后用于航路的风险值可以定义：

\[
r(\mathbf r,t)
=P(x(\mathbf r,t)>x_{safe}\mid D).
\]

这比直接把 TKE、ε、TI 混入路径代价更统一。

---

# 6. Q3-d：NWP 校准

NWP 原生预测记为：

\[
z^{NWP}(\mathbf r,t).
\]

如果模式有参数化 TKE / PBL turbulence diagnostics，优先使用；如果没有，再构造 diagnostic index。

必须记录：

\[
\Delta x_{native},\Delta z_{native},\Delta t_{native}.
\]

插值到 100 m 后仍标记：

```text
native-resolution-limited
```

而不是“100 m 高分辨率预报”。

## 6.1 用 c 做校准 reference

训练窗口：

\[
t\in T_{cal}.
\]

校准：

\[
x_c=g(z^{NWP})+\epsilon.
\]

验证必须 rolling-origin：

```text
past → calibrate
future → test
```

不能随机打散时次。

指标分两类：

连续：

\[
RMSE,\ MAE,\ correlation.
\]

事件：

\[
POD,\ FAR,\ CSI,\ HSS.
\]

并单报高风险尾部：

\[
q_{0.9},q_{0.95},q_{0.99}.
\]

---

# 7. Q3-e：无 NWP 的 short nowcast

候选“风廓线 LSTM 失败→S 波段”这个方向保留，但不要用普通 k-means 吞掉极值。

推荐：

## 7.1 自适应空间压缩

```text
low-gradient region → coarse
high-gradient region → fine
high-risk cell       → mandatory keep
sensor neighborhood  → mandatory keep
```

## 7.2 forecast ensemble

例如：

\[
x_{t+h}^{(m)}=F_{\psi_m}(x_{1:t})
\]

得到：

\[
\mu_e,\quad q_{10},q_{50},q_{90}.
\]

如果融合多个模型，不用 `R² normalized weight`，而用：

\[
w_m\propto\frac1{\sigma_m^2}
\]

或 stacking：

\[
\hat y=\sum_mw_m\hat y_m,
\qquad
w_m\ge0,\quad\sum_mw_m=1.
\]

权重由**真正未来验证集**求。

---

# 8. 从场到航路：time-expanded graph

飞行器以：

\[
s_t=(x_t,y_t,z_t,\psi_t,t)
\]

为状态。

边：

\[
s_t\rightarrow s_{t+1}
\]

必须满足：

- 最大速度；
- 最大爬升/下降率；
- 最大转角/最小转弯半径；
- 禁飞区；
- 高度限制；
- 到达时间窗。

这比纯 3D xyz 网格更接近真实飞行。

---

# 9. 风险目标：从点值 TKE 升级为 CVaR / chance constraint

## 9.1 多目标代价

\[
J(\pi)=
\lambda_L\frac{L(\pi)}{L_0}
+
\lambda_M\frac{M(\pi)}{M_0}
+
\lambda_R\,R(\pi).
\]

其中 `R` 不用单次场值，而用：

\[
R(\pi)=
CVaR_q\left[
\int_\pi r(\mathbf r,t)dt
\right].
\]

这样专门惩罚尾部危险。

## 9.2 chance constraint

也可以要求：

\[
P\left(
\max_{t\in\pi}x(\mathbf r(t),t)
\le x_{safe}
\right)
\ge1-\delta.
\]

例如：

\[
\delta=0.05.
\]

这比硬写一个确定性 `TKE_max` 更能利用上游 uncertainty。

---

# 10. A* 如何真正声明“最优”

边代价：

\[
c(e)\ge0.
\]

启发函数：

\[
h(n)\le h^*(n).
\]

则 A* 在有限图上可得到最优解。

论文必须公开：

- 邻居集合；
- diagonal move 是否允许；
- 竖直动作代价；
- 时间维度；
- heuristic；
- admissibility 说明。

结论写：

> 在给定离散网格、动作集和代价函数下的最优路径。

不是：

> 真实连续空域的绝对最优航路。

---

# 11. 验证闭环

最终至少需要六张核心图/表：

1. **Q1**：blocked/LOSO validation table；
2. **Q1**：teacher/student vertical-profile overlay；
3. **Q2**：analysis mean + uncertainty + sensor density；
4. **Q2**：leave-one-sensor-out skill table；
5. **Q3**：forecast horizon error curve；
6. **Route**：length-risk Pareto + multiple-seed / method comparison。

路线至少比较：

```text
straight
shortest-distance Dijkstra
risk-aware Dijkstra/A*
stochastic optimizer if used
robust/CVaR route
```

而且都用**同一场、同一约束、同一代价 evaluator**。

---

# 12. 一句话重构

候选论文可以抽象成：

\[
\boxed{
\text{Reference hierarchy}
\rightarrow
\text{Multi-source analysis}
\rightarrow
\text{Forecast calibration}
\rightarrow
\text{Risk-aware route}
}
\]

我们的升级版则是：

\[
\boxed{
\text{Observation operators}
\rightarrow
\text{Probabilistic state}
\rightarrow
\text{Calibrated ensemble forecast}
\rightarrow
\text{Chance/CVaR trajectory optimization}
}
\]

核心变化只有一句话：

> **把“不确定性”从论文最后的免责声明，变成模型里真正流动的数据。**
