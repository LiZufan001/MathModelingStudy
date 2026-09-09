# 比赛速查：从 B23104860044 提炼的结构化矩阵 / 硬件近似题打法

> 适用：DFT/FFT、结构化线性变换、稀疏矩阵分解、整数/低比特量化、乘法器优化、Kronecker、误差—复杂度权衡。

---

# 0. 看到这些关键词就翻这份

- DFT / FFT；
- Toeplitz / circulant / Kronecker / block matrix；
- 把一个大矩阵写成多个低复杂度矩阵乘积；
- 系数只能取整数、2 的幂、有限字母表；
- 每行/每列限制非零数；
- 乘法器数、位宽、硬件复杂度；
- 精度必须低于某个硬阈值；
- 剪枝 + 量化 / 稀疏 + 离散化；
- 要求最小复杂度但允许近似误差。

第一反应：

> **把它当成“受约束计算图设计”，不要当成一般黑箱矩阵优化。**

---

# 一、开题第一小时：锁官方 evaluator

在任何算法前写：

```python
def official_loss(...):
    ...

def official_cost(...):
    ...
```

然后手工做至少 5 个小样例。

特别检查：

```text
norm 还是 norm²？
除 N 还是 N²？
β 在哪一边？
复数模还是模平方？
哪些系数官方算免费？
复杂度是乘法次数、非零数还是 bit×乘法次数？
```

**不要相信自己“看懂公式了”。必须写测试。**

---

# 二、先找精确结构 baseline

结构化矩阵通常已经有经典快速算法：

| 结构 | 第一联想 |
|---|---|
| DFT | FFT / butterfly |
| circulant | FFT diagonalization |
| Toeplitz | embedding / FFT |
| Kronecker | mixed-product property |
| block diagonal | 独立小块 |
| low rank | SVD / QR / randomized methods |
| sparse graph operator | graph structure / sparse factorization |

先得到：

```text
exact solution
error = 0
cost = C0
```

后续所有近似方法的意义就是：

> 用多少 error 换多少 cost。

---

# 三、画 Pareto，不要只追一个“综合分”

至少记录：

\[
(J,C,K)
\]

其中：

- J：官方误差；
- C：官方复杂度；
- K：factor depth。

有余力再加：

```text
runtime
peak memory
coefficient bit width
latency / depth
```

画：

```text
error vs cost
error vs K
cost vs K
```

评审一眼就能看懂你的 trade-off。

---

# 四、连续参数先解析消元

见到：

```text
scale β
bias
one-dimensional coefficient
linear least-squares subproblem
```

先求闭式解。

例如：

\[
\min_\beta\|F-\beta H\|_F^2
\]

直接：

\[
\beta^*=\frac{\Re\langle H,F\rangle_F}{\|H\|_F^2}.
\]

不要让 GA/PSO/网格搜索优化一个能一行解掉的变量。

---

# 五、把约束写成 projection

## 稀疏

```python
ProjSparse(row): keep top-k magnitude entries
```

## 有限整数 / 量化

```python
ProjQuant(x): nearest allowed value
```

## 指定 support

```python
ProjSupport(x): zero forbidden entries
```

## 单位模

```python
ProjUnit(z): z / abs(z)
```

这样算法可以统一写成：

```text
continuous improvement
        ↓
projection to feasible set
        ↓
re-evaluate
```

---

# 六、两个投影不交换，就必须测顺序

若：

\[
P_AP_B(X)\ne P_BP_A(X),
\]

至少测：

```text
A-B
B-A
A-B-A
B-A-B
alternating until stable
```

典型：

```text
剪枝 → 量化
量化 → 剪枝
```

不要凭直觉说哪一种“一定更好”。

---

# 七、SVD 之前先看 singular spectrum

先画：

```python
s = svdvals(A)
plot(s)
```

问三个问题：

1. 是否快速衰减？
2. 是否大量重复？
3. 是否存在明显 spectral gap？

### 如果快速衰减

低秩近似有意义。

### 如果平坦

不要讲：

> “前几个奇异向量最重要。”

像 DFT 就属于平谱。

### 如果重复

SVD basis 不唯一，要检查结果对 basis rotation 是否敏感。

---

# 八、算法名必须与代码对应

要写 ADMM，代码至少应该看得到：

```text
primal update
auxiliary-variable projection
dual update
primal residual
dual residual
```

否则就叫：

```text
alternating projection
greedy sparsification
hard thresholding
projected gradient
```

一个准确的普通算法名，比一个对不上的高级算法名更安全。

---

# 九、Kronecker / block structure：先拆再算

若：

\[
F=A\otimes B,
\]

优先考虑：

\[
(A_1\otimes B_1)(A_2\otimes B_2)
=(A_1A_2)\otimes(B_1B_2).
\]

流程：

```text
处理小矩阵
↓
组合 factor
↓
最后做局部修正
```

不要先显式构造大矩阵再优化。

---

# 十、精度硬门槛题：feasibility first

若题目说：

\[
J\le\epsilon,
\qquad
\min C,
\]

正确优先级：

```text
阶段 1：找到任何 J≤ε 的可行解
阶段 2：保持 J≤ε，降低 C
```

而不是：

```text
一直降低 C
然后发现误差超标
```

报告中一定写：

```text
feasible = YES / NO
margin = ε - J
```

---

# 十一、残差修正模板

如果已有：

\[
H\approx F,
\]

可尝试追加修正 factor：

\[
HX\approx F.
\]

连续最优：

\[
X^*=H^+F
\]

再 projection：

```text
X* → sparse / quantized X
```

但是一定要：

```python
if loss(H @ X) < loss(H):
    accept
else:
    reject
```

连续域最优不代表投影后还更优。

---

# 十二、复杂度账本：永远从实际计算图出发

不要拿：

```text
nnz(final matrix)
```

代替实际运算数。

先问：

```text
输入向量如何经过 factor 1？
如何经过 factor 2？
每个边上的系数是什么？
哪些乘法免费？
哪些中间量能共享？
```

再数：

```text
nontrivial multipliers
adds
shifts
memory
pipeline stages
```

复杂度是计算图属性，不只是矩阵属性。

---

# 十三、结果必须自动生成

推荐：

```text
run.py
  ↓
results/*.json
  ↓
make_tables.py
  ├─ tables.md
  ├─ figures/
  └─ summary_numbers.json
```

论文摘要、正文表格、结论都从同一个结果源读取。

重点防：

- 摘要是旧实验；
- 表格是新实验；
- 正文又手抄了一版。

---

# 十四、比赛现场算法升级顺序

baseline 合法后：

1. analytic scaling；
2. 支持位置优化；
3. projection order；
4. alternating projected LS；
5. local search / coordinate descent；
6. residual correction；
7. beam search；
8. 只有前面不够再考虑 GA/PSO。

不要一开始就把全部整数矩阵编码成染色体。

---

# 十五、论文怎么讲故事

推荐：

```text
题目硬件需求
   ↓
经典精确算法 baseline
   ↓
结构中哪些部分最贵
   ↓
怎样用稀疏/量化替代
   ↓
官方误差与官方成本
   ↓
Pareto frontier
   ↓
特殊结构问题复用
   ↓
硬门槛下的进一步修正
```

这比“模型一用了 SVD，模型二用了 ADMM，模型三用了贪心”更有说服力。

---

# 十六、提交前 15 分钟检查表

- [ ] 官方公式是不是最新版？
- [ ] norm / norm² 对吗？
- [ ] 分母 N / N² 对吗？
- [ ] β 是否已解析优化？
- [ ] 免费系数集合完全对题面吗？
- [ ] C 真的是实际 multiplier count 吗？
- [ ] exact baseline 有吗？
- [ ] SVD spectrum 看过吗？
- [ ] 算法名称和代码一致吗？
- [ ] 所有 hard constraints PASS 吗？
- [ ] Q5/硬门槛明确标 feasible 吗？
- [ ] “最优”是否真的有证明？
- [ ] 表格是否自动生成？
- [ ] 摘要数字与结果文件一致？
- [ ] 随机算法是否固定 seed / 重复实验？

---

# 十七、一句话

> **结构决定搜索空间，官方指标决定结论能不能成立，实际计算图决定复杂度究竟是多少。**
