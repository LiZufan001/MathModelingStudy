# F24104860143｜时间尺度、参考系、单位与 NHPP 仿真审计

> 这份文件只做“硬审计”：**每个公式量纲是否成立、每个向量属于哪个参考系、时间尺度是否正确、随机过程 evaluator 是否真的实现了论文公式。**

---

# 1. 审计原则

任何高精度时间模型先固定四元组：

```text
(value, unit, frame, time_scale)
```

例如：

```text
r = [...]
unit = km
frame = BCRS
epoch = JD 2457062.500000011
time_scale = TDB
```

若四项中任意一项靠上下文猜，后面十几位小数都没有意义。

---

# 2. Q1 旋转矩阵正文错误

论文式 (3.45)：

\[
R_3(-\Omega)R_3(-i)R_3(-\omega)
\]

后续式 (3.46)、(3.47) 和 Python 实现等价于：

\[
R_3(-\Omega)R_1(-i)R_3(-\omega).
\]

因此：

> 式 (3.45) 是正文 typo；公开数值结果并未按该错误式计算。

---

# 3. TT→TDB：秒被直接加到 Julian Day

论文/代码：

```python
g = 6.24 + 0.017202*(JD_TT-2451545)
JD_TDB = JD_TT + 0.001657*sin(g)
```

标准低阶近似中：

\[
0.001657\sin g
\]

表示的是：

```text
seconds
```

因此若左边是 JD/day：

```python
JD_TDB = JD_TT + delta_seconds/86400
```

## 3.1 Q2 数值影响

MJD(TT)=57062.0：

```text
真实近似 TDB−TT       = +0.0009642178 s
论文代码喂给 DE200 的偏移 = +83.3084199 s
```

同一 DE200、同一 GCRS 卫星位置：

```text
论文代码 BCRS satellite position
[-112089814.98666005,
   87509670.23574984,
   37921311.96375863] km

修正时间单位后
[-112088169.53376675,
   87511413.50405256,
   37922067.80018316] km
```

欧氏位置差：

\[
2513.5211\ \mathrm{km}.
\]

几何时延：

```text
paper-code  -277.9236602398 s
corrected   -277.9305272693 s
absolute diff 6.867029 ms
```

## 3.2 Q3 数值影响

MJD(TT)=58119.1651507519：

```text
真实近似 TDB−TT       = -71.4458 μs
论文代码喂给 DE200 的偏移 = -6.1729143 s
```

BCRS satellite position difference：

\[
186.9181\ \mathrm{km}.
\]

几何时延：

```text
paper-code  -473.8840130407 s
corrected   -473.8838374526 s
absolute diff 0.175588 ms
```

结论：

> Q2/Q3 的 DE ephemeris 查询时刻存在单位错误，误差远大于论文重点展示的 ns/μs 小项。

---

# 4. 路径差：数字是 m，正文标签写 km

## Q2

论文：

```text
Δdgeo = -83319417239.6452 km
```

但 code：

```python
ds = -dot(r_km,n)*1e3 # m
```

最终：

\[
\frac{-8.3319417\times10^{10}\ m}{c}
=-277.92366\ s.
\]

所以该数字实际单位：

```text
m
```

而不是 km。

## Q3

同样：

```text
-142066853076.386...
```

实际是 m，正文标成 km。

### 识别办法

任何传播路径/时延结果做一次：

\[
|d|/c
\]

数量级 back-check。

1 AU / c ≈ 499 s，因此 BCRS Roemer delay 的百秒级结果意味着投影距离应是 `10^8 km` 或 `10^11 m`，不会是 `10^11 km`。

---

# 5. Q3 Earth / satellite z 中间量抄录错误

DE200 查询得到：

```text
EMB z         = 57,890,210.3794789 km
Earth/EMB z   = -1,451.1329569 km
```

因此：

```text
Earth/SSB z = 57,888,759.2465220 km
```

卫星 GCRS：

```text
+6,507.2626553 km
```

所以：

```text
Satellite/SSB z = 57,895,266.5091774 km
```

论文式 (5.9) 把后者提前写成 Earth z；式 (5.10) 再次写成 satellite z。

公开代码返回 satellite z = `57,895,266.5091774 km`，因此：

> 数值程序的 satellite state 没有因此错；错误位于正文中间结果记录。

---

# 6. “引力红移时延”量纲审计

论文：

\[
\Delta t=-\frac{GM_\odot}{r c^2}.
\]

SI：

```text
GM       m^3 s^-2
r        m
c^2      m^2 s^-2
```

所以：

\[
[GM/(rc^2)]=1.
\]

结果无量纲。

论文/代码给：

```text
-9.979327322105222e-9 s
```

这里的 `1e-8` 恰好就是太阳势 `U/c²` 常见的**钟速率相对修正量级**，但不能不经时间积分直接变成秒。

### 修正框架

若从弱场钟速率出发：

\[
\frac{d\tau}{dt}
\simeq1-\frac{U}{c^2}-\frac{v^2}{2c^2},
\]

要得到秒：

\[
\Delta t=\int\left(\frac{U}{c^2}+\frac{v^2}{2c^2}\right)dt.
\]

或者采用标准 TT/TCG/TCB/TDB conversion，不手工拆一个没有时间积分的 redshift term。

---

# 7. 动钟项：三层不一致

正文式 (5.5)：

\[
-2\frac{\mathbf r_{SSB}\cdot\mathbf v_{SSB}}{c^2}.
\]

函数：

```python
return +2*dot(p,v)/c**2
```

主程序：

```python
# BCRS call commented out
calculate_specialrelativity_delay(p_sate_GCRS, v_sate_GCRS)
```

因此：

| 层次 | sign | frame |
|---|---|---|
| 正文 | negative | SSB/BCRS |
| function | positive | generic |
| actual call | positive | GCRS |

实际输出：

\[
-7.02705\times10^{-10}s
\]

完全来自 GCRS `r·v`。

若把同一函数传入代码已经算出的 BCRS state：

\[
+1.73764\times10^{-2}s.
\]

这不代表后者是正确物理答案，只说明：

> **参考系选择会让该经验式的数值改变七个数量级，而论文没有解决这个一致性问题。**

---

# 8. Q4 标准 profile 的周期边界

附件 2：

```text
256 points
phase = 1/512, 3/512, ..., 511/512
```

即采样点是 phase-bin centers，不包含 0 和 1。

原始数据梯形积分约：

\[
1.0000000000002.
\]

说明它按题意接近归一化轮廓。

但公开代码：

```python
cs = CubicSpline(phi_x,h_y)
```

默认不是 periodic spline。

而 `phase % 1` 可以落在：

```text
[0, 1/512)
以及
(511/512, 1)
```

因此这两个边缘区间实际是 spline extrapolation，不是周期 wrap。

### 必须检查

```python
phi = dense_grid(0,1)
h = periodic_profile(phi)
assert min(h) >= 0
assert integral(h) ≈ 1
```

---

# 9. Linear interpolation baseline 的确定性代码错误

公开代码：

```python
(h2-h1)/(phi1-phi2)*(phi-phi1)+h1
```

正确：

```python
(h2-h1)/(phi2-phi1)*(phi-phi1)+h1
```

复现：

```text
buggy linear Pearson   = 0.99042015
paper Table 6.1        = 0.99042
```

说明表中 linear 结果确实与这个错误实现高度一致。

错误版在某些相位甚至得到：

```text
total λ(t) < 0
```

这对 Poisson intensity 在数学上是不允许的。

同 seed 修正线性插值后：

```text
Pearson ≈ 0.99375
```

已经不低于论文 cubic 的 `0.99351`。

结论：

> 不能用表 6.1 证明 cubic 优于 linear。

---

# 10. 原递推 NHPP 近似

公开代码：

```python
t_next = t - log(U)/lambda(t)
```

只有当下一个 waiting interval 内 `λ(s)` 变化不大时才近似合理。

严格条件应由：

\[
\Lambda(t_{next})-\Lambda(t)=-\ln U
\]

决定。

所以 low-flux 时 waiting time 增长，强度变化不能忽略，原论文提出改进是有理论动机的。

---

# 11. A.6 改进法：代码正确类型 vs 论文错误解释

公开 A.6：

```python
I = Poisson(Lambda_T)
U = Uniform(0,1,I)
tau = Lambda_T*U
t = inverse_Lambda(tau)
sort(t)
```

这是标准 conditional order-statistics NHPP sampler。

论文证明却写：

```text
tau_(i+1)-tau_i = R
R ~ Uniform(0,1)
所以 interval ~ Exp(1)
```

逻辑不成立。

### 两套正确理论不要混

**Time change：**

```text
Exp(1) waiting times
→ cumulative homogeneous arrival times
→ inverse Lambda
```

**Conditional order statistics：**

```text
N ~ Poisson(Lambda_T)
→ N iid Uniform points on cumulative-intensity interval
→ sort
→ inverse Lambda
```

A.6 属于后者。

---

# 12. Pearson 验证的逻辑边界

生成器本身：

\[
\lambda(\phi)=a+b h(\phi).
\]

折叠的大样本期望也是：

\[
E[profile(\phi)]\propto a+b h(\phi).
\]

Pearson：

\[
Corr(h,a+bh)=1\quad(b>0).
\]

因此 0.99+ 不出人意料。

它真正反映的是：

```text
finite-sample noise
+ binning
+ interpolation
+ sampler numerical error
```

而不是：

```text
真实 Crab 物理模型已被独立验证
```

---

# 13. χ² 实现 bug

理论：

\[
\chi^2=\sum_i\frac{(O_i-E_i)^2}{E_i},
\qquad E_i=np_i.
\]

代码：

```python
(O_i-n*p_i)**2/n*p_i
```

Python 左结合后：

\[
\frac{(O_i-E_i)^2}{n}\,p_i.
\]

理论需要：

\[
\frac{(O_i-E_i)^2}{n p_i}.
\]

所以论文的 `χ²=24.98915` 不是其公式对应的统计量。

另外经典 Pearson χ² 要求 expected count 不能大量过小，尾部必须合理合并；原代码没有满足这一前提。

---

# 14. 更强的 NHPP evaluator

## Count calibration

重复 M 次：

\[
\bar N\approx\Lambda(T),
\quad s_N^2\approx\Lambda(T).
\]

## Window calibration

对多个窗口：

\[
N(a,b)\sim Poisson(\Lambda(b)-\Lambda(a)).
\]

## Time rescaling

\[
z_i=\Lambda(t_i)-\Lambda(t_{i-1})
\overset{iid}{\sim}Exp(1).
\]

检查：

```text
KS
QQ plot
mean ≈1
variance ≈1
ACF ≈0
```

## Profile

```text
Pearson
RMSE
peak phase error
peak amplitude error
confidence band over seeds
```

---

# 15. 最终硬门槛

```text
[ ] every quantity has unit
[ ] every vector has frame
[ ] every epoch has time scale
[ ] seconds never directly add to JD
[ ] distance back-check via d/c
[ ] every delay formula passes dimensional analysis
[ ] no same effect double-counted in time conversion and delay terms
[ ] h(phi) periodic and nonnegative
[ ] lambda(t) nonnegative
[ ] baseline interpolation unit-tested
[ ] NHPP sampler tested by time rescaling
[ ] Monte Carlo metric reported mean±std, not one lucky seed
```

---

# 16. 一句话

> **物理随机过程题最危险的错误往往不是复杂公式不会推，而是秒和天、m 和 km、GCRS 和 BCRS、Uniform 和 Exponential 这些“基础对象”在不同章节悄悄换了身份。**
