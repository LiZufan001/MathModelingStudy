# F24104860143｜指导老师 / 评审老师报告

> 不是赛事官方评语，而是基于原题、79 页论文、公开代码、官方附件及 DE200 复算做的评审训练。

---

# 一、如果我是评审老师：第一页后的总体判断

这是一篇**系统结构很强、物理细节严谨性明显弱于整体叙事**的论文。

让我继续读的地方：

1. 四问前后关系非常清楚；
2. Q1 不直接调用黑箱，而是完整推导开普勒二体模型；
3. Q2/Q3 知道高精度 TOA 必须处理 time scale、reference frame、proper motion；
4. Q4 选 NHPP，和光子到达机制匹配；
5. 不只给随机序列，还做 folding、profile comparison 和统计检验；
6. 能主动发现局部强度冻结近似在低流量下的问题并提出改进；
7. 公开了大量代码，工程完成度高。

但如果我是熟悉天文计时/随机过程的评委，我很快会圈出：

> **你说“精确时延”，但 TT→TDB 的秒数为什么直接加到了 Julian Day？**

这会立刻把审查重点从“公式多不多”转到“单位和 reference frame 是否真的可靠”。

---

# 二、指导老师会表扬的 8 点

## 1. 四问是一条因果链

```text
orbit state
→ barycentric state
→ delay
→ phase
→ intensity
→ photon point process
→ folded profile
```

这是优秀建模论文最重要的骨架能力之一。

## 2. Q1 推导针对本题

不是“建立某模型，调用 MATLAB”，而是从二体动力学推到 r/v。

## 3. 知道几何时延是百秒主项

BCRS 距离量级约 1 AU，Roemer delay 百秒级，量级认知方向正确。

## 4. proper motion 真正进入方向向量

不是只在“模型优点”里提到脉冲星自行，而是修改 RA/Dec 后再算 `n_hat`。

## 5. Q4 选择 NHPP，而非普通 Poisson count model

这体现作者理解“到达时刻”的问题本质是 point process。

## 6. 从 λ(t) 到 Λ(t) 的框架完整

这使后续 inverse transform 有自然数学接口。

## 7. 知道初始 sampler 有近似条件

“低流量时 waiting interval 变长，局部强度冻结变差”是合理诊断。

## 8. 改进 A.6 的实际算法思想有水平

Poisson total + order-statistics + inverse cumulative intensity 是正规 NHPP simulation 技术，而不是随意调参数。

---

# 三、A级风险：会直接影响结论可靠性

## A1. TT→TDB 单位错误

`0.001657 sin(g)` 是秒，却直接加到以天为单位的 JD。

DE200 复算：

```text
Q2 ephemeris time error ≈ 83.308 s
Q2 BCRS position error ≈ 2513.5 km
Q2 Roemer delay error ≈ 6.867 ms

Q3 ephemeris time error ≈ 6.173 s
Q3 BCRS position error ≈ 186.9 km
Q3 Roemer delay error ≈ 0.1756 ms
```

对于一篇声称关注 μs/ns 修正的论文，这是核心风险。

## A2. “引力红移时延”公式量纲不成立

\[
GM/(rc^2)
\]

无量纲，不是秒。

它可解释为弱场钟速率的相对修正量级之一，却不能直接作为 time delay。

## A3. SR 动钟项正文、函数、调用不一致

```text
正文：-2 r_SSB·v_SSB/c²
function：+2 r·v/c²
actual call：GCRS r/v
```

公开结果 `-7.0e-10 s` 来自实际 GCRS 调用，而不是正文模型。

## A4. χ² evaluator 写错

论文公式：

\[
(O-E)^2/E.
\]

代码：

\[
(O-E)^2/n\times p.
\]

因此 χ²=24.98915 不能验证论文所声称的 Poisson goodness-of-fit。

## A5. linear interpolation baseline 实现错误

斜率分母符号反了，并可产生负 intensity。

论文表 6.1 的 linear Pearson 复现值恰好对应这个 bug，因此三种插值比较受到污染。

---

# 四、B级风险：不推翻整篇，但会削弱“精确”二字

## B1. Q1 round-trip 验证不是 independent validation

forward/inverse 共用同一理论，验证强度不足。

## B2. Q1 式 (3.45) 旋转轴写错

正文 `R3(-i)`；后续和代码实际 `R1(-i)`。

## B3. 路径长度 m/km 标签错

Q2、Q3 的 `8.33e10`、`1.42e11` 数值实际是 m，正文标成 km。

## B4. Q3 Earth z 中间值错位

式 (5.9) 写成 satellite z，式 (5.10) 又重复。

## B5. 只考虑 Sun 的 Shapiro/relativistic terms

作为竞赛简化可以，但不能称完整高精度 timing model。

## B6. Pearson validation 是 self-consistency

标准 template 同时是 generator 的输入与 evaluator 的 target，相关性天然趋近 1。

## B7. inverse method 的理论证明混淆 Uniform/Exponential

A.6 实现可成立，但正文证明不能成立。

## B8. 改进法“0.99351 优于 0.99351”

按公开两位以上数字看只是相等。

---

# 五、C级问题：工程与写作

1. 摘要关键词把“非齐次泊松分布”写成“非条件泊松分布”；
2. 代码硬编码 Windows `F:\shumo\...` 路径；
3. simulation seed 只展示单次，没有 mean±std；
4. `while(t_k<=t_e)` 后先 append next event，可能把第一个超过观测结束时刻的事件也加入序列；
5. cubic spline 未做 periodic boundary；
6. paper 对 `dt=0` 的 Q4 代码与“将 Q3 精确时延用于航天器 TOA”叙述没有完全联动；
7. 多个“精确”表述没有附相对于参考实现的误差。

---

# 六、为什么这些问题仍不抹掉它的获奖价值

需要公平评价。

它的整体优点仍然很突出：

- 选题难度高；
- 物理和统计两条线都覆盖；
- 四问完成度高；
- Q1 有较长的自主推导；
- Q2/Q3 至少意识到 barycentric timing 的关键组成；
- Q4 建立了完整可运行 simulator；
- 有图、有数、有代码、有改进；
- A.6 的采样策略本身属于正规算法思路。

所以更准确的总评不是“这篇错很多所以不好”，而是：

> **宏观模型架构与竞赛完成度很强；微观时间计量、相对论量纲与统计验证存在严重可改进空间。**

这也是国一论文最值得精读的原因——能同时学“为什么高分”和“哪些地方不能照抄”。

---

# 七、如果我是指导老师，赛中会设 7 个硬门槛

## Gate 1：Unit table

第一天必须有：

```text
GM_earth : km³/s²
GM_sun   : m³/s²
c        : m/s
ephemeris position : km
ephemeris derivative : km/day
JD/MJD   : day
time correction : second
```

## Gate 2：Frame table

```text
satellite state input → GCRS
Earth/EMB → relative ephemeris vector
EMB/SSB → BCRS
pulsar direction → ICRS/BCRS-compatible unit vector
```

## Gate 3：Dimension unit test

每个 delay function 必须返回 seconds，并能人工推量纲。

## Gate 4：参考实现

Q1 与 orbital library；Q2/Q3 与成熟 barycentric timing/astronomy library 做至少一个 sanity comparison。

## Gate 5：NHPP sampler statistical test

必须有 time-rescaling，而不是只画 histogram。

## Gate 6：baseline unit test

linear interpolation、binning、folding 必须有人工构造的小例子。

## Gate 7：所有结果 machine-generated

表格和摘要从统一 JSON/CSV 自动生成，避免“0.99351 优于 0.99351”。

---

# 八、模拟答辩 12 问

## Q1

**你们式 (3.45) 为什么倾角用 `R3(-i)`，代码却等价于 `R1(-i)`？**

应答：正文笔误，给出固定的 frame convention 和单元测试。

## Q2

**0.001657 是秒还是天？为什么可以直接加到 JD？**

应答：不能，应除以 86400；重新报告 DE200 和 delay 结果。

## Q3

**你们“精确”到 10^-10 s，但历表输入时刻错 6–83 s，如何解释？**

应答：有效位数必须由模型误差决定，修正 time-scale pipeline 后再报精度。

## Q4

**式 (4.24) 的路径差是 8.3×10^10 km，那除以光速为什么只有 278 s？**

应答：单位标签错误，该数值实际为 m。

## Q5

**`GM/(rc²)` 怎么得到秒？**

应答：得不到；它是 dimensionless rate correction，需要积分或纳入 Einstein time transformation。

## Q6

**动钟项到底该用 GCRS 还是 BCRS？为什么正文和代码不同？**

应答：应从统一的 time-coordinate transformation 推导，不靠切换输入 frame 调出期望数量级。

## Q7

**为什么 linear interpolation 会产生负 λ(t)？**

应答：公开代码分母符号写反，应修正 baseline 后重跑模型比较。

## Q8

**你们用 h(φ) 生成数据，再与 h(φ) 算相关系数，这能证明什么？**

应答：只能证明 simulator 对 prescribed template 的数值 fidelity；物理有效性需要独立观测或统计性质验证。

## Q9

**χ² 公式和代码为什么不是同一个？**

应答：公开代码存在括号/运算优先级错误，应改为 `(obs-exp)**2/exp` 并处理低期望频数。

## Q10

**NHPP 的相邻 transformed waiting time 到底是 Uniform 还是 Exponential？**

应答：time-change 构造的相邻等待是 Exp(1)；条件于总事件数 N 时，累计强度坐标的 N 个事件是 Uniform order statistics。两种等价采样框架不能混写。

## Q11

**为什么 256 bins 最优？**

应答：不能只引用惯例；应给 bin-count sensitivity，在 resolution、SNR、peak bias 间选 Pareto 点。

## Q12

**如果只保留本文一个创新/亮点，你保留什么？**

推荐：

> 把 orbital state、barycentric delay、pulsar phase 与 NHPP photon simulator 串成统一 pipeline，并将原局部近似 sampler 升级为 cumulative-intensity inverse/order-statistics sampler。

---

# 九、评审式总评

### 结构完整性

**很强。** 四问高度统一。

### 机理针对性

**强。** 二体轨道、proper motion、NHPP 都与题目直接相关。

### 数值/单位严谨性

**偏弱。** TT/TDB、m/km、redshift dimension、frame mismatch 是核心问题。

### 随机过程验证

**中等偏弱。** generator 有价值，但 evaluator 有代码错误且 self-consistency 成分大。

### 工程完成度

**高。** 全流程、可视化、代码量都很充分。

### 比赛迁移价值

**很高。** 尤其适合训练高精度物理题的 unit/frame/time-scale discipline。

---

# 十、一句话

> **评委会被完整的系统链吸引，但真正决定“精确模型”可信度的，是每一个时间尺度、参考系、单位和统计检验能否经得起独立复算。**
