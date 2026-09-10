# F24104860143｜物理机理 + 随机过程题比赛速查

> 适用：轨道/导航/计时、传感器事件流、粒子/光子到达、带物理状态的点过程仿真。

---

# 1. 第 1 小时先画四张表

## Units

```text
length: m / km
velocity: m/s / km/s
time: s / day
GM: 与 length 单位匹配
angle: deg / rad / mas
```

## Frames

```text
GCRS
BCRS
body-fixed?
source direction frame?
```

## Time scales

```text
UTC / TAI / TT / TCG / TCB / TDB
MJD / JD
```

## State dependency

```text
Q1 state → Q2 delay → Q3 precise delay → Q4 phase/intensity
```

---

# 2. 每个公式先做 dimension audit

```text
[ ] lhs/rhs same dimension
[ ] seconds not added to days
[ ] km not multiplied as if m twice
[ ] dimensionless rate correction not called seconds
```

发现维度不一致，优先修它，不要继续堆模型。

---

# 3. 物理题 baseline

先做最低可信层：

```text
simple dynamics
→ independent invariant check
→ dominant physical term
→ magnitude sanity check
```

例如 barycentric timing：

```text
Roemer ~ hundreds s
Shapiro ~ μs scale (geometry dependent)
```

若小修正比主项还大，先查单位/符号/reference frame。

---

# 4. 参考系纪律

函数签名不要：

```python
delay(r,v)
```

而要：

```python
delay(state_bcrs_tdb)
```

调用前 assert：

```python
assert state.frame == 'BCRS'
assert state.time_scale == 'TDB'
```

避免“同样是三维向量，换一个 frame 数值差七个数量级”。

---

# 5. 时间尺度纪律

任何近似式旁边直接写单位：

```python
delta_tdb_tt_s = ...   # second
jd_tdb = jd_tt + delta_tdb_tt_s/86400
```

不要写无后缀：

```python
dt = ...
```

---

# 6. 随机过程题工作流

```text
生成机制
→ intensity / hazard
→ integrated intensity
→ sampler
→ official observable
→ statistical diagnostics
```

NHPP：

\[
\lambda(t)\ge0,
\qquad
\Lambda(t)=\int\lambda.
\]

首选 sampler：

```text
inverse cumulative intensity
order statistics
thinning
```

不要默认“当前 λ 下指数等待”在非齐次情况下就是精确算法。

---

# 7. 两个 NHPP 公式必须背熟

## Time change

\[
E_i\sim Exp(1),
\quad S_k=\sum E_i,
\quad t_k=\Lambda^{-1}(S_k).
\]

## Conditional order statistics

\[
N\sim Poisson(\Lambda(T)),
\]

\[
U_i\sim U(0,1),
\quad t_i=\Lambda^{-1}(U_i\Lambda(T)),
\]

然后排序。

不要把 Uniform 与 exponential waiting time 混为一谈。

---

# 8. 周期信号必须把周期性写进插值

```text
phase 0 ≡ phase 1
```

所以：

```text
periodic extension
periodic spline
circular binning
```

并验：

```python
min(profile) >= 0
integral(profile) ≈ expected_normalization
```

---

# 9. Baseline 先单元测试再比较

算法比较前：

```text
linear interpolation
nearest
spline
```

先拿简单直线/正弦人工数据测试。

否则一个符号 bug 就能制造“高级方法显著更好”。

---

# 10. 仿真验证不要 self-reference

若：

```text
template h
→ generator
→ simulated data
→ compare back to h
```

高相关只能说明**数值自洽**。

还需要：

```text
count mean/variance calibration
time-rescaling KS/QQ
autocorrelation
multiple seeds mean±std
stress tests
```

---

# 11. 高精度结果的有效数字

不要因为 Python 打出：

```text
-473.8840196768914
```

就写 13 位小数。

有效精度由：

```text
model approximation
ephemeris accuracy
time-scale conversion
parameter uncertainty
numerical integration
```

共同决定。

论文可报告：

```text
value + estimated numerical/model uncertainty
```

而不是只报长小数。

---

# 12. 赛中评审检查清单

```text
[ ] 原题/赛中更正已锁定
[ ] unit table
[ ] frame table
[ ] time-scale table
[ ] dominant-term sanity check
[ ] each correction dimensionally valid
[ ] no double counting
[ ] baseline independently tested
[ ] simulator statistical test
[ ] multiple-seed uncertainty
[ ] result table auto-generated
[ ] abstract numbers synced
[ ] code path portable
```

---

# 13. 一句话

> **物理随机过程题的优先级：先把世界坐标和单位说清楚，再把随机机制说清楚，最后才是算法快不快、图漂不漂亮。**
