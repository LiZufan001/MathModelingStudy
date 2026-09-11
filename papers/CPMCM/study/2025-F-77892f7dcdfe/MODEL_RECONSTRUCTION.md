# MODEL_RECONSTRUCTION｜从“软概念”到可审计决策模型

> 目标：把 2025 F 候选中的有价值思想重构成一套比赛时可直接迁移的统一模型，而不是保留历史权重和题目专属阈值。

---

# 1. 统一对象

设空间域：

\[
\Omega\subset\mathbb R^2.
\]

场景元素集合：

\[
\mathcal O=\{O_1,\ldots,O_m\}.
\]

可行走区域：

\[
\Omega_f=\Omega\setminus \bigcup_j Obstacle_j.
\]

构建导航图：

\[
G=(V,E).
\]

每个节点不是只有坐标，而定义一个观察状态：

\[
s(v)=\left[s^{geo},s^{semantic},s^{visibility},s^{topology}\right].
\]

这样同一套状态表示可以服务：

- Q1 路径体验；
- Q2 空间格局；
- Q3 相似度。

---

# 2. Q1 重构：路径体验 = 状态变化 + surprise + 重复惩罚

路径：

\[
P=(v_1,\ldots,v_T).
\]

## 2.1 局部景观差异

推荐用 JS divergence 或加权集合差异：

\[
D_t=JS(p_t,p_{t+1}).
\]

如果状态是二元可见性，可用：

\[
D_t=d_H(s_t,s_{t+1}).
\]

## 2.2 意外性

\[
U_t=-\log\left(P(c_{t+1}|c_t)+\epsilon\right),
\]

其中 `c_t` 是状态聚类/主题类别。

## 2.3 变化防刷分

\[
Q_t=\frac{D_t}{\Delta l_t+\epsilon}w(\Delta l_t,\Delta l_{t+1}).
\]

避免把路径无限切碎刷高变化量。

## 2.4 重复率

边重复：

\[
R_E(P)=\frac{\sum_{e\in E}\max(n_e-1,0)l_e}{L(P)}.
\]

状态重复：

\[
R_S(P)=1-\frac{|\{c_t\}|}{T}.
\]

## 2.5 多目标

推荐保留：

\[
\max I(P)=\sum_t(\alpha Q_t+\beta U_t),
\]

\[
\min R(P),\qquad \min L(P).
\]

先得到 Pareto front，再由用户画像或 knee point 选解。

---

# 3. Q2 重构：幻境感不是总量，而是“状态层次 + 开合转换”

将园林划分为栅格/区域：

\[
\Omega=\bigcup_k A_k.
\]

每个区域提取：

\[
x_k=[diversity,aggregation,connectivity,visibility,enclosure,\ldots].
\]

## 3.1 区域主题

用 K-means/GMM/规则分类得到：

\[
z_k\in\{1,\ldots,K\}.
\]

主题本身不是美学分数，而只是状态。

## 3.2 开阔度

\[
O_k=f(V_k,D_k,E_k),
\]

分别表示：

- 可视通透；
- 障碍距离；
- 围合比例。

阈值由基准园/分位数标定，不直接经验拍定。

## 3.3 开合序列

沿代表游线：

\[
O_1,O_2,\ldots,O_T.
\]

定义：

变化强度：

\[
A_O=\frac1{T-1}\sum_t|O_{t+1}-O_t|.
\]

变化频率：

\[
F_O=\frac1{T-1}\sum_t\mathbf1(|\Delta O_t|>\tau).
\]

节律：

\[
Rhythm=\max_{\ell\in\mathcal L}ACF_O(\ell).
\]

## 3.4 “适量”复杂度

如果太简单/太复杂都不好：

\[
S_C=\exp[-(C-C^*)^2/\sigma_C^2].
\]

## 3.5 幻境感

不要直接 50/50。先得到两个 latent component：

\[
H_{static},\quad H_{dynamic}.
\]

最终：

\[
H=w_sH_{static}+w_dH_{dynamic}.
\]

权重采用：

\[
w(\lambda)=\lambda w_{AHP}+(1-\lambda)w_{CRITIC},
\]

并报告 `λ` sweep 下的排名稳定性。

---

# 4. Q3 重构：“有法无式” = 稳定共性 + 可解释个性

不要先做 179 维 cosine。

先对特征进行：

1. 缺失/异常处理；
2. correlation clustering；
3. VIF/PCA 去冗余；
4. 按语义分组。

得到：

\[
F_i=[F_i^{path},F_i^{layout},F_i^{visibility},F_i^{network}].
\]

## 4.1 共性法则

跨园特征 j：

\[
CV_j=\frac{sd(x_{1j},...,x_{nj})}{|mean(x_{1j},...,x_{nj})|+\epsilon}.
\]

定义稳定度：

\[
C_j=\exp(-CV_j/\tau).
\]

高 `C_j` 的特征构成：

\[
F_{law}.
\]

## 4.2 个性

先构造原型：

\[
\mu_{law}=\sum_iw_iF_i.
\]

个性指数：

\[
D_i=(F_i-\mu)^T\Sigma^{-1}(F_i-\mu).
\]

或者 SHAP/feature contribution 解释“它为什么特别”。

## 4.3 相似度

分模态算：

\[
S_{ij}^{(m)}.
\]

再融合：

\[
S_{ij}=\sum_mw_mS_{ij}^{(m)}.
\]

必须同时给：

- raw similarity；
- null-permutation similarity；
- bootstrap CI；
- rank stability。

若：

\[
S_{real}\approx S_{null},
\]

说明指标没有区分力。

---

# 5. 参数标定层

所有参数分四类：

| 类型 | 例子 | 标定方法 |
|---|---|---|
| 物理/几何 | 视线高、通行半径 | 题面/规范 |
| 数据尺度 | 栅格、采样步长 | stability curve |
| 阈值 | 开阔/围合、变化事件 | benchmark quantile / ROC |
| 价值权重 | 趣味 vs 距离 | Pareto / AHP+CRITIC / preference |

强制输出参数账本：

```text
parameter
meaning
unit
source
range
sensitivity
```

---

# 6. 统一验证层

## 6.1 机制

\[
Corr(turn\ density,scene\ change)>0.
\]

## 6.2 基线

- shortest path；
- random walk；
- distance-only；
- equal weight；
- single-metric similarity。

## 6.3 敏感性

\[
\theta\sim Uniform(0.8\theta_0,1.2\theta_0).
\]

报告：

- score CI；
- rank flip frequency；
- Pareto hypervolume variation。

## 6.4 泛化

新园林参数冻结。

## 6.5 人类证据（若来得及）

最少做一个小型 blinded pairwise survey：

```text
路线 A vs B
哪个更有趣？
```

用 Bradley-Terry：

\[
P(A>B)=\frac{e^{\theta_A}}{e^{\theta_A}+e^{\theta_B}}.
\]

再检验模型分数和人类偏好的一致性。

这种 pairwise 比要求同学“给 87.3 分”更稳定。

---

# 7. 最终统一输出

不要只给一张排名表。

推荐最终交付：

1. navigation graph；
2. scene-change heatmap；
3. Pareto route front；
4. 开合序列曲线；
5. static/dynamic 幻境二维坐标图；
6. similarity network；
7. common vs distinctive feature table；
8. parameter sensitivity；
9. new-object frozen-parameter validation；
10. score/rank uncertainty。

---

# 8. 一句话重构

> **把审美对象建成“空间状态 + 行进序列 + 网络结构”，把主观词拆成能由附件观测的机制；先在局部计算变化/意外/开合，再通过 Pareto 或经验证的权重聚合；最终用共性稳定度与个性偏离共同解释“有法无式”，并通过机制、基线、敏感性和冻结参数外对象形成完整验证闭环。**
