# C22106140003 模型与算法重构

> 这份文件不复述整篇论文，而是把作者真正可复用的技术骨架重新整理成“状态—约束—评分—策略—仿真”的形式。原论文中的符号存在少量方向/语义不一致，因此以下优先采用**正文物理含义 + 附录实际程序 + 最终结果表**互相校验后的口径；凡属于二次重构的内容均明确说明。

---

## 1. 系统抽象

把 PBS 看成一个有限资源的动态系统：

```text
涂装输出序列
    ↓
进车横移机
    ↓
┌──────────── PBS ────────────┐
│ 进车道 1   [10 个车位]      │
│ 进车道 2   [10 个车位]      │
│ ...                         │
│ 进车道 6   [10 个车位]      │
│ 返回道     [10 个车位]      │
└─────────────────────────────┘
    ↓
出车横移机
    ↓
总装输出序列
```

每次决策都不是在任意排列中挑一个顺序，而是在**当前可达状态**中选择下一动作。

---

## 2. 推荐的统一状态定义

原程序用多个 MATLAB 数组和标志位维护状态。若我们重新实现，建议显式定义：

\[
S(t)=\bigl(L(t),R(t),I(t),O(t),U(t),Y(t),\tau_{in}(t),\tau_{out}(t)\bigr)
\]

其中：

- \(L(t)\)：6 条进车道的车辆队列/车位占用；
- \(R(t)\)：返回道状态；
- \(I(t)\)：尚未进入 PBS 的涂装序列；
- \(O(t)\)：已形成的总装输出序列；
- \(U(t)\)：正在进车横移机上的车辆；
- \(Y(t)\)：正在出车横移机上的车辆；
- \(\tau_{in}(t)\)：进车横移机剩余占用时间；
- \(\tau_{out}(t)\)：出车横移机剩余占用时间。

原 MATLAB 代码中对应关系大致为：

| 重构状态 | 原代码代表变量 |
|---|---|
| 进车道状态 | `lan_fig` |
| 返回道状态 | `ret_fig` |
| 未进车序列 | `car_seq_in` |
| 已出车序列 | `x_out` |
| 进车任务剩余时间 | `flgi` |
| 出车任务剩余时间 | `flgo` |
| 当前进车 | `car_in_now1/2` |
| 当前出车 | `car_out_now` |

### 状态机思维的好处

任何策略只需要实现：

```text
action = policy(state)
next_state = transition(state, action)
```

这样 FIFO、RRF、LWT、MTT、贪心、beam search 都只是不同的 `policy`，物理状态转移不需要重写。

---

## 3. 硬约束与软目标要分层

### 3.1 硬约束

硬约束负责生成合法动作集合 \(\mathcal A(S)\)，典型包括：

- 每辆车同一时刻只能处于一个位置；
- 每车位最多一辆车；
- 单条进车道容量不超过 10；
- 车道内车辆不能穿越；
- 横移机被占用时不能接新任务；
- 车辆只能按 PBS 允许的方向移动；
- 返回道容量有限；
- 问题一中的 RRF/LWT 等强制优先规则。

### 3.2 软目标

软目标只用于在合法动作集合中比较优劣：

- 动力类型排列质量；
- 驱动类型排列质量；
- 返回道使用次数；
- 总调度时间。

> 比赛实现时，任何优化算法都不应自行“猜”硬约束。先由 simulator/transition 层拒绝非法动作，再在合法动作里优化。

---

## 4. 四类惩罚与统一评分器

为避免原论文中 Q 的符号歧义，重构时统一写成惩罚 \(P_i\)。

### 4.1 动力类型违例 \(P_1\)

找到输出序列中所有混动车位置：

\[
c_1,c_2,\ldots,c_m.
\]

理想条件为连续两个混动车之间恰有 2 辆非混动车，即

\[
c_{r+1}-c_r-1=2.
\]

定义违例：

\[
p_{1,r}=\mathbf 1(c_{r+1}-c_r-1\neq 2),
\]

则

\[
P_1=\sum_{r=1}^{m-1}p_{1,r}.
\]

这与附录 `fun_obj11.m` 的实际实现一致。

### 4.2 驱动类型违例 \(P_2\)

按驱动类型变化切分输出序列，检查每一相关分块内两驱/四驱数量是否为 1:1。定义：

\[
P_2=\#\{\text{不满足 1:1 的分块}\}.
\]

具体切块逻辑由 `fun_obj22.m` + `count_c.m` 完成。

### 4.3 返回道代价 \(P_3\)

\[
P_3=\sum_i N_{b,i}.
\]

它可以直接理解为“昂贵操作使用次数”。

### 4.4 时间代价 \(P_4\)

\[
T=t_e-t_s,
\]

\[
T_{LB}=9N+8t_m=9N+72,
\]

\[
P_4=0.01(T-T_{LB}).
\]

其中 \(T_{LB}\) 是论文给出的理论最快时间基线。

### 4.5 建议实现的唯一评分函数

\[
Score=0.4(100-P_1)+0.3(100-P_2)+0.2(100-P_3)+0.1(100-P_4).
\]

等价地，由于常数 100 的加权和固定，也可以最小化：

\[
Cost=0.4P_1+0.3P_2+0.2P_3+0.1P_4.
\]

**推荐程序只实现 `Cost` 或 `Score` 中的一种，不要同时维护两套方向。**

---

## 5. 问题一进车策略：FIFO + RRF + ETA 选道

问题一中进车源存在两类：

1. 涂装输出序列的下一辆车；
2. 返回道出口等待再次进入 PBS 的车。

由于题目规则规定返回道满足条件时必须优先，因此：

```text
if 返回道出口存在必须优先处理的车辆:
    candidate = 返回道车辆          # RRF
else:
    candidate = 涂装序列第一辆      # FIFO
```

得到 candidate 后，再选进车道。

### 5.1 作者的 ETA 思路

论文根据车道现有车辆数、进车横移时间和预计出车节拍，估计车辆放入每条进车道的时间成本。

可抽象为：

\[
ETA_j \approx n_j\bar t_{out,j}+t_{in,j},
\]

其中 \(n_j\) 为当前车道占用量，\(\bar t_{out,j}\) 表示该车道后续释放的近似时间成本。

然后：

\[
j^*=\arg\min_{j\in \mathcal L_{feasible}} ETA_j.
\]

### 5.2 为什么不是“最短队列”

若车道 4 当前有 6 辆车、车道 1 当前有 5 辆车，但横移到车道 4 明显更快，那么只看队长会选错。

因此更一般的调度原则是：

> **Shortest queue 是粗代理，earliest completion / minimum ETA 才是更直接的目标。**

---

## 6. 问题一出车策略：LWT + 一步贪心

### 6.1 LWT 负责“谁有资格被考虑”

当多个车道出口都有车时，问题一的规则要求更早到达出口者优先，因此：

\[
candidate = \arg\min_{v\in F(S)} arrival\_time(v),
\]

其中 \(F(S)\) 是当前位于各车道出口的车辆集合。

### 6.2 贪心负责“直出还是返回”

设当前输出序列为 \(O\)，候选车为 \(v\)。

计算立即输出后的局部排列惩罚：

\[
C_{direct}=0.4P_1(O\oplus v)+0.3P_2(O\oplus v).
\]

当前序列的局部惩罚：

\[
C_{now}=0.4P_1(O)+0.3P_2(O).
\]

使用一次返回道至少增加：

\[
C_{return}=0.2.
\]

因此附录代码表达的本质是：

```text
if C_direct > C_now + C_return
   and 返回道有容量
   and 尚有返回道使用额度:
       candidate -> 返回道
else:
       candidate -> 输出序列
```

注意：这里只比较了 Q1/Q2 与一次返回道的即时权衡，时间项的未来变化没有完整进入一步决策，所以它是**局部贪心**而非完整动态规划。

### 6.3 这是一个通用“昂贵操作”模板

很多题都能写成：

```text
if 不使用补救动作的损失 > 补救动作成本:
    使用补救动作
```

例如：

- 返工；
- 临时插单；
- 换线；
- 备用设备；
- 重路由；
- 超额库存；
- 数据修正/异常剔除。

---

## 7. 问题一完整伪代码

```text
initialize state S

while not all vehicles finished:
    advance lane/return-road movement
    decrease inbound/outbound machine timers

    # ---------- inbound ----------
    if inbound_machine_idle:
        if return_vehicle_must_go_first(S):       # RRF
            v = first_return_vehicle(S)
        else:                                     # FIFO
            v = next_paint_vehicle(S)

        feasible_lanes = lanes_with_capacity(S)
        j = argmin ETA(v, lane, S) over feasible_lanes
        dispatch_in(v, j)

    # ---------- outbound ----------
    if outbound_machine_idle:
        candidates = front_vehicles(S)

        if len(candidates) == 1:
            v = candidates[0]
        elif len(candidates) > 1:
            v = earliest_arrived(candidates)      # LWT
        else:
            v = None

        if v is not None:
            direct_cost = weighted_Q1_Q2(output + v)
            current_cost = weighted_Q1_Q2(output)

            if direct_cost > current_cost + return_cost \
               and return_has_space(S):
                dispatch_to_return(v)
            else:
                dispatch_to_output(v)

    S = update_state(S)
    assert_invariants(S)

return output_sequence, score, state_trace
```

---

## 8. 问题二：把硬优先级改成 MTT 决策

问题二取消问题一的两项优先约束。关键不是“少两个约束”，而是动作集合扩大了。

### 8.1 进车端

问题一：

```text
return road ready -> 必须优先
```

问题二：

```text
比较：
A. 下一辆涂装车现在开始送入 PBS 的预计完成时间
B. 返回道候选车等待到可送入 PBS 再完成运输的预计时间

选择更早完成的一方
```

可写成：

\[
source^*=\arg\min\{MTT_{paint},MTT_{return}\}.
\]

选出来源后，仍按最小 ETA 选目标进车道。

### 8.2 出车端

问题一由 LWT 强制最早到达者；问题二可在多个车道出口候选中直接比较运输时间：

\[
j^*=\arg\min_{j\in F(S)} MTT_j.
\]

选出车辆后，继续使用同一套“直出 vs 返回”的局部评分比较。

### 8.3 最重要的结构变化

```text
问题一：规则先过滤动作，优化只能在剩余自由度中进行
问题二：规则解除，动作集合扩大
       ↓
需要新的 policy 消化新增自由度
       ↓
MTT 成为统一选择标准
```

以后遇到“第二问取消某限制”的题目，应主动问：

> 新增自由度应该由什么量来定价？时间？成本？风险？收益？

---

## 9. 形式化 MILP 为什么全规模困难

论文进一步定义：

- \(\chi_{i,l}\)：车辆 i 是否分配到进车道 l；
- \(\varpi_{i,j}\)：车辆 i 是否位于最终输出序列位置 j。

仅最终排列就需要 \(N^2\) 个二元变量：

\[
\varpi\in\{0,1\}^{N\times N}.
\]

当 \(N=318\) 时，仅这部分就有：

\[
318^2=101124
\]

个 0-1 变量，还没算车道分配、状态、顺序和时间约束。

因此论文把 MILP 更适合作为：

1. 约束形式化；
2. 小规模精确模型；
3. 其他算法的理论参照；

而不是直接当完整 N=318 主求解器。

---

## 10. 遗传算法对比告诉了什么

作者在问题二模型上进一步引入：

- 二进制编码；
- 种群大小 200；
- 进化代数 1000；
- 车道分配变量 + 输出顺序变量。

实验结论：

- N=5：正常求解；
- N=20：性能下降，并开始出现约束不满足；
- N=100：约束不再满足，适应度甚至不如原始序列，计算达到小时级。

这里真正的教训不是“遗传算法不好”，而是：

> **如果编码空间里大量个体天然非法，而 repair/decoder 又不保证可行性，元启发式会把大量算力浪费在不可行空间。**

更好的做法是：

- 用仿真器作为 decoder，让任何染色体都映射成合法动作；或
- 只优化策略参数/局部优先级，而不直接编码完整 318 车排列。

---

## 11. 如果今天重新实现，我会怎样改架构

### 11.1 配置层

```python
ProblemSpec(
    n_vehicles,
    n_lanes,
    lane_capacity,
    return_capacity,
    move_time,
    inbound_times,
    outbound_times,
    weights,
    constraints,
)
```

不在代码里散落 `318`、`6`、`10`、`90` 等魔法数字。

### 11.2 状态层

```python
@dataclass
class PBSState:
    time: float
    lanes: list[deque]
    return_lane: deque
    waiting_input: deque
    output: list[int]
    inbound_machine: MachineState
    outbound_machine: MachineState
    return_count: int
```

### 11.3 评分层

```python
def penalties(output, return_count, makespan, spec):
    return P1, P2, P3, P4

def score(...):
    P = penalties(...)
    return sum(w[i] * (100 - P[i]) for i in range(4))
```

所有算法只调用这一处。

### 11.4 策略层

```python
class InboundPolicy:
    def choose_source(...): ...
    def choose_lane(...): ...

class OutboundPolicy:
    def choose_candidate(...): ...
    def choose_direct_or_return(...): ...
```

可以直接替换：

- `RRFInboundPolicy`
- `MTTInboundPolicy`
- `LWTOutboundPolicy`
- `MTTOutboundPolicy`
- `GreedyReturnPolicy`
- `BeamSearchReturnPolicy`

### 11.5 仿真层

尽量采用**事件驱动**而不是每秒遍历所有位置：

```text
下一事件 = min(
    进车任务完成时间,
    出车任务完成时间,
    某车到达车道出口时间,
    某返回道车辆到达接车点时间
)
```

这样状态表示更干净，也更容易扩展到不同运动时间。

---

## 12. 可以在作者方案上继续做的优化

### 路线 A：有限深度前瞻

从当前状态枚举未来 k=2~5 步合法动作：

\[
a^*=\arg\min_{a_0}\min_{a_1,\ldots,a_{k-1}}
\left[\text{局部评分损失}+\lambda\cdot\text{future heuristic}\right].
\]

优点：保留仿真可行性，同时减少一步贪心短视。

### 路线 B：Beam Search

每一步只保留评分最好的 B 个状态：

```text
frontier = {current_state}
repeat k steps:
    expand all legal actions
    evaluate
    keep top-B states
choose first action of best path
```

### 路线 C：滚动时域 MILP

不是一次优化 318 辆，而是只看未来 W 辆：

```text
current state
   ↓
MILP optimize next W vehicles
   ↓
execute first 1~k decisions
   ↓
update real state
   ↓
repeat
```

这通常比全规模 MILP 更现实。

### 路线 D：策略参数优化

用 GA/PSO/贝叶斯优化搜索：

- 返回道阈值；
- Q1/Q2 局部权重；
- ETA 中拥塞项权重；
- look-ahead 深度；

而不是搜索 318 辆车的完整排列。

---

## 13. 验证计划：如果是我们参赛，必须补齐

### 13.1 状态不变量断言

每个事件后检查：

```text
每辆车恰好出现在一个位置
每个车位至多一辆车
任何车道长度 <= capacity
输出序列无重复
已输出 + PBS 内 + 未进入 = 全部车辆
return_count 与历史动作一致
所有运动都遵守方向约束
```

### 13.2 评分单元测试

人为构造 5~20 辆车的小序列，手算：

- 完全满足动力类型间隔；
- 恰好一个 Q1 违例；
- 完全 1:1 驱动分块；
- 恰好一个 Q2 违例；
- 返回 0/1/2 次；
- 理论最短 / 多 100 s。

确保 `score()` 与人工结果完全一致。

### 13.3 消融实验

| 模型 | Q1/Q2 | 返回次数 | 时间 | 总分 |
|---|---:|---:|---:|---:|
| FIFO baseline | | | | |
| FIFO + RRF | | | | |
| LWT | | | | |
| LWT + greedy | | | | |
| MTT inbound only | | | | |
| MTT outbound only | | | | |
| full MTT + greedy | | | | |

### 13.4 鲁棒性

改变：

- 车型比例；
- 驱动比例；
- 车道容量；
- 横移时间；
- 返回道容量；
- N；

观察策略是否仍可行、得分是否平稳。

---

## 14. 最终技术抽象

把这篇论文压缩成一个通用公式，可以写成：

\[
\boxed{
\text{复杂调度}
=\text{状态转移模型}
+\text{合法动作生成}
+\text{优先级/ETA 策略}
+\text{增量评分}
+\text{滚动决策}
}
\]

其中：

- FIFO/RRF = **规则驱动优先级**；
- LWT = **等待时间驱动的 dispatch rule**；
- MTT = **预计完成时间驱动的 dispatch rule**；
- 贪心 = **一步 score-delta 决策**；
- MILP = **约束形式化/小规模精确参考**；
- MATLAB 主循环 = **可行性仿真器**。

这才是这篇论文最应该存入我们的长期“调度题工具箱”的内容。
