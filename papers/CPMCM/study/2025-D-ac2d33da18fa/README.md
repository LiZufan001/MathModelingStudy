# 2025 D 证据级深读：低空湍流监测及最优航路规划研究

> 候选证据 ID：`graduate:paper:2025-D:ac2d33da18fa`  
> 候选 PDF：60 页，SHA256 `ac2d33da18fa8fd500452655e0b6b92a82623fab99f303070157e812696b8217`  
> 强候选目标队：辽宁工程技术大学 石彤彤 / 赵其伟 / 安雪菱，国一编号 `D25101470116`  
> **状态：证据级深读，尚未看到候选 PDF 封面，因此不能标为目标队 exact-match 全文。**

来源边界见 [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md)。

---

# 0. 指导老师先给结论

这篇候选最值得学习的不是某一个“高级模型”，而是一套很清楚的**基准递进架构**：

```text
Q1
双设备物理基准 a
      ↓ teacher / pseudo-label
单设备数据模型 b

Q2
异构观测
      ↓ VAD / interpolation / OI
三维融合场 c

Q3
c 作为验证参照
      ↓
NWP 诊断场 d  ──→ A* 航路
观测短临场 e ──→ ACO 航路
```

这类设计非常适合“没有绝对真值、但有多个信息层级”的比赛题：

> **先构造一个信息更完整的 reference，再研究受限信息场景能逼近到什么程度。**

全文审读记录里最值得模仿的有五点：

1. **每一问都有内部参照系。** `a→b`、`c→d`，不是算法跑完只看图好不好看。
2. **负结果不藏。** 风廓线 LSTM 只有 `R²≈0.27–0.28`，正文明确判定“不可靠”，随后转向 S 波段雷达；失败实验真正推动了模型选择。
3. **三维场不是直接“插出来”。** 候选至少尝试 VAD、背景场、最优插值 OI、协方差和观测误差矩阵，再由结构函数推湍流量。
4. **优化问题真的给了基线。** A* 与直线和 10 条随机/样条路径比较，而不是只展示一条漂亮 3D 曲线。
5. 摘要和正文把 `a–e` 五个模型预先注册，前后接口比较清楚。

但是严格审计后，这篇也有一条非常典型的风险链：

```text
“基准”本身不是绝对真值
       ↓
时空随机切分可能过于乐观
       ↓
插值网格被误当成真实分辨率
       ↓
湍流代理量量纲 / 物理含义不完全统一
       ↓
NWP 被超分辨插值到 100 m
       ↓
路径代价混合距离和 TKE
       ↓
最后的“最优航路”显得比上游证据更确定
```

因此我们真正应该带走的原则是：

> **监测—预报—决策链越长，越需要把每一级的“不确定性、有效分辨率、验证边界”一起往后传，而不是只传一个场值。**

---

# 1. Q1：`a → b` 的 teacher–student 思路

全文审读记录给出 Q1 页码约 p.5–15。

## 1.1 模型 a：双资料物理基准

输入：

- 风廓线雷达；
- 微波辐射计；
- a/b 两站数据。

主要步骤：

```text
时间差 Δt + 高度差 Δh 匹配
        ↓
按高度双向插值并表
        ↓
位温 θ
        ↓
稳定度 / 风切变 → Ri
        ↓
速度脉动 → TKE
        ↓
模型 a 基准剖面
```

位温采用常见形式：

\[
\theta=T\left(\frac{P_0}{P}\right)^{0.286}.
\]

梯度理查逊数的典型形式为：

\[
Ri=
\frac{\frac{g}{\theta}\frac{\partial\theta}{\partial z}}
{\left(\frac{\partial u}{\partial z}\right)^2+
 \left(\frac{\partial v}{\partial z}\right)^2}.
\]

TKE：

\[
k=\frac12\left(u'^2+v'^2+w'^2\right).
\]

论文把更完整信息的模型 a 当成后续单设备模型 b 的监督参照。

### 这个设计值得学什么

它把一个很现实的问题转成了：

\[
\boxed{\text{rich-sensor teacher}\rightarrow\text{cheap-sensor student}}
\]

类似结构可迁移到：

- 多传感器设备 → 单传感器部署；
- 高成本实验 → 低成本代理；
- 高精度仿真 → 快速 surrogate；
- 全特征模型 → 缺特征模型。

## 1.2 模型 b：只用风廓线雷达

记录中的 b 路线：

```text
站点分层
+ 70/30 train-test split
+ 按 TKE 区间 Bootstrap
        ↓
Random Forest（正文 100 trees）
        ↓
以 a 输出为基准评估
        ↓
XGBoost 重训优化
```

报告指标：

\[
R^2: 0.4977\rightarrow0.5621,
\]

\[
MSE: 0.0425\rightarrow0.0370.
\]

并展示：

- RF / XGBoost 残差分布；
- 分站点残差箱线图；
- 优化前后成对比较。

这比“XGBoost 比 RF 高几个点”更完整，因为它至少看了 residual shape 和 site difference。

---

# 2. Q1 最重要的审计：teacher 不是 truth

论文的叙事是：

> 模型 a 信息更全，因此拿 a 作为模型 b 的“基准真值”。

比赛里这种做法完全可以用，但措辞必须准确。

更严格应写：

\[
\boxed{y^*=\text{reference / pseudo-label}}
\]

而不是：

\[
\boxed{y^*=\text{physical ground truth}}.
\]

因为 a 本身也依赖：

- 测量误差；
- 时间/高度配准；
- 数值微分；
- 平均窗口；
- Ri / TKE 的代理假设。

所以 b 对 a 的高拟合只证明：

> **b 能逼近 a。**

不能自动证明：

> **b 准确恢复真实大气湍流。**

这是本篇第一条非常值得你们记住的评审边界。

---

# 3. Q1 第二个风险：随机 70/30 可能泄漏时空相关性

湍流廓线数据不是 iid 表格数据。

相邻：

- 时间；
- 高度层；
- 同站点；

通常高度相关。

如果把所有点打散再做 70/30：

```text
10:00, 500m → train
10:06, 500m → test
10:00, 550m → test
```

那么测试集和训练集可能近乎是邻居。

这会令：

\[
R^2_{random\ split}
>
R^2_{real\ deployment}.
\]

更严谨的验证应该至少包含：

1. **blocked-time split**：整段时间留出；
2. **leave-one-site-out**：整个站点留出；
3. **rolling-origin forecast split**；
4. 强湍流极端事件单独留出。

这比继续调 XGBoost 深度更重要。

---

# 4. Q2：异构传感器 → 三维融合场

记录中的 Q2 为 p.15–23，目标网格：

- 水平约 100 m；
- 垂直约 50 m；
- 覆盖地面站矩形区域；
- 输出三维湍流强度 / 耗散率场。

主链：

```text
-9999 → NaN / QC
      ↓
Doppler radial velocity
      ↓ VAD least squares
u, v horizontal wind
      ↓
100×100 horizontal grid
      ↓
X-band / S-band weighted background
      ↓
Optimal Interpolation (OI)
+ ground-station IDW
+ wind-profiler 3D spline
      ↓
3D fused wind field
      ↓
2nd-order structure function
      ↓
ε field + TKE / turbulence proxy
```

## 4.1 VAD

径向速度满足类似：

\[
V_r=u\cos\theta+v\sin\theta,
\]

多方位观测后用最小二乘反演水平风分量。

## 4.2 OI

论文记录中的更新形式：

\[
x_a=x_b+K(y-Hx_b),
\]

\[
K=BH^T(HBH^T+R)^{-1}.
\]

其中：

- `B`：背景误差协方差，高斯相关模型；
- `R`：观测误差协方差，取对角；
- 记录参数包括风廓线约 `σ=0.3`、地面站约 `σ=0.8 m/s`。

这种写法的优点是：

> 插值结果不再只是“离谁近听谁的”，而是显式表达背景场与观测的不确定性。

---

# 5. Q2 最值得追问的三个问题

## 5.1 `100 m grid` 不等于 `100 m information resolution`

把一个公里级/百米级探测资料插值到：

\[
\Delta x=100\text{ m}
\]

只说明：

> 输出数组每 100 m 有一个格点。

不说明：

> 每 100 m 都有独立观测信息。

因此应区分：

\[
\boxed{grid\ spacing}
\neq
\boxed{effective\ resolution}.
\]

如果不区分，最终 3D 图会产生“看起来非常精细”的伪确定感。

更好的论文应同时画：

- analysis field；
- observation density；
- distance-to-observation；
- posterior / kriging variance；
- effective-resolution map。

## 5.2 X/S 固定 `0.6/0.4` 为什么？

固定权重相当于：

\[
x_b=0.6x_X+0.4x_S.
\]

但雷达可信度实际上会随：

- 距离；
- SNR；
- 波束高度；
- 地物遮挡；
- 弱回波；
- 分辨率；

变化。

所以比固定权重更自然的是：

\[
w_s(\mathbf r,t)\propto\frac1{\sigma_s^2(\mathbf r,t)}.
\]

即**空间时变 uncertainty weight**。

## 5.3 `TI = ε^(1/3)` 的量纲

耗散率：

\[
[\varepsilon]=\mathrm{m^2/s^3}.
\]

因此：

\[
[\varepsilon^{1/3}]
=\mathrm{m^{2/3}/s}.
\]

它不是传统意义无量纲的 turbulence intensity：

\[
TI_{classic}=\frac{\sigma_u}{\bar U}.
\]

所以如果论文把：

\[
\varepsilon^{1/3}
\]

直接叫“湍流强度 TI”，应至少说明：

> 这是 **turbulence proxy / index**，不是传统无量纲 TI。

否则不同章节中的 `TKE / ε / TI` 很容易产生物理口径混淆。

---

# 6. Q2 验证：空间格局一致 ≠ 独立准确

候选记录显示：

- TKE 与另一湍流指标空间格局互相印证；
- 河流区与城市区有不同强度；
- 750–1250 m 出现较强层；
- 1500 m 以上衰减；
- 正文还主动承认 TKE 个别极大值存在计算缺陷。

这些属于：

\[
\boxed{physical\ plausibility / internal\ consistency}
\]

而不是：

\[
\boxed{independent\ validation}.
\]

更强方案应做：

```text
leave one sensor / station out
       ↓
用剩余资料融合
       ↓
回预测被留出的真实观测
       ↓
RMSE / MAE / rank correlation / event skill
```

也就是 **withheld-sensor validation**。

---

# 7. Q3 模型 d：NWP → 湍流场 → A*

记录中的模型 d：

```text
WRF nc
(Ua, Va, Wa, Z)
       ↓
RegularGridInterpolator
       ↓
100m × 100m × 50m grid
       ↓
time-mean fluctuation TKE
       ↓
3D cost field
       ↓
A*
       ↓
optimal route
```

TKE：

\[
k=\frac12(u'^2+v'^2+w'^2).
\]

路径代价记录为类似：

\[
J(\pi)=\sum_i
\left[d_i+\alpha\,k_i^\beta\right].
\]

约束包括：

- 区域边界；
- 高度范围；
- `TKE≤TKE_max`；
- 速度约 `30 m/s`；
- 总时间不超过约 3 h。

验证中：

- A* 代价约 `1.14×10^7`；
- 直线约 `4.2×10^8`；
- 10 条随机/样条对照约 `4.2×10^8 ~ 1.14×10^9`。

这个对照至少说明候选没有只画一条路线。

---

# 8. Q3 最大的物理风险：NWP 插值不产生真实小尺度湍流

如果原始 NWP 水平分辨率远粗于 100 m，那么：

```text
coarse NWP
   ↓ interpolation
100 m grid
```

并不会创造新的物理信息。

因此：

\[
\boxed{100m\ interpolated\ field}
\neq
\boxed{100m\ turbulence\ forecast}.
\]

更严重的是：

用几个预报时次的 resolved wind 相对时间均值：

\[
u'=u-\bar u
\]

得到的方差包含：

- 天气尺度变化；
- 中尺度变化；
- 数值模式演变；

并不自动等价于：

- 飞行器实际感受到的湍流脉动；
- 模式未解析的 sub-grid turbulence。

所以 d 模型必须回答：

> **你的 TKE 是 resolved variability、parameterized TKE，还是经验 turbulence diagnostic？**

三者不能混写。

---

# 9. 路径代价的量纲和 Pareto 问题

如果：

\[
J=\sum(d_i+\alpha k_i^\beta),
\]

则：

\[
[d_i]=m,
\]

\[
[k_i]=m^2/s^2.
\]

所以 `α` 必须承担相应单位，或者先把两项无量纲化。

比赛里更推荐：

\[
J=
\lambda_L\frac{L}{L_0}
+
\lambda_R\frac{R}{R_0}
+
\lambda_M\frac{M}{M_0}.
\]

其中：

- `L`：路程；
- `R`：湍流风险；
- `M`：机动成本。

然后画：

\[
\boxed{length-risk\ Pareto\ frontier}
\]

而不是只给一组 `α,β`。

记录还指出正文参数块里 `α=200, β=1.5` 存在疑似排版位置问题。比赛里这种问题必须通过**参数表 + 代码常量自动导出**避免。

---

# 10. A* 的“最优”到底是什么意思

如果满足：

1. 图上所有 edge cost 非负；
2. heuristic admissible；
3. 最好 consistent；
4. 状态空间和邻接动作完整表达允许机动；

那么 A* 可以得到：

\[
\boxed{该离散图上的全局最短路}.
\]

这比“我随机生成 10 条都没它好”强得多。

反过来：

随机路径比较只能说明：

> A* 比这 10 个样本好。

不能证明：

> 连续三维真实空域上的全局最优。

因此论文应把“最优”的作用域写清楚：

```text
optimal on the discretized time-space graph
under the declared motion/cost model
```

而不是无限外推。

---

# 11. Q3 模型 e：失败的风廓线 LSTM → S 波段 + LSTM

这部分反而很值得学。

候选先尝试风廓线：

\[
R^2\approx0.27,
\]

调参后：

\[
R^2\approx0.28.
\]

正文直接判定不可靠。

然后改成：

```text
S-band 02–05 observations
       ↓
3D RBF interpolation
       ↓
10×10×5 coarse grid
       ↓
k-means representative points
       ↓
LSTM
(time_steps=3, hidden=64, 2 layers,
dropout=0.2, Adam≈1e-3, early stop)
       ↓
R²≈0.77
```

再将风廓线与 S 波段预测：

\[
\text{按 }R^2\text{ 归一化加权融合},
\]

最后用三维蚁群算法规划路径。

这类“失败路线公开→换数据源”的叙事很好。

---

# 12. 但 e 仍有三个需要补的实验

## 12.1 `R² weight` 不是最自然的融合权重

`R²`：

- 可能为负；
- 不直接等于误差方差；
- 不同数据分布下不可简单当 precision。

更合理：

\[
w_m\propto\frac1{\sigma_m^2}
\]

或者 stacking / Bayesian model averaging。

最关键必须做 ablation：

```text
S-band only
WPR only
fusion
```

如果 fusion 不比最强单模好，就不要为了“多源融合”而融合。

## 12.2 k-means 降采样可能抹掉最危险极值

路径规划真正关心的往往不是平均场，而是：

\[
\max TKE
\]

和高分位尾部。

`k-means` 代表点天然偏向密度中心，可能把稀有强湍流小斑块吞掉。

因此降采样需要：

- extreme-preserving sampling；
- adaptive mesh refinement；
- 高梯度区加密；
- top-q risk cells 强制保留。

## 12.3 ACO 航路缺同尺度基线

记录中模型 e 最后的蚁群路径没有像 d 那样给：

- 直线；
- Dijkstra；
- A*；
- 随机路径；

的统一代价表。

而 ACO 是随机算法，还应：

- 多随机种子；
- 报均值/标准差；
- 收敛曲线；
- 与确定性图搜索对比。

否则“找到一条可行路径”和“优化有效”是两回事。

---

# 13. 本篇真正可迁移的五条经验

## 经验 1：没有真值时先造 reference hierarchy

```text
best-available reference
→ reduced-information model
→ compare
```

但必须叫 reference / pseudo-label，不要偷换为 absolute truth。

## 经验 2：多源融合先统一“对象”，再统一“网格”

不是把各种设备全部插值后平均。

应先写：

\[
y_s=H_sx+\epsilon_s.
\]

明确每个传感器到底观测 `x` 的什么投影。

## 经验 3：输出网格必须附 effective resolution

画得细不代表知道得细。

## 经验 4：预报模型的 validation split 必须模拟未来

不能随机切时序点。

## 经验 5：决策模型不能比上游场更“自信”

上游如果只是 proxy + interpolation，终点就不应该只交一条确定航线。

更合理是：

- expected-optimal route；
- robust route；
- worst-case / CVaR route；
- route uncertainty band。

---

# 14. 对我们队最有用的升级路线

我会把这篇候选重构成：

```text
Observation + QC
       ↓
Sensor-specific observation operators
       ↓
Probabilistic turbulence state
(mean + uncertainty + effective resolution)
       ↓
Rolling-origin calibrated forecast ensemble
       ↓
Time-expanded risk graph
       ↓
Chance-constrained / CVaR route planning
       ↓
Pareto frontier + robustness validation
```

这比单纯把：

`RF + XGBoost + OI + LSTM + A* + ACO`

算法名串起来更重要。

详细数学重构见：

- [`MODEL_RECONSTRUCTION.md`](MODEL_RECONSTRUCTION.md)
- [`TURBULENCE_TO_ROUTE_AUDIT.md`](TURBULENCE_TO_ROUTE_AUDIT.md)
- [`REVIEWER_REPORT.md`](REVIEWER_REPORT.md)
- [`COMPETITION_PLAYBOOK.md`](COMPETITION_PLAYBOOK.md)
