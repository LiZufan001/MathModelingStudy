# COMPETITION_PLAYBOOK｜多源监测 + 三维场 + 预报 + 航路优化速查

适用题型：

- 气象/环境场估计；
- 多传感器融合；
- 无完整真值的 proxy 建模；
- 时空短临预测；
- 风险场上的路径/调度优化；
- “监测→预警→决策”连续子问。

---

# 1. 看到题目后的第一反应

不要先想：

```text
RF? XGBoost? LSTM? A*?
```

先画五层：

```text
S1 Observation
S2 Reference / latent state
S3 Spatial analysis
S4 Forecast
S5 Decision
```

每层只问四件事：

1. 输入是什么？
2. 输出是什么？
3. 输出的不确定性是什么？
4. 下一层为什么能用它？

---

# 2. 没有 ground truth 时的 reference hierarchy

常见设计：

```text
高信息量 / 高成本资料
        ↓
reference model A
        ↓
低成本 / 少传感器 model B
```

写作时：

- `reference`
- `best-available estimate`
- `pseudo-label`

任选其一。

慎用：

- `真实值`
- `绝对真值`

除非确有独立实测真值。

---

# 3. 多源融合的正确起手式

不要：

```text
所有数据 → 插值 → 加权平均
```

要先统一为：

\[
y_s=H_sx+\epsilon_s.
\]

然后做：

```text
coordinate alignment
unit alignment
QC
observation operator
uncertainty
assimilation
```

---

# 4. 一个比赛够用的 OI / 3DVAR 模板

\[
J(x)=
\frac12(x-x_b)^TB^{-1}(x-x_b)
+
\frac12(y-Hx)^TR^{-1}(y-Hx).
\]

如果数据和时间有限，可以用简化协方差：

\[
B_{ij}=\sigma_b^2
\exp(-d_h^2/2L_h^2-d_v^2/2L_v^2).
\]

但参数表必须写：

| 参数 | 来源 | 范围 | 敏感性 |
|---|---|---|---|
| `Lh` | variogram/经验 | ... | ... |
| `Lv` | vertical decorrelation | ... | ... |
| `σb` | background residual | ... | ... |
| `R_s` | sensor error | ... | ... |

---

# 5. 三维图旁边必须再放一张“不确定性图”

高质量组合：

```text
(a) analysis mean
(b) posterior std / kriging variance
(c) observation density
(d) horizontal/vertical section
```

这样能主动防止评委说：

> 你这个光滑 3D 场是不是纯插值画出来的？

---

# 6. Grid spacing / resolution 固定用语

正确：

> 结果输出到 100 m analysis grid。

谨慎：

> 获得 100 m 分辨率湍流场。

除非有实际 downscaling/validation 支撑。

---

# 7. 时序模型验证模板

禁止把时间序列随机 shuffle 作为最终结果。

比赛标准模板：

```text
train: early period
valid: middle period
test : final period
```

再做 rolling origin：

```text
T1 → predict T2
T1:T2 → predict T3
...
```

指标：

\[
RMSE(h), MAE(h), R^2(h)
\]

按 horizon 报。

永远加一个：

\[
\hat y_{t+h}=y_t
\]

persistence baseline。

---

# 8. 预测失败怎么写

非常推荐：

```text
Route A failed
→ show metric
→ diagnose why
→ change information source / model assumption
→ Route B
```

不要：

> “经过不断调参，最终取得优异效果。”

候选 D 里风廓线 LSTM `R²≈0.27` 的负结果就是很好的比赛写法范例。

---

# 9. 降采样必须 risk-preserving

如果下游是路径规划，不要只保均值。

推荐：

```text
keep all high-risk cells
keep high-gradient cells
keep near-sensor cells
coarsen only smooth safe regions
```

判断降采样好坏看：

\[
\Delta J_{route}
\]

而不只是重构 MSE。

---

# 10. 风险场到航路的三种层级

## Level 1｜确定场

\[
\min_\pi L+\lambda R.
\]

## Level 2｜多目标

\[
\min_\pi (L,R,M).
\]

输出 Pareto frontier。

## Level 3｜概率风险

\[
\min_\pi
L+\lambda CVaR_q(R).
\]

或：

\[
P(\max risk\le r_{safe})\ge1-\delta.
\]

比赛有时间时至少做到 Level 2。

---

# 11. 路径算法选择

## Dijkstra

适合：

- 网格不太大；
- 要绝对稳；
- baseline。

## A*

适合：

- 已知终点；
- 图大；
- 能构造 admissible heuristic。

## ACO / GA / PSO

适合：

- 非规则编码；
- 非局部复杂约束；
- 多目标扩展。

但必须：

- multiple seeds；
- deterministic baseline；
- same evaluator。

不要因为“高级”就放弃 A*。

---

# 12. A* 的标准证明句

可以直接改写：

> 在构造的时空离散图中，所有边代价非负；启发函数取当前位置至终点的理论最小剩余距离代价，不高估真实剩余代价，因此具有 admissibility。故 A* 返回该离散动作空间和既定代价函数下的全局最优路径。

然后主动加边界：

> 该最优性不等价于连续真实空域中、未建模动力学下的绝对最优航迹。

这两句一起写，评委反而更放心。

---

# 13. Cost 一律先无量纲化

危险写法：

\[
J=L+200\cdot TKE^{1.5}.
\]

推荐：

\[
J=
\lambda_1\frac{L}{L_0}
+
\lambda_2\frac{R}{R_0}
+
\lambda_3\frac{M}{M_0}.
\]

权重：

- sweep；
- Pareto；
- 业务阈值；

三选一解释。

---

# 14. 最少图表配置

如果是 100 h 华为杯，这类题建议正文核心：

1. 全文模型接口图；
2. 多源时空 coverage 图；
3. reference vs reduced model profile；
4. blocked validation table；
5. 3D analysis mean；
6. uncertainty / observation density；
7. forecast horizon curve；
8. high-risk slice；
9. Pareto frontier；
10. route overlay；
11. route risk profile vs time；
12. robustness table。

图不要重复堆 30 张相似切片。

---

# 15. 最少消融实验

## Observation ablation

```text
all sensors
- radar X
- radar S
- profiler
- surface stations
```

## Forecast ablation

```text
persistence
single model
fusion
```

## Route ablation

```text
distance only
risk only
combined
robust/CVaR
```

这样可以真正回答：

> 哪个模块贡献了多少？

---

# 16. 三类常见假漂亮结果

## 16.1 细网格云图

细 ≠ 准。

## 16.2 高 R²

随机时间切分高 R² ≠ 未来预测高 R²。

## 16.3 一条弯曲的 3D 路线

看起来会避障 ≠ cost 最优、动力学可飞、预测稳健。

---

# 17. 统一 uncertainty interface

每个模型都输出：

```text
value
uncertainty
valid_domain
resolution
QC_flag
```

例如：

```python
FieldEstimate(
    mean=...,
    std=...,
    native_resolution=...,
    effective_resolution=...,
    valid_mask=...,
    qc=...
)
```

下游不得只拿 `.mean` 就把其他字段全丢了。

---

# 18. 赛场 20 分钟检查清单

看到监测/融合/预报/路径题，先回答：

- [ ] 主状态变量到底是什么？
- [ ] reference 是真值还是 pseudo-label？
- [ ] 不同传感器的 `H_s` 是什么？
- [ ] 单位统一了吗？
- [ ] grid spacing 和 effective resolution 分开了吗？
- [ ] validation 有没有时间泄漏？
- [ ] persistence baseline 有吗？
- [ ] high-risk extreme 被降采样吞了吗？
- [ ] route cost 各项量纲一致吗？
- [ ] 最优性的作用域写清了吗？
- [ ] stochastic optimizer 重复了吗？
- [ ] uncertainty 传到最终 route 了吗？

---

# 19. 一句话比赛模板

> **先用信息最全的数据构建可审计 reference，再用观测算子和不确定性完成多源融合；用真正的未来切分校准预报，最后把概率风险而非单一场值送入带动力学约束的时空路径优化，并用 Pareto 与鲁棒性实验说明“为什么这条路线值得飞”。**
