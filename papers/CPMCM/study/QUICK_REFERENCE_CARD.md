# 华为杯正赛速查卡｜卡住时先翻这里

> 这是 `COMPETITION_MASTER_PLAYBOOK.md` 的极限压缩版。  
> 用法：比赛现场卡住时按“症状 → 第一动作”查，不从头阅读。

---

# 1. 题刚拿到

先写：

```text
输入
输出
官方指标
hard constraints
独立样本单位
单位/时间/空间尺度
baseline
最大风险
```

然后问：

> **如果只能做一个最简单但完全可信的版本，它是什么？**

---

# 2. 症状 → 第一动作

| 症状 | 第一动作 |
|---|---|
| 规则极多、调度很乱 | 先写 simulator / legal action generator |
| 搜索空间爆炸 | 先找层次结构、聚类、分块、等价类 |
| 不知道近似解好不好 | 算 lower bound / relaxation |
| ML 分数很好 | 先查 split / leakage / majority baseline |
| 时间序列很好看 | 改成过去→未来的 blocked split |
| 分类严重偏一类 | 报 macro-F1 / balanced accuracy / confusion matrix |
| 图像检测已经完成 | 继续问 pixel→physical quantity 怎么标定 |
| 插值三维图很漂亮 | 查 effective resolution / observation density |
| 物理结果很多小数 | 查单位、参考系、量级、invariant |
| NWP/仿真直接进决策 | 先做 bias calibration / uncertainty |
| 路径规划想上 ACO/GA | 先跑 Dijkstra/A* baseline |
| 综合评价想上 AHP | 先把软概念拆成可观察机制 |
| 权重不知道怎么定 | AHP + 客观权重 + sensitivity |
| 两目标冲突 | 先画 Pareto，不急着加权 |
| 结果“概率” | 先定义随机事件是什么 |
| 结果全都相似度 0.98+ | 查高维饱和、共线、null baseline |
| 模型不断加复杂度 | 查是否真的解决了一个已知失败模式 |
| 快到交稿还想换模型 | 停；补验证、图表、审计 |

---

# 3. 七个强制接口

任何方案都要有：

```text
1. official_score()
2. check_feasibility()
3. baseline()
4. split_protocol
5. unit/frame ledger
6. sensitivity/ablation
7. single-source results export
```

少一个，就优先补它，而不是加新算法。

---

# 4. 各题型最稳主线

### 调度/排样

```text
feasibility → lower bound → greedy → repair → local search
```

### 物理/动态

```text
unit ledger → mechanism evaluator → baseline → optimize → invariant
```

### 数据预测

```text
group/time split → simple baseline → features → model → error analysis
```

### 矩阵/复杂度

```text
cost ledger → structure → exact baseline → approximation → error-cost
```

### 图像/视频

```text
pixel → calibration → physical state → downstream task → end-to-end validate
```

### 多源场/航路

```text
QC → fusion → uncertainty → forecast calibration → A* → risk-aware route
```

### 主观评价

```text
concept → mechanism → anti-gaming metric → calibration → sensitivity → external object
```

---

# 5. 数据切分三条铁律

1. 同一实验/人/订单/设备产生的多行不能拆到 train/test 两边；
2. 时间序列只能过去预测未来；
3. scaler/PCA/feature selection/resampling 必须只在 train fold fit。

---

# 6. 每问至少给评委四类证据

```text
Baseline
Feasibility / invariant
Sensitivity / ablation
Independent / worst-case validation
```

如果没有真值，至少做到：

```text
理论应然关系
+ baseline
+ 参数扰动
+ 冻结参数的新对象
```

---

# 7. 最后 12–18 小时禁止做的事

- 新增一个未经验证的大模型；
- 为了“高级”把简单模型全部换掉；
- 人工改正文数字但不更新结果源；
- 新增大量无实验支撑的公式；
- 重新定义 evaluator；
- 只看最终分数、不跑 feasibility。

允许：

```text
修 bug
补验证
补 baseline
补敏感性
补图
修解释
统一数字
排版
```

---

# 8. 最后一句

> **先证明结果是真的，再证明方法很强。**
