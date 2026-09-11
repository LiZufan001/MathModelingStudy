# COMPETITION_PLAYBOOK｜主观评价 / 空间体验 / 多指标美学题速查

适用：美学、舒适度、趣味性、空间体验、景区路线、服务质量、城市活力等“软概念 + 硬附件”赛题。

---

# 1. 20 分钟开题框架

先画：

```text
Concept
→ Mechanism
→ Observable
→ Metric
→ Decision
→ Validation
```

禁止直接：

```text
Concept
→ AHP
→ Score
```

---

# 2. 软概念四拆

- 状态：当前是什么；
- 变化：前后差多少；
- 结构：整体怎么组织；
- 决策：人在里面怎么行动。

每个概念最多先放 2–4 个机制，别一上来 30 个指标。

---

# 3. 路径体验模板

\[
I(P)=\sum_t[\alpha D(s_t,s_{t+1})+\beta Surprise_t]-\gamma Repeat(P).
\]

其中：

\[
Surprise_t=-\log P(s_{t+1}|s_t).
\]

路径算法优先级：

```text
Dijkstra/A* baseline
→ λ sweep
→ Pareto
→ NSGA-II（真需要再上）
```

---

# 4. “过少过多都不好”模板

\[
S(x)=\exp[-(x-x^*)^2/\sigma^2].
\]

不要强行把所有指标都正向化。

---

# 5. benchmark 标定模板

题面指定参考对象时：

```text
benchmark
→ 参数/阈值校准
→ freeze
→ 其他对象评分
```

新对象验证不能重新调参。

---

# 6. 权重模板

\[
w(\lambda)=\lambda w_{AHP}+(1-\lambda)w_{CRITIC}.
\]

至少 sweep：

\[
\lambda=0,0.2,\ldots,1.
\]

报：

- Kendall τ；
- top-k 稳定率；
- rank flips。

---

# 7. 指标防作弊四问

- 拆成更多段会不会刷高？
- 路线更长会不会天然刷高？
- 重复复制一个高度相关指标会不会刷高？
- 样本更多会不会机械提高多样性？

任何一个“会”，先修指标。

---

# 8. 相似度红旗

若：

\[
S_{ij}\text{ 全都很接近 1},
\]

不要高兴，先查：

- feature collinearity；
- cosine concentration；
- duplicate features；
- normalization。

必须加 null-permutation baseline。

---

# 9. 没有真值的四层验证

```text
mechanism consistency
+ naive baseline
+ sensitivity / robustness
+ frozen-parameter external validation
```

能做专家/用户 pairwise survey，再加第五层。

---

# 10. 图表最小配置

1. 概念→机制流程图；
2. feasible/navigation graph；
3. 局部状态/视域示意；
4. 路径变化曲线；
5. Pareto front；
6. 单指标相关矩阵；
7. 综合评分+置信区间；
8. sensitivity/rank stability；
9. similarity network/PCA；
10. new-object validation。

---

# 11. 赛末 10 分钟硬检查

- [ ] 每个指标能对应题面机制吗？
- [ ] 单位/方向/适量关系写清了吗？
- [ ] 高相关指标去重了吗？
- [ ] 权重来源和敏感性有吗？
- [ ] 优化目标能被路线长度刷分吗？
- [ ] 新对象是否冻结参数？
- [ ] 相似度是否有区分度？
- [ ] 评分是否给不确定性？
- [ ] 高级算法有没有真实结果，不只是公式？
- [ ] 摘要数字能从正文表格一键追溯吗？

---

# 12. 一句话

> **先把主观词变成可观察机制，再设计防作弊指标；能保留多目标就别急着压成一个分数，必须加权就做主客观组合与敏感性；最后用机制、基线、扰动和外对象四层证据告诉评委：这个“美学分数”不是我们拍脑袋拍出来的。**
