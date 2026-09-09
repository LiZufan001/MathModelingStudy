# A21102480004｜模型与算法重构

> 目标：不照抄原文符号，而是把这道题整理成一套以后还能复用的“计算图—结构发现—近似计算—线性求解—压缩—验证”框架。原论文与公开附录之间存在若干指标/阈值不一致，因此以下凡涉及官方指标，均以赛题定义为准。

---

# 1. 统一计算图

对每个 `j=1,...,J`、`k=1,...,K`：

\[
H_{j,k}\in\mathbb C^{M\times N},
\qquad M=4,N=64.
\]

标准流水线：

```text
H_{j,k}
   ↓ SVD
V_{j,k} ∈ C^{64×2}
   ↓ Gram
A_{j,k}=V^H V + σ²I ∈ C^{2×2}
   ↓ solve / inverse
W_{j,k}=V A^{-1} ∈ C^{64×2}
```

数据共有：

\[
J\times K=4\times384=1536
\]

个 H 矩阵/数据集。

因此总计算成本天然可以拆成：

\[
C_{total}
=C_{preprocess}
+N_{SVD}\,C_{SVD}
+N_{solve}\,C_{solve}
+C_{other}.
\]

这比只讨论某个核的 Big-O 更有用，因为它揭示两个正交优化方向：

1. 降低 `N_SVD`：少算几次；
2. 降低 `C_SVD/C_solve`：每次算便宜一点。

---

# 2. 第一层：结构发现与代表元复用

## 2.1 廉价相似度代理

原论文定义列范数向量：

\[
z(H)=(\|h_1\|_2,\ldots,\|h_N\|_2),
\]

再用 Pearson correlation：

\[
s(H_a,H_b)=corr(z(H_a),z(H_b)).
\]

它适合作为 cheap screening，但不应被当作最终精度保证。

推荐重构：

```text
cheap similarity
     ↓
产生候选复用关系
     ↓
真正 rho evaluator 做最终验收
```

## 2.2 相似图

对同一 j 的 384 个 H 建图：

\[
G=(\mathcal V,\mathcal E),
\]

若：

\[
s(H_p,H_q)\ge \tau,
\]

则连边 `(p,q)`。

注意：相似不传递，所以“连通分量 = 一类”的简单做法不可靠。

## 2.3 代表元选择

原论文使用父子结点贪心。更统一的模型是：

为每个候选代表 r 定义其可覆盖集合：

\[
S_r=\{q:\rho(V_q,\widehat V_q^{(r)})\ge0.99\}.
\]

选尽量少的代表：

\[
\min \sum_r x_r
\]

s.t.

\[
\sum_{r:q\in S_r}x_r\ge1,
\qquad x_r\in\{0,1\}.
\]

这是 set cover 形式。

比赛规模不大时可：

- 贪心 set cover；
- ILP 求小规模精确解；
- facility-location 变体；
- 用计算成本而非“代表元数量”作为代表权重。

更一般的目标：

\[
\min
C_{similarity}
+\sum_r x_r C_{SVD}(r)
+\sum_q C_{reuse}(q).
\]

这样才能真正对齐“总计算复杂度最低”。

---

# 3. 第二层：randomized SVD

目标是找 Q：

\[
\|A-QQ^HA\|\le\varepsilon.
\]

然后：

\[
B=Q^HA,
\]

\[
B=\widetilde U\Sigma V^H,
\]

\[
U=Q\widetilde U.
\]

## 3.1 建议比赛实现

原矩阵 H 只有 `4×64`，所以随机 SVD 未必天然比高度优化的普通 SVD 快。

因此不要预设随机 SVD 一定优越，应做 crossover test：

```matlab
for method = ordinary / randomized
    for seed = ...
        计官方复杂度
        计 runtime
        验 rho
    end
end
```

## 3.2 rank / residual 自适应

推荐停止条件直接围绕精度：

\[
\|(I-QQ^H)A\|_2\le\epsilon.
\]

或者更贴题地：

```text
逐步增 rank
→ 生成 V_hat
→ 调 official rho
→ 首次满足 rho_min≥0.99 即停止
```

这样 rank 不依赖经验阈值。

## 3.3 随机算法必须记录

- seed；
- 采样数；
- oversampling p；
- power iteration 次数（若用）；
- 最差 rho；
- 多次运行的均值/标准差；
- 官方 complexity。

---

# 4. 第三层：不要显式求逆——利用正定结构求解

设：

\[
A=V^HV+\sigma^2I.
\]

因为：

\[
x^HAx=\|Vx\|^2+\sigma^2\|x\|^2>0,
\]

所以 A 是 Hermitian positive definite。

目标：

\[
W=VA^{-1}.
\]

等价于：

\[
AW^H=V^H.
\]

## 4.1 Cholesky 路线

\[
A=LL^H.
\]

解：

\[
LY=V^H,
\]

再解：

\[
L^HW^H=Y.
\]

### MATLAB

```matlab
A = V' * V + sigma2 * eye(L);
R = chol(A);                 % A = R'R
W_H = R \ (R' \ V');
W = W_H';
```

实际编码时还应核对 MATLAB `chol` 返回的上下三角定义并写单元测试。

## 4.2 为什么优先 solve 而不是 inverse

- 数值稳定性通常更好；
- 不形成不必要的逆矩阵；
- A 很小且有结构；
- 容易利用 Hermitian positive definite；
- 题面本身也允许把逆转换为方程组求解。

## 4.3 如果仍研究 Strassen

应把它定位为通用计算核研究，并分三层报告：

```text
理论操作数
官方加权复杂度
实际 runtime
```

且必须标 crossover：

\[
n<n_0 \Rightarrow \text{BLAS better},
\]

\[
n\ge n_0 \Rightarrow \text{recursive method may win}.
\]

---

# 5. Strassen–Winograd 重新归类

若 2×2 block 方法每层使用：

- 7 个子矩阵乘法；
- 15 个矩阵加减；

递推仍是：

\[
T(n)=7T(n/2)+O(n^2),
\]

故：

\[
T(n)=O(n^{\log_2 7}).
\]

因此正确的复杂度账应写：

```text
原始 Strassen: 7 mult + 18 add（常见形式）
Winograd variant: 7 mult + 15 add
两者 exponent 相同，常数不同
```

不能因为减少了 3 次 block addition 就把指数改成 Coppersmith–Winograd 的约 2.376。

---

# 6. 压缩的统一低秩模型

对于一个二维块：

\[
A\in\mathbb C^{m\times n},
\]

rank-r 截断 SVD：

\[
A_r=U_r\Sigma_rV_r^H.
\]

存储元素数：

\[
S(r)=mr+r+nr=r(m+n+1).
\]

原始存储：

\[
mn.
\]

只有当：

\[
r(m+n+1)<mn
\]

时才值得压缩。

---

# 7. rank 不要按“线性奇异值贡献率”选

Eckart–Young 给出：

\[
\|A-A_r\|_F^2=\sum_{i>r}\sigma_i^2.
\]

所以 dB 误差应直接计算：

\[
err(r)
=10\log_{10}
\frac{\sum_{i>r}\sigma_i^2}
     {\sum_i\sigma_i^2}.
\]

选择：

\[
r^*=\min\{r:err(r)\le-30\text{ dB}\}.
\]

### MATLAB 模板

```matlab
s = svd(A,'econ');
energy = s.^2;
total = sum(energy);
for r = 0:length(s)
    tail = sum(energy(r+1:end));
    err_db = 10*log10(max(tail,realmin)/total);
    if err_db <= -30
        break;
    end
end
```

这样 rank 的含义与官方指标完全一致。

---

# 8. block size 也是优化变量

定义 partition P，把 A 切成多个块 `A_b`。

每块选：

\[
r_b^*=\min\{r:err_b(r)\le\epsilon_b\}.
\]

总存储：

\[
S(P)=\sum_b r_b(m_b+n_b+1)+S_{meta}(P).
\]

总编解码复杂度：

\[
C(P)=\sum_b[C_{SVD}(b)+C_{reconstruct}(b)]+C_{meta}.
\]

真正的 Q2 是双目标：

\[
\min (S(P),C(P)).
\]

可输出 Pareto front，而不是只找“压缩最多”的一点。

---

# 9. Q3 的更强端到端重构

原论文是：

```text
compress H
→ decompress H
→ compute V/W
→ compress W
→ decompress W
```

更理想是保留 low-rank factors：

\[
H\approx U_H\Sigma_HV_H^H.
\]

然后尽量直接从因子得到所需子空间/Gram 信息，避免恢复完整 H。

一个可研究框架：

```text
H
↓ block low-rank factors
{U_b,Σ_b,V_b}
↓ representative selection in factor space
representative factors
↓ subspace estimation
V_hat
↓ Cholesky solve
W_hat
↓ optional low-rank storage
compressed W_hat
```

优化变量包括：

- block partition；
- H rank；
- similarity threshold；
- representative set；
- randomized-SVD rank；
- W rank。

目标：

\[
\min \alpha C_{calc}+\beta S_{store}
\]

或直接输出 Pareto front，约束：

\[
\rho_{min}(W)\ge0.99,
\]

以及涉及中间压缩时：

\[
err_H,err_W\le-30\text{ dB}.
\]

---

# 10. 一个统一的现代实现架构

```python
class OfficialEvaluator:
    def rho(self, ref, pred): ...
    def fro_error_db(self, ref, pred): ...
    def op_cost(self, trace): ...
    def storage_bits(self, representation): ...

class SimilarityModel:
    def cheap_score(self, H1, H2): ...
    def build_graph(self, Hrow, threshold): ...

class RepresentativeSelector:
    def select(self, graph, accuracy_validator): ...

class LowRankSolver:
    def randomized_svd(self, H, eps, seed): ...

class WSolver:
    def solve(self, V):
        # Cholesky / linear solve
        ...

class Compressor:
    def select_rank_by_fro_error(self, block, limit_db): ...
    def compress(self, block): ...
    def decompress(self, factors): ...
```

总流程只允许通过 `OfficialEvaluator` 给出最终结论。

---

# 11. 推荐的实验表

## Q1

| 方法 | 代表元数 | SVD 次数 | 官方 complexity | runtime | rho_min(V) | rho_min(W) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | | | | | | |
| rSVD | | | | | | |
| rep reuse | | | | | | |
| rep + rSVD | | | | | | |
| + Cholesky | | | | | | |

## Q2

| block size | retained bits | saving % | compress cost | decompress cost | err_H/W |
|---|---:|---:|---:|---:|---:|
| whole | | | | | |
| 256 | | | | | |
| 128 | | | | | |
| 64 | | | | | |

## Q3

| pipeline | total calc | peak memory | final storage | rho_min(W) |
|---|---:|---:|---:|---:|
| standard | | | | |
| paper-style serial | | | | |
| factor-space E2E | | | | |

---

# 12. 复现时必须写的断言

```python
assert 0 <= rho <= 1 + 1e-12
assert err_db <= -30 + tol
assert predicted_shape == reference_shape
assert np.isfinite(all_metrics)
```

还要对存储公式做维度恒等检查：

```text
U: m×r
S: r
V: n×r
total = r(m+n+1)
```

任何手写公式必须由程序自动生成/验证，避免 `1793 → 1739` 这种错误。

---

# 13. 重构后的核心思想

> **结构复用负责减少“次数”，randomized SVD 负责减少“单次成本”，线性求解负责利用正定结构，低秩分块负责减少“存储”，OfficialEvaluator 负责把所有近似锁在题目精度边界内。**
