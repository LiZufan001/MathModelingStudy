# PRACTICAL_MODELING_TOOLKIT｜主观概念量化题实战工具箱

> 本文件不是复述某一篇论文。它从 2025 F 四份“优秀论文选”人工深读证据中，只抽取**赛场可迁移**的方法设计，并把历史权重/阈值全部视为需要重新标定的参数。

适用题型：

- 美学、舒适度、吸引力、活力、协调性、韧性、幸福感；
- 城市空间、旅游体验、景区路线；
- 产品体验、服务质量、可持续性；
- “好不好看/好不好用/有没有趣/是否协调”等软目标；
- 给了图、坐标、轨迹、多模态附件，但没有直接标签的题。

---

# 1. 第一反应：别问“用 AHP 还是熵权”，先问“这个词发生在哪里”

任何软概念先拆成：

\[
Concept = Mechanism_1 + Mechanism_2 + \cdots
\]

建议用四类机制扫描：

| 类型 | 问题 | 例子 |
|---|---|---|
| 状态 | 某一时刻/位置是什么样？ | 开阔度、密度、可视元素 |
| 变化 | 相邻状态变了多少？ | 异景、节奏、波动 |
| 结构 | 整体空间怎么组织？ | 连通、聚集、分区、层级 |
| 决策 | 人/系统如何在其中行动？ | 游线、选址、调度 |

园林题中：

```text
趣味性
= 景观丰富 + 变化幅度 + 意外性 - 重复

幻境感
= 元素格局 + 开合状态 + 开合节奏
```

## 实战规则

如果你无法写出：

> “这个指标对应题意中的哪一个可观察机制？”

就先不要把它放进评价体系。

---

# 2. 一个元素可以有多个物理角色：不要“一物一参数”

另一份 F 题优秀论文用了一个非常实战的处理：植物同时有：

- **通行障碍半径** `η_walk r`；
- **视域遮挡半径** `η_vis r`。

这比把植物简单画成一个圆合理得多。

一般化：

```text
Object
├─ collision footprint
├─ sensing footprint
├─ influence footprint
└─ risk footprint
```

例如：

- 仓库货架：不能走区域 ≠ 传感器遮挡区域；
- 风机：实体半径 ≠ 尾流影响半径；
- 医院：建筑位置 ≠ 服务覆盖半径；
- 基站：物理位置 ≠ 信号影响域。

> **同一对象在不同子模型中的作用不同，就允许有不同的有效几何尺度。**

---

# 3. “体验”问题必须变成序列

静态统计回答不了过程体验。

标准模板：

\[
s_1,s_2,\ldots,s_T
\]

其中 `s_t` 是人在第 t 个位置看到/感受到的状态。

再从序列构造：

- 水平：`s_t` 本身；
- 一阶变化：`d(s_t,s_{t+1})`；
- 二阶变化：变化速度是否又在变；
- 周期：是否有重复节奏；
- surprise：状态转移概率。

可直接用：

\[
Surprise_t=-\log P(s_{t+1}|s_t).
\]

这一招适合：

- 旅游游线；
- 电影/剧情节奏；
- 用户点击流；
- 交通状态；
- 设备故障演化。

---

# 4. 指标一定要做“防作弊测试”

这是四篇 F 题里非常值得迁移的思想。

## 4.1 例：异景变化不能被“切短路径”刷高

如果简单：

\[
Score=\sum_i d(s_i,s_{i+1}),
\]

把路线切成更多极短段可能人为增大累计变化。

一个优秀候选用了类似链条：

1. 用对称稳定的 JS divergence 比较景观分布；
2. 除以段长，消除纯长度效应；
3. 用 `min(l_i,l_{i+1})` 等温和权重，防极短段爆炸；
4. 在候选路径集合上统一归一化。

一般化写法：

\[
q_i = \frac{d(p_i,p_{i+1})}{l_i+\epsilon}w(l_i,l_{i+1}).
\]

然后问四个“攻击问题”：

- 把一个对象拆成两个，分数会不会凭空上升？
- 重复复制同一特征，综合分会不会变高？
- 路线变长，分数是不是必然变高？
- 样本量变大，熵/多样性是不是机械上升？

> **先攻击自己的指标，再交给评委攻击。**

---

# 5. “不是越多越好”时，用适量度而不是线性正向化

审美、生态、风险管理中经常出现：

> 太少不好，太多也不好。

不要硬用：

\[
score=x/x_{max}.
\]

推荐适量度：

\[
S(x)=\exp\left[-\frac{(x-x^*)^2}{\sigma^2}\right].
\]

或者分段三角/梯形函数。

适用：

- 转折数；
- 景观复杂度；
- 植物密度；
- 交通密度；
- 库存；
- 温度舒适度；
- 风险暴露。

## 参数怎么定？

`x*` 不要拍脑袋，可来自：

1. 题面 benchmark；
2. 专家规范；
3. 数据中高评价对象；
4. 网格搜索 + 验证指标；
5. Pareto knee point。

---

# 6. 题目给“基准对象”，就把它变成 calibration anchor

2025 F 明确指定寄畅园 100 分。

实战不要只做：

\[
minmax(x).
\]

而应设计：

\[
Score_j(x)=100\cdot g_j(x;x_{ref}).
\]

三种指标分别处理：

## 正向指标

\[
S=100\frac{x}{x_{ref}}
\]

必要时 cap。

## 负向指标

\[
S=100\frac{x_{ref}}{x+\epsilon}.
\]

## 适量指标

\[
S=100\exp[-(x-x^*)^2/\sigma^2].
\]

这能把题面语言真正写进模型。

---

# 7. 阈值不要“经验取 0.5”：五步数据驱动标定

一份 F 题候选给了非常实用的超参标定套路，可直接迁移：

```text
Step 1 选题面指定 benchmark / calibration subset
Step 2 网格扫描参数
Step 3 同时计算 2~3 个质量指标
Step 4 找稳定平台，不迷信单点最优
Step 5 平台中值 + 邻域敏感性
```

例如聚类参数 α：

\[
Q(\alpha)=w_1Silhouette+w_2CH-w_3DB.
\]

不是直接取：

\[
\alpha=\arg\max Q.
\]

而是先找：

\[
\mathcal P=\{\alpha:Q(\alpha)\ge0.98Q_{max}\},
\]

再取：

\[
\alpha^*=median(\mathcal P).
\]

好处：避免一个尖锐、不可复现的“最优点”。

---

# 8. AHP 如何避免沦为形式

AHP 最大的问题不是方法老，而是经常：

```text
我们认为A重要
→ 5
我们认为B较重要
→ 3
→ 权重
```

然后没有任何验收。

实战推荐三层：

## 8.1 AHP 只表达价值偏好

输出：

\[
w_s.
\]

必须给一致性：

\[
CR<0.1.
\]

## 8.2 CRITIC/熵权表达数据区分力

输出：

\[
w_o.
\]

## 8.3 组合

\[
w(\lambda)=\lambda w_s+(1-\lambda)w_o.
\]

然后扫：

\[
\lambda\in[0,1].
\]

输出排名稳定性：

- top-1 是否稳定；
- top-3 是否稳定；
- Kendall τ；
- Spearman ρ。

如果权重一变排名就翻转，论文应诚实说：

> 结论依赖价值偏好。

而不是把一组权重包装成客观真理。

---

# 9. 真正多目标时优先 Pareto，不要提前压成一个分数

题面常写：

> “既……又……”

例如：

- 趣味性高；
- 重复路径少；
- 路程不能太长。

这是多目标：

\[
\max I(P),\quad \min R(P),\quad \min L(P).
\]

如果直接：

\[
0.5I-0.3R-0.2L,
\]

你实际上替用户做了价值判断。

优先输出 Pareto front：

```text
短而普通
↔
适中且有趣
↔
长但体验最丰富
```

然后根据题意选择 knee solution。

赛场优先级：

1. 小问题：枚举 Pareto；
2. 图路径：multi-objective label setting / ε-constraint；
3. 非规则复杂编码：NSGA-II；
4. 时间不够：扫多个 λ，而不是只报一个 λ。

---

# 10. Fine graph → Macro graph：先算准，再优化

F1 候选的微观/宏观双层路网是一个非常好的通用技巧。

```text
dense samples
   ↓ 算视域、风险、能耗等
fine graph
   ↓ 提取关键转折/交叉/事件点
macro graph
   ↓
optimization
```

这叫**计算解耦**：

- 评价器需要高分辨率；
- 优化器不需要每个像素都是决策点。

适用于：

- 路径规划；
- 调度事件压缩；
- 时序 change point；
- 地图导航；
- 网格 PDE 后的策略搜索。

---

# 11. 相似度模型一定做“区分度审计”

F1 候选出现：

\[
mean\ similarity\approx0.986,
\]

45 对全部 >0.85。

这是红旗。

高维 cosine 的常见问题：

- 正值特征居多；
- 指标高度共线；
- 标准化后方向很接近；
- 重复指标等价于重复投票。

## 实战至少做四项

### 11.1 Null baseline

随机打乱对象-特征对应关系，得到：

\[
S_{null}.
\]

要求：

\[
S_{real}\text{ 与 }S_{null}\text{ 有明显分离}.
\]

### 11.2 去共线

- 相关阈值；
- VIF；
- PCA；
- cluster features。

### 11.3 看 rank stability

bootstrap 特征/对象，重复排名。

### 11.4 相似度不是只有一种

同时比较：

- cosine；
- correlation distance；
- Mahalanobis；
- Jaccard（集合）；
- graph edit / topology；
- sequence DTW/HMM divergence。

---

# 12. “有法无式”最好显式拆成 common + distinctive

非常适合主观文化类题：

\[
F=F_{common}\oplus F_{distinctive}.
\]

共性可定义：

- 跨对象 CV 小；
- bootstrap 稳定；
- 跨数据源一致。

个性可定义：

- deviation from prototype；
- unique feature contribution；
- cluster-specific features。

例如：

\[
Common_j=\exp(-CV_j/\tau),
\]

\[
Distinct_i=\|z_i-\mu_{prototype}\|_M.
\]

这样才能真正解释：

> 为什么它们属于同一种风格，又为什么没有模板化复制。

---

# 13. 没有 ground truth 时的“四层验证法”

这是本阶段最应该记住的模板。

## Layer 1｜机制一致性

题面说“转折多 → 异景强”，检查：

\[
Corr(turn\ density,scene\ change)>0.
\]

## Layer 2｜朴素 baseline

例如：

- 最短路；
- 随机路线；
- 距离-only；
- 单指标评分。

## Layer 3｜敏感性 / 稳健性

- 权重 ±20%；
- 阈值 sweep；
- 网格尺寸；
- 采样间距；
- 随机种子。

## Layer 4｜外对象冻结参数泛化

```text
原对象标定
→ freeze
→ 新对象直接运行
```

只要中间偷偷针对新对象调参，就不算泛化。

如果可以再加：

## Layer 5｜外部人类证据

- 专家评分；
- 游客问卷；
- 官方推荐路线；
- 行为轨迹/停留时长。

---

# 14. 评分必须带不确定性

不要只报：

```text
A 92.37
B 90.84
```

而应通过：

- bootstrap；
- 权重采样；
- 阈值采样；
- 输入坐标误差；

得到：

\[
Score_i=\hat\mu_i\pm CI_i.
\]

如果：

\[
CI_A\cap CI_B\neq\emptyset,
\]

就不要强行说 A 显著优于 B。

这是软评价题从“打分表”升级成“统计模型”的关键一步。

---

# 15. 扩展指标必须“从附件里长出来”

一份候选扩展了“综合透视”美学，比较好的地方是：

- 建筑开口；
- 树冠径；
- 假山多边形；
- 可视通道；

都能由附件数据直接计算。

相反，危险做法是：

> 附件只有坐标，却突然引入“文化内涵指数、哲学意境指数、历史厚重感”，再用 AHP 打分。

实战规则：

> **新增概念必须先回答：它的观测量在哪里？**

没有观测量，就放讨论/展望，不放主结论。

---

# 16. 数据预处理也要按“成因”分，不要统一插值

另一份候选的实用做法：先区分缺失原因，再用不同策略。

模板：

| 缺失类型 | 原因 | 策略 |
|---|---|---|
| 几何断点 | CAD/采样边界 | topology repair / local interpolation |
| 真正不存在 | 该区域无元素 | 保持 0，不插值 |
| 测量缺失 | 数据丢失 | 邻域/模型插补 |
| 语义未知 | 分类不确定 | unknown flag / probability |

> **0、missing、unknown 是三种不同状态。**

---

# 17. 赛场 30 分钟软指标建模流程

遇到主观综合评价题，按这个顺序：

```text
0. 写出题面真正的软概念
1. 每个概念拆 2~4 个机制
2. 给每个机制绑定附件可观察量
3. 优先找成熟学科指标
4. 检查单调/适量/阈值型关系
5. 为指标设计防作弊测试
6. 先不加权，画单指标分布和相关矩阵
7. 去共线
8. 能 Pareto 就不先加权
9. 必须加权时用主客观组合 + sensitivity
10. 定义机制一致性 baseline
11. 冻结参数做新对象泛化
12. bootstrap 给排名/评分置信度
```

---

# 18. 推荐的论文结构

这类题正文不要按：

```text
AHP
熵权
聚类
GA
```

而按：

```text
4.1 主观概念的可观测机制
4.2 状态/空间表示
4.3 指标定义与防作弊设计
4.4 参数和权重标定
4.5 优化/评分
4.6 机制验证
4.7 敏感性与外对象泛化
```

算法是工具，不是章节主角。

---

# 19. 我们比赛时应该直接复用的代码接口

建议赛前准备下面这些通用函数：

```python
build_feasible_region(objects)
build_navigation_graph(region)
raycast_visibility(point, direction, objects)
state_vector(point)
sequence_change(states, metric="js")
robust_normalize(x, reference=None)
suitability(x, optimum, sigma)
combine_weights(w_subjective, w_objective, lam)
pareto_rank(objectives)
sensitivity_sweep(params, evaluator)
bootstrap_score(data, evaluator)
rank_stability(score_samples)
```

评价器统一：

```python
def evaluate(solution, params):
    return {
        "feasible": ...,
        "raw_metrics": ...,
        "normalized_metrics": ...,
        "objectives": ...,
        "score": ...,
    }
```

这样正式比赛换题时，只需要换机制和数据接口。

---

# 20. 一句话现场模板

> **面对主观概念，先把它拆成能由附件直接观测的状态、变化与结构机制；指标必须防刷分、权重必须做敏感性，能多目标就保留 Pareto；没有真值时用理论应然关系、朴素基线、参数扰动和冻结参数外对象验证形成四层证据闭环。**
