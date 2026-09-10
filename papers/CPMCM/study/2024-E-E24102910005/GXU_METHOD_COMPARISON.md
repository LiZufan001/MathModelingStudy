# 2024 E｜广西大学王家宝队官方方法路线对照

> **边界声明：本文件不是该队论文全文精读。**  
> 目标团队：王家宝、石磊、施涵（广西大学）  
> 参赛编号：`E24105930017`  
> 奖项：全国一等奖  
> 当前可靠信息来源：广西大学电气工程学院官方获奖报道。当前仓库未收录与该队精确对应的完整 PDF。

---

# 1. 校方公开的方法链

广西大学官方报道明确介绍该队作品《高速公路应急车道紧急启用模型》的核心方法：

```text
YOLOv10 + FairMOT
   ↓
车辆目标检测与跟踪
   ↓
交通流参数
   ↓
AHP + K-means + 改进机器学习
   ↓
交通流拥堵预测
   ↓
模糊逻辑
   ↓
应急车道启用决策
```

在没有原论文全文的情况下，以上只能作为**官方方法摘要**，不能进一步断言具体公式、参数、精度、数据划分或实现细节。

---

# 2. 与本轮 E24102910005 的共性

两支队都抓住了同一条正确主线：

```text
video perception
→ traffic state
→ congestion prediction
→ shoulder decision
```

说明 2024 E 的优秀解普遍不是单独做一个交通流方程，也不是单独做目标检测，而是强调感知与控制联动。

---

# 3. 差异：跟踪器

广西大学公开路线：

```text
YOLOv10 + FairMOT
```

本轮全文：

```text
YOLOv10m + ByteTrack
```

两者都属于 detection + multi-object tracking pipeline。

从建模角度，真正应该比较的不是算法名字，而是：

```text
count error
track stability under congestion
speed-estimation error
occlusion robustness
runtime
```

没有这些指标，无法仅凭 FairMOT/ByteTrack 名称判断哪个更适合本题。

---

# 4. 差异：拥堵模型的哲学

广西大学公开路线包含：

```text
AHP
K-means
improved machine learning
```

说明更偏向：

> **多指标交通状态表征 + 聚类/预测。**

本轮 E24102910005 则更明显使用：

```text
fundamental diagram
shock/discontinuous traffic flow
conservation accumulation K(t)
AdaBoost
```

更偏向：

> **交通机理状态 + 机器学习预测。**

两条路线都可以成立。

指导老师会更关心：

> 上游模块产生的变量有没有真正成为下游模型的输入？

例如 AHP 若只是“算一次权重”，K-means 若只是“画个聚类图”，但最终预测/控制不用它们，就属于链条断裂。

---

# 5. 差异：决策层

广西大学官方报道明确写到：

> 基于模糊逻辑构建应急车道启用决策系统。

这与本轮论文的硬阈值：

```text
K > 0.8 → open
K < 0.6 → close
```

形成很好的两类方法对照。

### 硬阈值 + hysteresis

优点：

- 清楚；
- 可审计；
- 易做安全 hard constraints；
- 实时实现简单。

缺点：

- 临界状态较刚性；
- 阈值校准敏感。

### fuzzy logic

优点：

- 可以柔和融合密度、速度、流量、预测概率等；
- 对“轻度/中度/重度”这类渐变状态自然。

风险：

- membership function 若主观给定，会把不确定性藏进规则库；
- 很容易变成“规则很多但无法验证”；
- 安全性不能被 fuzzy score 抵消。

因此最好的融合方案是：

```text
fuzzy / probabilistic score
        ↓
normal traffic decision
        +
hard safety overrides
        +
hysteresis / dwell time
```

---

# 6. 我们该怎样吸收两篇的优点

推荐比赛框架：

```text
YOLO + robust tracker
        ↓
metric calibration
        ↓
q/u/rho + conservation storage
        ↓
physical indicators + data-driven latent state
        ↓
time-aware congestion forecast
        ↓
fuzzy/probability risk score
        ↓
finite-state controller with hysteresis
        ↓
hard safety constraints
```

这里：

- 学广西大学：多指标状态融合、模糊决策；
- 学南京工业：守恒式 `K(t)`、滞回开闭、下游状态与传感器设计；
- 我们自己补：严格 calibration、时间验证、counterfactual sensitivity、安全硬约束。

---

# 7. 若未来找到广西大学完整论文，优先核查什么

```text
[ ] YOLOv10/FairMOT 是否有人工 benchmark
[ ] speed/density 是否做 metric calibration
[ ] AHP 权重来自专家、熵权还是数据
[ ] K-means 聚什么变量、K 如何选
[ ] improved ML 改了什么
[ ] train/test 是否按时间隔离
[ ] fuzzy membership functions 如何标定
[ ] fuzzy output 如何转成 open/close
[ ] 是否有 hysteresis
[ ] 安全条件是否 hard constraint
[ ] 效果量化是否来自真实/仿真反事实
[ ] 监控点成本是否优化
```

找到全文后应新建独立目录，不覆盖 `E24102910005` 的精读资料。

---

# 8. 一句话

> **同题异解最值得比较的不是“ByteTrack 还是 FairMOT”，而是感知结果如何经过状态建模、预测和规则系统，最终形成一个可验证、可安全执行的闭环。**
