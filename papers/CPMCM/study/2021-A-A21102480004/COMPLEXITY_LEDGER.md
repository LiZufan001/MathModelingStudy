# A21102480004｜复杂度与存储“统一账本”

> 用途：正式比赛遇到“最小计算复杂度 / 最小存储复杂度 / 编解码复杂度”时直接套这套记账方法。最重要的原则：**Big-O、墙钟时间、题目给定的复杂度计分不是一回事。**

---

# 1. 官方基本操作权重

2021 A 题给出了统一计价规则：

| 操作 | complexity unit |
|---|---:|
| 加法 / 减法 | 1 |
| 乘法 | 3 |
| 倒数 | 25 |
| 开方 | 25 |
| `exp/log/sin/cos` | 25 |
| 其他未明确操作 | 100 |

复数运算不能只记“一次复乘”。应先拆为实数基本操作，再按表计价。

例如普通复数乘：

\[
(a+bi)(c+di)=(ac-bd)+(ad+bc)i
\]

含：

- 4 次实乘；
- 2 次实加/减。

若按题面权重：

\[
C_{cmul}=4\times3+2\times1=14.
\]

复数加法：

\[
C_{cadd}=2.
\]

这也是为什么复杂度账本应落实到**基本运算**。

---

# 2. 固定数据规模

每个数据集：

\[
M=4,N=64,L=2,J=4,K=384.
\]

H：

\[
4\times64\times4\times384
\]

复元素个数：

\[
4\cdot64\cdot4\cdot384=393216.
\]

W：

\[
64\times2\times4\times384
\]

复元素个数：

\[
64\cdot2\cdot4\cdot384=196608.
\]

每复元素 64 bit，因此原始存储：

### H

\[
393216\times64
=25,165,824\text{ bit}.
\]

### W

\[
196608\times64
=12,582,912\text{ bit}.
\]

这两项应该作为所有压缩率报告的**唯一基线**。

---

# 3. 官方精度 evaluator

## 3.1 rho

对向量 a,b：

\[
\rho(a,b)=\frac{|a^Hb|}{\|a\|_2\|b\|_2}.
\]

必须满足：

\[
0\le\rho\le1.
\]

MATLAB：

```matlab
rho = norm(a' * b) / (norm(a) * norm(b));
assert(rho <= 1 + 1e-10);
```

不要写成：

```matlab
norm(a'*b)/norm(a)*norm(b)
```

后者因左结合会算错。

## 3.2 压缩误差

官方口径：

\[
err_A=10\log_{10}
\frac{\sum\|\widehat A-A\|_F^2}
     {\sum\|A\|_F^2}.
\]

MATLAB：

```matlab
num = 0;
den = 0;
for t = 1:T
    num = num + norm(Ahat{t} - A{t}, 'fro')^2;
    den = den + norm(A{t}, 'fro')^2;
end
err_db = 10 * log10(num / den);
```

**分母一定是原始 A，不是重构 Ahat。**

---

# 4. Q1 的复杂度账本结构

不要只写：

```text
SVD O(mn²)
Strassen O(n^2.807)
```

应该记录**实际调用次数和基本运算数**。

建议代码中统一 trace：

```python
ledger = {
    'real_add': 0,
    'real_mul': 0,
    'reciprocal': 0,
    'sqrt': 0,
    'other': 0,
}
```

最终：

```python
cost = (
    1  * ledger['real_add']
  + 3  * ledger['real_mul']
  + 25 * ledger['reciprocal']
  + 25 * ledger['sqrt']
  + 100* ledger['other']
)
```

如果某个库函数无法精确展开，可：

1. 自己按标准算法推导运算数；或
2. 明确写上界；
3. 全部方法统一采用同一估计口径。

---

# 5. 预处理成本不能“免费”

代表元复用会减少 SVD，但需要先计算矩阵间相似性。

同一行 K=384 个矩阵若全两两比较：

\[
\binom{384}{2}=73536
\]

对/行。

4 行就是：

\[
294144
\]

对/数据集。

所以必须问：

> **相似度预处理成本是否小于省下来的 SVD 成本？**

完整账本：

\[
C_{rep}
=C_{feature}
+C_{pairwise}
+C_{cluster}
+N_{parent}C_{SVD}
+C_{reuse}.
\]

而 baseline：

\[
C_{base}=1536C_{SVD}+C_{W}.
\]

只有：

\[
C_{rep}<C_{base}
\]

时，“聚类减少 SVD”才是真正降低总复杂度。

### 进一步改进

避免全 pairwise：

- LSH / ANN；
- sorted signature；
- coarse-to-fine；
- incremental representative matching。

使相似度搜索也能降复杂度。

---

# 6. SVD / randomized SVD 的账必须分开

记录至少：

| 项目 | ordinary SVD | randomized SVD |
|---|---:|---:|
| 调用次数 | | |
| H×Ω | - | |
| 正交化 | - | |
| residual check | - | |
| small SVD | | |
| power iteration | - | |
| 总官方 complexity | | |
| rho_min | | |

随机 SVD 的“随机抽样、投影、QR、残差检测”都不是免费操作。

若 H 只有 `4×64`，randomized SVD 的额外管理成本可能抵消收益，所以一定用账本实测。

---

# 7. W 的求解账本：inverse vs solve

标准：

\[
A=V^HV+\sigma^2I.
\]

因为 L=2，这里的 A 实际只有 `2×2`。

对题目原始尺度而言，专门设计 1024×1024 通用求逆算法不一定是最直接的主收益来源。

推荐列：

| 方法 | Gram cost | factor/solve cost | extra memory | numerical stability |
|---|---:|---:|---:|---|
| explicit inverse | | | | |
| LU solve | | | | |
| Cholesky solve | | | | |
| hybrid Strassen inverse | | | | |

### 一个重要评审问题

论文用 512/1024 维扩展矩阵证明 Strassen crossover，很能展示算法研究能力；但**原题的核心小矩阵 A 是 2×2**。

因此必须区分：

- “算法对大矩阵一般有效”；
- “它对本题六组数据的总官方复杂度有多大贡献”。

这两件事不能用同一张 runtime 图代替。

---

# 8. Strassen 的三种账

## 8.1 渐近账

\[
T(n)=7T(n/2)+O(n^2)
\Rightarrow O(n^{2.807}).
\]

## 8.2 基本运算账

每层明确：

- 7 个子乘法；
- 18 次 block add（典型 Strassen）或 15 次（Winograd variant）；
- copy / allocation 若题目复杂度不计，可另列工程成本。

## 8.3 runtime 账

报告：

- 语言；
- BLAS；
- CPU；
- precision；
- cutoff；
- warmup；
- 重复次数；
- median/mean。

只有三账分开，评委才能理解“理论上省多少、官方计分省多少、实际跑快多少”。

---

# 9. 低秩存储公式自动生成

对于 `m×n` rank-r SVD：

\[
A_r=U_r\Sigma_rV_r^H.
\]

存：

\[
mr+r+nr=r(m+n+1).
\]

因此：

```python
def lowrank_elements(m,n,r):
    return r*(m+n+1)
```

不要人工抄常数。

## 9.1 W whole reshape

`256×768`：

\[
S_W(r)=1025r.
\]

节省：

\[
196608-1025r.
\]

## 9.2 H whole reshape

`256×1536`：

\[
S_H(r)=1793r.
\]

节省：

\[
393216-1793r.
\]

论文写 `1739r`，应在复现时纠正。

## 9.3 256×256 block

每块：

\[
513r_b.
\]

W 三块：

\[
S_W=513\sum_{b=1}^{3}r_b.
\]

H 六块：

\[
S_H=513\sum_{b=1}^{6}r_b.
\]

---

# 10. rank 与 -30 dB 的精确关系

对奇异值：

\[
\sigma_1\ge\cdots\ge\sigma_q.
\]

rank-r 最优 Frobenius 近似的相对误差：

\[
E_r=
\frac{\sum_{i=r+1}^{q}\sigma_i^2}
     {\sum_{i=1}^{q}\sigma_i^2}.
\]

约束：

\[
10\log_{10}E_r\le-30.
\]

等价：

\[
E_r\le10^{-3}.
\]

也就是保留至少：

\[
99.9\%
\]

的**平方奇异值能量**。

这是最直接的 rank selector。

---

# 11. 存储不能漏 metadata

若压缩格式不是固定块固定 rank，还要考虑：

- 每块 rank；
- block boundary；
- index；
- permutation；
- representative id；
- codebook / model parameter。

题面如果明确只统计矩阵数据元素，可按官方口径；但论文里应同时声明：

```text
official counted storage = ...
engineering total storage including metadata = ...
```

这样不会把格式开销藏掉。

---

# 12. Q2 是双目标，不要只比压缩率

推荐输出 Pareto 表：

| method | storage bits | saving % | compress complexity | decompress complexity | err_dB |
|---|---:|---:|---:|---:|---:|
| whole SVD | | | | | |
| 256-block | | | | | |
| 128-block | | | | | |
| 4×4 rank1 | | | | | |

如果题目说存储和计算“同等重要”，可以：

1. 不主观硬凑权重，先给 Pareto front；
2. 再做归一化等权综合评分：

\[
Score=0.5\widetilde S+0.5\widetilde C.
\]

并做权重敏感性分析。

---

# 13. Q3 端到端账本

必须把所有中间过程算进去：

```text
H compression
H decompression
similarity extraction
representative search
rSVD
Gram
solve
W compression
W decompression
```

如果采用直接 factor-space 方案，则：

```text
H factorization
representative selection in factor space
subspace solve
W factor representation
```

用同一张表比较，才能证明“端到端”真的更低。

---

# 14. 比赛可直接复制的 ledger 表

```markdown
| module | shape | calls | real add | real mul | recip | sqrt | other | official cost | peak bits |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| feature extraction | | | | | | | | | |
| similarity | | | | | | | | | |
| representative select | | | | | | | | | |
| SVD/rSVD | | | | | | | | | |
| Gram | | | | | | | | | |
| solve | | | | | | | | | |
| compress | | | | | | | | | |
| decompress | | | | | | | | | |
| TOTAL | | | | | | | | | |
```

程序自动生成这一表，论文只负责解释。

---

# 15. 最后验收清单

- [ ] `rho` 有括号，且断言不超过 1；
- [ ] error 分母是原矩阵；
- [ ] 所有预处理进入 complexity；
- [ ] 所有压缩/解压过程进入 complexity；
- [ ] Big-O 与 official cost 分开；
- [ ] runtime 环境写清；
- [ ] storage 的复数 bit 宽统一；
- [ ] SVD 存储公式由 shape 自动生成；
- [ ] random seed 固定并做多次试验；
- [ ] 所有阈值有扫描曲线或自动选择；
- [ ] 双目标有 Pareto / 等权处理；
- [ ] 最终 Q3 报端到端总账，而不是各模块局部成绩。

> **算法题真正让评委信服的，不是“我用了很多快算法”，而是“我能把每一分钱计算和每一 bit 存储都算清楚，而且官方 evaluator 一遍验过”。**
