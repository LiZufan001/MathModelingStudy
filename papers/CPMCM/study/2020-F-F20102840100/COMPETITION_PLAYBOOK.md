# 比赛速查：从 F20102840100 提炼的“机理 + 动态优化”打法

> 适用：题目同时出现**物理状态、连续时间/时序数据、控制变量、离散开关、多目标或最坏值目标**时。典型场景包括能源、液体、储能、热管理、水库、姿态控制、生产控制等。

---

# 0. 看到这些关键词就联想到本篇

若题目有 4 项以上，优先考虑本框架：

- 质量/能量守恒；
- 几何位置会随状态改变；
- 连续供给/消耗；
- 设备开关；
- 最短运行时间；
- 多资源同时工作数量限制；
- 目标是全过程最大误差；
- 需要输出完整时序策略；
- 第二/三问新增初始条件或外层设计变量；
- 姿态/环境随时间变化。

核心口诀：

> **mechanism first → simulator second → controller third → optimizer last**

---

# 一、开题第一阶段：官方条件和自加假设必须分栏

立即做一张表：

| 条件 | 官方给定 | 我们增加 | 为什么需要 | 是否会缩小可行域 |
|---|---|---|---|---|
| 流量上限 | ✓ | | | |
| 最短持续时间 | ✓ | | | |
| 固定控制周期 T | | ✓ | 降维 | 是 |
| 流量比例离散 | | ✓ | 降维 | 是 |

**任何“我们自己加的条件”都不能悄悄混进题意。**

尤其是：

```text
官方允许 >=
我们改成 ==
```

这种变化一定要做对照实验。

---

# 二、先找系统中最难、最常被调用的物理函数

2020 F 中是：

```text
fuel_mass + attitude -> fuel centroid
```

其他题可能是：

```text
temperature + power -> efficiency
flow + pressure -> network state
SOC + current -> battery voltage
water level + release -> storage
position + load -> deformation
```

问自己：

> 后面的优化器每评估一次方案，最核心要调用哪个函数？

这个函数优先做到：

- 正确；
- 快；
- 可测试；
- 可解释。

---

# 三、能解析就先解析，别默认数值黑箱

寻找：

- 对称性；
- 降维；
- 分段；
- 几何组合；
- 守恒关系；
- 无量纲化。

如果能把数值积分换成解析公式，后续优化速度可能提升几个数量级。

但解析模型必须做 independent check：

```text
解析解 vs 高精度数值法
```

随机多点比较，而不是只看曲线连续。

---

# 四、把系统写成状态转移，而不是散落变量

模板：

\[
S_{t+1}=F(S_t,u_t,w_t).
\]

例如：

```python
State = {
    "time": ...,
    "inventory": ...,
    "machine_status": ...,
    "remaining_min_on": ...,
    "environment": ...,
}
```

动作：

```python
Action = {
    "on_off": ...,
    "flow": ...,
}
```

唯一接口：

```python
next_state = transition(state, action)
```

### 绝对不要

```python
c_oil = update(oil)
score = evaluate(oil, c_oil)   # 新旧状态混用
```

---

# 五、先写硬约束检查器

```python
def check_action(state, action):
    ...
```

检查：

- 上下界；
- 容量；
- 同时运行数量；
- minimum-up/down time；
- 流量守恒；
- 库存非负；
- 时域完整。

优化器只允许从合法动作中选。

> **硬约束由 simulator 保证，目标函数只负责比较合法解。**

---

# 六、题目说“最大误差最小”时的标准写法

目标：

\[
\min_u\max_t e_t.
\]

引入辅助变量：

\[
\min Z
\]

s.t.

\[
e_t\le Z,\quad\forall t.
\]

这是 minimax / epigraph 思维。

别看到轨迹误差就条件反射写 MSE。

---

# 七、先做一个 100% 合法的 baseline

第一版不要求高分。

目标：

```text
完整跑完
没有非法状态
结果表能输出
评价器能验分
```

baseline 可以很简单：

- 固定优先级；
- 最近目标；
- 最小即时误差；
- 均匀分配；
- rule-based controller。

**没有 baseline，就没法证明后续算法真的有用。**

---

# 八、全时域搜不动时：先优化“策略类”

不要直接让 GA 编码 7200 秒每秒动作。

把策略压缩成：

```text
控制周期 T
资源组合 G
流量比例 alpha
阈值 beta
优先级权重
```

从：

\[
O(A^N)
\]

缩成每块有限候选。

但论文必须说清：

> 求的是受限策略空间内的好解。

---

# 九、滚动贪心的标准 baseline

```text
当前状态 S
 ↓
枚举当前合法动作
 ↓
模拟未来一个块
 ↓
算块内最坏误差
 ↓
选最优动作
 ↓
更新 S
```

优点：

- 快；
- 稳；
- 可解释；
- 易实现；
- 易输出完整方案。

缺点：

> **myopic。**

当前最优可能消耗掉未来最需要的资源。

---

# 十、baseline 不够时的升级顺序

建议按复杂度逐步增加：

1. 更细的连续参数搜索；
2. 改控制周期；
3. 增加未来资源余量惩罚；
4. 2~5 block look-ahead；
5. beam search；
6. rolling-horizon NLP/MILP；
7. 外层优化策略参数；
8. 小规模精确求解做 reference。

不要一步跳到巨型 GA。

---

# 十一、连续比例变量不要轻易粗离散

两个资源共同满足需求：

\[
u_1+u_2=d.
\]

只需要一个：

\[
u_1=\alpha d,
\quad
u_2=(1-\alpha)d.
\]

`α` 是一维变量。

可用：

- bounded scalar search；
- 黄金分割；
- coarse-to-fine；
- 0.1 → 0.02 局部细化。

这通常比固定 `[0.1,...,0.9]` 更划算。

---

# 十二、官方给的额外自由度要做“值不值得用”实验

例如允许：

\[
q(t)\ge demand(t).
\]

不要未经实验就改成：

\[
q(t)=demand(t).
\]

至少比较：

| 策略 | 最大误差 | 额外耗油 | 计算量 |
|---|---:|---:|---:|
| 不允许额外操作 | | | |
| 允许额外操作 | | | |

然后才有资格说“为了简化，我们采用……”。

---

# 十三、遇到“初始状态也可设计”的后续问

不要只优化初始时刻指标。

错误倾向：

```text
先让 t=0 最好
再跑控制器
```

更强：

```text
outer optimizer
    ↓
initial state
    ↓
full controller simulation
    ↓
whole-horizon objective
```

即：

\[
\min_x J(x,\pi(x)).
\]

外层可以用：

- DE；
- CMA-ES；
- Bayesian optimization；
- PSO。

---

# 十四、用 DE/GA 时必须留下什么证据

论文至少记录：

```text
population size
mutation / inertia
crossover
iterations
stopping rule
random seed
number of repeats
runtime
best/mean/std
```

再给一张收敛曲线。

不要用半页介绍“遗传算法是什么”，却不给自己的超参数。

---

# 十五、参数扫描和“拟合”不是一回事

如果只是：

```text
x=1 → y1
x=2 → y2
x=3 → y3
```

这叫：

> 参数扫描 / 离散实验。

只有真正：

- 建拟合函数；
- 给拟合指标；
- 求连续极值

才叫拟合优化。

写作术语要准确。

---

# 十六、评委最想看到的验证矩阵

## 16.1 物理正确性

```text
守恒：PASS
容量：PASS
单位：PASS
已知样例：PASS
```

## 16.2 数值模型

```text
解析解 vs 数值法
```

## 16.3 算法效果

| 方法 | max error | runtime |
|---|---:|---:|
| baseline | | |
| greedy | | |
| improved | | |

## 16.4 消融

```text
去掉 look-ahead
去掉额外自由度
粗网格 vs 细网格
```

## 16.5 最优性参考

小窗口精确解：

\[
gap=\frac{J-J_{ref}}{J_{ref}}.
\]

---

# 十七、完整时域一定要覆盖

若 horizon = `H`，block size = `T`：

```python
start = 0
while start < H:
    end = min(start + T, H)
    solve(start, end)
    start = end
```

不要通过：

```python
while start + T <= H
```

默默丢掉尾段。

也不要正文说 `T | H`，代码却取消整除条件。

---

# 十八、所有关键数字自动生成

比赛后期最容易出现：

```text
8080.17467 -> 手工写成 8080.1467
```

建议最终脚本直接生成：

```text
results.md
summary.json
latex_table.tex
```

摘要、正文表格从同一个 `summary.json` 取数。

至少在冻结前自动 assert：

```python
assert abs(sum(initial)-reported_total) < tol
assert abs(total_supply-total_demand-dumped) < tol
```

---

# 十九、论文故事线模板

适合机理 + 优化题：

```text
1. 为什么现象复杂
2. 基础机理模型
3. 独立验证机理模型
4. 状态与官方约束
5. baseline 控制器
6. 规模问题与策略降维
7. 改进优化方法
8. 后续问题通过增加设计变量自然扩展
9. 验证 / 消融 / 敏感性 / runtime
10. 优缺点
```

不要写成：

```text
Q1 用 A 算法
Q2 用 B 算法
Q3 用 C 算法
Q4 用 D 算法
```

那样很容易散。

---

# 二十、赛场 15 分钟终检

- [ ] 官方约束和自加假设是否分清？
- [ ] 有没有擅自把 `>=` 改成 `==`？
- [ ] 所有单位统一吗？
- [ ] 状态更新后评价函数是否只读新状态？
- [ ] minimum-on/off time 真正满足吗？
- [ ] 最后一个不完整时间块处理了吗？
- [ ] 经验参数有来源吗？
- [ ] baseline 保存了吗？
- [ ] improved 真比 baseline 好吗？
- [ ] 是否有独立模型验证？
- [ ] 是否有至少一个最优性参考？
- [ ] 外层优化目标和原题目标一致吗？
- [ ] 摘要数字与结果表自动核对了吗？
- [ ] 随机算法能否复现？
- [ ] 所有输出文件重新读回验收了吗？

---

# 二十一、一句话记忆

从 2020 F 真正应该记住：

> **先把“状态如何决定物理结果”做成可信模型，再把“大而难的控制问题”压缩成可算策略；但所有主动降维都必须用对照实验说明代价，所有优化结果都要同时证明“合法”和“确实更好”。**
