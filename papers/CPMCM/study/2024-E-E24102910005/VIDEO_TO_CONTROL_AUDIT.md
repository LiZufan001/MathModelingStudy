# E24102910005｜视频测量—预测—控制专项审计

> 目的：检查从视频像素到应急车道决策的每一层是否有明确的**单位、标定、验证对象和误差边界**。

---

# 1. 全链条审计框架

```text
video
 ↓
vehicle detection / tracking
 ↓
count / pixel trajectory
 ↓ calibration
q, u, rho
 ↓
traffic state / congestion wave
 ↓
10-min forecast
 ↓
K(t) state
 ↓
OPEN/CLOSE
 ↓
counterfactual benefit
```

任何上游误差都会进入下游。因此不能只报告最后一个 `R²` 或 48.3%。

---

# 2. Measurement layer

## 2.1 Density

论文：

\[
\rho=\frac{\text{mean current-frame vehicle count}}{50m}.
\]

风险：50 m 是假设，不是由道路标线/相机参数标定得到。

如果真实有效视场长度为 `L+ΔL`，则：

\[
\hat\rho=\frac{N}{L},\qquad
\rho=\frac{N}{L+\Delta L},
\]

相对误差直接由长度误差传递。

建议：homography + known road markers / lane width / camera pose。

## 2.2 Speed

目标跟踪得到的是图像坐标：

\[
(x_p(t),y_p(t)).
\]

真实速度要求：

\[
(x_p,y_p)\rightarrow (X,Y)_{road}\rightarrow v.
\]

若没有透视标定，直接拿 pixel displacement × constant scale 在不同纵深不成立。

## 2.3 Detection benchmark

应人工标注一小段：

```text
vehicle detection: precision / recall / mAP
tracking: ID switch / IDF1
line count: MAE / MAPE
speed: MAE km/h
```

拥堵场景需要单独统计，因为遮挡最大。

---

# 3. 单位账本

全文应固定：

```text
q   veh/h
u   km/h
rho veh/km
N   veh
L   km
t   h or min, but integral must convert consistently
```

然后：

\[
q=u\rho
\]

才维度闭合。

论文同时出现：

```text
q: veh/min and veh/h
rho: veh/m and veh/km
```

虽然部分数值可换算，但正式实现必须由变量名/单位系统强制转换。

建议代码：

```python
flow_vph
speed_kph
density_vpkm
segment_length_km
```

禁止用含糊的 `q`, `speed`, `rho` 在跨模块接口中传递。

---

# 4. Shock-wave algebra audit

论文式 (32)：

\[
t_d=\frac{\rho_m}{\rho_m-\rho_0}\tau.
\]

正确整理：

\[
\boxed{\tau=\frac{\rho_m-\rho_0}{\rho_m}t_d}.
\]

论文式 (33)：

\[
\tau=\frac{\rho_m-\rho_0}{\rho_0}t_d.
\]

两者不等价。

### D 点手算

```text
rho0 = 165 veh/km
rhom = 350 veh/km
td   = 30 min
```

正确代数：

\[
\tau=\frac{185}{350}\times30=15.86\text{ min}.
\]

论文式 (33)：

\[
\tau=\frac{185}{165}\times30=33.64\text{ min}.
\]

论文表 10：

```text
25 min
```

三者不一致。

### C 点

```text
rho0=230
rhom=350
td=30
```

正确：

\[
10.29\text{ min}.
\]

论文式 (33)：

\[
15.65\text{ min}.
\]

表 10：

```text
38 min
```

因此 Q1 的预警验证**无法从正文公式复现**。

正式比赛必须：

```python
assert abs(table_value - evaluator(input_row)) < tol
```

---

# 5. Published regression equation sanity check

论文：

\[
\rho_D=198.7+60.1\rho_A-44.7\rho_B+89.4\rho_C+\epsilon.
\]

表 7 的输入约为：

```text
rhoA ~ 100–300
rhoB ~ 100–300
rhoC ~ 100–300 veh/km
```

仅以 `A=192.4, B=226.3, C=227` 代入，右侧就会达到约：

\[
2.2\times10^4\text{ veh/km},
\]

而真实 D 约数百 veh/km。

所以：

> 公开的式 (39) 不可能按字面生成正文预测结果。

可能原因包括标准化系数漏写、系数小数点/版本错误等，但没有原附件代码，不能猜具体正确式。

---

# 6. Time-series validation audit

论文 D 点共有：

\[
134\text{ one-minute samples}.
\]

分成：

```text
94 train
40 test
```

但没有明确 chronological split。

## 6.1 禁止普通 random split

相邻分钟高度相关：

\[
\rho(t)\approx\rho(t+1).
\]

随机划分会让几乎相邻的时刻分别落入 train/test。

推荐：

```text
rolling origin
blocked holdout
leave-congestion-event-out
leave-day-out
```

## 6.2 必须有 naive baseline

10 min ahead 最少比较：

\[
\hat\rho_D(t+10)=\rho_D(t)
\]

以及：

```text
D own lags
A/B/C only
A/B/C + D lags
physical travel-time model
AdaBoost
```

如果 AdaBoost 没明显超过 persistence，就不能因为 `R²=0.968` 直接称“强预测”。

## 6.3 Lag 必须来自数据/机理

题目说“例如提前十分钟”不等于真实传播滞后就是 10 min。

推荐：

- cross-correlation；
- estimated travel time `distance / speed`；
- shock-wave speed；
- distributed lag model。

---

# 7. `K(t)` semantic audit

论文：

\[
K_{ij}(t)=\frac{Q_{0,ij}+\int(q_i-q_j)dt}{Q_{m,ij}}.
\]

这是守恒意义上的：

\[
\frac{N_{ij}(t)}{N^{max}_{ij}},
\]

最准确应叫：

```text
normalized accumulation
normalized storage ratio
```

而不是传统 detector occupancy。

这个状态本身非常值得保留。

### 建议离散化

\[
N_{k+1}=\operatorname{clip}
\left(N_k+(q_{in,k}-q_{out,k})\Delta t,0,N_{max}\right).
\]

然后：

\[
S_k=N_k/N_{max}.
\]

这样更适合实时控制。

---

# 8. Threshold and calibration audit

论文使用：

```text
open  if K > 0.8
close if K < 0.6
```

这是很好的 hysteresis。

但 0.8 也被用于 `Qm` 的反推：

```text
13:29 K=1
14:10 K=0.8
→ infer Qm=1193
```

随后又用 K=0.8 判拥堵/开启，存在 partially circular calibration。

推荐：

```text
calibration days → estimate Nmax
validation days  → choose thresholds
holdout days     → final evaluation
```

---

# 9. Counterfactual audit

论文 Q3：

\[
q_D'(t)=1.3q_D(t).
\]

因此 48.3% 是：

\[
\text{assumed 30% capacity gain}
\Rightarrow
\text{simulated 48.3% congestion-duration reduction}.
\]

它不是实测 causal effect。

## 推荐敏感性表

| capacity gain | congestion duration | reduction | max storage |
|---:|---:|---:|---:|
| 10% | ... | ... | ... |
| 20% | ... | ... | ... |
| 30% | ... | ... | ... |
| 40% | ... | ... | ... |
| 50% | ... | ... | ... |

并加入：

- merge friction；
- downstream bottleneck；
- lane-changing capacity drop；
- compliance rate。

最好使用 CTM / LWR 作为 counterfactual simulator。

---

# 10. Decision-state-machine audit

建议不是简单：

```text
if K>0.8: open
```

而是：

```text
CLOSED
  ↓ warning probability high
PREPARE
  ↓ sustained + downstream spare capacity + safety clear
OPEN
  ↓ K<low threshold for dwell time
CLEARING
  ↓ lane empty
CLOSED
```

hard override：

```text
incident → CLEAR / emergency-only
emergency vehicle request → CLEAR
sensor failure → fail-safe
spillback downstream → do not open
```

---

# 11. Sensor placement audit

论文提出：

```text
move B → E
optional F in CD
```

思路是合理的：补下游状态与应急车道利用率。

但“信息冗余”应定量证明。

可定义：

\[
VOI(S)=L_{base}-L_{with\ S},
\]

其中损失：

\[
L=c_1\cdot false\ open+c_2\cdot missed\ congestion+c_3\cdot delay+c_4\cdot safety\ risk.
\]

再求：

\[
\max_S VOI(S)-\lambda Cost(S).
\]

这会把 Q4 从“布点建议”升级为真正的 sensor placement optimization。

---

# 12. 比赛前检查清单

```text
[ ] detection/tracking 有人工 benchmark
[ ] pixel→meter 有明确 calibration
[ ] q/u/rho 单位统一
[ ] conservation state 可手算复现
[ ] 公式推导后用一行数据单测
[ ] time split 不随机泄漏
[ ] forecast 有 persistence baseline
[ ] lag 来自传播机理/数据
[ ] open/close 使用 hysteresis
[ ] safety 是 hard constraint
[ ] counterfactual assumptions 明写
[ ] policy effect 做 sensitivity
[ ] sensor placement 用最终控制 utility 评价
[ ] 摘要数字来自同一机器结果源
```

---

# 13. 一句话

> **从视频到控制的长链模型，最大的风险不是最后一个算法不够高级，而是前面的测量误差、单位或验证泄漏一路被放大，最后却被一个漂亮的控制曲线掩盖。**
