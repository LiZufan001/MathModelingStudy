# 2025 D 同题候选证据级深读：基于多源数据融合的低空湍流监测与航路优化

> evidence ID：`graduate:paper:2025-D:95743f6ef8d6`  
> 候选 PDF：110 页，SHA256 `95743f6ef8d686730d1229ab16f02d42a3698ee051b25870ca5e8f525fddb7b9`  
> **重要：这篇候选不能绑定为关昊岩/谢卓毅/杨骞队 `D25101470007`。** 目标队官方题名与候选题名不同，来源边界见 [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md)。

---

# 0. 指导老师先给结论

这篇候选最大的优点不是“算法很多”，而是它比上一篇 D 题候选更明确地把**不确定性、数据质量与风险规划**写进系统接口：

```text
Q1
双源物理综合指标 Ia
        ↓ reference
单源雷达指标 Ib
        ↓ 多回归器标定
optimized Ib

Q2
多源异构观测
        ↓ QC / 时空对齐 / 各向异性权重
变分融合 3D field
        ↓ Kalman / 半拉格朗日
forecast + confidence + uncertainty

Q3
NWP calibration d
观测外推 e
        ↓
A* + robust objective + chance constraint
        ↓
route / departure-window decision
```

相比上一篇 `ac2d33da18fa`，它更强调：

1. **variational fusion** 而不只是 OI；
2. **confidence / uncertainty field**；
3. NWP 的分层标定；
4. 路径上的鲁棒目标和机会约束；
5. 多模型 forecast ensemble。

但它的问题也更明显：

- 论文从 p.47 后明显出现“公式堆砌”，很多高级模型没有结果落地；
- 摘要的 `82%`、`35%` 关键结果在正文找不到复现链；
- `Ia/Ib∈[0,1]` 与 RMSE 约 `5–8` 数量级矛盾；
- 公开附录存在合成数据兜底和物理上站不住脚的速度分量拆解；
- RF 评估含明显 in-sample 风险；
- A* 被假设“保证全局最优”，但没有先证明 heuristic admissibility；
- 目标输出 100 m/50 m，与部分 NWP 结果实际 500 m/400 m 的展示口径并存。

所以这篇最适合我们的学习姿势是：

> **学它“不确定性层 + NWP 校正 + 风险规划”的系统架构；不要学它用大量未落地公式制造技术密度。**

---

# 1. Q1：双源 reference → 单源可部署模型

全文审读记录将 Q1 定位在约 p.9–26。

## 1.1 模型 a：物理综合指标

输入包括：

- 风廓线雷达；
- 微波辐射计温度廓线；
- 多波束径向速度；
- 谱宽 SW。

主链：

```text
温度按高度插值
   ↓
位温 θ
   ↓
多波束最小二乘 → u,v
   ↓
垂直梯度 / wind shear S
   ↓
Richardson number Ri
   ↓
TKE proxy ≈ SW²
   ↓
Ia composite index
```

位温：

\[
\theta=T\left(\frac{1000}{P}\right)^{0.286},
\]

气压采用简化指数廓线：

\[
P=1013.25\exp(-z/8400).
\]

风切变：

\[
S=\sqrt{\left(\frac{\partial u}{\partial z}\right)^2+
\left(\frac{\partial v}{\partial z}\right)^2}.
\]

候选综合指标：

\[
I_a=
0.3\exp(-0.5Ri)
+0.5TKE_{norm}
+0.2S_{norm}.
\]

模型 b 初始形式：

\[
I_b=0.5SW_{norm}+0.5S_{norm}.
\]

然后用 regularized least-squares / RF 等方法，让 b 拟合 a。

## 1.2 这套设计为什么合理

本质还是：

\[
\boxed{rich\ information\ reference\rightarrow deployable\ reduced\ model}.
\]

这种题不一定有真实湍流标签；把多源物理指标当 pseudo-label，是可接受的工程策略。

候选比上一篇更进一步的一点是：它一次比较了 **11 种回归器**，不是只在 RF/XGBoost 两个模型间挑。

记录中 RF 测试结果最好：

\[
RMSE\approx5.1234,
\qquad
R^2\approx0.8543.
\]

梯度提升出现：

\[
R^2_{train}=0.9981,
\qquad
R^2_{test}=0.8001,
\]

论文主动指出过拟合，这种“看 train-test gap 而不是只报冠军模型”的意识值得学。

---

# 2. Q1 最严重的数学一致性问题：指标范围 vs RMSE

论文叙事中 Ia/Ib 是归一化综合指数，按字面应在约 `[0,1]` 范围。

但又报告：

\[
RMSE\approx 5\sim8.
\]

如果预测量和真值都严格在 `[0,1]`，那么单点绝对误差最大不过 1，因此：

\[
RMSE\le1.
\]

所以二者不可能同时成立。

这意味着至少存在一种未披露口径：

- 结果表使用了 `×10` / `×100` 缩放；
- Ia/Ib 实际没有裁剪到 `[0,1]`；
- RMSE 对应另一个目标量；
- 表格单位或摘要数字抄错。

在没有 PDF/代码完整复现前不能替作者选择答案，但评审结论非常明确：

> **评价指标的量纲/范围没有闭环。**

另外：

\[
\exp(-0.5Ri)
\]

当 `Ri<0` 时会大于 1，因此即使另外两项归一化，Ia 也不会天然落在 `[0,1]`。若实际做 clip，论文应明说。

---

# 3. `TKE≈SW²`：好用的 proxy，不等于物理 TKE

多普勒谱宽 `SW` 与速度离散程度有关，用：

\[
SW^2
\]

构造 turbulence proxy 有工程直觉。

但谱宽通常还包含：

- turbulence broadening；
- beam broadening；
- unresolved shear；
- platform / scanning geometry；
- signal noise。

真正的 TKE 单位是：

\[
[m^2/s^2].
\]

而 `SW²` 虽同量纲，却不是自动等于：

\[
\frac12(u'^2+v'^2+w'^2).
\]

所以建议写：

> `spectral-width-based turbulence energy proxy`

而不是无条件叫真实 TKE。

这正好与上一篇 D 候选形成方法分歧：

- D1：时间脉动风场算 TKE；
- D2：谱宽做代理。

两种都不是绝对真值，必须靠独立观测或下游一致性验证决定谁更可靠。

---

# 4. Q1 的验证风险：RF 有 in-sample 嫌疑

人工审读记录指出公开附录存在“对训练特征原地预测评估”的实现路径。

如果模型：

```text
fit(X_train, y_train)
↓
predict(X_train)
↓
report R²
```

那这个指标不能作为泛化证据。

即使正文另有 train/test 表，也必须确保最终主结论引用的是 held-out 结果。

对于这种高度时空相关数据，最稳妥的比赛验证是：

```text
blocked time
leave-one-site-out
leave-one-height-band-out
extreme-event holdout
```

而不是普通随机点切分。

---

# 5. Q2：变分融合是本文最值得学的部分

Q2 约 p.27–47，目标是 2 km 以下三维湍流强度场。

## 5.1 数据进入融合前做了什么

候选主链：

```text
missing / bad values
→ neighborhood weighted fill
→ quadratic detrend
→ Hampel / MAD 3σ
→ cubic spline time resample
→ coordinate transform
→ SNR / velocity / spatial QC
→ anisotropic distance
→ semivariogram
```

这比“把三个 CSV merge 后直接插值”成熟得多，因为它承认：

> **多源融合之前，最重要的是先定义每个 source 到底有多可信。**

## 5.2 融合权重

候选使用类似：

\[
w=w_{dist}\,w_{source}\,w_{time}.
\]

记录参数包括：

- WPR source weight `1.0`；
- DWR `0.8`；
- AWS `0.6`；
- `γ=10`；
- time decay `τ=30min`。

这些参数至少把“距离、设备、时间”三个可信度来源显式化。

但如果后面的变分观测项又用：

\[
R^{-1}
\]

表达传感器误差，那么 `w_source` 与 `R` 可能重复编码 source reliability。

更干净的做法是：

> **尽量把可信度统一塞进 covariance，而不是一套经验权重 + 一套误差协方差重复计权。**

## 5.3 变分目标

候选写成：

\[
J(T)=J_{obs}+\lambda_bJ_b+\lambda_sJ_s.
\]

其中：

- observation mismatch；
- background deviation；
- spatial smoothness。

这其实就是一个简化的 3DVAR / variational smoothing 框架。

相比上一候选 OI：

- OI 更直接、可审计；
- variational 更灵活，可以加入非均匀平滑、边界、物理约束。

比赛里二者没有绝对高低：

> **如果你没时间验证 30 个正则项，简单 OI 反而比“高级但没消融”的变分模型更强。**

---

# 6. Q2 最强的一点：终于把 uncertainty 显式做出来

候选不仅输出 T field，还给：

\[
\sigma^2_{total}
=
\sigma^2_{obs}
+
\sigma^2_{interp}
+
\sigma^2_{model}
\]

以及信息量 confidence field。

这个方向完全正确：

```text
mean field
+ uncertainty field
+ observation density
```

远胜过只给一张漂亮三维云图。

但公式隐含了一个强假设：

> 三类误差彼此独立。

若不独立，应出现 covariance cross-terms：

\[
Var(a+b+c)
=\sum Var+
2\sum Cov.
\]

实际中 interpolation error 与 model error 很可能高度相关，因此更稳的是 ensemble / bootstrap 直接估 posterior spread。

---

# 7. Q2 的分辨率问题仍然存在

题目要求的分析网格是：

\[
100m\times100m\times50m.
\]

候选也大量按这个网格描述输出。

但是：

\[
\boxed{analysis\ grid\ spacing\neq effective\ information\ resolution}.
\]

即使变分模型比普通插值高级，也不能凭算法把稀疏传感器之间的独立信息变成 100 m。

论文应该同时报告：

- native sensor resolution；
- analysis grid；
- effective resolution；
- confidence/variance；
- distance to observation。

否则“高分辨率”很容易只是数组变密。

---

# 8. Q2 结果与验证

人工审读记录给出：

\[
RMSE\approx0.143,
\]

\[
MAE\approx0.098,
\]

\[
R^2\approx0.756.
\]

摘要还称空间相关系数约 `0.87`，并写：

\[
I(z)=I_0e^{-z/2000}.
\]

但后二者在正文没有足够清晰的独立复现图表，因此只能作为“论文摘要主张”，不能升级为强结论。

真正建议的 Q2 验证是：

```text
leave one sensor out
→ fuse remaining sensors
→ predict held-out sensor
```

然后按：

- 距观测距离；
- 高度；
- turbulence regime；
- source type；

分别画误差。

---

# 9. Q3：NWP calibration d

Q3 约 p.47–61。

## 9.1 先插值再校正

NWP 数据先做：

- horizontal bilinear interpolation；
- vertical linear interpolation；
- 统一目标网格。

然后不是直接把 NWP 湍流指数拿去规划，而是建立高度分层二次校正：

\[
I_d^{cal}(z)
=
a(z)+b(z)I_{raw}+c(z)I_{raw}^2.
\]

并用 L2 正则化，LM 求解。

记录中使用：

```text
02:00–04:30 train
04:30–05:00 validation
+ 5-fold CV
```

这条“**先用观测融合场校正 NWP bias，再预报**”比上一篇候选直接从 WRF 计算 TKE 更接近统计后处理/MOS 思想。

这是第二篇最值得学的地方。

## 9.2 但 5-fold 必须是 time-aware

如果 `5-fold CV` 是随机打散时间，那么它会破坏真实预测场景。

应改为：

```text
blocked folds / rolling origin
```

同时按 forecast horizon 报：

\[
RMSE(h),\quad R^2(h),\quad CSI(h).
\]

---

# 10. Q3：观测外推 e

候选没有上来就堆 LSTM，而是比较五种：

- linear trend；
- moving average；
- exponential smoothing；
- multivariate regression；
- spatiotemporal correlation。

记录结果：

\[
RMSE_{multi-reg}\approx0.1634,
\quad
R^2\approx0.7542,
\]

集成：

\[
RMSE_{ens}\approx0.1612,
\quad
R^2\approx0.7693.
\]

这里很值得学的一点是：

> **简单模型横评 + ensemble，往往比直接 LSTM 更适合短数据竞赛。**

而且这也和上一候选形成鲜明对照：

- D1：风廓线 LSTM 失败，再换 S 波段 LSTM；
- D2：一开始就保留多种简单时序 baseline，再做 ensemble。

对于数据不长、小时级预测，我更偏向 D2 这个思路。

---

# 11. 但“预测更平滑”对安全可能是坏事

记录中实测范围约：

\[
0.04\sim0.88,
\]

预测约：

\[
0.06\sim0.69.
\]

也就是说预测峰值明显被压平。

如果目标是平均场 RMSE，这可能看起来不错；

如果目标是避开危险湍流，则：

> **under-predict extremes 比普通 RMSE 高一点更危险。**

所以安全类 forecast 必须额外评估：

\[
P(\hat I>I_{crit}\mid I>I_{crit}),
\]

也就是 hit rate / recall of hazardous events。

再配：

- false alarm rate；
- CSI；
- Brier score；
- reliability diagram。

---

# 12. 路径规划：架构很先进，证据却最弱

候选一路加入：

```text
A*
→ improved g/h
→ risk aversion
→ robust objective
→ chance constraint
→ fuzzy / multi-criteria decision
→ dynamic replanning
```

最基础边 cost：

\[
Cost_{ij}
=\frac{T_i+T_j}{2}d_{ij}.
\]

改进版大致：

\[
g(n)=g(parent)+d[I(n)^p+\alpha].
\]

又进一步写：

\[
\min E[J]+\lambda Var[J],
\]

以及：

\[
P(I>I_{crit})\le\varepsilon.
\]

这些概念方向都对。

但是全文审读记录明确指出：

- A* 没有路径代价数字对照表；
- 没有 straight-line / Dijkstra / random baseline；
- 鲁棒/机会约束没有清晰结果落地；
- 摘要称“识别准确率 82%”“暴露量降低 35%”，正文没有计算过程。

所以这是一个典型：

> **method sophistication > evidence sophistication。**

---

# 13. A* “保证全局最优”不是一个可以直接假设的事实

A* 在离散图上最优，需要：

1. edge cost 非负；
2. heuristic admissible；
3. 实现满足标准搜索条件。

如果 edge cost 是：

\[
d[I^p+\alpha],
\]

那么欧氏距离启发函数：

\[
h=d_{euclid}
\]

只有在每单位距离最小 cost：

\[
I^p+\alpha\ge1
\]

时才天然不高估。

若最小值小于 1，`h=d_euclid` 可能比真实剩余总代价更大，从而失去 admissibility。

安全写法应该构造：

\[
h(n)=c_{min}\,d_{euclid}(n,goal),
\]

其中：

\[
c_{min}
\le
\min_{all\ feasible\ edges}
\frac{cost}{distance}.
\]

所以论文假设章节直接写“A* 可以保证全局最优”属于循环论证风险。

---

# 14. 公式堆砌问题：这是这篇最明显的写作反例

人工全文审读发现，Q3 后半段引入约 30 个编号公式，包括：

- ST-GCN；
- graph attention；
- ensemble forecast；
- kernel interpolation；
- wavelet；
- EMD；
- power spectrum；

但没有对应结果、消融、表格或下游贡献。

这在评审眼里不是“方法丰富”，而容易变成：

> **没有 evidence 的公式库存。**

高水平论文更好的原则：

> 一个模型如果没有真正改变中间量、结果或结论，就不要写进主模型链。

可放附录 / alternatives / future work，而不是正文占 30 个公式编号。

---

# 15. 附录代码的两个严重可信度问题

审读记录指出：

## 15.1 合成数据兜底

`make_default_obs` 会用 `np.random` 生成 50 个观测点；示例温度廓线还有硬编码。

如果真实文件读取失败，程序仍可能“正常跑出一张图”。

这对于比赛复现极其危险。

正式版代码应该：

```python
if missing_required_input:
    raise FileNotFoundError
```

而不是 silent fallback 到 synthetic data。

## 15.2 径向速度直接拆成 u/v/w

代码出现类似：

```text
u = 0.7 * radial_velocity
v = 0.7 * radial_velocity
w = 0.2 * radial_velocity
```

这种写法没有正确的观测几何依据。

雷达径向速度满足：

\[
V_r
=u\cos\theta\cos\phi
+v\sin\theta\cos\phi
+w\sin\phi.
\]

必须由多方位/多仰角观测反演，不能靠常数比例拆分。

如果这个 fallback 真进入主结果链，那么后续：

```text
wind shear
→ Ri
→ turbulence field
→ route
```

都会继承物理错误。

---

# 16. 同题两篇的真正方法分歧

详见 [`SAME_PROBLEM_COMPARISON.md`](SAME_PROBLEM_COMPARISON.md)。这里只给结论：

- D1（`ac2d`）更像**可执行工程链**：OI + 负结果转路线 + A*/ACO + 路径基线；
- D2（`9574`）更像**完整决策系统设计**：变分 + uncertainty + NWP bias correction + robust/chance A*；
- D1 的 path evidence 更扎实；
- D2 的 uncertainty architecture 更先进；
- D1 高级模型较少但更落地；
- D2 公式更丰富，但有明显“写了没算”的问题。

如果我们自己比赛，最佳路线不是二选一，而是：

> **D1 的证据纪律 + D2 的不确定性/预报校正架构。**

---

# 17. 我们自己的统一升级路线

把这篇重写成：

```text
raw heterogeneous observations
       ↓ observation operators + QC
probabilistic latent turbulence state
       ↓
posterior mean + posterior covariance
       ↓
NWP bias calibration / observation nowcast
       ↓
forecast distribution
       ↓
space-time risk graph
       ↓
chance-constrained / CVaR A*
       ↓
route + uncertainty + fallback plan
```

比“多放几个 AI 算法”更重要。

---

# 18. 指导老师评价

**值得学：**

- 物理综合指标先做 reference；
- 多模型横评能看到 overfit；
- 变分融合比纯插值更有状态估计意识；
- confidence / error propagation 显式进入 Q2；
- NWP 不是直接用，而是分层校正；
- e 保留简单 baseline 并做 ensemble；
- 路径层开始考虑 robust/chance constraints。

**必须改：**

- target range 与 RMSE 先统一；
- 删除无结果的 30 个公式；
- synthetic fallback 禁止进入正式结果；
- 雷达速度用真实观测方程反演；
- time-aware validation；
- effective resolution 与 grid spacing 分开；
- extreme-event skill 单独报告；
- A* admissibility 真正证明；
- route 必须有数字基线；
- robust/chance 模块必须有消融和结果。

---

# 19. 一句话总结

> **这篇最大的价值，是把“多源融合”从加权插值升级成“带不确定性的状态估计”，再把 NWP 偏差校正和概率风险带入航路；最大的风险，是技术栈扩张速度超过了验证证据，导致很多高级公式并没有真正进入可复现结果链。**
