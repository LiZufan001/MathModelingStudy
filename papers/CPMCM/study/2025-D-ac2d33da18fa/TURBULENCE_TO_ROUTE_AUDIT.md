# TURBULENCE_TO_ROUTE_AUDIT｜湍流监测到航路规划专项审计

这份文件专门检查候选论文中最容易被三维图和算法名掩盖的问题：

> **量纲、尺度、有效分辨率、验证独立性、风险传播和“最优”口径。**

---

# 1. 量纲账本

| 量 | 典型符号 | 单位 | 审计重点 |
|---|---|---:|---|
| 位温 | `θ` | K | 与温度/气压单位一致 |
| 理查逊数 | `Ri` | 1 | 分母弱切变时需正则化 |
| TKE | `k` | m²/s² | 平均窗口决定脉动定义 |
| 耗散率 | `ε` | m²/s³ | 结构函数尺度需位于适用区间 |
| `ε^(1/3)` | - | m^(2/3)/s | **不是传统无量纲 TI** |
| 传统 turbulence intensity | `TI=σ_U/Ū` | 1 | 需参考平均风速 |
| 路径长度 | `L` | m | 与风险项相加前需归一化/配单位 |

## 红线 1

若写：

\[
TI=\varepsilon^{1/3},
\]

必须明确它是**风险代理量**而不是传统 turbulence intensity。

## 红线 2

若路径代价写：

\[
J=\sum(d_i+\alpha k_i^\beta),
\]

则 `α` 有单位；若论文把 `α` 当纯无量纲调参常数，应先归一化。

---

# 2. TKE 的“脉动”到底相对谁

\[
u'=u-\bar u.
\]

关键不是公式，而是：

> `ū` 怎么算？

必须写清：

- averaging window；
- 是否滑动；
- 是否分高度层；
- 是否去趋势；
- 是否在 stationary window 内计算。

不同窗口得到的是不同尺度的 fluctuation。

例如几小时 NWP 风场相对时间均值的波动，可能主要是天气场变化，不是秒级/分钟级 turbulence。

---

# 3. Ri 数值稳定性

\[
Ri=\frac{N^2}{S^2}
\]

其中：

\[
S^2=(\partial_zu)^2+(\partial_zv)^2.
\]

当：

\[
S^2\rightarrow0,
\]

`Ri` 会爆大。

比赛实现至少应：

```text
finite difference QC
minimum shear floor
height-edge handling
outlier clipping / robust transform
sensitivity check
```

否则极端 `Ri` 可能只是数值微分噪声。

---

# 4. Teacher-label leakage 审计

Q1 b 模型的 label 来自 a。

因此要同时检查两类 leakage。

## 4.1 明显数据泄漏

同一时间/高度点的衍生量不能一部分当 feature、一部分通过 teacher 又回到 label 中而未声明。

## 4.2 时空相关泄漏

随机点切分会让：

```text
邻近时间
邻近高度
同一站点
```

同时出现在 train/test。

比赛 checklist：

- [ ] 是否按整段时间切？
- [ ] 是否留站点？
- [ ] scaler / imputer 是否只 fit train？
- [ ] bootstrap 是否在 split 后做？
- [ ] teacher 参数是否用到 test period？

---

# 5. 多源同化的对象一致性

不能简单说：

```text
地面站
+ 风廓线
+ 雷达
= 三维湍流场
```

要逐个写 observation operator：

\[
y_s=H_sx+\epsilon_s.
\]

例如：

- 地面站：近地层点位风/温度；
- 风廓线：垂直剖面风场/谱宽；
- 多普勒雷达：沿波束径向速度；
- NWP：网格解析/参数化状态。

它们不是同一种量，必须先转换或在观测算子里表达差异。

---

# 6. 固定 X/S `0.6/0.4` 权重审计

固定权重只在以下情况比较容易辩护：

1. 有独立验证集搜索过；
2. 全研究区质量基本稳定；
3. 结果对权重不敏感。

否则至少做：

\[
w_X\in[0,1],\qquad w_S=1-w_X
\]

的 sensitivity curve。

更好：

\[
w_s(\mathbf r,t)\propto1/\sigma_s^2(\mathbf r,t).
\]

---

# 7. OI / 3DVAR 的 `B` 和 `R` 才是模型核心

公式：

\[
x_a=x_b+BH^T(HBH^T+R)^{-1}(y-Hx_b)
\]

看起来标准，但真正决定结果的是：

- `B` 的水平相关尺度；
- `B` 的垂直相关尺度；
- 背景方差；
- `R` 的各设备误差；
- 代表性误差；
- 不同设备是否相关。

所以论文若给几十页图，却没给这些参数的：

```text
来源
估计方法
敏感性
```

可信度仍然不够。

---

# 8. 伪分辨率审计

设原始数据分辨率：

\[
\Delta x_{native}=1\text{ km}
\]

插值后：

\[
\Delta x_{grid}=100\text{ m}.
\]

不能写：

> 分辨率提高到 100 m。

只能写：

> 在 100 m analysis grid 上重采样 / 同化输出。

需要配套：

\[
L_{eff}(\mathbf r)
\]

或 posterior variance 来告诉读者哪些 100 m 像素其实高度相关。

---

# 9. 结构函数 → ε 审计

\[
D_{LL}(s)=C_2(\varepsilon s)^{2/3}
\]

适用条件涉及：

- inertial subrange；
- 局地均匀；
- 局地各向同性近似。

低空城市边界层：

- 建筑尾流；
- 地形；
- 地表热力；

可能明显破坏这些条件。

比赛中至少做：

1. 多个 separation scale `s`；
2. log-log slope 检查；
3. `C2` sensitivity；
4. 城市/河流分区比较；
5. out-of-domain flag。

---

# 10. “两个指标空间格局一致”不是交叉验证

如果 TKE 和 ε proxy 都来自相同风场/插值场，它们并非独立证据。

这类验证最多叫：

\[
internal\ consistency.
\]

真正独立的验证应是：

```text
留出一个站/设备
→ 不参与融合
→ 用融合场回预测它
```

或者额外独立资料。

---

# 11. NWP 100 m 重采样审计

对模式变量做 `RegularGridInterpolator` 是数值重采样，不是动力降尺度。

因此：

\[
\text{interpolated fine grid}
\neq
\text{fine-scale forecast skill}.
\]

如果需要真实百米级：

- nested WRF / LES；
- statistical downscaling；
- observation-conditioned super-resolution；
- terrain/building correction；

至少要有一种真实增加信息的机制。

---

# 12. NWP 的 TKE 口径

若用：

\[
\frac12[(u-\bar u)^2+(v-\bar v)^2+(w-\bar w)^2]
\]

从少量预报时次直接计算，得到的是“resolved temporal variability”的某种量。

不能自动等价于真实小尺度湍流 TKE。

优先检查 NWP 文件是否已有：

- TKE；
- PBL scheme diagnostics；
- Richardson number；
- vertical velocity variance；
- turbulent diffusion coefficients。

若没有，应该称：

> NWP turbulence diagnostic index

而不是物理真值 TKE。

---

# 13. LSTM 验证审计

候选报告：

- WPR LSTM `R²≈0.27–0.28`；
- S-band route `R²≈0.77`。

必须补：

## horizon-wise metrics

\[
RMSE(h),\quad h=1,2,...
\]

因为一步预测很好不代表 1 h 递推稳定。

## rolling origin

```text
train past
validate later
never shuffle future back into train
```

## persistence baseline

大气短临必须比较：

\[
\hat x_{t+h}=x_t.
\]

如果 LSTM 连 persistence 都赢不了，就不应上航路层。

---

# 14. k-means 降网格审计

普通 k-means 优化的是簇内平方距离：

\[
\sum_i\|x_i-\mu_{c(i)}\|^2.
\]

它不关心：

> 最危险的 1% 湍流格点有没有保住。

所以路径规划场降采样应加入：

```text
high-risk mandatory cells
high-gradient cells
sensor vicinity
route corridor
```

甚至直接以 expected routing regret 作为压缩指标。

---

# 15. R² 加权融合审计

若：

\[
w_i=R_i^2/\sum_jR_j^2,
\]

问题包括：

- `R²` 不是 precision；
- 可为负；
- 对分布改变敏感；
- 两模型误差可能相关。

最少用 validation residual variance：

\[
w_i\propto1/RMSE_i^2.
\]

更高级：

- stacking；
- Bayesian model averaging；
- quantile regression ensemble。

---

# 16. 航路 cost 量纲审计

原始式类似：

\[
J=\sum_i(d_i+\alpha k_i^\beta).
\]

推荐先变成：

\[
J=
\lambda_L L^*
+
\lambda_R R^*
+
\lambda_M M^*.
\]

全部无量纲：

\[
L^*=L/L_0.
\]

风险不建议只取均值：

\[
R^*=CVaR_{0.95}(\text{path risk}).
\]

---

# 17. A* optimality audit

真正证明离散图最优需要：

- 非负 edge cost；
- admissible heuristic；
- 状态/动作定义完整。

10 条随机路线都更差只是辅助证据。

还需要检查：

- 是否同起终点；
- 是否同样满足 TKE 上限；
- 是否同样满足高度/速度；
- 随机样条是否有非法穿越；
- cost evaluator 是否完全一致。

---

# 18. 飞行器动力学审计

只有：

```text
speed=30 m/s
forward movement
```

不足以表示大型飞行器机动限制。

至少加入：

\[
|\dot z|\le V_{z,max},
\]

\[
|\dot\psi|\le\omega_{max},
\]

\[
R_{turn}\ge R_{min}.
\]

更进一步加入 acceleration / energy。

---

# 19. ACO reproducibility audit

ACO 是随机算法。

一条最好路径不够。

至少：

```text
30 independent seeds
mean cost
std cost
best/worst
convergence generation
success rate
```

并与 deterministic A* / Dijkstra 同图比较。

---

# 20. 从场误差传播到路径误差

这是整篇最应该补、也最有价值的一项。

对每个 ensemble turbulence field：

\[
x^{(m)}(\mathbf r,t)
\]

分别求路径：

\[
\pi^{(m)}.
\]

然后统计：

- route overlap；
- path length CI；
- maximum-risk CI；
- route corridor width；
- endpoint arrival-time CI。

如果小小的场扰动就让路径完全换道：

> 决策不稳健。

这比单纯展示 3D 航线图更有说服力。

---

# 21. 比赛提交前的 12 个硬检查

- [ ] teacher 是否明确叫 reference/pseudo-label？
- [ ] 时序是否 blocked split？
- [ ] 是否 leave-one-site/sensor-out？
- [ ] TKE averaging window 是否固定？
- [ ] Ri 分母是否做弱切变保护？
- [ ] `TI/ε/TKE` 单位是否统一？
- [ ] analysis grid 和 effective resolution 是否区分？
- [ ] OI 的 `B/R` 是否有来源和敏感性？
- [ ] NWP 插值有没有被误写成超分辨率？
- [ ] 路径 cost 是否无量纲/单位一致？
- [ ] A*/ACO 是否使用同一 evaluator 做基线？
- [ ] 场 uncertainty 是否传播到 route uncertainty？

如果这 12 项全部过，论文可信度会比“多堆三个算法”提升得更明显。