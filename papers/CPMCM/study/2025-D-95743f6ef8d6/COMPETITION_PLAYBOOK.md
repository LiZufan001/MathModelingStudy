# COMPETITION_PLAYBOOK｜多源融合 + NWP 校正 + 风险航路速查

适用：

- 多源气象/环境监测；
- 稀疏观测三维场；
- 数值模式偏差校正；
- 短临预测；
- 风险地图上的路径规划。

---

# 1. 先固定“主风险量”

全文只能有一个主状态：

```text
TKE / EDR / calibrated risk index / turbulence proxy
```

其他量：

```text
Ri
SW
shear
variance
```

只能是 features / diagnostics。

不要在章节间把不同物理量都叫“湍流强度”。

---

# 2. 多源融合六步

```text
1 coordinate
2 time
3 unit
4 QC
5 observation operator
6 uncertainty
```

然后再：

```text
OI / 3DVAR / Kalman
```

---

# 3. Reference model 用语

推荐：

- best-available reference；
- pseudo-label；
- high-information estimate。

谨慎：

- truth；
- ground truth。

---

# 4. 一个比赛够用的 3DVAR

\[
J(x)=
\frac12(x-x_b)^TB^{-1}(x-x_b)
+
\frac12(y-Hx)^TR^{-1}(y-Hx)
+
\lambda\|Lx\|^2.
\]

至少解释：

- `B` correlation length；
- `R` sensor error；
- `L` smoothness；
- λ 如何选。

---

# 5. 100m 网格固定措辞

写：

> output on a 100 m analysis grid。

不要直接写：

> achieved 100 m real resolution。

必须同时给 uncertainty / observation density。

---

# 6. NWP 一定先做 bias correction

最小模板：

\[
r^{cal}=a(z)+b(z)r^{raw}.
\]

数据够再：

\[
r^{cal}=a(z)+b(z)r^{raw}+c(z)(r^{raw})^2.
\]

验证：

```text
past fit
future validate
```

不能随机 K-fold 当主结果。

---

# 7. Forecast baseline 顺序

必须先跑：

```text
persistence
linear trend
moving average
exponential smoothing
multivariate regression
```

再决定是否上：

- LSTM；
- Transformer；
- GNN。

数据短时，简单模型赢很正常。

---

# 8. Extreme-event evaluator

平均 RMSE 之外：

\[
I>I_{crit}
\]

报告：

```text
POD / Recall
FAR
CSI
Brier
lead time
```

安全问题最怕“平均很准，峰值全漏”。

---

# 9. Forecast uncertainty

至少做 ensemble：

\[
\mu=\sum w_m\hat x_m,
\]

\[
\sigma^2=\sum w_m(\hat x_m-\mu)^2.
\]

权重建议：

\[
w_m\propto1/(RMSE_m^2+\epsilon).
\]

比直接按 `R²` 正归一化更稳。

---

# 10. Path cost 先无量纲

\[
J=
\lambda_L\frac{L}{L_0}
+
\lambda_R\frac{R}{R_0}
+
\lambda_M\frac{M}{M_0}.
\]

不要直接：

```text
meters + TKE + degree
```

生加。

---

# 11. 安全航路三级模板

## Level 1

\[
\min L+\lambda E[R].
\]

## Level 2

\[
\min L+\lambda CVaR_{0.95}(R).
\]

## Level 3

\[
P(\max R\le R_{crit})\ge1-\delta.
\]

至少做到 Level 2，就比“绕开红色区”更有说服力。

---

# 12. A* 必查 admissibility

构造：

\[
h(n)=c_{min}d_{euclid}.
\]

确保：

\[
h\le J^*_{remain}.
\]

然后才写：

> discrete graph 下 A* global optimum。

边界必须同时写：

> 不等于连续真实飞行器动力学下绝对最优航迹。

---

# 13. 路径最少对照

```text
straight
shortest-distance
mean-risk A*
CVaR A*
chance A*
```

表格：

| path | length | avg risk | max | q95/CVaR | exceed prob | time |
|---|---:|---:|---:|---:|---:|---:|

---

# 14. 禁止公式注水

模型写进主文前问：

- 有输出吗？
- 有结果吗？
- 有对照吗？
- 改变结论了吗？

四个都没有：

> 删掉，放 future work。

---

# 15. 禁止 synthetic fallback 混主程序

正式程序：

```python
assert real_data_loaded
```

演示数据：

```text
demo/
```

物理数据缺失必须 fail loudly。

---

# 16. 摘要数字回链

摘要每一个数字必须有：

```text
result_id
→ table/figure
→ script
```

没有正文出处的 `82% / 35%` 一律删。

---

# 17. 20 分钟赛末检查

- [ ] 主风险量统一了吗？
- [ ] reference 没叫 truth 吧？
- [ ] metric range/unit 对得上吗？
- [ ] train/test 没随机泄漏时间吧？
- [ ] 100m 是 analysis grid 还是实际 resolution？
- [ ] NWP 是用过去校正未来吗？
- [ ] extreme event recall 报了吗？
- [ ] uncertainty 传给 route 了吗？
- [ ] A* heuristic 证明了吗？
- [ ] route baseline 同 evaluator 吗？
- [ ] 摘要数字都能回链吗？
- [ ] 无结果公式删了吗？

---

# 一句话

> **多源融合题最强的写法不是把 3DVAR、Kalman、LSTM、A* 全放进去，而是让每一个观测带着误差进入状态估计，让每一个预报带着概率进入路径规划，再用真正的未来验证和统一 route evaluator 证明系统从“看得见”走到了“飞得安全”。**
