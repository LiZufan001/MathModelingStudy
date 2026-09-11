# SAME_PROBLEM_COMPARISON｜2025 D 两篇同题优秀论文候选对照

对照对象：

- **D1**：`graduate:paper:2025-D:ac2d33da18fa`，60 页，《低空湍流监测及最优航路规划研究》；与石彤彤/赵其伟/安雪菱国一作品高度吻合，但尚未核封面。
- **D2**：`graduate:paper:2025-D:95743f6ef8d6`，110 页，《基于多源数据融合的低空湍流监测与航路优化》；**不能绑定关昊岩/谢卓毅/杨骞队**，仅作同题第二条完整路线证据。

---

# 1. 总览

| 层 | D1 `ac2d` | D2 `9574` | 评价 |
|---|---|---|---|
| Q1 reference | Ri + 时间脉动 TKE | Ri + `SW²` + shear 综合指数 | D1 物理量更直接；D2 指标组合更完整但口径有矛盾 |
| Q1 reduced model | RF → XGBoost | 正则回归 + 11 回归器，RF 最优 | D2 模型比较更丰富；D1 叙事更简洁 |
| Q2 fusion | VAD + X/S 背景 + OI | QC + anisotropy + variational + Kalman | D2 状态估计架构更先进 |
| uncertainty | 较弱 | confidence + error propagation | D2 明显更好 |
| NWP d | WRF → TKE diagnostic → A* | NWP diagnostic → 分层非线性校正 → A* | D2 的 bias correction 更合理 |
| short-nowcast e | profiler LSTM 失败 → S-band LSTM → ACO | 多个简单时序模型 + ensemble → A* | D2 对短数据更稳健；D1 的负结果叙事更好 |
| route evidence | A* vs straight + 10 random/spline，有数值 cost | robust/chance A* 公式丰富，但无完整数值 baseline | D1 证据更扎实 |
| uncertainty-to-route | 基本确定性 | robust objective + chance constraint | D2 思想更先进，但落地不足 |
| writing | 方法较少、执行较清楚 | 技术栈很大、后半有公式注水 | D1 更克制 |
| reproducibility | 有参数/代码口径问题 | synthetic fallback、物理拆分、in-sample 风险更大 | 两篇都需重做；D2 风险更重 |

---

# 2. Q1：同一个 teacher-student 骨架，两种物理口径

## D1

```text
radar + radiometer
→ θ / Ri
→ temporal wind fluctuation TKE
→ model a
→ RF / XGBoost model b
```

特点：

- teacher 物理解释直观；
- 直接承认 a 只是 reference 更合理；
- b 的结果只有中等 `R²≈0.56`，没有过度包装。

## D2

```text
radar + radiometer
→ θ / Ri
→ SW² + shear
→ normalized composite Ia
→ Ib
→ 11 regressors / RF
```

特点：

- 把发生倾向、扰动强度和 shear 分层组合；
- 横评 11 模型并识别 gradient boosting overfit；
- 但 `[0,1]` 与 RMSE 5–8 的矛盾很严重；
- `SW²` 需要明确只是 proxy。

### 我们怎么选

比赛时间紧：

> 选 D1 式“物理 reference + 少量代理模型”。

数据条件更复杂、能完整做 calibration：

> 用 D2 的 composite features，但统一量纲并做 out-of-sample calibration。

---

# 3. Q2：OI vs variational assimilation

## D1：OI

\[
x_a=x_b+K(y-Hx_b).
\]

优点：

- 数学闭环短；
- covariance 作用清楚；
- 比赛好解释；
- 容易做 leave-one-sensor-out。

缺点：

- 对非线性约束、复杂正则扩展较弱；
- uncertainty 传播写得不够系统。

## D2：variational

\[
J(T)=J_{obs}+\lambda_bJ_b+\lambda_sJ_s.
\]

再配：

- anisotropic distance；
- semivariogram；
- Kalman；
- semi-Lagrangian；
- confidence field；
- uncertainty decomposition。

优点：

> 更像真正的“state estimation system”。

缺点：

> 模块多以后，如果没有消融，就不知道 RMSE 0.143 到底是谁贡献的。

### 我们怎么选

最推荐：

> **先实现 OI baseline，再把 variational 当升级。**

流程：

```text
IDW baseline
→ OI baseline
→ 3DVAR
→ + anisotropy
→ + time filtering
```

每一步都报增益。

---

# 4. “细网格”问题：两篇都没有真正解决

两篇最终都会把场放到接近：

\[
100m\times100m\times50m
\]

的分析网格。

但 sensor native resolution / coverage 并没有因此变化。

所以二者共有风险：

\[
\boxed{fine\ grid\ visualization\rightarrow false\ precision}.
\]

D2 比 D1 好的一点是至少输出 confidence/error；但仍没有真正给 effective resolution map。

我们应该补：

\[
L_{eff}(\mathbf r,z,t)
\]

或者简单用 observation distance / posterior variance 表示可信尺度。

---

# 5. Q3 NWP：D2 明显比 D1 更值得学

## D1

基本是：

```text
WRF Ua/Va/Wa/Z
→ interpolate
→ temporal fluctuation TKE
→ route
```

问题：

- NWP temporal fluctuation 不一定等于 turbulence TKE；
- 粗场超分辨插值风险；
- 缺观测 bias calibration。

## D2

```text
NWP diagnostics
→ observation-based calibration
→ layer-wise nonlinear correction
→ forecast
```

这一层明显更合理，因为承认：

> NWP 是有系统偏差的 forecast source，不是 truth。

### 最佳合并

\[
r_{forecast}
=
r_{NWP}+f(\text{recent residuals},z,terrain,time).
\]

而不是重新拟合整个 NWP 场。

---

# 6. Q3 nowcast：D1 的失败实验 vs D2 的 baseline discipline

## D1

风廓线 LSTM：

\[
R^2\approx0.27\rightarrow0.28.
\]

正文承认失败，转 S-band LSTM：

\[
R^2\approx0.77.
\]

这是很好的**negative-result narrative**。

## D2

直接比较：

- trend；
- MA；
- exponential smoothing；
- multivariate regression；
- spatiotemporal；
- ensemble。

最后 ensemble：

\[
RMSE\approx0.1612,
\qquad R^2\approx0.7693.
\]

这是很好的**simple-baseline discipline**。

### 我们应该两者都学

> 先做简单 baseline；如果复杂模型失败，保留失败结果并解释为什么换信息源，而不是只换算法。

---

# 7. 路径规划：D1 赢在证据，D2 赢在问题意识

## D1

A* 路径 cost：

\[
1.14\times10^7
\]

而 straight/random/spline 大约：

\[
4.2\times10^8\sim1.14\times10^9.
\]

虽然这并不证明连续空间全局最优，但至少：

> **有统一 evaluator 和数字对照。**

## D2

加入：

\[
\min E[J]+\lambda Var[J],
\]

以及：

\[
P(I>I_{crit})\le\varepsilon.
\]

甚至多准则和动态重规划。

思想更接近真实航空风险决策。

问题是：

> 没有清楚的 baseline table 证明这些升级真的改变了结果。

### 最佳合并

用 D2 的 risk formulation，按 D1 的 evidence discipline 验收：

| path | length | mean risk | q95 | CVaR95 | exceed prob | runtime |
|---|---:|---:|---:|---:|---:|---:|

没有这张表，不写“降低 35%”。

---

# 8. 两篇都存在的共同硬伤

## 8.1 reference ≠ truth

两篇都让高信息模型当 teacher。

必须写：

> best-available reference / pseudo-label。

## 8.2 时间切分

两篇都必须强化：

- blocked；
- rolling；
- extreme-event holdout。

## 8.3 分辨率

两篇都不能把插值网格当真实分辨率。

## 8.4 风险量纲

都需要统一：

- TKE；
- EDR；
- SW proxy；
- normalized index。

不应章节间随意切换。

## 8.5 route dynamics

都需要显式：

- max climb；
- max turn；
- speed；
- time；
- no-fly；
- battery/endurance。

否则是 graph path，不是 aircraft trajectory。

---

# 9. 如果我是指导老师，会怎么拼成我们自己的 2026 模板

```text
Step 1 物理定义主风险变量
Step 2 rich-source reference + uncertainty
Step 3 reduced sensor surrogate
Step 4 OI baseline
Step 5 3DVAR / variational upgrade
Step 6 leave-one-sensor-out validate
Step 7 NWP residual calibration
Step 8 persistence / regression / advection / ensemble
Step 9 probabilistic forecast + extreme calibration
Step 10 time-expanded graph
Step 11 distance A* baseline
Step 12 mean-risk A*
Step 13 CVaR / chance A*
Step 14 route table + robustness
```

这条路线把：

- D1 的落地性；
- D2 的系统性；

合并到一起。

---

# 10. 写作层面谁更强

## D1 更值得学

- 高级模型数量少；
- 失败实验推动决策；
- route 有数字 baseline；
- 逻辑短。

## D2 更值得学

- 摘要直接给模型数学形态；
- uncertainty 是正式输出；
- NWP bias correction 有独立层；
- 评价章节明确写失效场景。

## D2 不应学

- 30 个不落地公式；
- 摘要数字正文找不到；
- synthetic fallback；
- 把 A* 最优性写成假设。

---

# 11. 评审式最终结论

若只问“哪篇路线更高级”：

> D2。

若问“哪篇公开证据更让我放心”：

> D1。

若问“我们比赛应该学哪一篇”：

> **两篇拼起来学。**

最值得组合的四个模块：

1. D1：负结果驱动模型切换；
2. D1：统一 route baseline；
3. D2：uncertainty-aware variational fusion；
4. D2：NWP correction + robust/chance route。

---

# 一句话

> **同题异解最有价值的不是判断“谁用了更高级的算法”，而是看谁把不确定性、验证和最终决策真正接了起来：D1 更像能交付的工程原型，D2 更像完整系统蓝图；我们的目标应是用 D1 的证据标准去验收 D2 的系统架构。**
