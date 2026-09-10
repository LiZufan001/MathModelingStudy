# F24104860143｜模型与算法重构

> 目标：保留原论文“轨道 → 时延 → 相位 → NHPP → 折叠”的优秀系统结构，同时修正时间单位、参考系、相对论小项和随机过程验证。

---

# 1. 统一数据对象：任何物理量都带元数据

建议从代码层先禁止裸数组跨模块传递：

```python
StateVector(
    r_km,
    v_km_s,
    frame,       # GCRS / BCRS
    time_scale,  # TT / TDB / TCB
    jd
)
```

每个时间：

```python
Epoch(value, format='MJD', scale='TT')
```

每个 delay 函数只接收明确定义的 frame / scale。

---

# 2. Q1：轨道模块

## 2.1 forward model

\[
a=\frac{h^2}{\mu(1-e^2)},\qquad
p=a(1-e^2),\qquad
r=\frac{p}{1+e\cos f}.
\]

在 perifocal frame：

\[
\mathbf r_{PQW}=\begin{bmatrix}r\cos f\\r\sin f\\0\end{bmatrix},
\]

\[
\mathbf v_{PQW}=\sqrt{\frac\mu p}
\begin{bmatrix}-\sin f\\e+\cos f\\0\end{bmatrix}.
\]

再使用唯一、经过单元测试的旋转矩阵：

\[
\mathbf r_{GCRS}=R_3(-\Omega)R_1(-i)R_3(-\omega)\mathbf r_{PQW}.
\]

## 2.2 validation

不要只做 forward→inverse round trip。

至少同时检查：

\[
\|\mathbf r\times\mathbf v\|-h,
\]

\[
\epsilon=\frac{v^2}{2}-\frac\mu r=-\frac\mu{2a},
\]

\[
\mathbf e=\frac{\mathbf v\times\mathbf h}{\mu}-\frac{\mathbf r}{r},
\quad \|\mathbf e\|=e.
\]

然后与独立库/数值积分交叉。

---

# 3. Q2：参考系和时间尺度模块

## 3.1 TT→TDB

若只采用题目规模下的低阶近似：

\[
\Delta_{TDB-TT}=0.001657\sin g\quad [s],
\]

则：

\[
JD_{TDB}=JD_{TT}+\frac{\Delta_{TDB-TT}}{86400}.
\]

不要把“秒数”直接加到“天”。

更高要求时直接用成熟天文时间库，不手抄简化公式。

## 3.2 GCRS→BCRS

在题目给出的简化语境下：

\[
\mathbf r_{SC,BCRS}
=\mathbf r_{EMB,BCRS}
+\mathbf r_{Earth/EMB}
+\mathbf r_{SC,GCRS}.
\]

速度同理，但必须确认 ephemeris derivative 的时间单位；`jplephem.compute_and_differentiate()` 的导数需要明确从 km/day 转成 km/s。

## 3.3 proper motion

若题目给 `μα, μδ` 为角速度，则：

\[
\alpha(t)=\alpha_0+\mu_\alpha(t-t_0),
\]

\[
\delta(t)=\delta_0+\mu_\delta(t-t_0).
\]

单位链明确写：

```text
mas/year → deg/day → rad
```

再：

\[
\hat n=
(\cos\delta\cos\alpha,
 \cos\delta\sin\alpha,
 \sin\delta)^T.
\]

## 3.4 Roemer delay

统一符号约定：

\[
\Delta_R=-\frac{\mathbf r_{SC,BCRS}\cdot\hat n}{c}
\]

或使用相反号都可以，但全文必须一致并解释“spacecraft TOA → SSB TOA”是哪一方向。

---

# 4. Q3：不要把相对论拆成量纲不闭合的小公式

更可靠的思路是：

\[
t_{SSB}=t_{SC}+\Delta_R+\Delta_E+\Delta_S+\cdots
\]

其中：

- `ΔR`：Roemer / geometric；
- `ΔS`：Shapiro；
- `ΔE`：Einstein / clock-coordinate correction，把引力势与运动钟速差放在一致时间尺度变换里处理。

## 4.1 Shapiro

太阳一阶项可保留：

\[
\Delta_S
=-\frac{2GM_\odot}{c^3}
\ln(1+\cos\Theta)
\]

或等价的由太阳—航天器位置与 source direction 写出的形式。

需明确 sign convention。

## 4.2 Einstein / clock correction

不要直接写：

\[
GM/(rc^2)\ [s].
\]

更合适的建模形式是先写钟速率：

\[
\frac{d\tau}{dt}
\approx1-\frac{U}{c^2}-\frac{v^2}{2c^2},
\]

再对时间积分：

\[
\Delta_E(t)=\int_{t_0}^t
\left(\frac{U}{c^2}+\frac{v^2}{2c^2}+\cdots\right)dt.
\]

或者在竞赛时间有限时：

> 使用标准 TT↔TDB/TCB 转换作为 Einstein correction 的实现，并清楚说明它已经包含哪些势场/运动项，避免重复加项。

## 4.3 一张“避免 double counting”表

| effect | implemented where | 是否再单独加 |
|---|---|---|
| Earth orbital velocity | TT↔TDB / Einstein | 否，若已包含 |
| solar gravitational potential | TT↔TDB / Einstein | 否，若已包含 |
| geometric path | Roemer | 是 |
| solar curved-space propagation | Shapiro | 是 |
| proper motion | source direction | 是 |

这种表比堆公式更能让评审相信模型闭环。

---

# 5. Q4：标准 NHPP 模型

## 5.1 periodic pulse profile

标准轮廓 `h(φ)` 必须显式周期：

\[
h(\phi+1)=h(\phi).
\]

而且归一化：

\[
\int_0^1h(\phi)d\phi=1.
\]

不要让普通 cubic spline 在 `[0,1]` 两端自由外推。

可使用：

```text
circular extension
或 periodic spline
```

并检查：

```python
assert min(h(phi_grid)) >= 0
assert abs(integral(h)-1) < tol
```

## 5.2 phase model

\[
\Phi(t)=\Phi_0+\nu\Delta t
+\frac12\dot\nu\Delta t^2
+\frac16\ddot\nu\Delta t^3,
\]

\[
\phi(t)=\Phi(t)\bmod1.
\]

注意：若模拟 spacecraft TOA，必须先决定相位用 SSB 时间还是 spacecraft time；统一通过 `delay(t)` 转换，不把 `dt=0` 写死后仍声称已经考虑 Q3。

## 5.3 intensity

题目给背景流量密度 `F_b`、源流量密度 `F_s` 和面积 `A`：

\[
\lambda_b=AF_b,
\qquad
\lambda_s=AF_s,
\]

\[
\lambda(t)=\lambda_b+\lambda_s h(\phi(t)).
\]

必须验证：

\[
\lambda(t)\ge0.
\]

---

# 6. 三种可选 NHPP sampler

## 方法 A：inverse cumulative intensity

定义：

\[
\Lambda(t)=\int_{t_0}^t\lambda(s)ds.
\]

生成：

\[
E_i\sim Exp(1),
\quad S_k=\sum_{i=1}^kE_i,
\]

若 `S_k≤Λ(T)`：

\[
t_k=\Lambda^{-1}(S_k).
\]

这是 time-transformation 法。

## 方法 B：Poisson total + order statistics

\[
N\sim Poisson(\Lambda(T)-\Lambda(0)),
\]

\[
U_i\sim Uniform(0,1),
\]

\[
y_i=\Lambda(0)+U_i[\Lambda(T)-\Lambda(0)],
\]

\[
t_i=\Lambda^{-1}(y_i),
\]

最后排序。

这就是原论文 A.6 真正实现的方法，应明确叫：

> conditional order-statistics method。

## 方法 C：thinning

若能找 majorizer：

\[
\lambda(t)\le \lambda^*(t),
\]

先从 `λ*` 采候选，再以：

\[
\lambda(t)/\lambda^*(t)
\]

接受。

三种方法都比“把当前 λ 固定到下一个事件”为原则上更可靠的 baseline。

---

# 7. 数值求 Λ 和 Λ^{-1}

## 7.1 网格误差必须可控

建议做采样间隔敏感性：

```text
dt = T/64
T/128
T/256
T/512
T/1024
```

比较：

- `Λ(T)`；
- 事件总数均值；
- folded-profile RMSE；
- Pearson；
- runtime。

直到指标稳定。

## 7.2 单调插值

`Λ(t)` 必须单调递增。

逆映射可用：

- monotone linear interpolation；
- PCHIP；
- binary search + local interpolation。

不建议对 `Λ` 使用可能破坏单调性的普通高阶 spline。

---

# 8. 正确的 validation stack

原论文主要：

```text
Pearson(profile, template)
+ count χ²
```

建议升级为四层。

## V1. 强度积分校准

理论：

\[
E[N(0,T)]=\Lambda(T),
\quad Var[N(0,T)]=\Lambda(T).
\]

多次 Monte Carlo 比较 empirical mean/variance。

## V2. time-rescaling

事件时间：

\[
t_1<t_2<\cdots<t_n.
\]

计算：

\[
z_i=\Lambda(t_i)-\Lambda(t_{i-1}).
\]

正确 NHPP：

\[
z_i\sim iid\ Exp(1).
\]

报告：

- KS p-value；
- QQ plot；
- lag-1 autocorrelation。

## V3. profile recovery

报告：

```text
Pearson
RMSE
peak phase bias
peak amplitude bias
```

并注明它是 **self-consistency**，不是 independent physical validation。

## V4. independent / stress validation

改变：

- source/background ratio；
- observation time；
- spin derivative；
- bin count；
- start phase。

检查 sampler 是否保持统计性质。

---

# 9. 对原论文结果的复算解释

## 9.1 原递推法

复现公开 cubic-spline + seed=10：

- 事件数约 `4.25×10^4`；
- Pearson `≈0.993513`；

与论文 `0.99351` 对得上。

## 9.2 修正 linear baseline

论文 linear 函数分母符号反了。

同一 seed：

- 错误代码：Pearson `≈0.990420`，匹配论文表；
- 修正后：Pearson `≈0.99375`。

说明“cubic 明显最好”不能成立为公平算法比较。

## 9.3 改进 order-statistics

按 A.6 逻辑 + seed=42，在当前 SciPy 环境复算 Pearson 约：

\[
0.99596.
\]

因此论文最后写成与旧 cubic 恰好相同的 `0.99351` 很可能不是当前公开代码同一运行输出；至少必须回到唯一结果源核验。

---

# 10. 推荐的工程目录

```text
orbit.py
  elements_to_state()
  state_to_elements()
  validate_invariants()

time_scales.py
  tt_to_tdb()

frames.py
  gcrs_to_bcrs()

pulsar.py
  proper_motion()
  phase()
  periodic_profile()

delay.py
  roemer()
  shapiro()
  einstein_or_clock()
  total_delay()

nhpp.py
  cumulative_intensity()
  sample_inverse()
  sample_orderstats()
  sample_thinning()

validate.py
  time_rescaling_test()
  count_calibration()
  profile_metrics()
```

避免一个脚本内同时维护 km、m、TT、TDB、GCRS、BCRS。

---

# 11. 比赛版最小闭环

如果只有几十小时：

```text
1. 正确 Q1 二体状态
2. 正确 TT/TDB 单位
3. DE ephemeris → BCRS
4. Roemer baseline
5. Sun Shapiro
6. 统一说明 Einstein/clock 的实现口径
7. periodic h(φ)
8. order-statistics NHPP
9. fold
10. time-rescaling + profile RMSE/Pearson
```

先保证这 10 步无单位和统计错误，再增加更高阶天体/相对论项。

---

# 12. 一句话

> **高精度物理模型最可靠的架构，不是“把所有修正项都写出来”，而是让每一个修正项在同一 reference frame、time scale、unit system 和 evaluator 中可独立测试。**
