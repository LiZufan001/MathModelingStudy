# 2024 E｜视频交通预测与控制题比赛速查

> 适用于：交通视频、监控传感器、排队/拥堵、容量控制、动态启停、设备布点等“感知→预测→决策”题。

---

# 一、拿题后先画一条链

```text
raw sensor
→ measurement
→ physical state
→ forecast
→ decision
→ counterfactual
→ placement
```

每个箭头写清：

```text
input / output / unit / uncertainty / evaluator
```

---

# 二、视频数据先解决“米”，再解决“AI”

必须先确认：

```text
fps
camera view length
pixel-to-road mapping
lane ROI
line crossing definition
```

优先：homography + 已知道路几何。

检测/跟踪只负责：

```text
who / where / when
```

真正交通参数需要 metric calibration。

---

# 三、交通三要素统一单位

推荐：

\[
q:\mathrm{veh/h},\quad
u:\mathrm{km/h},\quad
\rho:\mathrm{veh/km}.
\]

sanity check：

\[
q\approx u\rho.
\]

不能一张表 veh/min、下一张图 veh/h，却不显式转换。

---

# 四、区间状态首选守恒

\[
N_{t+1}=N_t+(q_{in}-q_{out})\Delta t.
\]

\[
S_t=N_t/N_{max}.
\]

这往往比瞬时摄像头 density 更稳。

---

# 五、持续拥堵不要只做瞬时分类

把任务直接定义成：

\[
P(\text{未来30min持续拥堵}\mid \mathcal F_t).
\]

报告：

```text
precision / recall
lead time
false alarm rate
miss rate
```

而不只报告 regression R²。

---

# 六、时序预测禁止随手 random split

最低标准：

```text
train = earlier
val/test = later
```

更好：rolling origin。

必须有 persistence baseline：

\[
\hat y_{t+h}=y_t.
\]

---

# 七、lag 不等于 forecast horizon

“提前 10 min”是预测 horizon；A/B/C 到 D 的物理 lag 应由：

```text
distance/speed
cross-correlation
wave propagation
```

另行估计。

---

# 八、动态启停一定考虑 hysteresis

例如：

```text
S > 0.80 → OPEN
S < 0.60 → CLOSE
0.60–0.80 → keep previous state
```

再加：

```text
minimum dwell time
confirmation duration
clearance phase
```

避免 chatter。

---

# 九、安全型资源必须 hard override

应急车道不能只进入加权评分。

```text
事故
救援车辆
下游 spillback
传感器异常
```

应有强制逻辑。

---

# 十、政策效果必须写成反事实

没有真实 treatment/control 时：

```text
assumption → simulation → conditional conclusion
```

例如：

> 若肩道开放使有效容量增加 30%，模型预测拥堵时长下降 X%。

而不是：

> 肩道开放使拥堵下降 X%。

必须做 capacity sensitivity。

---

# 十一、多模型串联的最低验收

```text
YOLO output 是否真的进入 q/rho/v？
traffic model 是否影响 forecast/control？
forecast 是否改变 OPEN/CLOSE？
control effect 是否由 simulator 重新计算？
placement 是否改善最终 control metric？
```

答不上来就可能是模型堆砌。

---

# 十二、赛末五分钟检查

```text
[ ] 公式用一组表格数手算
[ ] 单位全部一致
[ ] 图表和摘要数字同源
[ ] test 没随机时间泄漏
[ ] baseline 已比较
[ ] safety hard rule 已写
[ ] scenario assumptions 写在结果标题
[ ] sensitivity 至少一张图
```

---

# 十三、一句话

> **传感器决策题，先保证“测得对”，再保证“预测真”，最后才讨论“控制优”；控制曲线漂亮不能替前两层兜底。**
