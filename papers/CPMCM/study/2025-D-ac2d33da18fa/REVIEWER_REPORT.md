# REVIEWER_REPORT｜2025 D 候选论文模拟评审

> 本报告只评价证据 ID `graduate:paper:2025-D:ac2d33da18fa` 所对应的 60 页候选论文方法与审读记录。  
> **由于尚未看到封面队号，本报告不把它直接等同于 `D25101470116`。**

---

# 1. 总体评价

这是一篇结构完整、工程链较强的多源气象建模作品。

它最成熟的地方是：

- 没有把三问写成三个互不相干的算法；
- `a→b` 和 `c→d` 都主动建立内部 reference；
- Q2 从多源风场融合走到三维 turbulence field；
- Q3 真正把 forecast field 接到了 route optimization；
- 风廓线 LSTM 的负结果被保留并用于路线切换；
- A* 至少给直线和随机/样条基线，而不是只展示漂亮航迹。

如果我是指导老师，我会认可它的**系统组织能力**。

如果我是严评委，我最担心的是：

> 上游 reference / interpolation / proxy 的不确定性没有充分量化，但下游“最优航路”的口气越来越确定。

这是整篇最核心的可信度矛盾。

---

# 2. 强项

## 2.1 reference hierarchy 很适合没有真值的题

```text
rich sensors → a
restricted sensor → b
multi-source fusion → c
NWP / short nowcast → d/e
```

它让每一级都有比较对象。

## 2.2 负结果叙事真实

风廓线 LSTM：

\[
R^2\approx0.27\rightarrow0.28
\]

作者没有继续包装，而是明确认为不可靠，转向 S 波段资料。

这类“失败→解释→换路线”比删掉失败实验更像真正建模。

## 2.3 Q2 不是纯 IDW 拼图

引入：

- VAD；
- 背景场；
- OI；
- `B/R`；
- structure function；

至少形成了一个数据同化意识。

## 2.4 决策层有 baseline 意识

模型 d 的 A*：

- 与直线；
- 10 条随机/样条路线；

比较统一代价。

虽然这不能独立证明真实连续空间全局最优，但明显好于只报一条路径。

---

# 3. 主要扣分风险

## 3.1 模型 a 被叫作“基准真值”过强

模型 a 仍然是推导产物，不是直接 ground truth。

它依赖：

- 观测误差；
- 时空配准；
- 数值微分；
- Ri/TKE 公式；
- averaging window。

因此 b 对 a 的指标只能证明 teacher imitation。

## 3.2 Q1 随机 70/30 可能高估泛化

时空高度数据存在强相关。

更应：

- blocked time；
- leave-one-site-out；
- extreme-event holdout。

## 3.3 Q2 有伪分辨率风险

把结果输出在：

\[
100m\times100m\times50m
\]

不等于观测真的支持该尺度独立结构。

## 3.4 多源权重与 covariance 参数证据不足

X/S 固定 `0.6/0.4`、`R` 中固定设备误差、`B` 高斯相关尺度，都应有：

- 来源；
- 数据估计；
- sensitivity。

## 3.5 `ε^(1/3)` 的物理名称风险

如果它被称作 conventional TI，量纲不一致。

## 3.6 TKE 异常值已发现但未闭环

候选正文明确承认 Q2 个别 TKE 极大值异常。

优秀论文可以承认缺陷，但如果该场还被下游用作验证基准，必须说明：

- 异常点如何处理；
- 是否进入 c→d 校准；
- 对航路是否敏感。

## 3.7 NWP 细网格可能只是重采样

`RegularGridInterpolator` 不会创造百米级湍流信息。

## 3.8 路径 cost 缺少统一量纲 / Pareto

\[
d+\alpha k^\beta
\]

如果未归一化，需要解释 `α` 单位。

单组 `α,β` 也不能展示安全—距离 trade-off。

## 3.9 e 模型融合与航路验证弱于 d

S-band LSTM `R²≈0.77` 后，又按 `R²` 融合较差的风廓线模型；需要 ablation 证明 fusion 真有增益。

ACO 路径没有和 A*/Dijkstra 同尺度对照，也缺随机种子统计。

---

# 4. 模拟答辩：16 个问题

## Q1. 为什么模型 a 可以当“真值”？

理想回答：

> 不能称绝对真值，只能称 best-available reference。我们会通过独立站点/设备留出进一步量化其误差，并把 a 的不确定性传给 b。

## Q2. 70/30 切分是不是把相邻时刻同时分到了训练和测试？

理想回答：

> 随机切分只作为开发指标，正式结果增加 blocked-time 和 leave-one-site-out。

## Q3. TKE 里的平均风采用多长窗口？

追问目的：

> averaging window 决定“湍流脉动”和“天气变化”的尺度分界。

## Q4. 风切变很小时 Ri 会不会数值爆炸？

要求回答：

- 最小 shear floor；
- 数值微分平滑；
- extreme Ri QC。

## Q5. 为什么 X/S 波段是 0.6 / 0.4？

如果回答“经验设置”，继续追：

> 权重 0.5/0.5 或 0.8/0.2 时核心空间结论变不变？

## Q6. OI 的 `B` 相关长度和 `R` 方差怎么来的？

这是 Q2 最重要的参数来源问题。

## Q7. 你说水平分辨率 100 m，是网格间距还是实际有效分辨率？

理想回答必须承认：

> 是 analysis grid spacing；effective resolution 受原生传感器分辨率和 covariance 控制。

## Q8. `ε^(1/3)` 为什么叫 TI？单位是什么？

如果不能立刻回答量纲，说明物理指标口径没有吃透。

## Q9. 论文承认 TKE 有异常极大值，那这些值有没有进入模型 d 的校准 reference？

需要：

- 异常 mask；
- robust loss；
- sensitivity。

## Q10. WRF 风场插值到 100 m 后为什么能表示 100 m 湍流？

理想回答：

> 不能。插值只是在细网格评估粗分辨率模式场；必须把 native-resolution limit 写清楚。

## Q11. 你从 NWP 风速相对时间均值计算的“ TKE ”和边界层参数化 TKE 是同一个物理量吗？

正确方向：

> 不是，需要区分 resolved temporal variance 与 sub-grid TKE。

## Q12. 原题要求用前三小时观测作为 d 的验证标准，你的显式 RMSE / MAE / event skill 在哪里？

全文审读记录指出这里展示不足。

## Q13. `distance + α·TKE^β` 两项单位不同，为什么可以直接相加？

需要：

- normalization；
- unit-bearing α；
- Pareto sensitivity。

## Q14. 为什么 10 条随机路线都更差就能证明 A* 全局最优？

正确回答：

> 不能。A* 的离散图最优性来自 admissible heuristic 等条件；随机路线只是 sanity baseline。

## Q15. 风廓线 LSTM R² 只有 0.28，为什么还要按 R² 加权加入最终融合？

必须做：

```text
S-band only vs WPR only vs fusion
```

## Q16. 蚁群路径重复 30 次结果稳定吗？为什么不用同一张图上的 A* 作 baseline？

需要：

- seed statistics；
- convergence；
- same evaluator；
- same constraints。

---

# 5. 如果我是指导老师，赛前会要求补的实验

优先级从高到低：

1. **时空 blocked validation**；
2. **leave-one-sensor/site-out assimilation validation**；
3. **TI / ε / TKE 单位与定义统一表**；
4. **B/R 与 X/S 权重敏感性**；
5. **NWP native resolution 声明 + d 的真正未来误差表**；
6. **length-risk Pareto frontier**；
7. **ACO/A*/Dijkstra 统一 evaluator 对照**；
8. **field ensemble → route ensemble 鲁棒性**。

如果时间只够补三个：

> 选 1、5、6。

因为它们分别卡住：

- 学习泛化；
- 预报真实性；
- 最终决策合理性。

---

# 6. 评委视角的一句话评价

> **工程链完整、reference 递进和负结果叙事很成熟；但“reference 不等于真值、细网格不等于高分辨率、风险航路不能比上游场更确定”这三条可信边界若补齐，论文会从“算法链完整”真正升级成“科学链闭环”。**
