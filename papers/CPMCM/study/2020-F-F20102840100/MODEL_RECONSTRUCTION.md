# F20102840100 模型与算法重构

> 目的：把论文的四问重新整理成一套统一、可复现、可扩展的“机理状态模型 + 混合动态优化”框架。本文不是逐字转述原论文；对原文中不够严谨或实现口径不一致的地方，采用原题约束重新定义。

---

# 1. 总体结构

统一把系统写成：

\[
\text{状态 }S_t
\xrightarrow{\text{供油动作 }u_t}
S_{t+1}
\xrightarrow{\text{几何/质量模型}}
\mathbf c_t
\xrightarrow{\text{目标}}
J.
\]

其中：

- `S_t`：6 个油箱剩余油量、开关持续时间、飞行姿态等；
- `u_t`：各油箱此时的供油/转移流量；
- `c_t`：当前整机质心；
- `J`：全时域最大质心偏差。

四问只是对这个统一模型开放不同变量：

| 问题 | 已知 | 决策/求解 |
|---|---|---|
| Q1 | 油量轨迹、俯仰角 | 计算质心 |
| Q2 | 初始油量、理想质心轨迹 | 供油策略 |
| Q3 | 发动机需求 | 初始油量 + 供油策略 |
| Q4 | 初始油量、俯仰角轨迹 | 供油策略，使质心接近原点 |

---

# 2. 状态变量

设 6 个油箱在时刻 `t` 的燃油质量为：

\[
\mathbf m(t)=
[m_1(t),m_2(t),\ldots,m_6(t)]^T.
\]

定义主油箱对发动机供油速度：

\[
u_2,u_3,u_4,u_5\ge0,
\]

备用油箱转移速度：

\[
u_1\;(1\rightarrow2),\qquad
u_6\;(6\rightarrow5).
\]

离散时间步长为 `Δt` 时，质量状态转移可写成：

\[
\begin{aligned}
m_1(t+1)&=m_1(t)-u_1(t)\Delta t,\\
m_2(t+1)&=m_2(t)+u_1(t)\Delta t-u_2(t)\Delta t,\\
m_3(t+1)&=m_3(t)-u_3(t)\Delta t,\\
m_4(t+1)&=m_4(t)-u_4(t)\Delta t,\\
m_5(t+1)&=m_5(t)+u_6(t)\Delta t-u_5(t)\Delta t,\\
m_6(t+1)&=m_6(t)-u_6(t)\Delta t.
\end{aligned}
\]

任何策略都必须通过这一唯一 `transition()` 更新状态。

---

# 3. 油箱燃油质心函数

对第 `k` 个油箱，定义：

\[
\mathbf r_k
=
G_k(m_k,\theta),
\]

其中：

- `m_k`：燃油质量；
- `θ`：飞行器俯仰角；
- `G_k`：问题一推导出的分段解析几何函数。

## 3.1 为什么使用分段解析几何

矩形油箱在 `x-z` 截面中随液面位置和倾角产生若干拓扑区域：

```text
矩形
三角形
梯形 A
梯形 B
五边形
...
```

对每一种区域：

1. 根据面积守恒由油量求液面位置；
2. 把液体区域拆成矩形/三角形等简单图形；
3. 利用组合图形质心：

\[
\bar x=\frac{\sum_i A_i x_i}{\sum_i A_i},\qquad
\bar z=\frac{\sum_i A_i z_i}{\sum_i A_i};
\]

4. 再由油箱局部坐标变换到飞行器坐标。

这使 `G_k` 成为一个高频可调用、无数值积分步长误差的计算模块。

## 3.2 建议的实现接口

```python
def tank_fuel_centroid(tank, fuel_mass, theta):
    assert 0 <= fuel_mass <= tank.capacity_mass
    region = classify_region(tank, fuel_mass, theta)
    local = analytic_centroid(region, tank, fuel_mass, theta)
    return transform_to_aircraft(local, tank, theta)
```

### 必须测试

- 空油箱；
- 满油箱；
- `theta=0`；
- 正负临界角两侧；
- 区域切换临界油量；
- 与高精度网格积分对照。

---

# 4. 整机质心

空机质量为 `M0`，质心为原点，则：

\[
\mathbf c(t)=
\frac{
\sum_{k=1}^{6}m_k(t)G_k(m_k(t),\theta(t))
}{
M_0+\sum_{k=1}^{6}m_k(t)
}.
\]

若空机质心不是原点，则把 `M0 r0` 加入分子即可。

这一函数应成为整个工程的**唯一质心真源**：

```python
def aircraft_centroid(state):
    ...
```

Q1/Q2/Q3/Q4 都只能调用它，不能各自复制一份公式。

---

# 5. 官方供油硬约束

## 5.1 流量上限

设题目给出的上限为 `U_i`：

\[
0\le u_i(t)\le U_i.
\]

原始附件给出：

\[
(U_1,U_2,U_3,U_4,U_5,U_6)
=(1.1,1.8,1.7,1.5,1.6,1.1)\ \mathrm{kg/s}.
\]

## 5.2 库存约束

\[
0\le m_k(t)\le C_k.
\]

备用油箱转入主油箱时也不能导致主油箱超容量。

## 5.3 同时供油数量

主油箱中最多 2 个同时向发动机供油：

\[
\sum_{i=2}^{5}z_i^{eng}(t)\le2.
\]

整个系统最多 3 个油箱同时发生供油：

\[
\sum_{i=1}^{6}z_i(t)\le3.
\]

## 5.4 最短连续供油时间

一旦油箱从关切换到开：

\[
\text{on-duration}\ge60s.
\]

这是典型 minimum-up-time 约束。

程序层面建议显式维护：

```python
remaining_min_on[i]
```

而不是靠分块长度顺带“近似满足”。

## 5.5 发动机需求与排油

官方条件：

\[
q(t)=u_2+u_3+u_4+u_5\ge d(t).
\]

定义排出的多余燃油：

\[
w(t)=q(t)-d(t)\ge0.
\]

原论文实际主要取 `w(t)=0`，这是一个额外简化，不是官方硬约束。

重构时必须保留 `w(t)`，再通过实验判断是否值得让它非零。

---

# 6. Q2 的统一 minimax 模型

给定理想质心：

\[
\mathbf c^*(t),
\]

目标：

\[
\min_{u,z}\max_t
\|\mathbf c(t)-\mathbf c^*(t)\|_2.
\]

引入辅助变量 `Z`，可写成 epigraph：

\[
\min Z
\]

满足：

\[
\|\mathbf c(t)-\mathbf c^*(t)\|_2\le Z,
\quad \forall t,
\]

再加所有流量、库存、并发、minimum-up-time 约束。

这比笼统写“二次混合优化”更准确地表达问题本质。

---

# 7. 原论文的策略空间降维

原问题太大，因此作者把每个时间块的动作压缩为：

\[
a_b=(G_b,\alpha_b,T),
\]

其中：

- `G_b`：当前块开启的油箱组合；
- `α_b`：多主油箱供油时的流量比例；
- `T`：块长度。

然后滚动：

```text
S_b
 ↓ enumerate candidate actions
simulate block
 ↓
evaluate block max deviation
 ↓
choose best a_b
 ↓
S_{b+1}
```

数学上，这等价于把原始控制空间：

\[
\mathcal U_{original}
\]

缩成一个小得多的：

\[
\mathcal U_{policy}\subset\mathcal U_{original}.
\]

因此真正求的是：

\[
\min_{u\in\mathcal U_{policy}}J(u),
\]

而不是严格意义上的：

\[
\min_{u\in\mathcal U_{original}}J(u).
\]

这一区分应该在论文中明确。

---

# 8. 原论文滚动贪心的干净伪代码

```python
state = initial_state
worst = 0

while state.time < horizon:
    actions = enumerate_feasible_block_actions(state)

    best = None
    best_value = INF

    for action in actions:
        next_state, trace = simulate_block(state, action)

        if not check_hard_constraints(trace):
            continue

        block_value = max(
            distance(centroid(s), target(s.time))
            for s in trace
        )

        if block_value < best_value:
            best_value = block_value
            best = (action, next_state, trace)

    execute(best)
    worst = max(worst, best_value)
    state = best.next_state

return worst
```

### 原方法的核心弱点

候选动作按：

\[
\max_{t\in block}e(t)
\]

比较，却没有显式估算 action 对未来状态可控性的影响。

---

# 9. 第一层升级：从一步贪心到 look-ahead

最简单升级：保留未来 `H` 个块。

\[
a_b^*=\arg\min_a
\left[
\max_{\tau\in b}e(\tau)
+\lambda\hat V(S_{b+1})
\right].
\]

`V` 可以用很粗的未来风险指标：

- 剩余各油箱可控余量；
- 左右/前后力矩储备；
- 主油箱距离空罐的安全裕量；
- 未来需求峰值下的最大可供流量。

即使不做完整动态规划，也能降低纯 myopic 贪心的问题。

---

# 10. 第二层升级：beam search

每个时间块不只保留 1 个当前最好状态，而是保留前 `K` 个：

```text
state set size = K
for each block:
    expand all feasible actions
    score candidate states
    keep best K
```

优点：

- 始终只生成合法状态；
- 比完整动态规划轻；
- 能修正“一步局部最好导致未来很差”；
- 很适合供油组合数量有限的场景。

比赛现场 `K=10~100` 往往就能提供很好的质量/速度折中。

---

# 11. 第三层升级：滚动时域优化 / MPC

对未来窗口 `W` 秒建立优化：

\[
\min Z
\]

s.t.

\[
\|c_t-c_t^*\|\le Z,
\quad t=t_0,\ldots,t_0+W,
\]

以及状态方程与硬约束。

只执行第一个控制段，然后窗口向前滚动。

这样：

- 不需要一次求完整 7200 s；
- 但每次决策能看见未来；
- 比纯贪心更有优化理论基础。

若几何函数过于非线性，可：

- 对当前油量附近局部线性化；
- 预计算质心 lookup table；
- 用 piecewise linear approximation；
- 对油箱组合离散、流量连续部分做小规模 NLP/QP。

---

# 12. 流量比例不应只硬枚举 0.1 网格

若确定某块由两个主油箱 `i,j` 同时供油，且不排额外燃油：

\[
u_i+u_j=d.
\]

只需一个连续比例变量：

\[
u_i=\alpha d,\qquad
u_j=(1-\alpha)d.
\]

满足流量上限即可确定 `α` 的合法区间。

然后在一维连续区间上：

- 黄金分割；
- bounded scalar optimization；
- coarse-to-fine grid

都比固定 0.1 步长更精细，计算量也很小。

如果开放排油，则再引入：

\[
q\ge d
\]

和总流量变量 `q`。

---

# 13. 备用油箱不该用未经说明的固定比例

原附录可见不同问题中有经验比例。

更一致的建模是把 `u_1,u_6` 直接作为控制量：

\[
0\le u_1\le1.1,
\qquad
0\le u_6\le1.1,
\]

并满足接收主油箱容量约束。

如果为了降维必须设：

\[
u_1=\beta u_2,
\]

那么 `β` 应：

1. 作为显式超参数；
2. 扫描范围；
3. 报告敏感性；
4. 或由外层优化器自动寻找。

不要让它变成藏在代码里的魔法数字。

---

# 14. Q3 的完整联合问题

Q3 不仅有控制 `u(t)`，还要选初始燃油：

\[
\mathbf m(0).
\]

完整形式：

\[
\min_{\mathbf m(0),u(t)}
\max_t\|c(t)-c^*(t)\|.
\]

约束包括：

\[
0\le m_k(0)\le C_k,
\]

以及末端剩余燃油：

\[
\sum_k m_k(T)\ge850\ \mathrm{kg}.
\]

作者用了“先初始分配、再动态控制”的 decomposition。

---

# 15. Q3 更推荐的 outer-inner 优化

若完整联合求解太大，可保留 decomposition，但外层目标必须改成全过程指标：

```python
def outer_objective(initial_fuel):
    result = run_controller(initial_fuel)
    return result.max_centroid_error
```

然后：

```text
DE / CMA-ES / Bayesian optimization
                ↓
6 个初始油量
                ↓
完整滚动控制仿真
                ↓
全过程最大偏差
```

这样外层真正优化的是题目目标，而不是“初始一秒看起来最好”。

### 约束处理

可把总油量显式参数化：

\[
\sum_km_k(0)=M_{fuel,0}.
\]

或者让总量本身也参与搜索，同时给剩余油量添加硬约束。

---

# 16. 原始数据一致性核验

对题目附件直接求和得到：

| 问题 | 发动机总需求 / kg | 论文报告主供油量 |
|---|---:|---:|
| Q2 | 6441.524211750931 | ≈6441.52421 |
| Q3 | 6805.174668678576 | 与正文采用的消耗量一致 |
| Q4 | 7035.545162954991 | ≈7035.54516 |

说明论文在总需求/总供油量这一层具有很好的数据自洽性。

Q3 最终初始配置之和约：

\[
8080.17467kg,
\]

减去发动机需求后约剩：

\[
1275kg=1.5m^3,
\]

满足题目至少 1m³ 的要求。

---

# 17. 全工程应该有的状态不变量

每个仿真步后断言：

```text
1. 0 <= tank_mass <= tank_capacity
2. every flow <= its cap
3. max 2 engine tanks active
4. max 3 total tanks active
5. newly opened tank satisfies >=60 s minimum-on duration
6. backup tanks never feed engine directly
7. engine inflow >= demand
8. mass conservation:
   previous fuel - engine consumption - dumped fuel
   == current fuel
9. time covers [0, 7200] completely
10. centroid uses the NEW state after transition
```

第 10 条专门防止 `oil / c_oil` 一类旧状态混用问题。

---

# 18. 验证计划

## 18.1 几何模型验证

随机生成：

```text
fuel_mass × theta
```

用解析公式与高精度数值积分比较。

报告：

- max absolute error；
- RMSE；
- 临界区域附近误差。

## 18.2 动力学守恒

人工构造一个 120s 小例：

```text
2号 -> engine 1 kg/s
1号 -> 2号 0.5 kg/s
```

手算每个油箱末端质量，与程序一致。

## 18.3 official-data regression

必须复现原始附件中的已知质心点与需求总量。

## 18.4 baseline

至少：

- 固定油箱优先级；
- 原论文滚动贪心；
- look-ahead / beam search。

## 18.5 消融

| 改动 | max error | 说明 |
|---|---:|---|
| 不允许额外排油 | | 原论文式受限策略 |
| 允许排油 | | 检验额外自由度价值 |
| ratio=0.1 grid | | |
| continuous ratio | | |
| greedy | | |
| look-ahead | | |

## 18.6 小规模最优 gap

截取前 `300~600s`，用更强的精确/高质量优化求一个 reference：

\[
gap=\frac{J_{heuristic}-J_{ref}}{J_{ref}}.
\]

这会极大增强论文对启发式质量的说服力。

---

# 19. 推荐代码架构

```text
fuel_model/
  geometry.py          # 单油箱解析质心
  aircraft.py          # 整机质心
  dynamics.py          # 油量状态转移
  constraints.py       # 官方硬约束
  data.py              # 读取原始附件

controllers/
  baseline.py
  greedy.py
  beam_search.py
  mpc.py

optimization/
  initial_fuel_de.py
  tune_policy.py

validation/
  test_geometry.py
  test_mass_balance.py
  test_min_up_time.py
  test_official_examples.py
  compare_baselines.py

main_q1.py
main_q2.py
main_q3.py
main_q4.py
```

所有问题共用：

```python
aircraft_centroid(state)
transition(state, action)
check_constraints(state, action)
```

这是避免论文四问越写越散、代码四份复制后发生口径漂移的关键。

---

# 20. 最终可迁移模型范式

这篇论文可抽象成：

\[
\boxed{
\text{几何/物理机理}
\rightarrow
\text{状态空间模型}
\rightarrow
\text{minimax 目标}
\rightarrow
\text{策略空间降维}
\rightarrow
\text{滚动优化}
\rightarrow
\text{外层设计变量优化}
}
\]

适用的不只是供油，还包括：

- 电池热管理；
- 储能充放电；
- 水库调度；
- 多罐液体配比；
- 航天器姿态/质量分布控制；
- 多能源系统；
- 库存-生产动态控制。

真正值得带走的是这种结构，不是某个固定 `T=85` 或某个 0.7 比例。
