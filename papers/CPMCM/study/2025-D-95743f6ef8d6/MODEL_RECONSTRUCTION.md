# MODEL_RECONSTRUCTION｜2025 D：从多源观测到概率风险航路

这份文件不是复述候选论文，而是把同题中最有价值的思想重构成一套更统一、可审计、适合比赛落地的模型。

---

# 1. 统一目标

整题不要拆成“模型 a/b/c/d/e + 若干算法”，而应统一为：

\[
\boxed{
\text{Observation}
\rightarrow
\text{Latent Turbulence State}
\rightarrow
\text{Forecast Distribution}
\rightarrow
\text{Risk-aware Route}
}
\]

核心状态：

\[
x(\mathbf r,z,t)
\]

表示某个统一定义下的 turbulence risk state。

必须先固定它到底是：

- TKE；
- EDR；
- spectral-width proxy；
- normalized risk index；
- 或经标定的综合指数。

全文只允许一个“主风险状态”，其他 Ri、SW、shear、TKE 等都是 observation features / diagnostics。

---

# 2. 观测算子层

每个传感器 s 建模为：

\[
y_s=H_s(x,\eta_s)+b_s+\epsilon_s,
\]

其中：

- `H_s`：传感器观测算子；
- `η_s`：几何/分辨率/扫描参数；
- `b_s`：系统偏差；
- `ε_s`：随机误差。

不要把所有设备一上来就变成一个“湍流强度”。

## 2.1 风廓线雷达

真实径向速度关系：

\[
V_r
=u\cos\theta\cos\phi
+v\sin\theta\cos\phi
+w\sin\phi.
\]

多波束情况下用 least squares / VAD 反演 `u,v,w`。

严禁：

```text
u = a * Vr
v = b * Vr
w = c * Vr
```

作为正式物理模型。

## 2.2 微波辐射计

主要提供温度廓线，用于：

\[
\theta
\rightarrow
\frac{\partial\theta}{\partial z}
\rightarrow
Ri.
\]

## 2.3 多普勒天气雷达

可使用：

- radial velocity；
- spectral width；
- local shear；
- reflectivity/QC；

但 `SW²` 只当 turbulence proxy，除非做了 beam/shear broadening correction。

---

# 3. Reference hierarchy

如果没有直接 turbulence truth，建立：

\[
y^*=f(\text{rich sensors})
\]

作为 best-available reference。

同时明确：

\[
y^*\neq\text{absolute truth}.
\]

受限模型：

\[
\hat y_b=g(\text{cheap sensors}).
\]

训练：

\[
\min_g
\sum_t
\ell(g(X_t),y_t^*)
+
\lambda\Omega(g).
\]

验证必须包含：

```text
blocked time
leave one site out
height-band holdout
extreme-event holdout
```

---

# 4. 主融合模型：简化 3DVAR / Bayesian MAP

状态：

\[
x\in\mathbb R^n.
\]

背景：

\[
x_b\sim N(\mu_b,B).
\]

观测：

\[
y_s=H_sx+\epsilon_s,
\qquad
\epsilon_s\sim N(0,R_s).
\]

求：

\[
\hat x
=
\arg\min_x
\left[
\frac12(x-x_b)^TB^{-1}(x-x_b)
+
\frac12\sum_s(y_s-H_sx)^TR_s^{-1}(y_s-H_sx)
+
\lambda\|Lx\|^2
\right].
\]

其中：

- `B`：背景相关；
- `R_s`：传感器误差；
- `L`：水平/垂直各向异性平滑算子。

## 4.1 为什么不再单独乘 `w_source`

若 source quality 已在 `R_s` 中体现：

\[
R_s\downarrow
\Rightarrow
\text{sensor weight}\uparrow,
\]

则不应再随意乘一个固定 source weight，避免重复计权。

## 4.2 各向异性 covariance

\[
B_{ij}
=
\sigma_b^2
\exp\left(
-\frac{d_h^2}{2L_h^2}
-\frac{d_v^2}{2L_v^2}
\right).
\]

`Lh/Lv` 可由 variogram / residual correlation 估计。

---

# 5. 输出的不只是 mean field

定义统一接口：

```text
FieldEstimate
- mean
- std / covariance
- valid_mask
- native_resolution
- analysis_grid
- effective_resolution
- observation_density
- qc_flag
```

下游 forecast / route 不允许只拿 `.mean`。

如果精确 posterior covariance 太贵，可用：

- ensemble；
- bootstrap；
- diagonal Hessian inverse approximation；
- leave-one-sensor residual model。

---

# 6. NWP 校正：不要只做插值

NWP 原始 risk diagnostic：

\[
r^{raw}_{nwp}(\mathbf r,z,t).
\]

观测融合 reference：

\[
r^{obs}(\mathbf r,z,t).
\]

按高度/区域建立 bias correction：

\[
r^{cal}
=
a(z)+b(z)r^{raw}+c(z)(r^{raw})^2.
\]

或更稳：

\[
r^{cal}=r^{raw}+\Delta r,
\]

\[
\Delta r
=f(z,terrain,time,r^{raw},\nabla r^{raw}).
\]

可选：

- ridge / spline；
- GAM；
- quantile regression；
- residual GP；
- gradient boosting。

关键不是模型名，而是：

> **训练只看过去，验证只看未来。**

---

# 7. 短临 forecast：概率而不是单值

## 7.1 Baselines

至少：

\[
\hat x_{t+h}=x_t
\]

persistence。

再比较：

- linear trend；
- exponential smoothing；
- multivariate regression；
- advection；
- ensemble。

## 7.2 Ensemble distribution

令多个模型：

\[
\hat x^{(m)}_{t+h}.
\]

权重不要直接用 R² 正归一化，推荐：

\[
w_m\propto\frac1{RMSE_m^2+\epsilon}
\]

或 stacking。

得到：

\[
\mu_{t+h}
=\sum_mw_m\hat x^{(m)}_{t+h}.
\]

预测方差：

\[
\sigma^2_{t+h}
=
\sum_mw_m
(\hat x^{(m)}-\mu)^2
+
\sigma^2_{obs/model}.
\]

---

# 8. 极端风险必须单独校准

平均 RMSE 不够。

定义危险阈值：

\[
r>r_{crit}.
\]

报告：

- POD / recall；
- FAR；
- CSI；
- Brier score；
- reliability curve；
- extreme quantile error。

如果预测场更平滑、峰值降低，必须检查是否发生：

\[
\boxed{extreme\ underestimation}.
\]

---

# 9. 空间-时间图上的航路

节点：

\[
n=(x,y,z,t).
\]

动作必须满足：

- 空域边界；
- 高度上下限；
- 最大爬升/下降率；
- 最大转弯角/曲率；
- 速度范围；
- 禁飞区；
- 电量/航时。

边代价：

\[
c_e
=
\lambda_L\frac{d_e}{L_0}
+
\lambda_R\,Risk_e
+
\lambda_M\,Maneuver_e.
\]

所有项先无量纲化。

---

# 10. Risk 不再只用 mean

## 10.1 Expected risk

\[
Risk_e=E[R_e].
\]

## 10.2 CVaR

\[
Risk_e=CVaR_{0.95}(R_e).
\]

## 10.3 Chance constraint

\[
P(R_e>R_{crit})\le\epsilon.
\]

或者整条路径：

\[
P\left(
\max_{e\in\pi}R_e\le R_{crit}
\right)
\ge1-\delta.
\]

安全类题优先用后两者。

---

# 11. A* 的 admissible heuristic

如果单位距离最小代价为：

\[
c_{min}>0,
\]

用：

\[
h(n)=
c_{min}
\,d_{euclid}(n,goal).
\]

必须满足：

\[
h(n)\le J^*_{remain}(n).
\]

只有这样才能说：

> A* 在当前离散状态空间和定义的 cost 下返回全局最优。

不要把这句话写进“模型假设”，而要写成算法性质证明。

---

# 12. 路径结果的 baseline 套装

统一 evaluator 下至少比较：

```text
straight line
shortest-distance Dijkstra/A*
mean-risk A*
CVaR A*
chance-constrained A*
```

如果另有 ACO/GA/PSO：

- 30 seeds；
- mean ± std；
- feasibility rate；
- runtime；
- same constraints。

---

# 13. 两篇 2025 D 合并后的最佳路线

从 `ac2d33da18fa` 借：

- 负结果驱动路线切换；
- OI 的可审计性；
- 路径 baseline；
- A*/ACO 分工。

从 `95743f6ef8d6` 借：

- variational state estimation；
- confidence / uncertainty field；
- NWP bias calibration；
- simple-model forecast ensemble；
- robust / chance route formulation。

合并：

```text
physical reference
→ probabilistic 3DVAR/OI analysis
→ calibrated NWP + observation ensemble
→ forecast distribution
→ time-aware risk graph
→ CVaR / chance A*
→ deterministic baselines + robustness
```

---

# 14. 最小可交付版本

比赛时间不足时，不要把这套系统做成 30 个模型。

## Q1

- Ri + shear + SW proxy reference；
- ridge / RF reduced model；
- blocked validation。

## Q2

- OI/3DVAR 二选一；
- posterior variance proxy；
- leave-one-sensor-out。

## Q3

- persistence + regression + advection ensemble；
- NWP residual calibration；
- time-expanded A*；
- distance / mean-risk / CVaR 三个 baseline。

这样已经足够形成高质量闭环。

---

# 15. 一句话重构

> **真正的低空湍流航路题不是“把几个传感器插值成一张图再跑 A*”，而是先通过观测算子和误差协方差估计一个带不确定性的三维状态，再对 NWP 和观测短临进行时间上严格的概率校准，最后在时空图上最小化尾部风险，并用可证明的启发函数和统一 baseline 证明路径确实更安全。**
