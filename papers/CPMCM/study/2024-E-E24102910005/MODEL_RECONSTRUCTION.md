# E24102910005｜模型与算法重构

> 目标：保留原论文最好的“视频→状态→预测→控制→布点”架构，但把测量标定、时间验证、反事实仿真与安全约束补成一个可复现闭环。

---

# 1. 统一系统图

```text
camera video
   ↓
Detector + Tracker
   ↓
Metric calibration
   ↓
per-lane q / v / occupancy observations
   ↓
Conservation state estimator / CTM
   ↓
current segment state x_t
   ↓
10-min forecast p(congestion | information_t)
   ↓
finite-state shoulder controller
   ↓
traffic simulator / digital twin
   ↓
travel time + queue + safety + robustness
   ↓
sensor-placement value of information
```

核心原则：

> **每一个模块的输出都必须有单位、时间戳、置信度，并成为下一模块的显式输入。**

---

# 2. Measurement model

对相机 `c`、车道 `l`、时间窗 `k`：

\[
z_{clk}=\{n_{cross},\,v,\,occupancy,\,confidence\}.
\]

利用 homography：

\[
H_c:[x_{pixel},y_{pixel},1]^T\mapsto[X_{road},Y_{road},1]^T.
\]

轨迹速度：

\[
v_i(k)=\frac{\|r_i(t_2)-r_i(t_1)\|}{t_2-t_1}.
\]

流量：

\[
q_{cl}(k)=\frac{N_{cross,cl}(k)}{\Delta t}.
\]

对测量误差建立：

\[
z_k=h(x_k)+\varepsilon_k,
\qquad
\varepsilon_k\sim(0,R_k).
\]

`R_k` 应来自人工标注子集，而不是拍脑袋。

---

# 3. State model：优先守恒而不是瞬时 count

将 A–D 间路段离散为 cell。最简单的区间车辆数：

\[
N_{s,k+1}=N_{s,k}+\Delta t(q_{in,s,k}-q_{out,s,k}).
\]

归一化：

\[
S_{s,k}=\frac{N_{s,k}}{N_{s,max}}.
\]

这就是原论文 `K(t)` 最有价值的部分，但统一改名 `storage ratio S`。

若数据允许，升级为 Cell Transmission Model：

\[
N_i^{k+1}=N_i^k+y_{i-1}^k-y_i^k,
\]

\[
y_i^k=\min\{D_i(N_i^k),S_{i+1}(N_{i+1}^k)\},
\]

其中 demand/supply 可由 fundamental diagram 标定。

这样开启应急车道不是简单 `q_D×1.3`，而是修改对应 cell 的：

- capacity；
- critical density；
- lane-change friction；
- receiving capacity。

---

# 4. Congestion definition

避免同时混用 `ρm`、`ρcritical`、`warning threshold`。

定义：

```text
rho_jam       静止/极端堵塞密度
rho_critical  最大流量对应密度
rho_warn      预警密度
S_open        控制开启阈值
S_close       控制关闭阈值
```

拥堵事件：

\[
C_t=1
\iff
\rho_t>\rho_{critical}
\land v_t<v_{critical}
\]

持续拥堵：

\[
\sum_{j=0}^{T_c-1} C_{t+j}\Delta t\ge30\text{ min}.
\]

最终预测目标直接定义成：

\[
P(\text{next 30 min sustained congestion}\mid\mathcal F_t).
\]

这比先算某个 `τ` 再和实际持续时间绕一圈更直接对齐题意。

---

# 5. Forecast model

构造时刻 t 可获得的信息：

\[
X_t=
[\rho_A(t-l_A),\rho_B(t-l_B),\rho_C(t-l_C),
 q_A,q_B,q_C,
 v_A,v_B,v_C,
 S_{AB},S_{BC},S_{CD},
 \rho_D(t),\ldots].
\]

lag 不固定写死 10，而由：

\[
l_i\approx d_i/v_i
\]

与 cross-correlation 联合确定。

建立两类输出：

1. 回归：
   \[
   \hat\rho_D(t+10)
   \]
2. 概率：
   \[
   \hat p_t=P(C_{t+10:t+40}=1)
   \]

比赛时间紧时可用：

```text
Persistence
Linear/ElasticNet
Random Forest / ExtraTrees / LightGBM
```

关键不是模型名，而是 rolling-origin evaluation。

---

# 6. Validation protocol

时间序列不能 random split。

推荐：

```text
Fold 1: early → later
Fold 2: early+middle → later
...
```

若有多天视频：leave-one-day-out。

指标至少：

```text
rho forecast: MAE / RMSE
warning: precision / recall / F1
lead time: mean/median minutes
false alarms per hour
missed sustained congestions
```

并与：

\[
\hat\rho_{t+10}=\rho_t
\]

的 persistence baseline 比较。

---

# 7. Shoulder control as finite-state machine

状态：

```text
CLOSED
PREPARE
OPEN
CLEARING
EMERGENCY_OVERRIDE
```

建议规则：

### CLOSED → PREPARE

\[
p_t>p_{warn}
\land S_{up}>S_{warn}.
\]

### PREPARE → OPEN

\[
S_{up}>S_{open}
\land S_{down}<S_{safe}
\land \text{safety_clear}=1.
\]

### OPEN → CLEARING

\[
S_{up}<S_{close}
\]

持续至少 `T_confirm`，其中：

\[
S_{close}<S_{open}
\]

实现滞回。

### CLEARING → CLOSED

检测到肩道已清空后关闭。

任何事故/急救需求进入：

```text
EMERGENCY_OVERRIDE
```

优先级高于拥堵效率。

---

# 8. Objective function

不要只最小拥堵时间。可以写：

\[
J=
\alpha T_{travel}
+\beta Q_{max}
+\gamma T_{congestion}
+\eta N_{switch}
+\xi R_{safety}.
\]

安全约束可以不放加权目标，而作为硬约束：

\[
R_{safety}\le R_{max}.
\]

实际竞赛中，如果安全数据不足，宁可使用 hard logical constraints，也不要凭主观 AHP 给“生命安全”一个可被效率抵消的权重。

---

# 9. Counterfactual simulator

原论文 `+30% capacity` 可以作为一个 scenario，但必须做敏感性。

定义 action：

\[
a_t\in\{0,1\}.
\]

对应容量：

\[
C_t=C_0[1+g(a_t)]
\]

其中 `g` 考虑：

- 新增车道名义容量；
- 合流/换道摩擦；
- 司机利用率；
- 下游 bottleneck。

至少跑：

\[
g=0.1,0.2,0.3,0.4,0.5.
\]

比较：

```text
no control
paper threshold control
probability + hysteresis control
oracle upper bound
```

输出：

- total vehicle hours；
- congestion duration；
- max queue；
- number of shoulder switches；
- safety constraint violations。

---

# 10. Sensor placement

候选摄像头集合 `S`，成本 `c_j`。

定义：

\[
Utility(S)
=-L_{control}(S)-\lambda\sum_{j\in S}c_j.
\]

其中控制损失可由闭环 replay 得到。

求：

\[
\max_{S\subseteq\mathcal C} Utility(S).
\]

简单比赛版本可用 greedy forward selection：

```text
每轮加入使 validation control loss 降低最多的 camera
直到 cost budget 用完
```

这会把“把 B 搬到 E”从经验建议升级成可验证结果。

---

# 11. 不确定性传播

measurement uncertainty：

\[
q\pm\sigma_q,\quad
v\pm\sigma_v,\quad
\rho\pm\sigma_\rho.
\]

Monte Carlo / bootstrap 推到：

\[
P(S_t>S_{open}),
\qquad
P(\text{congestion duration}>30min).
\]

控制器使用概率而不是单个硬估计：

\[
P(S>S_{open})>0.9
\]

再开启。

这样可以直接解释视频漏检/测速噪声对最终决策的影响。

---

# 12. 最小可行比赛实现

如果只有 3 天比赛，不必一开始就做完整 CTM。

```text
Day 1
YOLO/tracker → manual calibration → q/v/rho
↓
conservation N(t), S(t)

Day 2
rolling validation → 10-min forecast
↓
persistence vs RF/GBDT
↓
state-machine controller

Day 3
capacity sensitivity replay
↓
sensor placement greedy
↓
plots + evaluator + result consistency
```

这比同时上 YOLO、ARIMA、AHP、聚类、AdaBoost、模糊逻辑更稳。

---

# 13. 核心迁移模板

\[
\boxed{
Observation
\rightarrow Calibration
\rightarrow State
\rightarrow Forecast
\rightarrow Action
\rightarrow Counterfactual
\rightarrow Sensor\ Design
}
\]

只要题目存在“传感器数据最后要支持决策”，优先按这条链建模。
