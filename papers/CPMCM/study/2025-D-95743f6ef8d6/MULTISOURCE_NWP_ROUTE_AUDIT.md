# MULTISOURCE_NWP_ROUTE_AUDIT｜多源融合、NWP 校正与航路风险专项审计

这份文件专门记录候选 `95743f6ef8d6` 中最值得赛前复用的审计规则。

---

# A. Q1：指标定义与评价必须先闭环

## A1. `[0,1]` 指标不可能得到 RMSE 5–8

若：

\[
y,\hat y\in[0,1],
\]

则：

\[
|y-\hat y|\le1,
\]

因此：

\[
RMSE\le1.
\]

候选同时报告归一化 Ia/Ib 与 5–8 量级 RMSE，必有未披露缩放/口径变化。

**赛场规则：**每个主指标旁边固定写：

```text
name
range
unit
normalization
inverse_transform
metric unit
```

## A2. `exp(-0.5 Ri)` 不天然归一化

当：

\[
Ri<0,
\]

有：

\[
\exp(-0.5Ri)>1.
\]

若最终指标必须在 `[0,1]`，需要：

- clipping；
- logistic mapping；
- min-max calibration；

之一，并写清楚。

## A3. `SW²` 是 proxy，不是自动等于 TKE

谱宽受 turbulence 之外的 broadening 影响。

正式论文应命名：

> spectral-width turbulence proxy

并通过：

- independent sensor；
- synthetic/known flow；
- downstream event skill；

至少一种方式校准。

---

# B. 训练/验证审计

## B1. 禁止 in-sample RF 指标当主结果

```text
fit train
predict train
report R²
```

只允许用于 sanity check。

主结果必须来自 held-out future/site/event。

## B2. 时空数据不能随机点切分

最少做：

```text
blocked time
leave-one-site-out
extreme-event holdout
```

如果要交叉验证，使用：

```text
time-blocked K-fold
```

而不是 shuffle K-fold。

---

# C. 多源融合审计

## C1. 统一 observation model

\[
y_s=H_sx+\epsilon_s.
\]

每个 source 都要写：

| source | observation | native resolution | error | operator |
|---|---|---|---|---|
| AWS | point met vars | point | σ_A | interpolation/operator |
| WPR | profile/radial velocity | vertical profile | σ_W | VAD |
| DWR | polar volume | radar gate | σ_D | polar→Cartesian |
| MWR | temperature profile | profile | σ_M | θ/Ri |

## C2. source weight 与 R 不要双重计权

若：

\[
w_s\propto1/\sigma_s^2,
\]

同时观测项又用：

\[
R_s^{-1},
\]

需说明二者分别编码什么，否则是 double counting。

## C3. 误差方差相加隐含独立性

候选：

\[
\sigma^2_{total}
=\sigma^2_{obs}+\sigma^2_{interp}+\sigma^2_{model}.
\]

真实情况：

\[
Var(X+Y+Z)
=\sum Var+2\sum Cov.
\]

如果无法估 cross-covariance，优先 ensemble/bootstrap。

---

# D. 分辨率审计

## D1. analysis grid ≠ effective resolution

100 m 网格只是：

\[
\Delta x_{array}=100m.
\]

不等于真实大气信息每 100 m 独立。

任何“高分辨率场”旁必须报告：

- native sensor resolution；
- interpolation scale；
- covariance length scale；
- posterior uncertainty；
- observation density。

## D2. NWP 500m/400m 与 100m/50m 口径并存

候选 Q3 一部分结果展示用约：

```text
500 m horizontal
400 m vertical
```

但目标网格表又是：

```text
100 m
50 m
```

正式比赛必须统一：

- compute grid；
- display grid；
- native NWP grid；
- effective resolution。

---

# E. NWP 校正审计

## E1. 校正是对的，但只能用过去校正未来

推荐：

```text
02:00-04:00 fit
04:00-04:30 tune
04:30-05:00 blind validate
05:00-08:00 forecast
```

滚动更新时每一步只用当时之前的数据。

## E2. 高度分层二次模型要防过拟合

\[
I^{cal}=a(z)+b(z)I+c(z)I^2.
\]

若每个高度层数据很少，系数可能剧烈抖动。

可改为：

\[
a(z),b(z),c(z)
\]

采用 spline / smoothness regularization，保证随高度平滑。

## E3. 平均误差之外要看 threshold skill

对于安全问题：

\[
I>I_{crit}
\]

才是真正关心事件。

报告：

- POD；
- FAR；
- CSI；
- lead time；
- reliability。

---

# F. 预测平滑审计

候选记录：

```text
observed ≈ 0.04-0.88
forecast ≈ 0.06-0.69
```

这很可能意味着 peak attenuation。

必须检查：

\[
E[\hat I-I\mid I>q_{0.9}].
\]

若显著为负，就存在危险事件系统性低估。

安全模型宁可：

- RMSE 稍高；
- extreme recall 更高；

也不要平均值漂亮却漏掉峰值。

---

# G. A* 最优性审计

## G1. 不能把“全局最优”写成假设

A* 最优性是需要证明的算法性质。

条件：

1. edge costs nonnegative；
2. heuristic admissible；
3. graph/state definition fixed。

## G2. 欧氏距离未必 admissible

若 edge cost：

\[
c=d(I^p+\alpha),
\]

而：

\[
I^p+\alpha<1,
\]

则：

\[
h=d_{euclid}
\]

可能高估真实剩余 cost。

安全写法：

\[
h=c_{min}d_{euclid},
\]

其中 `c_min` 是所有可行边单位距离 cost 的严格下界。

---

# H. 路径“更安全”必须有统一 evaluator

候选最大证据缺口之一是没有完整数值 baseline。

至少比较：

| route | length | mean risk | max risk | CVaR95 | exposure time | cost | feasible |
|---|---:|---:|---:|---:|---:|---:|---|
| straight | | | | | | | |
| shortest | | | | | | | |
| mean-risk A* | | | | | | | |
| robust/CVaR A* | | | | | | | |

没有这张表，就不要写：

> 暴露量降低 35%。

---

# I. 摘要数字必须回链正文

候选摘要的：

- 中度以上湍流识别准确率 `82%`；
- 湍流暴露量下降 `35%`；

全文审读未发现完整复现出处。

**赛场规则：**摘要任何数字必须能通过 `result_id` 自动回链正文表格/JSON。

推荐：

```text
results.json
→ paper tables
→ abstract numbers
```

不要人工抄。

---

# J. 公式落地审计

候选 Q3 后半段约 30 个公式涉及：

- ST-GCN；
- attention；
- ensemble；
- kernel interpolation；
- wavelet；
- EMD；
- spectrum。

但很多没有结果。

每个正式模型至少需要一项：

```text
parameter
output
ablation
metric
figure/table
```

五项全无 → 移到备选方案/附录，不进主模型。

---

# K. 代码复现审计

## K1. 禁止 synthetic fallback 静默运行

正式结果脚本：

```python
if not input_exists:
    raise RuntimeError("required contest data missing")
```

synthetic demo 必须独立：

```text
demo/
```

## K2. 雷达观测几何必须写对

径向速度：

\[
V_r
=u\cos\theta\cos\phi
+v\sin\theta\cos\phi
+w\sin\phi.
\]

必须解线性系统/最小二乘，不得常数比例分解。

---

# L. 赛前硬门槛

提交前逐项打勾：

- [ ] 所有主指标 range/unit 一致；
- [ ] proxy 不冒充 truth；
- [ ] train/test 按时间/站点隔离；
- [ ] source uncertainty 不重复计权；
- [ ] grid spacing 与 effective resolution 区分；
- [ ] NWP 只用过去标定未来；
- [ ] extreme event skill 单独报告；
- [ ] A* heuristic admissibility 已证明；
- [ ] route 有统一 baseline 表；
- [ ] 摘要每个数字可回链正文；
- [ ] 无结果公式已删除；
- [ ] synthetic demo 与正式代码隔离。

---

# 一句话

> **多源融合题真正的审计重点不是“你用了 3DVAR 还是 Kalman”，而是每一个数值到底是什么量、从哪里来、分辨率有多真、验证有没有偷看未来，以及最终路径所谓“更安全”能不能被同一个 evaluator 独立复算。**
