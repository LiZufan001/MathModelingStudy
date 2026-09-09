# B23104860044｜模型与算法统一重构

> 目的：不照抄原论文算法名，而是把 2023 B 重新整理成一个严格的“结构—约束—投影—复杂度—误差”优化框架。所有目标与验收均以赛中官方修正后的定义为准。

---

# 1. 统一问题

设目标矩阵为 DFT 类矩阵 `F`，寻找因子链：

\[
H(A)=A_1A_2\cdots A_K
\]

以及实标量 β，使：

\[
\boxed{
J(A,\beta)=\frac1N\|F-\beta H(A)\|_F^2
}
\]

尽可能小，同时控制硬件复杂度。

五个问题本质上只是可行集合不同：

| 问题 | 稀疏 | 有限整数取值 | Kronecker 结构 | 精度硬门槛 |
|---|---|---|---|---|
| Q1 | ✓ |  |  |  |
| Q2 |  | ✓ |  |  |
| Q3 | ✓ | ✓ |  |  |
| Q4 | ✓ | ✓ | ✓ |  |
| Q5 | ✓ | ✓ |  | `J≤0.1` |

因此最好从一开始就写成一个统一优化器，只更换 projection / structure module。

---

# 2. 两个可行集合

## 2.1 行稀疏集合

\[
\mathcal S=
\{A:\|A[i,:]\|_0\le2,\ \forall i\}.
\]

投影 `Proj_S(X)`：每行保留绝对值最大的两个元素，其余置零。

注意：若某些位置由 butterfly topology 预先规定，则 projection 应只在允许 support 上进行。

## 2.2 量化集合

\[
P_q=\{0,\pm1,\pm2,\ldots,\pm2^{q-1}\}.
\]

\[
\mathcal Q_q=
\{A:\Re A_{ij},\Im A_{ij}\in P_q\}.
\]

`Proj_Q(X)` 分别对实部、虚部做最近邻量化。

---

# 3. β 应在每次迭代中解析消元

固定因子链 H 后：

\[
\min_{\beta\in\mathbb R}\|F-\beta H\|_F^2.
\]

展开：

\[
f(\beta)=\|F\|_F^2-2\beta\Re\langle H,F\rangle_F+\beta^2\|H\|_F^2.
\]

令导数为零：

\[
\boxed{
\beta^*=rac{\Re\langle H,F\rangle_F}{\|H\|_F^2}
}
\]

若题意允许 β 为复数，则：

\[
\beta^*=\frac{\langle H,F\rangle_F}{\|H\|_F^2}.
\]

比赛实现中，每次因子更新后都应重新求 β*，不使用经验范数比。

---

# 4. 先做 exact FFT baseline

对于 `N=2^t`，radix-2 FFT 天然提供精确稀疏分解：

\[
F_N=B_tB_{t-1}\cdots B_1P.
\]

每个 butterfly stage 的每行只有极少非零元素。

因此 Q1 的第一个 baseline 必须是：

```text
exact FFT factorization
J = 0
K ≈ log2 N
C = 按官方规则逐 stage 计数
```

随后所有近似方法都与它比较：

| 方法 | J | C | K | peak coeff magnitude |
|---|---:|---:|---:|---:|
| exact FFT | 0 | | log2N | |
| approximate butterfly | | | | |
| BSVD-like | | | | |

这样 Q1 被正确理解成 **accuracy–hardware Pareto problem**，而不是单纯“找一个稀疏分解”。

---

# 5. 不建议依赖默认 SVD 的原因

对未归一化 DFT：

\[
F_m^HF_m=mI.
\]

所有奇异值都等于：

\[
\sqrt m.
\]

因此对：

\[
R=\operatorname{diag}(F_{N/2},F_{N/2})
\]

同样有完全平坦的 singular spectrum。

这意味着：

- 没有“前几个奇异值更重要”；
- SVD basis 不唯一；
- 默认数值 SVD 返回哪个 basis 具有实现依赖性；
- 后续硬阈值稀疏会对这个任意 basis 敏感。

## 更稳妥的重构方向

不要把 SVD 当成 importance ranking，而把问题写成：

> 在等价 unitary basis 中寻找**更稀疏友好**的表示。

例如引入 unitary Q：

\[
R=(UQ)S(VQ)^H
\]

然后优化：

\[
\min_Q
\operatorname{Cost}
(\operatorname{Proj}_{\mathcal S}(UQ),
 \operatorname{Proj}_{\mathcal S}(VQ)).
\]

这是比“直接稀疏默认 SVD basis”更符合本题结构的二次研究方向。

---

# 6. 真正的 alternating projected optimization

给定初始结构因子 `A_1,...,A_K`：

```text
repeat:
    for k = 1...K:
        固定其它因子
        对 A_k 做连续域最小二乘 / 梯度下降
        A_k ← Proj_S(A_k)       # 若要求稀疏
        A_k ← Proj_Q(A_k)       # 若要求量化
    β ← analytic_beta(F, product(A))
    计算官方 J 与 C
until 收敛
```

## 单因子子问题

记：

\[
L_k=A_1\cdots A_{k-1},\qquad
R_k=A_{k+1}\cdots A_K.
\]

则：

\[
\min_{A_k}
\|F-\beta L_kA_kR_k\|_F^2.
\]

向量化后：

\[
\operatorname{vec}(L_kA_kR_k)
=(R_k^T\otimes L_k)\operatorname{vec}(A_k).
\]

因此连续域是标准 least squares。

无需把所有因子同时塞给元启发式算法。

---

# 7. 如果真的要用 ADMM，应完整写出来

例如处理一个单因子的稀疏约束：

\[
\min_A f(A)+I_{\mathcal S}(Z)
\quad s.t.\quad A=Z.
\]

scaled ADMM：

### A-update

\[
A^{t+1}=\arg\min_A
f(A)+\frac\rho2\|A-Z^t+U^t\|_F^2.
\]

### Z-update

\[
Z^{t+1}
=\operatorname{Proj}_{\mathcal S}(A^{t+1}+U^t).
\]

### dual update

\[
U^{t+1}=U^t+A^{t+1}-Z^{t+1}.
\]

并记录：

\[
r^t=A^t-Z^t,
\qquad
s^t=\rho(Z^t-Z^{t-1}).
\]

若没有 dual update 和 primal/dual residual，就不要把算法写成 ADMM。

---

# 8. Q2：量化位置是一个设计变量

应至少比较两条路线。

## Route A：end-to-end quantization

\[
\hat F=\operatorname{Proj}_{\mathcal Q}(F).
\]

优点：逼近对象直接是原矩阵。

## Route B：factor quantization

先有：

\[
F\approx A_1\cdots A_K,
\]

再：

\[
\hat A_k=\operatorname{Proj}_{\mathcal Q}(A_k).
\]

优点：中间因子可能出现更多简单系数，硬件更友好。

必须同时报告：

```text
official J
C=qL
K
coefficient histogram
```

---

# 9. Q3：把 S-Q / Q-S 升级为 projection-order experiment

两个非凸投影：

\[
P_S,P_Q
\]

一般满足：

\[
P_QP_S(X)\ne P_SP_Q(X).
\]

所以至少比较：

```text
S-Q
Q-S
S-Q-S
Q-S-Q
alternating projection until stable
```

并且所有方案都从**同一连续 baseline**出发，否则比较会混入初始化差异。

建议记录：

| pipeline | J | C | K | runtime |
|---|---:|---:|---:|---:|
| S-Q | | | | |
| Q-S | | | | |
| alternating | | | | |

---

# 10. Q4：Kronecker structure first

若：

\[
F=F_a\otimes F_b,
\]

且：

\[
F_a=\prod_iA_i,
\qquad
F_b=\prod_iB_i,
\]

当 factor stage 可以对齐时：

\[
F=\prod_i(A_i\otimes B_i).
\]

因此算法顺序应是：

```text
识别 Kronecker
↓
分别处理小矩阵
↓
利用 mixed-product property 合并
↓
最后再做稀疏/量化微调
```

而不是先形成大矩阵再黑箱优化。

同理可迁移到：

- block diagonal；
- Toeplitz；
- circulant；
- low-rank + sparse；
- tensor product。

---

# 11. Q5：把 GIG 重构为 projected residual correction

当前：

\[
H=A_1\cdots A_K.
\]

希望追加：

\[
HX\approx F/\beta.
\]

连续域：

\[
X^*=(\beta H)^+F.
\]

然后：

\[
X\leftarrow P_{\mathcal S\cap\mathcal Q}(X^*).
\]

加入因子链：

\[
H\leftarrow HX.
\]

随后重新优化：

\[
\beta\leftarrow\beta^*(F,H).
\]

## 更稳妥的接受规则

由于 projection 后不保证误差下降：

```python
X_cont = pinv(beta*H) @ F
X_proj = project(X_cont)
H_new = H @ X_proj
beta_new = optimal_beta(F, H_new)

if official_loss(F,H_new,beta_new) < current_loss:
    accept
else:
    reject / try another projection
```

这样 GIG 成为真正的 monotonic improvement framework。

---

# 12. Q5 必须把 feasibility 与 optimization 分开

硬约束：

\[
J\le0.1.
\]

比赛流程必须先问：

```text
有没有找到 feasible solution？
```

只有找到以后，才开始：

\[
\min C.
\]

因此推荐输出：

```text
best_J = ...
feasible = best_J <= 0.1

if feasible:
    report minimum C found under J<=0.1
else:
    report best achieved J and gap to threshold
```

绝不能因为误差下降就把问题表述成“已解决”。

---

# 13. 正确硬件复杂度模块

官方免费系数集合：

\[
\mathcal E=
\{0,\pm1,\pm j,\pm1\pm j\}.
\]

对直接按 factor chain 作用于向量的实现：

\[
L=
\sum_{k=1}^{K}
\sum_{i,j}
\mathbf1\{A_k[i,j]\notin\mathcal E\}.
\]

于是：

\[
\boxed{C=qL}.
\]

这个 evaluator 与误差 evaluator 一样，应在开题第一阶段单独做单元测试。

---

# 14. 推荐的 Pareto evaluator

不要只输出一个“最好方案”。

定义：

```python
record = {
    'J': official_loss,
    'C': hardware_complexity,
    'K': num_factors,
    'runtime': seconds,
    'peak_memory': bytes,
}
```

一个方案被另一个方案支配，如果：

\[
J_2\le J_1,
\quad C_2\le C_1,
\quad K_2\le K_1
\]

且至少一个严格小于。

最终报告 Pareto frontier，而不是只挑一个加权和。

---

# 15. 最低可复现代码骨架

```python
def official_loss(F, factors, beta=None):
    H = product(factors)
    if beta is None:
        beta = optimal_beta(F, H)
    E = F - beta * H
    J = np.linalg.norm(E, 'fro')**2 / F.shape[0]
    return J, beta


def hardware_cost(factors, q):
    free = {0, 1, -1, 1j, -1j,
            1+1j, 1-1j, -1+1j, -1-1j}
    L = sum(np.count_nonzero(~is_in_free_set(A, free))
            for A in factors)
    return q * L


def evaluate(F, factors, q):
    J, beta = official_loss(F, factors)
    C = hardware_cost(factors, q)
    return {'J':J, 'C':C, 'K':len(factors), 'beta':beta}
```

所有 Q1–Q5 都只调用这一套 evaluator。

---

# 16. 如果今天重新参赛，我的技术路线

## Q1

```text
exact FFT baseline
→ structured factor graph
→ projected alternating minimization
→ J-C-K Pareto
```

## Q2

```text
whole-matrix quantization
vs
factor quantization
→ coefficient histogram
→ official C comparison
```

## Q3

```text
same continuous initialization
→ S-Q / Q-S / alternating projections
→ Pareto comparison
```

## Q4

```text
Kronecker split first
→ optimize small factors
→ recombine
→ local projected refinement
```

## Q5

```text
find feasible J≤0.1 first
→ projected pseudoinverse correction
→ re-optimize β every iteration
→ only after feasibility minimize C
```

---

# 17. 最重要的重构思想

> **DFT 题不是“搜索一个神奇整数矩阵”，而是设计一张受硬件约束的线性计算图。矩阵因子只是这张计算图的代数表示。**

一旦这样理解，FFT、Kronecker、稀疏 support、量化、乘法器数量、factor depth 和逼近误差就会自然进入同一个设计空间。
