# 比赛速查：从 A21102480004 提炼的“矩阵 / 算法复杂度 / 压缩”题打法

> 适用：题目要求低计算复杂度、低存储、近似精度约束，或给出大批结构相似的矩阵/张量/信号块。

核心关键词：

> **structure first, ledger always, evaluator first**

---

# 一、看到什么题型时立刻联想到这篇

出现以下几项时优先翻本文件：

- 大量同形矩阵重复计算；
- SVD / eig / inverse / solve 占主要成本；
- 允许近似，但有明确误差阈值；
- 数据之间存在相似性、低秩、稀疏、对称/Hermitian；
- 要同时优化 computation + storage；
- 要设计压缩/解压；
- 题目自己给了运算复杂度计价表；
- 第三问要求 end-to-end redesign。

---

# 二、开题前 1 小时：先写 evaluator，不写算法

## 1. 精度函数

例如：

```matlab
function rho = rho_official(a,b)
    rho = abs(a' * b) / (norm(a) * norm(b));
    assert(rho <= 1 + 1e-10);
end
```

## 2. dB error

```matlab
function e = rel_fro_db(A,Ahat)
    e = 10*log10(norm(A-Ahat,'fro')^2 / norm(A,'fro')^2);
end
```

若官方是全样本期望，则先累加分子/分母再 log，不要对每样本 dB 做平均。

## 3. storage

```matlab
bits = num_complex * 64;
```

若有低秩因子：

```matlab
num = r*(m+n+1);
```

## 4. complexity

按官方基本操作权重写统一计数器。

**验收：**先用手工小例子验证 evaluator，再允许队友调用。

---

# 三、把整个算法画成计算图

例如：

```text
H
│
├─ similarity feature
│    ↓
│ representative selection
│
├─ SVD / subspace
│    ↓
│ V
│
├─ Gram + solve
│    ↓
│ W
│
└─ compression / storage
```

每个节点标：

- shape；
- call count；
- complexity；
- peak memory；
- approximation error。

目标不是立刻优化，而是找到**最贵的 20% 节点**。

---

# 四、复杂度优化的四个层次

## Layer 1：减少调用次数

问：

- 哪些输入相似？
- 是否能共享结果？
- 是否能缓存？
- 是否能增量更新？

对应方法：

- representative / prototype；
- clustering；
- memoization；
- low-rank update；
- nearest-neighbor reuse。

## Layer 2：降低单次计算

- randomized SVD；
- truncated SVD；
- iterative solve；
- fast transform；
- sparse kernel。

## Layer 3：利用特殊结构

看到这些词要立即反应：

| 结构 | 可能算法 |
|---|---|
| symmetric / Hermitian | Cholesky / eig simplification |
| positive definite | Cholesky / CG |
| low rank | Woodbury / factors / truncated SVD |
| sparse | sparse solve / sparse storage |
| Toeplitz/circulant | FFT |
| repeated blocks | reuse / tensorization |
| banded | banded solve |

## Layer 4：改计算图

开放问不要满足于：

```text
原流程每一步各自加速
```

要问：

> 中间变量是否根本不需要显式构造？

例如：

```text
compress → decompress → compute
```

可能改成：

```text
compute directly on compressed factors
```

---

# 五、相似矩阵复用的标准打法

## Step 1：cheap feature

先找便宜特征：

```text
column norms
row norms
trace
singular-value sketch
random projection
moments
```

## Step 2：候选关系

不要求 cheap score 完美，只用来筛候选。

## Step 3：representative selection

不要默认“聚类完每类选第一个”。

可转化：

- set cover；
- k-medoids；
- dominating set；
- facility location。

## Step 4：official accuracy 兜底

复用后必须通过真实指标。

### 最重要的实验

画：

```text
similarity threshold
    vs
representative count / complexity / rho_min
```

找到 Pareto 区域。

---

# 六、randomized SVD 的使用条件

不要因为名字高级就上。

优先适用：

- m,n 很大；
- target rank 很小；
- 只需 dominant subspace；
- 容许近似；
- matrix-vector product 便宜。

谨慎：

- `4×64` 这种很小矩阵；
- 高精度要求；
- QR/随机投影管理成本较高。

必须报告：

```text
ordinary SVD official cost
rSVD official cost
runtime
rho
seed stability
```

---

# 七、看到 inverse，先问能不能 solve

永远先尝试：

```text
x = A\b
```

而不是：

```text
x = inv(A)*b
```

如果 A 是 HPD：

```text
chol
```

如果多 RHS：一次 factorization，多次 solve。

如果 A 只发生低秩变化：

- Woodbury；
- Sherman–Morrison。

**显式逆通常不是首选。**

---

# 八、Fast matrix multiplication 的正确使用姿势

## 不要混淆三件事

### 1. asymptotic complexity

```text
O(n^3)
O(n^2.807)
```

### 2. official operation cost

题目给定的加权基本操作数。

### 3. wall-clock runtime

受：

- BLAS；
- cache；
- allocation；
- language；
- vectorization；
- CPU/GPU

影响。

## 必须做 crossover

```text
n = 16,32,64,...
```

找：

\[
n_0=\min\{n:T_{fast}(n)<T_{base}(n)\}.
\]

之后 hybrid：

```text
n < n0 → BLAS
else → recursive
```

---

# 九、压缩题的标准数学骨架

对矩阵 A：

\[
A=U\Sigma V^H.
\]

rank-r：

\[
A_r=U_r\Sigma_rV_r^H.
\]

### 存储

\[
S(r)=r(m+n+1).
\]

### Frobenius error

\[
E(r)=\frac{\sum_{i>r}\sigma_i^2}{\sum_i\sigma_i^2}.
\]

### dB

\[
10\log_{10}E(r).
\]

直接找满足阈值的最小 r。

**不要先发明“贡献率 0.966”，再事后验。**

---

# 十、block compression 怎么选块

候选：

```text
whole
512
256
128
64
32
...
```

每种报告：

- ranks；
- storage bits；
- compression complexity；
- decompression complexity；
- error；
- metadata。

理解 tradeoff：

```text
块太大：局部秩差异被掩盖
块太小：共享低秩结构损失 + metadata/计算增多
```

中间值常常最好。

---

# 十一、双目标不要只报一个压缩率

若题目：

```text
min storage
min encode/decode computation
```

优先给 Pareto front。

如果必须综合：

1. 归一化；
2. 按题意等权；
3. 做权重敏感性。

不要直接：

```text
0.5×bits + 0.5×seconds
```

单位不同，必须先归一化。

---

# 十二、算法题最容易踩的 8 个坑

1. **评价公式少括号。**
2. **分母拿错 reference。**
3. Big-O 当作题目规定 complexity。
4. runtime benchmark 不同语言/库混着比。
5. 预处理成本没算。
6. random method 只跑一次。
7. threshold 人工调完不交代。
8. 理论算法名称和实际代码不是一回事。

比赛末尾专门做“公式—代码—结果”三方审计。

---

# 十三、论文写作故事线模板

## 13.1 Baseline

先给标准算法和成本瓶颈。

## 13.2 Structure

展示数据有什么结构：

- correlation；
- rank spectrum；
- sparsity；
- symmetry。

## 13.3 Reduce calls

代表元 / 复用。

## 13.4 Reduce kernel cost

近似分解 / structured solve。

## 13.5 Compression

用统一误差约束选 rank/block。

## 13.6 End-to-end

消掉不必要的中间重构。

## 13.7 Validation

四张主表：

```text
complexity
storage
accuracy
runtime
```

---

# 十四、正式比赛 15 分钟检查表

- [ ] 所有官方指标都由独立 evaluator 生成；
- [ ] 理论范围有 assert，例如 rho≤1；
- [ ] complexity 按官方权重，不只 Big-O；
- [ ] 预处理进入总账；
- [ ] 编码和解码都进入总账；
- [ ] storage 单位统一到 bit；
- [ ] 低秩公式按 shape 自动计算；
- [ ] random seed 固定；
- [ ] 至少 5 次随机重复；
- [ ] threshold 有扫描或自适应；
- [ ] baseline 保存；
- [ ] 每个组件有消融；
- [ ] runtime 环境一致；
- [ ] 算法引用名称和代码公式核对；
- [ ] Q3 有真正端到端总账。

---

# 十五、这一篇给我们的比赛口诀

> **先算清，再算快；先验对，再优化；先找结构，再上算法。**
